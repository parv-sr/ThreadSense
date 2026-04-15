from __future__ import annotations

import asyncio
import os
import re
from enum import StrEnum
from typing import Any, Sequence

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.src.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

MESSAGES_PER_PACKET = int(os.getenv("MESSAGES_PER_PACKET", "15"))
MAX_CONCURRENT_PACKETS = max(3, int(os.getenv("MAX_CONCURRENT_PACKETS", "6")) )


class ExtractionPropertyType(StrEnum):
    SALE = "SALE"
    RENT = "RENT"
    OTHER = "OTHER"


class ExtractionListingIntent(StrEnum):
    OFFER = "OFFER"
    REQUEST = "REQUEST"


class ExtractionFurnished(StrEnum):
    FULLY_FURNISHED = "FULLY_FURNISHED"
    SEMI_FURNISHED = "SEMI_FURNISHED"
    UNFURNISHED = "UNFURNISHED"
    UNKNOWN = "UNKNOWN"


class ListingExtractionResult(BaseModel):
    """Canonical extractor output mapped to v2 DB columns."""

    property_type: ExtractionPropertyType = Field(default=ExtractionPropertyType.OTHER)
    listing_intent: ExtractionListingIntent = Field(default=ExtractionListingIntent.OFFER)
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
    is_irrelevant: bool = False
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
    def __init__(
        self,
        *,
        max_retries: int = 3,
        messages_per_packet: int = MESSAGES_PER_PACKET,
        max_concurrent_packets: int = MAX_CONCURRENT_PACKETS,
    ) -> None:
        self.max_retries = max_retries
        self.messages_per_packet = max(1, messages_per_packet)
        self.max_concurrent_packets = max(1, max_concurrent_packets)
        self._semaphore = asyncio.Semaphore(self.max_concurrent_packets)
        self._system_prompt = _build_system_prompt()

        self._model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=settings.openai_api_key,
        )
        self._structured_model = self._model.with_structured_output(BatchEnvelope, method="json_mode")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _invoke_packet(self, packet_messages: Sequence[str]) -> BatchEnvelope:
        prompt_user = construct_batch_prompt(packet_messages)
        full_prompt = f"SYSTEM INSTRUCTIONS:\n{self._system_prompt}\n\nUSER INPUT:\n{prompt_user}"
        async with self._semaphore:
            return await self._structured_model.ainvoke(full_prompt)

    async def _process_packet(
        self,
        packet_messages: Sequence[str],
        *,
        start_global_index: int,
    ) -> list[tuple[int, ListingExtractionResult | None, str | None]]:
        try:
            envelope = await self._invoke_packet(packet_messages)
            results_map = {item.message_index: item for item in envelope.results}
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "preprocess_packet_failed",
                start_global_index=start_global_index,
                packet_size=len(packet_messages),
                error=str(exc),
            )
            return [(start_global_index + i, None, None) for i in range(len(packet_messages))]

        packet_outputs: list[tuple[int, ListingExtractionResult | None, str | None]] = []
        for local_idx in range(len(packet_messages)):
            global_idx = start_global_index + local_idx
            item = results_map.get(local_idx)
            if item is None:
                packet_outputs.append((global_idx, None, None))
                continue

            raw_item = item.model_dump_json()
            if item.is_irrelevant or not item.listings:
                packet_outputs.append((global_idx, None, raw_item))
                continue

            best = max(item.listings, key=lambda x: x.confidence_score)
            if best.is_irrelevant:
                packet_outputs.append((global_idx, None, raw_item))
                continue

            packet_outputs.append((global_idx, best, raw_item))
        return packet_outputs

    async def extract_many(self, message_texts: Sequence[str]) -> list[tuple[ListingExtractionResult | None, str | None]]:
        if not message_texts:
            return []

        packets: list[tuple[int, Sequence[str]]] = []
        for i in range(0, len(message_texts), self.messages_per_packet):
            packets.append((i, message_texts[i : i + self.messages_per_packet]))

        tasks = [
            self._process_packet(packet_messages, start_global_index=start_idx)
            for start_idx, packet_messages in packets
        ]
        nested = await asyncio.gather(*tasks)

        flattened: list[tuple[int, ListingExtractionResult | None, str | None]] = [
            item for packet in nested for item in packet
        ]
        flattened.sort(key=lambda x: x[0])

        results: list[tuple[ListingExtractionResult | None, str | None]] = [
            (None, None) for _ in range(len(message_texts))
        ]
        for idx, extracted, raw_output in flattened:
            if 0 <= idx < len(results):
                results[idx] = (extracted, raw_output)
        return results

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
    if extraction.listing_intent:
        fields.append(f"Intent: {extraction.listing_intent}")
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
