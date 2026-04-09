from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class RAGResponse(BaseModel):
    """Structured API response returned by the chat endpoint."""

    table_html: str = Field(description="HTML table of matched listings.")
    reasoning: str = Field(description="Natural-language explanation with [source:<chunk_id>] citations.")
    sources: list[str] = Field(default_factory=list, description="Unique source chunk IDs used in answer.")


def trim_recent_messages(messages: Sequence[BaseMessage], *, keep_last: int = 5) -> list[BaseMessage]:
    """Keep only the most recent conversation turns for model context."""

    if keep_last <= 0:
        return []
    return list(messages[-keep_last:])


def extract_chunk_id(doc: Document) -> str:
    """Resolve canonical chunk ID from document metadata."""

    meta = doc.metadata or {}
    candidates = (
        meta.get("chunk_id"),
        meta.get("raw_message_chunk_id"),
        meta.get("listing_id"),
        meta.get("id"),
    )
    for value in candidates:
        if value:
            return str(value)
    return ""


def extract_cited_sources(reasoning: str) -> list[str]:
    """Extract unique source IDs from reasoning citation syntax."""

    return sorted(set(re.findall(r"\[source:([^\]]+)\]", reasoning)))


def render_table_html(rows: list[dict[str, Any]]) -> str:
    """Render the mandatory listing table with an inline View Source action."""

    headers = ["BHK", "Price", "Location", "Contact Number", "Timestamp", "Sender", "Listing ID", "Source"]
    thead = "".join(f"<th>{header}</th>" for header in headers)

    body_rows: list[str] = []
    for row in rows:
        chunk_id = html.escape(str(row.get("chunk_id", "")))
        listing_id = html.escape(str(row.get("listing_id", chunk_id)))
        view_source_button = (
            "<button "
            'type="button" '
            f'data-chunk-id="{chunk_id}" '
            "class=\"view-source-btn\" "
            f"onclick=\"fetch('/chat/source/{chunk_id}').then(r => r.json()).then(console.log)\""
            ">View Source</button>"
        )

        body_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('bhk', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('price', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('location', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('contact_number', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('timestamp', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('sender', 'N/A')))}</td>"
            f"<td>{listing_id}</td>"
            f"<td>{view_source_button}</td>"
            "</tr>"
        )

    tbody = "".join(body_rows) if body_rows else "<tr><td colspan='8'>No matching listings found.</td></tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"
