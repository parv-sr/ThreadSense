from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class QueryConstraints:
    normalized_query: str
    filters: dict[str, Any] = field(default_factory=dict)
    intent_terms: set[str] = field(default_factory=set)


def _normalize_location_tokens(text: str) -> str:
    normalized: str = re.sub(r"\s+", " ", text).strip().lower()
    normalized = normalized.replace(" w ", " west ").replace(" e ", " east ")
    normalized = normalized.replace("w.", "west").replace("e.", "east")
    return normalized


def parse_query_constraints(query: str) -> QueryConstraints:
    raw_query: str = (query or "").strip()
    lowered_query: str = raw_query.lower()
    normalized_query: str = lowered_query

    replacements: list[tuple[str, str]] = [
        (r"\b([0-9]+)\s*[-/]?\s*bhk\b", r"\1 bhk"),
        (r"\b([0-9]+)\s*rk\b", "studio"),
        (r"\bbkc\b", "bandra kurla complex"),
        (r"\bandheri\s*w\b", "andheri west"),
        (r"\bandheri\s*e\b", "andheri east"),
        (r"\bbandra\s*w\b", "bandra west"),
        (r"\bbandra\s*e\b", "bandra east"),
        (r"\bkhar\s*w\b", "khar west"),
        (r"\bkhar\s*e\b", "khar east"),
    ]
    for pattern, replacement in replacements:
        normalized_query = re.sub(pattern, replacement, normalized_query, flags=re.IGNORECASE)
    normalized_query = re.sub(r"\s+", " ", normalized_query).strip()

    filters: dict[str, Any] = {}
    intent_terms: set[str] = set()

    bhk_match: re.Match[str] | None = re.search(r"\b(\d+(?:\.\d+)?)\s*bhk\b", normalized_query)
    if bhk_match is not None:
        filters["bhk"] = float(bhk_match.group(1))
        intent_terms.add("bhk")
    elif "studio" in normalized_query or re.search(r"\b1\s*rk\b", normalized_query):
        filters["bhk"] = 0.5
        intent_terms.add("bhk")

    if any(token in normalized_query for token in ("rent", "lease", "leave and license", "tenant")):
        filters["transaction_type"] = "RENT"
        intent_terms.add("rent")
    elif any(token in normalized_query for token in ("sale", "buy", "purchase", "ownership", "resale")):
        filters["transaction_type"] = "SALE"
        intent_terms.add("sale")

    if any(token in normalized_query for token in ("office", "shop", "showroom", "warehouse", "commercial")):
        filters["property_type"] = "COMMERCIAL"
        intent_terms.add("commercial")
    elif any(token in normalized_query for token in ("flat", "apartment", "bhk", "villa", "residential", "studio")):
        filters["property_type"] = "RESIDENTIAL"
        intent_terms.add("residential")

    max_price_match: re.Match[str] | None = re.search(r"\b(?:under|max|upto|up to)\s*₹?\s*(\d+(?:\.\d+)?)\s*(cr|crore|l|lac|lakh|k)?\b", normalized_query)
    min_price_match: re.Match[str] | None = re.search(r"\b(?:above|min|from)\s*₹?\s*(\d+(?:\.\d+)?)\s*(cr|crore|l|lac|lakh|k)?\b", normalized_query)

    def _to_inr(value: float, unit: str | None) -> float:
        unit_normalized: str = (unit or "").lower()
        if unit_normalized in {"cr", "crore"}:
            return value * 10_000_000.0
        if unit_normalized in {"l", "lac", "lakh"}:
            return value * 100_000.0
        if unit_normalized in {"k"}:
            return value * 1_000.0
        return value

    if max_price_match is not None:
        filters["max_price"] = _to_inr(float(max_price_match.group(1)), max_price_match.group(2))
        intent_terms.add("budget")
    if min_price_match is not None:
        filters["min_price"] = _to_inr(float(min_price_match.group(1)), min_price_match.group(2))
        intent_terms.add("budget")

    known_locations: list[str] = [
        "bandra",
        "khar",
        "santacruz",
        "andheri",
        "juhu",
        "worli",
        "dadar",
        "chembur",
        "powai",
        "borivali",
        "malad",
        "goregaon",
        "bkc",
        "kurla",
    ]
    normalized_for_location: str = _normalize_location_tokens(normalized_query)
    for location in known_locations:
        if location in normalized_for_location:
            if "west" in normalized_for_location and location in normalized_for_location:
                filters["location"] = f"{location} west"
            elif "east" in normalized_for_location and location in normalized_for_location:
                filters["location"] = f"{location} east"
            else:
                filters["location"] = location
            intent_terms.add("location")
            break

    return QueryConstraints(
        normalized_query=normalized_query,
        filters=filters,
        intent_terms=intent_terms,
    )
