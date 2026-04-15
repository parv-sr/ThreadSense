from __future__ import annotations

import asyncio
import os
import re
from enum import StrEnum
from typing import Any, Sequence

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
You are ThreadSense v2's production-grade extraction engine for Indian real-estate WhatsApp and Telegram messages.
You must maximize recall while preserving precision. Missing fields should be avoided if evidence exists.

OUTPUT CONTRACT (MANDATORY)
- Return ONLY strict JSON object with top-level key: "results".
- results must contain one object per input message index.
- Each result item: {{"message_index": <int>, "listings": [PropertyListing...], "is_irrelevant": <bool>}}
- Never omit a message_index.
- For messages with multiple properties, create multiple listings.
- If no real-estate signal, set is_irrelevant=true and listings=[].

SCHEMA (REFERENCE)
{schema}

TASK DEFINITION
For each message:
1) Identify whether it is relevant to property listing or property requirement.
2) Extract one or more normalized PropertyListing objects.
3) Populate as many fields as supported by evidence in text.
4) Avoid hallucination: do not invent details not grounded in message.

HIGH-PRIORITY EXTRACTION RULES
A) LISTING INTENT
- OFFER: someone offering property (owner/broker posting inventory, "available", "for sale", "on rent").
- REQUEST: someone seeking property ("looking for", "need 2bhk", "require office space", "client requirement").
- If ambiguous but inventory-like with concrete specs and price => OFFER.
- If explicit requirement words exist => REQUEST.

B) TRANSACTION TYPE
- RENT when phrases indicate rent/lease/license/monthly amount/deposit.
  Examples: "rent", "lease", "leave & license", "85k pm", "deposit 3 lakh".
- SALE when phrases indicate sale/purchase/ownership/asking price one-time deal.
  Examples: "for sale", "resale", "asking 2.4 cr", "outright".
- If both rent and sale are mentioned for separate options, split into separate listings.
- If both appear but single interpretation needed, prefer RENT when monthly signals exist.

C) PRICE NORMALIZATION (INR integer rupees)
- Normalize all prices to full rupees as integer.
- 1.5 Cr / 1.5 crore / 1.5cr => 15000000
- 2 Cr => 20000000
- 85k / 85 K => 85000
- 1.2 L / 1.2 lakh / 1.2 lac => 120000
- 95,000 => 95000
- If price has words "all inclusive", still capture numeric amount.
- If message has multiple prices for different units/listings, split listings.
- If exact price unavailable ("budget 2-3 cr"):
  - For REQUEST, pick most specific usable anchor (e.g., lower bound 20000000) and include range hint in cleaned_text.
  - For OFFER with no fixed ask, leave price null.

D) PHONE NUMBER EXTRACTION
- Extract every distinct contact number present in message text.
- Normalize to 10-digit Indian mobile where possible.
- Examples:
  - +91 98765 43210 => 9876543210
  - 09876543210 => 9876543210
  - 98765-43210 / 9876543210 => 9876543210
- Ignore short non-phone numerics (prices, sqft, floor counts).
- Store all in contact_numbers list.

E) LOCATION / BUILDING / LANDMARK
- location: locality/micro-market ("Bandra West", "Whitefield", "Sector 62").
- building_name: project/society/tower name ("Lodha Park", "DLF Phase 5", "Eden Tower").
- landmark: nearby known marker if clearly mentioned ("near metro", "opp Phoenix Mall").
- Prefer micro-location over city-only text.
- If only city present and no locality, city may be used as location.
- Never force null when a usable location token exists.

F) PROPERTY TYPE
- RESIDENTIAL: apartment/flat/bhk/rk/studio/villa/house/penthouse/duplex.
- COMMERCIAL: office/shop/showroom/warehouse/godown/co-working.
- PLOT: plot/site/layout/residential plot/NA plot.
- LAND: farmland/agri land/acre/hectare.
- UNKNOWN only if truly impossible.

G) OTHER FIELD NORMALIZATION
- bhk: float, use 0.5 for RK/Studio.
- sqft: integer; if sq yd/gaj provided convert approx x9.
- furnishing allowed: FULLY_FURNISHED / FURNISHED / SEMI_FURNISHED / UNFURNISHED / UNKNOWN.
- parking: integer slots when identifiable.
- features: concise amenity tags like ["Sea View", "Balcony", "Lift", "Pets Allowed"].
- cleaned_text: one concise normalized sentence without spam/emoji names.

H) IRRELEVANCE FILTER (is_irrelevant=true)
Mark irrelevant only when message is clearly non-listing and non-requirement, such as:
- greetings, jokes, festival wishes, political forwards,
- logistics only ("call me", "ok thanks") with no property signals,
- pure media captions with no real-estate information.
Do NOT mark irrelevant if ANY valid property requirement/listing clues exist.

I) CONFIDENCE SCORE (0.0 to 1.0)
- Start at 0.35 when message is real-estate relevant.
- +0.20 if clear transaction type words found.
- +0.15 if clear location found.
- +0.10 if price extracted confidently.
- +0.10 if property type clear.
- +0.05 each for bhk/sqft/building/furnishing/contact evidence (cap +0.20 from these).
- -0.15 if message is highly ambiguous or conflicting.
- Clamp to [0.0, 1.0].
- Irrelevant messages should have empty listings and no confidence needed.

MULTI-LISTING HANDLING
- If message contains list/bullets/numbered inventory, split into separate listings when details differ (location/price/bhk/type).
- If repeated forwards of same unit in one message, deduplicate by key fields.

GOOD EXAMPLES
1) "Available 2bhk semi furnished in Hiranandani Powai, rent 85k, call +91 98765 43210"
   -> OFFER, RENT, RESIDENTIAL, bhk=2, location=Powai, building_name=Hiranandani, furnishing=SEMI_FURNISHED, price=85000, contact_numbers=[9876543210], relevant.
2) "Client requirement: 3 BHK to buy in Bandra West, budget 6-8 cr"
   -> REQUEST, SALE, RESIDENTIAL, location=Bandra West, bhk=3, price=60000000 anchor, relevant.
3) "Shop 450 sqft for lease at Koramangala 80k pm"
   -> OFFER, RENT, COMMERCIAL, sqft=450, location=Koramangala, price=80000.

BAD EXAMPLES (AVOID)
1) Returning null location when message says "Andheri West".
2) Returning price=85 for "85k" (must be 85000).
3) Marking requirement messages as OFFER when phrase includes "looking for".
4) Marking message irrelevant when it has clear property signal.
5) Mixing two different listings into one when price/location differ.

STRICT QUALITY CHECK BEFORE RETURNING
- Did you output exactly one result item per Message X?
- Are message_index values exactly matching Message numbers?
- Are numbers normalized (price/phone/sqft)?
- Are intents/transaction types inferred from language cues?
- Is irrelevance used conservatively?
- Is JSON valid and complete?
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
