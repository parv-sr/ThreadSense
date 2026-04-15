from __future__ import annotations

import asyncio
import re
from enum import StrEnum
from typing import Any

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.src.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


class ExtractionPropertyType(StrEnum):
    SALE = "SALE"
    RENT = "RENT"
    OTHER = "OTHER"


class ExtractionFurnished(StrEnum):
    FULLY_FURNISHED = "FULLY_FURNISHED"
    SEMI_FURNISHED = "SEMI_FURNISHED"
    UNFURNISHED = "UNFURNISHED"
    UNKNOWN = "UNKNOWN"


class ListingExtractionResult(BaseModel):
    property_type: ExtractionPropertyType = Field(default=ExtractionPropertyType.OTHER)
    bhk: float | None = Field(default=None)
    price: int | None = Field(default=None, description="Normalized full rupee amount")
    location: str | None = None
    contact_number: str | None = None
    furnished: ExtractionFurnished | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    area_sqft: int | None = None
    landmark: str | None = None
    is_verified: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if normalized.get("furnished") is None and normalized.get("furnishing") is not None:
            normalized["furnished"] = normalized.get("furnishing")
        if normalized.get("area_sqft") is None and normalized.get("carpet_area") is not None:
            normalized["area_sqft"] = normalized.get("carpet_area")
        if normalized.get("price") is None and normalized.get("rent") is not None:
            normalized["price"] = normalized.get("rent")

        if normalized.get("contact_number") is None and normalized.get("contact"):
            contact = normalized.get("contact")
            if isinstance(contact, list) and contact:
                first = contact[0]
                normalized["contact_number"] = first.get("phone") if isinstance(first, dict) else str(first)
        return normalized

    @field_validator("property_type", mode="before")
    @classmethod
    def normalize_property_type(cls, v: Any) -> ExtractionPropertyType:
        if isinstance(v, ExtractionPropertyType):
            return v
        s = str(v or "").strip().upper()
        if s in {"SALE", "SELL", "BUY", "OWNERSHIP"}:
            return ExtractionPropertyType.SALE
        if s in {"RENT", "LEASE", "LICENSE"}:
            return ExtractionPropertyType.RENT
        return ExtractionPropertyType.OTHER

    @field_validator("bhk", mode="before")
    @classmethod
    def normalize_bhk(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (float, int)):
            return float(v)
        s = str(v).strip().lower()
        match = re.search(r"(\d+(\.\d+)?)", s)
        if match:
            return float(match.group(1))
        if "studio" in s or "rk" in s:
            return 0.5
        return None

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        s = str(v).strip().lower().replace(",", "")
        match = re.search(r"(\d+(\.\d+)?)", s)
        if not match:
            return None
        value = float(match.group(1))
        if "cr" in s or "crore" in s:
            value *= 10_000_000
        elif "lac" in s or "lakh" in s:
            value *= 100_000
        elif s.endswith("k") or " k" in s:
            value *= 1_000
        return int(value)

    @field_validator("area_sqft", mode="before")
    @classmethod
    def normalize_area_sqft(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        match = re.search(r"(\d+(\.\d+)?)", str(v).replace(",", ""))
        if not match:
            return None
        return int(float(match.group(1)))

    @field_validator("contact_number", mode="before")
    @classmethod
    def normalize_phone(cls, v: Any) -> str | None:
        if not v:
            return None
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        if len(digits) >= 10:
            return digits[-10:]
        return None

    @field_validator("furnished", mode="before")
    @classmethod
    def normalize_furnished(cls, v: Any) -> ExtractionFurnished | None:
        if v is None or v == "":
            return None
        if isinstance(v, ExtractionFurnished):
            return v
        s = str(v).strip().upper().replace("-", "_").replace(" ", "_")
        if "FULL" in s:
            return ExtractionFurnished.FULLY_FURNISHED
        if "SEMI" in s:
            return ExtractionFurnished.SEMI_FURNISHED
        if "UNFURNISHED" in s or s == "EMPTY":
            return ExtractionFurnished.UNFURNISHED
        return ExtractionFurnished.UNKNOWN


class ListingExtractor:
    def __init__(self, *, max_retries: int = 3, rate_limit_concurrency: int = 5) -> None:
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(rate_limit_concurrency)
        self._model = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.openai_api_key)
        self._structured_model = self._model.with_structured_output(ListingExtractionResult, method="json_mode")

    async def extract(self, message_text: str) -> tuple[ListingExtractionResult | None, str | None]:
        if not message_text.strip():
            return None, ""

        prompt = (
            "Extract real-estate listing details from this WhatsApp message. "
            "Return JSON with fields exactly matching schema. "
            "property_type must be one of SALE, RENT, OTHER and indicates transaction intent only. "
            "Never use values like '2 BHK' for property_type; use bhk for bedroom count. "
            "Map furnishing to furnished, carpet area to area_sqft, and phone to contact_number. "
            "Price must be normalized to INR rupees (e.g. 1.5 Cr => 15000000, 85k => 85000). "
            "Set confidence_score in [0.0,1.0].\n\n"
            f"Message:\n{message_text[:5000]}"
        )

        raw_llm_output: str | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._semaphore:
                    result = await self._structured_model.ainvoke(prompt)
                raw_llm_output = result.model_dump_json()
                return result, raw_llm_output
            except Exception as exc:  # noqa: BLE001
                delay_s = 2 ** (attempt - 1)
                log.warning(
                    "preprocess_extract_attempt_failed",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    delay_seconds=delay_s,
                    error=str(exc),
                )
                if attempt >= self.max_retries:
                    return None, raw_llm_output
                await asyncio.sleep(delay_s)
        return None, raw_llm_output


def to_embedding_text(extraction: ListingExtractionResult, original_text: str) -> str:
    fields: list[str] = []
    if extraction.property_type:
        fields.append(f"Type: {extraction.property_type}")
    if extraction.bhk is not None:
        fields.append(f"BHK: {extraction.bhk}")
    if extraction.price is not None:
        fields.append(f"Price: {extraction.price} INR")
    if extraction.location:
        fields.append(f"Location: {extraction.location}")
    if extraction.area_sqft:
        fields.append(f"Area: {extraction.area_sqft} sqft")
    if extraction.furnished:
        fields.append(f"Furnished: {extraction.furnished}")
    if extraction.landmark:
        fields.append(f"Landmark: {extraction.landmark}")

    compact_source = re.sub(r"\s+", " ", original_text).strip()
    fields.append(f"Source: {compact_source[:1200]}")
    return " | ".join(fields)
