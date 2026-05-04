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
    """Render the required listing table with clickable listing IDs."""

    columns = ["ID", "Transaction", "Property", "Location", "BHK", "Price"]
    header_html = "".join(f"<th>{column}</th>" for column in columns)

    row_html: list[str] = []
    for row in rows:
        listing_id = html.escape(str(row.get("listing_id", "")))
        listing_button = (
            "<button "
            'type="button" '
            "class=\"listing-source-link\" "
            f'data-listing-id="{listing_id}"'
            f">{listing_id}</button>"
        )
        price = row.get("price")
        if price is None and (row.get("price_min") is not None or row.get("price_max") is not None):
            price = f"{row.get('price_min', 'N/A')} - {row.get('price_max', 'N/A')}"

        row_html.append(
            "<tr>"
            f"<td>{listing_button}</td>"
            f"<td>{html.escape(str(row.get('transaction_type', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('property_type', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('location', 'N/A')))}</td>"
            f"<td>{html.escape(str(row.get('bhk', 'N/A')))}</td>"
            f"<td>{html.escape(str(price or 'N/A'))}</td>"
            "</tr>"
        )

    body = "".join(row_html) if row_html else "<tr><td colspan='6'>No listings found.</td></tr>"
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body}</tbody></table>"


def last_five_conversation_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Return at most the last 5 human/assistant messages for conversational memory."""

    convo = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
    return convo[-5:]
