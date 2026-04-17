from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from typing import Any
from uuid import UUID

import structlog
from langchain_core.documents import Document
from langchain_core.tools import tool

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawMessageChunk
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.utils import extract_chunk_id

logger = structlog.get_logger(__name__)

_retriever_ctx: ContextVar[HybridQdrantRetriever | None] = ContextVar("retriever_ctx", default=None)
_docs_ctx: ContextVar[list[Document]] = ContextVar("docs_ctx", default=[])
_hybrid_retrieve_calls_ctx: ContextVar[int] = ContextVar("hybrid_retrieve_calls_ctx", default=0)


def set_retriever_context(retriever: HybridQdrantRetriever) -> None:
    """Bind retriever to the current async context for tool execution."""

    _retriever_ctx.set(retriever)
    _hybrid_retrieve_calls_ctx.set(0)


def clear_retriever_context() -> None:
    """Clear runtime retriever/doc context after request completion."""

    _retriever_ctx.set(None)
    _docs_ctx.set([])
    _hybrid_retrieve_calls_ctx.set(0)


def _coerce_docs(docs: list[Document] | None) -> list[Document]:
    if docs:
        return docs
    return _docs_ctx.get([])


def _normalize_location(text: str) -> str:
    normalized: str = str(text).lower()
    normalized = normalized.replace(" west", " w").replace(" east", " e")
    normalized = normalized.replace("w.", "w").replace("e.", "e")
    normalized = " ".join(normalized.split())
    return normalized


def _matches_scalar(metadata_value: Any, criteria_value: Any, key: str) -> bool:
    if criteria_value is None:
        return True

    if key == "location":
        lhs: str = _normalize_location(str(metadata_value or ""))
        rhs: str = _normalize_location(str(criteria_value))
        return rhs in lhs or lhs in rhs

    if key == "bhk":
        try:
            lhs_bhk: float = float(metadata_value)
            rhs_bhk: float = float(criteria_value)
            return abs(lhs_bhk - rhs_bhk) <= 0.51
        except (TypeError, ValueError):
            return str(metadata_value or "").strip().lower() == str(criteria_value).strip().lower()

    return str(metadata_value or "").strip().lower() == str(criteria_value).strip().lower()


def get_cached_docs() -> list[Document]:
    """Return documents cached by the most recent retrieval/filter tool call."""

    return _docs_ctx.get([])


def set_cached_docs(docs: list[Document]) -> None:
    """Persist docs for deterministic/fallback response generation."""

    _docs_ctx.set(docs)


@tool("hybrid_retrieve", parse_docstring=True)
async def hybrid_retrieve(query: str, filters: dict | None = None) -> list[Document]:
    """Run real hybrid retrieval against Qdrant using dense + sparse retrieval and metadata filters.

    Args:
        query: Search query describing desired property listings.
        filters: Optional metadata constraints such as bhk, location, sender, and min/max price.

    Returns:
        Ranked listing documents from Qdrant.
    """

    retriever = _retriever_ctx.get(None)
    if retriever is None:
        raise RuntimeError("Hybrid retriever context is not initialized")

    calls_so_far: int = _hybrid_retrieve_calls_ctx.get(0)
    _hybrid_retrieve_calls_ctx.set(calls_so_far + 1)
    if calls_so_far >= 1:
        cached_docs: list[Document] = _docs_ctx.get([])
        logger.warning(
            "tool_hybrid_retrieve_repeat_guard",
            query=query,
            filters=filters,
            calls=calls_so_far + 1,
            cached_count=len(cached_docs),
        )
        return cached_docs

    docs = await retriever.retrieve(query=query, filters=filters, limit=20)
    _docs_ctx.set(docs)
    logger.info("tool_hybrid_retrieve", query=query, filters=filters, count=len(docs))
    return docs


@tool("filter_listings", parse_docstring=True)
async def filter_listings(docs: list[Document], criteria: dict) -> list[Document]:
    """Filter listing documents based on explicit metadata criteria.

    Args:
        docs: Candidate listing documents to filter.
        criteria: Metadata constraints (bhk, location, sender, min_price, max_price).

    Returns:
        Subset of documents satisfying all criteria.
    """

    candidates = _coerce_docs(docs)
    output: list[Document] = []

    for doc in candidates:
        metadata = doc.metadata or {}
        include = True
        for key, value in (criteria or {}).items():
            if value is None:
                continue
            if key == "min_price":
                if float(metadata.get("price_numeric") or 0.0) < float(value):
                    include = False
                    break
            elif key == "max_price":
                if float(metadata.get("price_numeric") or 0.0) > float(value):
                    include = False
                    break
            elif not _matches_scalar(metadata.get(key, ""), value, key):
                include = False
                break
        if include:
            output.append(doc)

    _docs_ctx.set(output)
    logger.info("tool_filter_listings", before=len(candidates), after=len(output), criteria=criteria)
    return output


@tool("get_listing_details", parse_docstring=True)
async def get_listing_details(chunk_id: str) -> dict[str, Any]:
    """Retrieve full original `RawMessageChunk` from PostgreSQL by chunk UUID.

    Args:
        chunk_id: UUID of the underlying raw message chunk.

    Returns:
        Full source payload suitable for source inspection.
    """

    try:
        parsed_id = UUID(chunk_id)
    except ValueError:
        return {"error": "Invalid chunk_id", "chunk_id": chunk_id}

    async with AsyncSessionLocal() as session:
        chunk = await session.get(RawMessageChunk, parsed_id)
        if chunk is None:
            return {"error": "chunk not found", "chunk_id": chunk_id}

        return {
            "chunk_id": str(chunk.id),
            "message_start": chunk.message_start.isoformat() if chunk.message_start else None,
            "sender": chunk.sender,
            "raw_text": chunk.raw_text,
            "cleaned_text": chunk.cleaned_text,
            "status": chunk.status,
            "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
        }


@tool("summarize_listings", parse_docstring=True)
async def summarize_listings(docs: list[Document]) -> str:
    """Summarize the active listing set by location and sender distribution.

    Args:
        docs: Listing documents to summarize.

    Returns:
        Concise summary string for the current listing set.
    """

    candidates = _coerce_docs(docs)
    if not candidates:
        return "No listings are available to summarize."

    locations = Counter(str(doc.metadata.get("location", "Unknown")) for doc in candidates)
    senders = Counter(str(doc.metadata.get("sender", "Unknown")) for doc in candidates)
    return (
        f"{len(candidates)} listings across {len(locations)} locations and {len(senders)} senders. "
        f"Top locations: {', '.join(name for name, _ in locations.most_common(3))}."
    )


@tool("compare_listings", parse_docstring=True)
async def compare_listings(listing_ids: list[str]) -> str:
    """Compare selected listings from the active retrieved set.

    Args:
        listing_ids: Listing/chunk IDs to compare.

    Returns:
        Compact side-by-side comparison text.
    """

    docs = _docs_ctx.get([])
    ids = {str(item) for item in listing_ids}
    matched = [doc for doc in docs if extract_chunk_id(doc) in ids]
    if not matched:
        return "No matching listing IDs were found in the active results."

    lines: list[str] = []
    for doc in matched:
        metadata = doc.metadata or {}
        cid = extract_chunk_id(doc)
        lines.append(
            f"{cid}: {metadata.get('bhk', 'N/A')} | {metadata.get('location', 'N/A')} | {metadata.get('price', 'N/A')}"
        )
    return " ; ".join(lines)


RAG_TOOLS = [hybrid_retrieve, filter_listings, get_listing_details, summarize_listings, compare_listings]
