from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    table_html: str
    reasoning: str
    sources: list[str]
    thread_id: str
