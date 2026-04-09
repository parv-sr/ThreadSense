from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat prompt payload."""

    message: str = Field(min_length=1, max_length=6000)
    thread_id: str | None = Field(default=None, description="Stable thread identifier for memory.")


class RAGResponse(BaseModel):
    """Structured chat response payload."""

    table_html: str
    reasoning: str
    sources: list[str]


class ChatResponse(RAGResponse):
    """Structured chat response with thread tracking."""

    thread_id: str


class SourceResponse(BaseModel):
    """Raw source chunk detail returned for View Source actions."""

    chunk_id: str
    message_start: datetime | None
    sender: str | None
    raw_text: str
    cleaned_text: str | None
    status: str
    created_at: datetime | None
