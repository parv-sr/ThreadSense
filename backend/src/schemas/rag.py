from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParsedQuery(BaseModel):
    """Structured parse of user intent into hard filters + soft preferences for deterministic retrieval."""

    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    bhk_min: float | None = Field(default=None, ge=0.0)
    bhk_max: float | None = Field(default=None, ge=0.0)
    area_min: int | None = Field(default=None, ge=0)
    area_max: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None)
    parkings_required: int | None = Field(default=None, ge=0)
    hard_filters: dict[str, Any] = Field(default_factory=dict)
    soft_preferences: str = Field(default="")


class GradedListing(BaseModel):
    """Fast LLM grading over retrieved candidates after hard-filtered hybrid retrieval."""

    listing_id: str = Field(min_length=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    is_valid: bool
    reason: str = Field(default="")


class AnswerWithSources(BaseModel):
    """Strict final payload returned to API clients for deterministic UI rendering."""

    answer: str = Field(default="")
    table_html: str = Field(default="")
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
