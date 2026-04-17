from __future__ import annotations

import asyncio
import os
import re
from enum import StrEnum
from typing import Any, Sequence
from uuid import UUID

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator, model_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.src.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

MESSAGES_PER_PACKET = int(os.getenv("MESSAGES_PER_PACKET", "15"))
MAX_CONCURRENT_PACKETS = max(3, int(os.getenv("MAX_CONCURRENT_PACKETS", "6")))


class ExtractionPropertyType(StrEnum):
    SALE = "SALE"
    RENT = "RENT"
    OTHER = "OTHER"
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    PLOT = "PLOT"
    LAND = "LAND"
    UNKNOWN = "UNKNOWN"


class ExtractionListingIntent(StrEnum):
    OFFER = "OFFER"
    REQUEST = "REQUEST"


class ExtractionTransactionType(StrEnum):
    RENT = "RENT"
    SALE = "SALE"


class ExtractionFurnished(StrEnum):
    FULLY_FURNISHED = "FULLY_FURNISHED"
    FURNISHED = "FURNISHED"
    SEMI_FURNISHED = "SEMI_FURNISHED"
    UNFURNISHED = "UNFURNISHED"
    UNKNOWN = "UNKNOWN"


class PropertyListing(BaseModel):
    cleaned_text: str = Field(default="")
    listing_intent: ExtractionListingIntent = Field(default=ExtractionListingIntent.OFFER)
    transaction_type: ExtractionTransactionType = Field(default=ExtractionTransactionType.SALE)
    property_type: ExtractionPropertyType = Field(default=ExtractionPropertyType.UNKNOWN)
    location: str | None = None
    building_name: str | None = None
    bhk: float | None = None
    sqft: int | None = None
    price: int | None = Field(default=None, description="Normalized INR rupee amount")
    furnishing: ExtractionFurnished | None = None
    parking: int | None = None
    features: list[str] = Field(default_factory=list)
    contact_numbers: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_irrelevant: bool = False

    @field_validator("cleaned_text", mode="before")
    @classmethod
    def normalize_cleaned_text(cls, v: Any) -> str:
        if v is None:
            return ""
        text = re.sub(r"\s+", " ", str(v)).strip()
        return text[:1000]

    @field_validator("listing_intent", mode="before")
    @classmethod
    def normalize_listing_intent(cls, v: Any, info: Any) -> ExtractionListingIntent:
        if isinstance(v, ExtractionListingIntent):
            return v

        raw_text = " ".join(
            [
                str(v or ""),
                str((info.data or {}).get("cleaned_text") or ""),
            ]
        ).lower()
        request_terms = [
            "looking for",
            "need",
            "required",
            "requirement",
            "want",
            "seeking",
            "tenant needed",
            "client requirement",
        ]
        if any(term in raw_text for term in request_terms):
            return ExtractionListingIntent.REQUEST
        return ExtractionListingIntent.OFFER

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, v: Any, info: Any) -> ExtractionTransactionType:
        if isinstance(v, ExtractionTransactionType):
            return v
        raw = " ".join(
            [
                str(v or ""),
                str((info.data or {}).get("cleaned_text") or ""),
            ]
        ).lower()

        rent_terms = ["rent", "rental", "lease", "leave and license", "license", "per month", "/month", "pm"]
        sale_terms = ["sale", "sell", "resale", "buy", "purchase", "ownership", "outright", "all inclusive"]

        has_rent = any(term in raw for term in rent_terms)
        has_sale = any(term in raw for term in sale_terms)

        if has_rent and not has_sale:
            return ExtractionTransactionType.RENT
        if has_sale and not has_rent:
            return ExtractionTransactionType.SALE
        if has_rent and has_sale:
            if any(term in raw for term in ["per month", "/month", "pm", "deposit"]):
                return ExtractionTransactionType.RENT
            return ExtractionTransactionType.SALE
        return ExtractionTransactionType.SALE

    @field_validator("property_type", mode="before")
    @classmethod
    def normalize_property_type(cls, v: Any, info: Any) -> ExtractionPropertyType:
        if isinstance(v, ExtractionPropertyType):
            return v
        raw = " ".join(
            [
                str(v or ""),
                str((info.data or {}).get("cleaned_text") or ""),
            ]
        ).lower()

        if any(term in raw for term in ["office", "shop", "showroom", "warehouse", "godown", "commercial"]):
            return ExtractionPropertyType.COMMERCIAL
        if any(term in raw for term in ["plot", "na plot", "dtcp", "villa plot"]):
            return ExtractionPropertyType.PLOT
        if any(term in raw for term in ["land", "acre", "hectare", "agri land", "farmland"]):
            return ExtractionPropertyType.LAND
        if any(
            term in raw
            for term in [
                "bhk",
                "rk",
                "studio",
                "flat",
                "apartment",
                "penthouse",
                "duplex",
                "villa",
                "independent house",
                "residential",
            ]
        ):
            return ExtractionPropertyType.RESIDENTIAL
        return ExtractionPropertyType.UNKNOWN

    @field_validator("bhk", mode="before")
    @classmethod
    def normalize_bhk(cls, v: Any, info: Any) -> float | None:
        if v is None or v == "":
            raw = str((info.data or {}).get("cleaned_text") or "").lower()
        else:
            raw = str(v).lower()

        if "studio" in raw or re.search(r"\b[0o]\s*rk\b", raw) or "1 rk" in raw or "rk" in raw:
            return 0.5

        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bhk|bed|br)\b", raw)
        if match:
            return float(match.group(1))

        numeric = re.search(r"\b(\d+(?:\.\d+)?)\b", raw)
        if v is not None and numeric:
            return float(numeric.group(1))
        return None

    @field_validator("sqft", mode="before")
    @classmethod
    def normalize_sqft(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)

        s = str(v).replace(",", "").lower()
        match = re.search(r"(\d+(?:\.\d+)?)", s)
        if not match:
            return None
        value = float(match.group(1))
        if "sqyd" in s or "sq yd" in s or "gaj" in s:
            value *= 9
        return int(value)

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
        s = s.replace("₹", " ").replace("rs.", " ").replace("rs", " ").replace("inr", " ")
        match = re.search(r"(\d+(?:\.\d+)?)", s)
        if not match:
            return None

        base = float(match.group(1))
        if any(token in s for token in ["cr", "crore", "crores"]):
            base *= 10_000_000
        elif any(token in s for token in ["lac", "lakh", "lakhs", "lk", "l"]):
            if re.search(r"\b\d+(?:\.\d+)?\s*l\b", s) or any(t in s for t in ["lac", "lakh", "lakhs", "lk"]):
                base *= 100_000
        elif re.search(r"\b\d+(?:\.\d+)?\s*k\b", s) or "thousand" in s:
            base *= 1_000
        return int(base)

    @field_validator("furnishing", mode="before")
    @classmethod
    def normalize_furnishing(cls, v: Any) -> ExtractionFurnished | None:
        if v is None or v == "":
            return None
        if isinstance(v, ExtractionFurnished):
            return v
        s = str(v).strip().upper().replace("-", "_").replace(" ", "_")
        if "FULL" in s:
            return ExtractionFurnished.FULLY_FURNISHED
        if s == "FURNISHED":
            return ExtractionFurnished.FURNISHED
        if "SEMI" in s:
            return ExtractionFurnished.SEMI_FURNISHED
        if "UNFURNISHED" in s or "EMPTY" in s or "BARE" in s:
            return ExtractionFurnished.UNFURNISHED
        return ExtractionFurnished.UNKNOWN

    @field_validator("parking", mode="before")
    @classmethod
    def normalize_parking(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return max(0, v)
        if isinstance(v, float):
            return max(0, int(v))
        match = re.search(r"(\d+)", str(v))
        if match:
            return int(match.group(1))
        if str(v).strip().lower() in {"yes", "available", "covered", "open"}:
            return 1
        return None

    @field_validator("contact_numbers", mode="before")
    @classmethod
    def normalize_contact_numbers(cls, v: Any) -> list[str]:
        if not v:
            return []

        def _norm(num: str) -> str | None:
            digits = "".join(ch for ch in str(num) if ch.isdigit())
            if len(digits) == 12 and digits.startswith("91"):
                digits = digits[2:]
            if len(digits) == 11 and digits.startswith("0"):
                digits = digits[1:]
            if len(digits) >= 10:
                return digits[-10:]
            return None

        items = v if isinstance(v, list) else [v]
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = _norm(str(item))
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
        return out

    @field_validator("features", mode="before")
    @classmethod
    def normalize_features(cls, v: Any) -> list[str]:
        if not v:
            return []
        items = v if isinstance(v, list) else [v]
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = re.sub(r"\s+", " ", str(item)).strip()
            if not text:
                continue
            key = text.lower()
            if key not in seen:
                cleaned.append(text[:80])
                seen.add(key)
        return cleaned[:25]

    @field_validator("confidence_score", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        try:
            score = float(v)
        except (TypeError, ValueError):
            return 0.0
        if score < 0:
            return 0.0
        if score > 1:
            return 1.0
        return score


class ListingExtractionResult(BaseModel):
    """Canonical extractor output mapped to v2 DB columns."""

    property_type: ExtractionPropertyType = Field(default=ExtractionPropertyType.UNKNOWN)
    listing_intent: ExtractionListingIntent = Field(default=ExtractionListingIntent.OFFER)
    transaction_type: ExtractionTransactionType = Field(default=ExtractionTransactionType.SALE)
    bhk: float | None = Field(default=None)
    price: int | None = Field(default=None)
    location: str | None = None
    building_name: str | None = None
    contact_number: str | None = None
    furnished: ExtractionFurnished | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    area_sqft: int | None = None
    parking: int | None = None
    features: list[str] = Field(default_factory=list)
    landmark: str | None = None
    is_verified: bool = False
    is_irrelevant: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)

        if payload.get("area_sqft") is None and payload.get("sqft") is not None:
            payload["area_sqft"] = payload.get("sqft")
        if payload.get("furnished") is None and payload.get("furnishing") is not None:
            payload["furnished"] = payload.get("furnishing")
        if payload.get("contact_number") is None and payload.get("contact_numbers"):
            phones = payload.get("contact_numbers")
            if isinstance(phones, list) and phones:
                payload["contact_number"] = phones[0]
        return payload

    @field_validator("contact_number", mode="before")
    @classmethod
    def normalize_phone(cls, v: Any) -> str | None:
        if not v:
            return None
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) >= 10:
            return digits[-10:]
        return None

    @field_validator("location", "building_name", "landmark", mode="before")
    @classmethod
    def clean_text_fields(cls, v: Any) -> str | None:
        if v is None:
            return None
        text = re.sub(r"\s+", " ", str(v)).strip()
        return text or None


class BatchItemResult(BaseModel):
    message_index: int
    listings: list[PropertyListing] = Field(default_factory=list)
    is_irrelevant: bool = False


class BatchEnvelope(BaseModel):
    results: list[BatchItemResult] = Field(default_factory=list)


def _build_system_prompt() -> str:
    schema = BatchEnvelope.model_json_schema()
    return f"""
**ROLE**
You are ThreadSense, an expert extraction engine for Indian real-estate WhatsApp messages. 
Transform noisy, informal text into structured data. Maximize recall without hallucinating missing fields.

**STRICT OUTPUT CONTRACT**
- Output ONLY valid JSON.
- Top-level key must be `results` (an array).
- Map exactly ONE object per input `message_index`. NEVER skip an index.
- If a message lacks clear real estate intent, return: `{{"message_index": <int>, "is_irrelevant": true, "listings": []}}`

**EXTRACTION & NORMALIZATION RULES**
1. Price: Convert to pure integer Indian Rupees ('1.5 Cr' -> 15000000; '85k' -> 85000; '1.2 L/Lac' -> 120000). Strip currency symbols.
2. Intent: `OFFER` (available inventory) vs `REQUEST` (seeking/want/need).
3. Transaction: `RENT` (lease/monthly/PG) vs `SALE` (buy/sell/ownership). STRICTLY distinguish RENT vs SALE/OWNERSHIP based on phrasing.
4. Location: Extract specific micro-markets or building names (e.g., 'Bandra West', 'Lodha Bellissimo'). Strip generic city names like 'Mumbai'.
5. Specs: Map 'Studio' or '1 RK' to `0.5` BHK. 
6. Contact: Extract 10-to-12 digit phone numbers. Strip spaces and country codes (e.g., '+91').
7. Enums: Map strictly to the explicit values defined in the SCHEMA below. DO NOT use any other word, except the ones defined in the enums (e.g., FULLY_FURNISHED).
8. Confidence (0.0-1.0): Score based on clarity. Deduct points for missing price, location, or BHK.

**SCHEMA (REFERENCE)**
{schema}
""".strip()


def construct_batch_prompt(messages: Sequence[str]) -> str:
    parts = [
        "Extract real-estate data from these numbered messages.",
        "Return a JSON object with key 'results'.",
        "",
    ]
    for i, msg in enumerate(messages):
        safe_msg = (msg or "")[:6000]
        parts.append(f"--- Message {i} ---")
        parts.append(safe_msg)
        parts.append("")
    return "\n".join(parts)


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
        self._single_structured_model = self._model.with_structured_output(PropertyListing, method="function_calling")

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

            best_listing = max(item.listings, key=lambda x: x.confidence_score)
            if best_listing.is_irrelevant:
                packet_outputs.append((global_idx, None, raw_item))
                continue

            extracted = ListingExtractionResult.model_validate(best_listing.model_dump())
            packet_outputs.append((global_idx, extracted, raw_item))
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
        many = await self.extract_many([message_text])
        return many[0] if many else (None, None)

    async def aextract_batch(
        self,
        chunks: Sequence[tuple[UUID, str]],
    ) -> tuple[list[tuple[UUID, ListingExtractionResult | None]], dict[str, str]]:
        """
        v2 production batching path:
        - One structured-output call per message, but dispatched concurrently via `abatch`.
        - Keeps Pydantic validators as a post-processing safety net after model parsing.
        """
        if not chunks:
            return [], {}

        prompts: list[str] = []
        chunk_ids: list[UUID] = []
        for chunk_id, cleaned_text in chunks:
            chunk_ids.append(chunk_id)
            prompt: str = (
                "Extract one real-estate listing from this WhatsApp message. "
                "If irrelevant, set is_irrelevant=true.\n\n"
                f"Message:\n{(cleaned_text or '')[:6000]}"
            )
            prompts.append(prompt)

        raw_outputs: dict[str, str] = {}
        try:
            structured_results: list[PropertyListing] = await self._single_structured_model.abatch(prompts)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "batch_structured_extract_failed",
                batch_size=len(chunks),
                error=str(exc),
            )
            failed_results: list[tuple[UUID, ListingExtractionResult | None]] = [
                (chunk_id, None) for chunk_id in chunk_ids
            ]
            for chunk_id in chunk_ids:
                raw_outputs[str(chunk_id)] = f"abatch_error:{exc}"
            return failed_results, raw_outputs

        extracted_rows: list[tuple[UUID, ListingExtractionResult | None]] = []
        for chunk_id, structured in zip(chunk_ids, structured_results):
            try:
                # Re-validate through canonical extraction model to preserve all validators.
                canonical: ListingExtractionResult = ListingExtractionResult.model_validate(structured.model_dump())
                extracted_rows.append((chunk_id, canonical))
                raw_outputs[str(chunk_id)] = structured.model_dump_json()
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "batch_structured_extract_validation_failed",
                    chunk_id=str(chunk_id),
                    error=str(exc),
                )
                extracted_rows.append((chunk_id, None))
                raw_outputs[str(chunk_id)] = f"validation_error:{exc}"

        return extracted_rows, raw_outputs


def to_embedding_text(extraction: ListingExtractionResult, original_text: str) -> str:
    fields: list[str] = []
    fields.append(f"PropertyType: {extraction.property_type}")
    fields.append(f"Intent: {extraction.listing_intent}")
    fields.append(f"Transaction: {extraction.transaction_type}")

    if extraction.bhk is not None:
        fields.append(f"BHK: {extraction.bhk}")
    if extraction.price is not None:
        fields.append(f"Price: {extraction.price} INR")
    if extraction.location:
        fields.append(f"Location: {extraction.location}")
    if extraction.building_name:
        fields.append(f"Building: {extraction.building_name}")
    if extraction.area_sqft:
        fields.append(f"Area: {extraction.area_sqft} sqft")
    if extraction.furnished:
        fields.append(f"Furnished: {extraction.furnished}")
    if extraction.parking is not None:
        fields.append(f"Parking: {extraction.parking}")
    if extraction.features:
        fields.append(f"Features: {', '.join(extraction.features[:10])}")
    if extraction.landmark:
        fields.append(f"Landmark: {extraction.landmark}")
    if extraction.contact_number:
        fields.append(f"Contact: {extraction.contact_number}")

    compact_source = re.sub(r"\s+", " ", original_text).strip()
    fields.append(f"Source: {compact_source[:1200]}")
    return " | ".join(fields)
