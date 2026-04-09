from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.src.rag.prompts import FINAL_REASONING_PROMPT, REACT_PROMPT, SYSTEM_PROMPT
from backend.src.rag.state import AgentState
from backend.src.rag.tools import RAG_TOOLS, get_cached_docs
from backend.src.rag.utils import (
    ReasoningOutput,
    extract_chunk_id,
    extract_sources_from_reasoning,
    last_five_conversation_messages,
    render_table_html,
)

logger = structlog.get_logger(__name__)


class ReActRAGGraph:
    """Custom async ReAct StateGraph with dynamic agent/tool loop."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self.checkpointer = MemorySaver()
        self.llm = ChatOpenAI(model=model_name, temperature=0.1)
        self.tool_llm = self.llm.bind_tools(RAG_TOOLS)
        self.reasoning_llm = self.llm.with_structured_output(ReasoningOutput)

    async def _agent_node(self, state: AgentState) -> AgentState:
        """Reason about next action and optionally emit tool calls."""

        message_history = list(state.get("messages", []))
        convo_window = last_five_conversation_messages(message_history)

        prompt: list[BaseMessage] = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=REACT_PROMPT),
            *convo_window,
        ]

        logger.info("react_agent_node", thread_id=state.get("thread_id"), message_count=len(convo_window))
        ai_message = await self.tool_llm.ainvoke(prompt)
        return {"messages": [ai_message]}

    async def _tool_node(self, state: AgentState) -> AgentState:
        """Execute tool calls emitted by the latest assistant message."""

        messages = list(state.get("messages", []))
        if not messages or not isinstance(messages[-1], AIMessage):
            return {}

        ai_message: AIMessage = messages[-1]
        tool_messages: list[ToolMessage] = []

        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call.get("args", {})
            tool = next((t for t in RAG_TOOLS if t.name == tool_name), None)

            if tool is None:
                logger.warning("tool_not_found", tool=tool_name)
                tool_messages.append(
                    ToolMessage(content=f"Tool '{tool_name}' is unavailable.", tool_call_id=tool_call["id"], name=tool_name)
                )
                continue

            logger.info("tool_call_start", thread_id=state.get("thread_id"), tool=tool_name, args=args)
            result = await tool.ainvoke(args)
            logger.info("tool_call_done", thread_id=state.get("thread_id"), tool=tool_name)

            if isinstance(result, list) and result and isinstance(result[0], Document):
                content = json.dumps(
                    [
                        {
                            "chunk_id": extract_chunk_id(doc),
                            "metadata": doc.metadata,
                            "preview": doc.page_content[:240],
                        }
                        for doc in result[:20]
                    ],
                    default=str,
                )
            else:
                content = json.dumps(result, default=str)

            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"], name=tool_name))

        return {"messages": tool_messages, "retrieved_docs": get_cached_docs()}

    def _route_after_agent(self, state: AgentState) -> str:
        """Route agent output either to tool execution or finalization."""

        messages = list(state.get("messages", []))
        if not messages:
            return "finalize"

        last = messages[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "finalize"

    async def _finalize_node(self, state: AgentState) -> AgentState:
        """Build final table + reasoning with robust fallback behavior."""

        docs = list(state.get("retrieved_docs", []))
        if not docs:
            empty_table = render_table_html([])
            reasoning = (
                "I could not find matching listings in the current dataset. "
                "Try loosening budget, location, or BHK constraints and re-run the search."
            )
            return {
                "table_html": empty_table,
                "reasoning": reasoning,
                "sources": [],
                "messages": [AIMessage(content=reasoning)],
            }

        rows: list[dict[str, Any]] = []
        sources: list[str] = []
        for doc in docs[:20]:
            metadata = doc.metadata or {}
            chunk_id = extract_chunk_id(doc)
            if chunk_id:
                sources.append(chunk_id)

            rows.append(
                {
                    "bhk": metadata.get("bhk", "N/A"),
                    "price": metadata.get("price", metadata.get("price_text", "N/A")),
                    "location": metadata.get("location", "N/A"),
                    "contact_number": metadata.get("contact_number", metadata.get("phone", "N/A")),
                    "timestamp": metadata.get("timestamp", metadata.get("message_start", "N/A")),
                    "sender": metadata.get("sender", "N/A"),
                    "listing_id": metadata.get("listing_id", chunk_id),
                    "chunk_id": chunk_id,
                }
            )

        table_html = render_table_html(rows)
        unique_sources = sorted(set(sources))

        latest_user_query = ""
        for message in reversed(list(state.get("messages", []))):
            if isinstance(message, HumanMessage):
                latest_user_query = str(message.content)
                break

        evidence = [
            {
                "chunk_id": extract_chunk_id(doc),
                "metadata": doc.metadata,
                "preview": doc.page_content[:500],
            }
            for doc in docs[:12]
        ]

        try:
            reasoning_result = await self.reasoning_llm.ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    SystemMessage(content=FINAL_REASONING_PROMPT),
                    HumanMessage(
                        content=(
                            f"User query: {latest_user_query}\n"
                            f"Source IDs: {unique_sources}\n"
                            f"Evidence JSON: {json.dumps(evidence, default=str)}"
                        )
                    ),
                ]
            )
            reasoning = reasoning_result.reasoning
        except Exception as exc:  # noqa: BLE001
            logger.exception("final_reasoning_failed", error=str(exc))
            citations = " ".join(f"[source:{source}]" for source in unique_sources[:6])
            reasoning = (
                "These listings were selected because they best match your requested constraints "
                f"based on retrieved evidence. {citations}"
            )

        cited = extract_sources_from_reasoning(reasoning)
        if unique_sources and not cited:
            reasoning = reasoning + "\n\n" + " ".join(f"[source:{source}]" for source in unique_sources[:6])

        return {
            "table_html": table_html,
            "reasoning": reasoning,
            "sources": unique_sources,
            "messages": [AIMessage(content=reasoning)],
        }

    def compile(self):
        """Compile graph with conditional edges for true ReAct behavior."""

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tool_node)
        workflow.add_node("finalize", self._finalize_node)

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._route_after_agent,
            {
                "tools": "tools",
                "finalize": "finalize",
            },
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("finalize", END)

        return workflow.compile(checkpointer=self.checkpointer)
