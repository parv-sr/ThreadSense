from __future__ import annotations

import json
from typing import Any, Sequence

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from backend.src.core.config import get_settings
from backend.src.rag.prompts import FINAL_REASONING_PROMPT, REACT_PROMPT, SYSTEM_PROMPT
from backend.src.rag.tools import RAG_TOOLS, get_cached_docs
from backend.src.rag.utils import (
    ReasoningOutput,
    extract_chunk_id,
    extract_sources_from_reasoning,
    render_table_html,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


class ReActRAGGraph:
    """ThreadSense graph wrapper built on LangGraph's official ReAct agent."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self.checkpointer: MemorySaver = MemorySaver()
        self.llm: ChatOpenAI = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=settings.openai_api_key,
        )
        self.reasoning_llm = self.llm.with_structured_output(ReasoningOutput)

        # Switched to official create_react_agent to fix tool_call_id matching bug.
        self._agent = create_react_agent(
            model=self.llm,
            tools=RAG_TOOLS,
            checkpointer=self.checkpointer,
            state_modifier=f"{SYSTEM_PROMPT}\n\n{REACT_PROMPT}",
        )

    def compile(self):
        """Return compiled LangGraph ReAct agent."""

        return self._agent

    @staticmethod
    def _rows_from_retrieved_records(retrieved_records: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Normalize retrieved record payloads into table rows, sources, and evidence."""

        rows: list[dict[str, Any]] = []
        sources: list[str] = []
        evidence: list[dict[str, Any]] = []

        for record in list(retrieved_records)[:20]:
            metadata_value: Any = record.get("metadata", {})
            metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}

            chunk_value: Any = record.get("chunk_id") or metadata.get("chunk_id") or metadata.get("id")
            chunk_id: str | None = str(chunk_value) if chunk_value else None
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

            evidence.append(
                {
                    "chunk_id": chunk_id,
                    "metadata": metadata,
                    "preview": str(record.get("preview", ""))[:500],
                }
            )

        return rows, sources, evidence

    async def build_final_response(
        self,
        messages: Sequence[BaseMessage],
        retrieved_records: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        """Build UI response fields from retrieved docs + final assistant reasoning."""

        candidate_records: list[dict[str, Any]] = list(retrieved_records or [])
        if not candidate_records:
            docs: list[Document] = list(get_cached_docs())
            candidate_records = [
                {
                    "chunk_id": extract_chunk_id(doc),
                    "metadata": doc.metadata,
                    "preview": doc.page_content[:500],
                }
                for doc in docs
            ]

        logger.info("build_final_response_records", candidate_records_count=len(candidate_records))
        if not candidate_records:
            empty_table: str = render_table_html([])
            reasoning: str = (
                "I could not find matching listings in the current dataset. "
                "Try loosening budget, location, or BHK constraints and re-run the search."
            )
            return {
                "table_html": empty_table,
                "reasoning": reasoning,
                "sources": [],
            }

        rows: list[dict[str, Any]]
        sources: list[str]
        evidence: list[dict[str, Any]]
        rows, sources, evidence = self._rows_from_retrieved_records(candidate_records)

        table_html: str = render_table_html(rows)
        unique_sources: list[str] = sorted(set(sources))

        latest_user_query: str = ""
        for message in reversed(list(messages)):
            if isinstance(message, HumanMessage):
                latest_user_query = str(message.content)
                break

        final_agent_reasoning: str | None = None
        for message in reversed(list(messages)):
            if isinstance(message, AIMessage) and message.content:
                final_agent_reasoning = str(message.content)
                break

        if final_agent_reasoning:
            reasoning = final_agent_reasoning
        else:
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
                citations: str = " ".join(f"[source:{source}]" for source in unique_sources[:6])
                reasoning = (
                    "These listings were selected because they best match your requested constraints "
                    f"based on retrieved evidence. {citations}"
                )

        cited: list[str] = extract_sources_from_reasoning(reasoning)
        if unique_sources and not cited:
            reasoning = reasoning + "\n\n" + " ".join(f"[source:{source}]" for source in unique_sources[:6])

        return {
            "table_html": table_html,
            "reasoning": reasoning,
            "sources": unique_sources,
        }
