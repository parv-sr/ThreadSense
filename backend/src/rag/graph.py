from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.src.rag.prompts import FINAL_RESPONSE_INSTRUCTIONS, REACT_INSTRUCTIONS, SYSTEM_PROMPT
from backend.src.rag.state import AgentState
from backend.src.rag.tools import create_tools
from backend.src.rag.utils import RAGResponse, extract_chunk_id, extract_cited_sources, render_table_html, trim_recent_messages

logger = structlog.get_logger(__name__)


class RAGGraphBuilder:
    """Build and compile the async ReAct graph for the chat agent."""

    def __init__(self, retriever: Any, *, model_name: str = "gpt-4o-mini", max_steps: int = 10) -> None:
        self.max_steps = max_steps
        self.memory = MemorySaver()
        self.docs_holder: list[Document] = []

        self.llm = ChatOpenAI(model=model_name, temperature=0.1)
        self.reasoning_llm = self.llm.with_structured_output(RAGResponse)

        self.tools: list[BaseTool] = create_tools(
            retriever=retriever,
            docs_getter=self._get_docs,
            docs_setter=self._set_docs,
        )
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.tool_enabled_llm = self.llm.bind_tools(self.tools)

    def _get_docs(self) -> list[Document]:
        return self.docs_holder

    def _set_docs(self, docs: list[Document]) -> None:
        self.docs_holder = docs

    async def _agent_node(self, state: AgentState) -> AgentState:
        messages = trim_recent_messages(state.get("messages", []), keep_last=5)
        step_count = int(state.get("step_count", 0)) + 1

        prompt_messages: list[BaseMessage] = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=REACT_INSTRUCTIONS),
            *messages,
        ]

        logger.info("rag_agent_node", step_count=step_count, message_count=len(messages), thread_id=state.get("thread_id"))
        response = await self.tool_enabled_llm.ainvoke(prompt_messages)

        return {
            "messages": [response],
            "step_count": step_count,
            "retrieved_docs": self.docs_holder,
        }

    async def _tool_node(self, state: AgentState) -> AgentState:
        last_message = state.get("messages", [])[-1]
        if not isinstance(last_message, AIMessage):
            return {}

        tool_messages: list[ToolMessage] = []

        for call in last_message.tool_calls:
            tool_name = call["name"]
            args = call.get("args", {})
            tool = self.tool_map.get(tool_name)
            if tool is None:
                tool_messages.append(
                    ToolMessage(
                        content=f"Tool '{tool_name}' is unavailable.",
                        tool_call_id=call["id"],
                        name=tool_name,
                    )
                )
                continue

            logger.info("rag_tool_start", tool=tool_name, args=args)
            result = await tool.ainvoke(args)
            logger.info("rag_tool_done", tool=tool_name)

            if isinstance(result, list) and result and isinstance(result[0], Document):
                self.docs_holder = result
                tool_content = json.dumps(
                    [
                        {
                            "chunk_id": extract_chunk_id(doc),
                            "metadata": doc.metadata,
                            "preview": doc.page_content[:280],
                        }
                        for doc in result[:20]
                    ],
                    default=str,
                )
            else:
                tool_content = json.dumps(result, default=str)

            tool_messages.append(ToolMessage(content=tool_content, tool_call_id=call["id"], name=tool_name))

        return {"messages": tool_messages, "retrieved_docs": self.docs_holder}

    def _route_after_agent(self, state: AgentState) -> str:
        messages = state.get("messages", [])
        if not messages:
            return "finalize"

        last = messages[-1]
        if int(state.get("step_count", 0)) >= self.max_steps:
            return "finalize"
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "finalize"

    async def _finalize_node(self, state: AgentState) -> AgentState:
        docs = state.get("retrieved_docs") or self.docs_holder
        if not docs:
            empty = RAGResponse(
                table_html=render_table_html([]),
                reasoning=(
                    "I could not find relevant listings for your request after hybrid retrieval. "
                    "Try broadening filters (budget/location/BHK) or asking for nearby alternatives."
                ),
                sources=[],
            )
            return {
                "table_html": empty.table_html,
                "reasoning": empty.reasoning,
                "sources": empty.sources,
                "messages": [AIMessage(content=empty.reasoning)],
            }

        rows: list[dict[str, Any]] = []
        sources: list[str] = []
        for doc in docs[:20]:
            meta = doc.metadata or {}
            chunk_id = extract_chunk_id(doc)
            if chunk_id:
                sources.append(chunk_id)
            rows.append(
                {
                    "bhk": meta.get("bhk", "N/A"),
                    "price": meta.get("price", meta.get("price_text", "N/A")),
                    "location": meta.get("location", "N/A"),
                    "contact_number": meta.get("contact_number", meta.get("phone", "N/A")),
                    "timestamp": meta.get("timestamp", meta.get("message_start", "N/A")),
                    "sender": meta.get("sender", "N/A"),
                    "listing_id": meta.get("listing_id", chunk_id),
                    "chunk_id": chunk_id,
                }
            )

        table_html = render_table_html(rows)
        unique_sources = sorted(set(sources))

        doc_context = [
            {
                "chunk_id": extract_chunk_id(doc),
                "metadata": doc.metadata,
                "preview": doc.page_content[:500],
            }
            for doc in docs[:12]
        ]
        user_query = next((m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)), "")

        try:
            response = await self.reasoning_llm.ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    SystemMessage(content=FINAL_RESPONSE_INSTRUCTIONS),
                    HumanMessage(
                        content=(
                            f"User query: {user_query}\n"
                            f"Sources available: {unique_sources}\n"
                            f"Retrieved evidence JSON: {json.dumps(doc_context, default=str)}"
                        )
                    ),
                ]
            )
            reasoning = response.reasoning
        except Exception as exc:  # noqa: BLE001
            logger.exception("rag_reasoning_generation_failed", error=str(exc))
            fallback_citations = " ".join(f"[source:{src}]" for src in unique_sources[:5])
            reasoning = (
                "These listings were selected from hybrid retrieval results by matching your requested budget, "
                "BHK, location, and recency constraints where present. "
                f"{fallback_citations}"
            ).strip()

        cited = extract_cited_sources(reasoning)
        if unique_sources and not cited:
            reasoning = f"{reasoning}\n\nPrimary evidence: " + " ".join(
                f"[source:{source}]" for source in unique_sources[:6]
            )

        return {
            "table_html": table_html,
            "reasoning": reasoning,
            "sources": unique_sources,
            "messages": [AIMessage(content=reasoning)],
        }

    def compile(self):
        """Compile graph with MemorySaver checkpointer."""

        graph = StateGraph(AgentState)
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tool_node)
        graph.add_node("finalize", self._finalize_node)

        graph.set_entry_point("agent")
        graph.add_conditional_edges(
            "agent",
            self._route_after_agent,
            {
                "tools": "tools",
                "finalize": "finalize",
            },
        )
        graph.add_edge("tools", "agent")
        graph.add_edge("finalize", END)

        return graph.compile(checkpointer=self.memory)
