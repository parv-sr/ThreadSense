from __future__ import annotations

import asyncio
import os
import re
from enum import StrEnum
from typing import Any, Sequence

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
        alias_map = {
            "furnishing": "furnished",
            "carpet_area": "area_sqft",
            "sqft": "area_sqft",
            "rent": "price",
            "amount": "price",
            "phone": "contact_number",
            "phone_number": "contact_number",
            "mobile": "contact_number",
            "verified": "is_verified",
        }

        for source_key, target_key in alias_map.items():
            if normalized.get(target_key) is None and normalized.get(source_key) is not None:
                normalized[target_key] = normalized.get(source_key)

        if normalized.get("contact_number") is None and normalized.get("contact"):
            contact = normalized.get("contact")
            if isinstance(contact, list) and contact:
                first = contact[0]
                normalized["contact_number"] = first.get("phone") if isinstance(first, dict) else str(first)

        return normalized

    @field_validator("listing_intent", mode="before")
    @classmethod
    def normalize_listing_intent(cls, v: Any, info: ValidationInfo) -> ExtractionListingIntent:
        raw_text = str((info.data or {}).get("location") or "")
        merged = f"{str(v or '')} {raw_text}".lower()
        if any(term in merged for term in ["looking", "require", "need", "want", "requirement"]):
            return ExtractionListingIntent.REQUEST
        if str(v or "").upper().strip() in {"REQUEST", "REQUIREMENT", "LOOKING"}:
            return ExtractionListingIntent.REQUEST
        return ExtractionListingIntent.OFFER

    @field_validator("property_type", mode="before")
    @classmethod
    def normalize_property_type(cls, v: Any, info: ValidationInfo) -> ExtractionPropertyType:
        if isinstance(v, ExtractionPropertyType):
            return v

        merged = f"{str(v or '')} {str((info.data or {}).get('listing_intent') or '')}".upper()
        if any(token in merged for token in ["RENT", "LEASE", "LEAVE & LICENSE", "L&L"]):
            return ExtractionPropertyType.RENT
        if any(token in merged for token in ["SALE", "SELL", "BUY", "OWNERSHIP"]):
            return ExtractionPropertyType.SALE
        return ExtractionPropertyType.OTHER

    @field_validator("bhk", mode="before")
    @classmethod
    def normalize_bhk(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (float, int)):
            return float(v)
        s = str(v).strip().lower()
        if "studio" in s or "rk" in s:
            return 0.5
        match = re.search(r"(\d+(?:\.\d+)?)", s)
        return float(match.group(1)) if match else None

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        s = str(v).lower().replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", s)
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
        match = re.search(r"(\d+(?:\.\d+)?)", str(v).replace(",", ""))
        return int(float(match.group(1))) if match else None

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
        if "UNFURNISHED" in s or "EMPTY" in s:
            return ExtractionFurnished.UNFURNISHED
        return ExtractionFurnished.UNKNOWN


class BatchItemResult(BaseModel):
    message_index: int = Field(..., description="Local packet index from 0..N")
    listings: list[ListingExtractionResult] = Field(default_factory=list)
    is_irrelevant: bool = Field(default=False)


class BatchEnvelope(BaseModel):
    results: list[BatchItemResult] = Field(default_factory=list)


def _build_system_prompt() -> str:
    return """
You are ThreadSense v2's primary real-estate extraction engine for WhatsApp chats.
You MUST be precise, conservative, and schema-compliant.

OUTPUT CONTRACT (STRICT):
- Return a JSON object with key "results".
- "results" is a list where each entry corresponds to one input message index.
- Each entry must have: message_index, listings[], is_irrelevant.
- If message has no usable listing signal, set is_irrelevant=true and listings=[].

FOR EACH LISTING IN listings[]:
- property_type: one of SALE, RENT, OTHER.
- listing_intent: OFFER or REQUEST.
- bhk: numeric (studio/RK => 0.5), else null.
- price: integer INR only (normalized).
- location: concise locality/building hint, null if absent.
- contact_number: single best phone number (last 10 digits), else null.
- furnished: FULLY_FURNISHED | SEMI_FURNISHED | UNFURNISHED | UNKNOWN | null.
- floor_number, total_floors, area_sqft: integers when present.
- landmark: nearby marker if present.
- is_verified: true only if explicit markers like "verified", "RERA", "owner confirmed".
- is_irrelevant: true only if non-listing or too little signal.
- confidence_score in [0,1].

CLASSIFICATION RULES:
1) listing_intent
- REQUEST if user is seeking property ("looking for", "need", "requirement", "wanted").
- OFFER if user is advertising availability.

2) property_type
- RENT for rent/lease/license language.
- SALE for buy/sell/ownership/outright price language.
- OTHER for ambiguous/general ads or when only requirement intent appears.

PRICE NORMALIZATION (MANDATORY):
- 1.5 Cr / 1.5 Crore => 15000000
- 85k / 85 K => 85000
- 2.25 lac / 2.25 lakh => 225000
- Keep integer rupees only.
- If only deposit is present and no rent/sale amount, do not hallucinate main price.

PHONE EXTRACTION RULES:
- Prefer explicit phone numbers (with +91 allowed), normalize to last 10 digits.
- Ignore broker IDs, unit numbers, tower numbers.
- If multiple phones exist, choose the most likely contact number for this listing.

TEXT CLEANING RULES:
- Ignore emojis, greetings, hashtags, agent signatures, repetitive fluff.
- Keep only extraction-worthy facts.

IRRELEVANCE RULES (set is_irrelevant=true):
- greetings, jokes, social chatter, festival wishes.
- only "call me", "available", "ok" without property details.
- legal/finance chatter without specific listing.

CONFIDENCE GUIDANCE:
- 0.90-1.00: clear transaction + location + price and/or contact.
- 0.70-0.89: most fields present, minor ambiguity.
- 0.40-0.69: weak listing clues; incomplete details.
- 0.00-0.39: likely irrelevant/noisy.

GOOD EXAMPLES:
- "2 BHK fully furnished for rent in Bandra West 85k call +91 98xxxxxx" => OFFER, RENT, bhk=2, price=85000.
- "Need 1bhk in Andheri budget 45k" => REQUEST, OTHER, price=45000.
- "Office space for sale at BKC 3.2 Cr" => OFFER, SALE, price=32000000.

BAD EXTRACTION BEHAVIOR TO AVOID:
- Never put "2 BHK" into property_type.
- Never output strings for numeric fields if a numeric conversion is possible.
- Never fabricate location/contact/price.
- Never skip message indices.

You must comply with the schema exactly.
""".strip()


def construct_batch_prompt(messages: Sequence[str]) -> str:
    lines = [
        "Extract listings from the numbered messages below.",
        "Return ONLY valid JSON with top-level key 'results'.",
    ]
    for i, msg in enumerate(messages):
        safe_msg = (msg or "").strip()[:3000]
        lines.append(f"--- Message {i} ---\\n{safe_msg}")
    return "\n\n".join(lines)


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
        return (await self.extract_many([message_text]))[0]


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
