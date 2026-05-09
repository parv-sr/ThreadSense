"""Tests for the extraction and enrichment pipeline."""
from __future__ import annotations

from backend.src.preprocessing.extractor import (
    ExtractionFurnished,
    ExtractionPropertyType,
    ExtractionTransactionType,
    ListingExtractionResult,
    PropertyListing,
    _enrich_extraction,
    _estimate_confidence,
)


def test_enrich_extraction_populates_missing_core_fields() -> None:
    raw_text: str = "Available 3 BHK for rent in Bandra West, call +91 97695 66757"
    base: ListingExtractionResult = ListingExtractionResult(
        property_type=ExtractionPropertyType.RESIDENTIAL,
        bhk=None,
        location=None,
        contact_number=None,
        confidence_score=0.0,
    )

    enriched: ListingExtractionResult = _enrich_extraction(base, raw_text)

    assert enriched.bhk == 3.0
    assert enriched.location is not None
    assert "bandra" in enriched.location.lower()
    assert enriched.contact_number == "9769566757"
    assert enriched.confidence_score > 0.0


# ── Confidence score ─────────────────────────────────────────────────────

def test_confidence_high_when_all_fields_present() -> None:
    extraction = ListingExtractionResult(
        property_type=ExtractionPropertyType.RESIDENTIAL,
        location="Bandra West",
        price=50000,
        bhk=2.0,
        contact_number="9876543210",
    )
    score = _estimate_confidence(extraction, "2bhk rent bandra 50k call 9876543210")
    assert score >= 0.7


def test_confidence_low_when_minimal_info() -> None:
    extraction = ListingExtractionResult()
    score = _estimate_confidence(extraction, "hi")
    assert score <= 0.2


def test_enrich_extraction_handles_extreme_outliers() -> None:
    base = ListingExtractionResult(
        property_type=ExtractionPropertyType.RESIDENTIAL,
        bhk=500.0, 
        price=10,
        confidence_score=0.0,
    )
    enriched = _enrich_extraction(base, "massive building")
    score = _estimate_confidence(enriched, "massive building")
    assert score < 0.5 


def test_enrich_extraction_with_malformed_contact() -> None:
    base = ListingExtractionResult(
        contact_number="not a number 123",
        confidence_score=0.0
    )
    enriched = _enrich_extraction(base, "call me at not a number 123")
    assert enriched.contact_number is None or enriched.contact_number.isdigit()
