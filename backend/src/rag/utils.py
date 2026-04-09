from __future__ import annotations

import html
import re
from collections.abc import Iterable

from pydantic import BaseModel, Field


class RAGResponse(BaseModel):
    table_html: str = Field(description="Rendered HTML table.")
    reasoning: str = Field(description="Natural-language reasoning with citations.")
    sources: list[str] = Field(default_factory=list)


def extract_source_ids_from_reasoning(reasoning: str) -> list[str]:
    return sorted(set(re.findall(r"\[source:([0-9a-fA-F\-]{8,})\]", reasoning)))


def validate_citations(reasoning: str, available_sources: Iterable[str]) -> tuple[bool, list[str]]:
    cited = extract_source_ids_from_reasoning(reasoning)
    available = set(available_sources)
    missing = [cid for cid in cited if cid not in available]
    return (len(missing) == 0, missing)


def render_table_html(rows: list[dict[str, str]]) -> str:
    headers = ["bhk", "price", "location", "contact_number", "timestamp", "sender", "listing_id", "source"]
    thead = "".join(f"<th>{h}</th>" for h in headers)
    body_rows: list[str] = []

    for row in rows:
        listing_id = html.escape(row.get("listing_id", ""))
        action = (
            f'<button type="button" data-listing-id="{listing_id}" '
            f'class="view-source-btn">View Source</button>'
        )
        body_rows.append(
            "<tr>"
            + f"<td>{html.escape(row.get('bhk', ''))}</td>"
            + f"<td>{html.escape(row.get('price', ''))}</td>"
            + f"<td>{html.escape(row.get('location', ''))}</td>"
            + f"<td>{html.escape(row.get('contact_number', ''))}</td>"
            + f"<td>{html.escape(row.get('timestamp', ''))}</td>"
            + f"<td>{html.escape(row.get('sender', ''))}</td>"
            + f"<td>{listing_id}</td>"
            + f"<td>{action}</td>"
            + "</tr>"
        )

    tbody = "".join(body_rows) if body_rows else "<tr><td colspan='8'>No listings found.</td></tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"
