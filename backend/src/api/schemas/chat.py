from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat payload for the RAG endpoint."""

    message: str = Field(min_length=1, max_length=6000)
    thread_id: str | None = Field(default=None, description="Optional thread UUID for memory continuity")


class ChatResponse(BaseModel):
    """Structured RAG response payload."""

    table_html: str
    reasoning: str
    sources: list[str]
    thread_id: str


class SourceResponse(BaseModel):
    """Full raw source chunk details for View Source actions."""

    chunk_id: str
    message_start: datetime | None
    sender: str | None
    raw_text: str
    cleaned_text: str | None
    status: str
    created_at: datetime | None
