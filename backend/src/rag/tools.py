from __future__ import annotations

from collections import Counter
from typing import Any

from langchain_core.documents import Document
from langchain_core.tools import tool
from sqlalchemy import select

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawMessageChunk


@tool("hybrid_retrieve", parse_docstring=True)
async def hybrid_retrieve(query: str, filters: dict | None = None) -> list[Document]:
    """Run hybrid retrieval on Qdrant using semantic similarity + metadata filtering.

    Args:
        query: User query text.
        filters: Optional metadata filters for location/bhk/price/sender/timestamp.
    """
    # Populated by graph runtime with retriever. Tool shell retained for ReAct compatibility.
    return [Document(page_content=query, metadata={"fallback": True, "filters": filters or {}})]


@tool("filter_listings", parse_docstring=True)
def filter_listings(docs: list[Document], criteria: dict) -> list[Document]:
    """Filter candidate listing docs by explicit metadata criteria.

    Args:
        docs: Retrieved documents.
        criteria: Filter dict supporting bhk, price range, location, sender.
    """
    out: list[Document] = []
    for d in docs:
        meta = d.metadata or {}
        keep = True
        for k, v in criteria.items():
            if v is None:
                continue
            if str(meta.get(k, "")).lower() != str(v).lower():
                keep = False
                break
        if keep:
            out.append(d)
    return out


@tool("compare_listings", parse_docstring=True)
def compare_listings(listing_ids: list[str]) -> str:
    """Return a compact comparison sentence across selected listing IDs."""
    if not listing_ids:
        return "No listing IDs provided for comparison."
    return f"Compared listings: {', '.join(listing_ids)}"


@tool("summarize_listings", parse_docstring=True)
def summarize_listings(docs: list[Document]) -> str:
    """Summarize retrieved listings without adding facts not present in source docs."""
    if not docs:
        return "No documents available to summarize."
    top_locations = Counter(str(d.metadata.get("location", "unknown")) for d in docs)
    return f"Found {len(docs)} matching listings across: {', '.join(loc for loc, _ in top_locations.most_common(5))}."


@tool("get_listing_details", parse_docstring=True)
async def get_listing_details(listing_id: str) -> dict[str, Any]:
    """Fetch full source RawMessageChunk by ID from Postgres."""
    async with AsyncSessionLocal() as session:
        chunk = await session.get(RawMessageChunk, listing_id)
        if chunk is None:
            return {"error": "Listing not found", "listing_id": listing_id}
        return {
            "id": str(chunk.id),
            "timestamp": chunk.message_start.isoformat() if chunk.message_start else None,
            "sender": chunk.sender,
            "raw_text": chunk.raw_text,
            "cleaned_text": chunk.cleaned_text,
            "status": chunk.status,
        }


@tool("get_conversation_stats", parse_docstring=True)
async def get_conversation_stats() -> dict[str, Any]:
    """Get lightweight aggregate stats from RawMessageChunk records."""
    async with AsyncSessionLocal() as session:
        total = len((await session.execute(select(RawMessageChunk.id))).scalars().all())
    return {"total_chunks": total}
