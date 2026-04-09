from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from langchain_core.documents import Document
from langchain_core.tools import StructuredTool, tool
from sqlalchemy import select

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawMessageChunk
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.utils import extract_chunk_id

logger = structlog.get_logger(__name__)


def _coerce_documents(raw_docs: list[Document] | list[dict[str, Any]]) -> list[Document]:
    docs: list[Document] = []
    for item in raw_docs:
        if isinstance(item, Document):
            docs.append(item)
        else:
            docs.append(Document(page_content=str(item.get("page_content", "")), metadata=item.get("metadata", {})))
    return docs


def create_tools(
    retriever: HybridQdrantRetriever,
    docs_getter: Callable[[], list[Document]],
    docs_setter: Callable[[list[Document]], None],
) -> list[StructuredTool]:
    """Create tool instances bound to runtime retriever and state bridges."""

    @tool("hybrid_retrieve", parse_docstring=True)
    async def hybrid_retrieve(query: str, filters: dict | None = None) -> list[Document]:
        """Run hybrid retrieval on Qdrant using vector similarity + BM25 + metadata filters.

        Args:
            query: Free-form user retrieval query.
            filters: Optional metadata filters (bhk, price bounds, location, sender, listing_id).

        Returns:
            A ranked list of langchain Document objects from Qdrant.
        """

        docs = await retriever.retrieve(query=query, filters=filters, limit=20)
        docs_setter(docs)
        logger.info("tool_hybrid_retrieve", query=query, filters=filters, count=len(docs))
        return docs

    @tool("filter_listings", parse_docstring=True)
    def filter_listings(docs: list[Document], criteria: dict) -> list[Document]:
        """Filter retrieved listing documents by metadata constraints.

        Args:
            docs: Candidate listing documents.
            criteria: Field constraints such as bhk, location, sender, min_price, max_price.

        Returns:
            Documents matching the supplied constraints.
        """

        normalized_docs = _coerce_documents(docs or docs_getter())
        result: list[Document] = []

        for doc in normalized_docs:
            metadata = doc.metadata or {}
            keep = True

            for key, value in (criteria or {}).items():
                if value is None:
                    continue
                if key == "min_price":
                    numeric = float(metadata.get("price_numeric") or 0)
                    if numeric < float(value):
                        keep = False
                        break
                elif key == "max_price":
                    numeric = float(metadata.get("price_numeric") or 0)
                    if numeric > float(value):
                        keep = False
                        break
                else:
                    if str(metadata.get(key, "")).lower() != str(value).lower():
                        keep = False
                        break

            if keep:
                result.append(doc)

        docs_setter(result)
        logger.info("tool_filter_listings", before=len(normalized_docs), after=len(result), criteria=criteria)
        return result

    @tool("get_listing_details", parse_docstring=True)
    async def get_listing_details(chunk_id: str) -> dict[str, Any]:
        """Fetch the full original RawMessageChunk from PostgreSQL by chunk_id.

        Args:
            chunk_id: UUID of the raw message chunk.

        Returns:
            Raw chunk payload including raw_text and cleaned_text.
        """

        try:
            parsed_id = UUID(chunk_id)
        except ValueError:
            return {"error": "Invalid chunk_id", "chunk_id": chunk_id}

        async with AsyncSessionLocal() as session:
            chunk = await session.get(RawMessageChunk, parsed_id)
            if chunk is None:
                return {"error": "Chunk not found", "chunk_id": chunk_id}

            return {
                "chunk_id": str(chunk.id),
                "timestamp": chunk.message_start.isoformat() if chunk.message_start else None,
                "sender": chunk.sender,
                "raw_text": chunk.raw_text,
                "cleaned_text": chunk.cleaned_text,
                "status": chunk.status,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
            }

    @tool("summarize_listings", parse_docstring=True)
    def summarize_listings(docs: list[Document]) -> str:
        """Generate a concise statistical summary for retrieved listing documents.

        Args:
            docs: Listing documents to summarize.

        Returns:
            A compact human-readable summary string.
        """

        normalized_docs = _coerce_documents(docs or docs_getter())
        if not normalized_docs:
            return "No listing documents are currently available to summarize."

        by_location = Counter(str(d.metadata.get("location", "Unknown")) for d in normalized_docs)
        by_sender = Counter(str(d.metadata.get("sender", "Unknown")) for d in normalized_docs)
        return (
            f"Retrieved {len(normalized_docs)} listings across "
            f"{len(by_location)} locations and {len(by_sender)} senders. "
            f"Top locations: {', '.join(loc for loc, _ in by_location.most_common(3))}."
        )

    @tool("compare_listings", parse_docstring=True)
    def compare_listings(listing_ids: list[str]) -> str:
        """Compare selected listing IDs using currently retrieved docs.

        Args:
            listing_ids: List of listing/chunk IDs to compare.

        Returns:
            A short comparison summary based on listing metadata.
        """

        ids = {str(item) for item in listing_ids}
        matched = [d for d in docs_getter() if extract_chunk_id(d) in ids]
        if not matched:
            return "No matching listing IDs found in the active retrieved set."

        lines: list[str] = []
        for doc in matched:
            m = doc.metadata or {}
            cid = extract_chunk_id(doc)
            lines.append(
                f"{cid}: {m.get('bhk', 'N/A')} in {m.get('location', 'N/A')} at {m.get('price', 'N/A')}"
            )
        return " | ".join(lines)

    return [hybrid_retrieve, filter_listings, get_listing_details, summarize_listings, compare_listings]
