from __future__ import annotations

from backend.src.preprocessing.extractor import (
    ExtractionPropertyType,
    ListingExtractionResult,
    _enrich_extraction,
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
