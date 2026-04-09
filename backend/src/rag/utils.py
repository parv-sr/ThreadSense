from __future__ import annotations

import html
import re
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field


class ReasoningOutput(BaseModel):
    """Structured payload for final reasoning generation."""

    reasoning: str = Field(description="Detailed explanation with inline source citations.")


def extract_chunk_id(doc: Document) -> str:
    """Get a stable chunk id from document metadata."""

    metadata = doc.metadata or {}
    for key in ("chunk_id", "raw_message_chunk_id", "listing_id", "id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def extract_sources_from_reasoning(reasoning: str) -> list[str]:
    """Collect cited source IDs from reasoning text."""

    return sorted(set(re.findall(r"\[source:([^\]]+)\]", reasoning)))


def render_table_html(rows: list[dict[str, Any]]) -> str:
    """Render required output table and View Source button column."""

    columns = ["BHK", "Price", "Location", "Contact Number", "Timestamp", "Sender", "Listing ID", "Source"]
    header_html = "".join(f"<th>{column}</th>" for column in columns)

    row_html: list[str] = []
    for row in rows:
        chunk_id = html.escape(str(row.get("chunk_id", "")))
        listing_id = html.escape(str(row.get("listing_id", chunk_id)))
        source_btn = (
            "<button "
            'type="button" '
            "class=\"view-source-btn\" "
            f'data-chunk-id="{chunk_id}" '
            f"onclick=\"fetch('/chat/source/{chunk_id}').then(r => r.json()).then(data => window.dispatchEvent(new CustomEvent('threadsense:source', {{ detail: data }})))\""
            ">View Source</button>"
        )

        row_html.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('bhk', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('price', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('location', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('contact_number', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('timestamp', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('sender', 'N/A')))}</td>"
            f"<td>{listing_id}</td>"
            f"<td>{source_btn}</td>"
            "</tr>"
        )

    body = "".join(row_html) if row_html else "<tr><td colspan='8'>No listings found.</td></tr>"
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body}</tbody></table>"


def last_five_conversation_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Return at most the last 5 human/assistant messages for conversational memory."""

    convo = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
    return convo[-5:]
