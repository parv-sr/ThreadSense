"""Tests for the deduplication and filtering logic in the ingestion pipeline."""
from __future__ import annotations

from backend.src.tasks.ingestion import (
    JUNK_RE,
    KEYWORDS_RE,
    _looks_like_listing_candidate,
    _normalize_for_hash,
)


def test_normalize_for_hash_consistency() -> None:
    """Same text+sender should always produce the same hash."""
    h1 = _normalize_for_hash("2bhk rent bandra", "Alice")
    h2 = _normalize_for_hash("2bhk rent bandra", "Alice")
    assert h1 == h2


def test_normalize_for_hash_whitespace_insensitive() -> None:
    h1 = _normalize_for_hash("2bhk  rent   bandra", "Alice")
    h2 = _normalize_for_hash("2bhk rent bandra", "Alice")
    assert h1 == h2


def test_normalize_for_hash_different_senders() -> None:
    h1 = _normalize_for_hash("2bhk rent bandra", "Alice")
    h2 = _normalize_for_hash("2bhk rent bandra", "Bob")
    assert h1 != h2


def test_looks_like_listing_positive() -> None:
    assert _looks_like_listing_candidate("2bhk flat for rent in Bandra West") is True
    assert _looks_like_listing_candidate("Office space 1500 sqft goregaon") is True
    assert _looks_like_listing_candidate("Available 1 rk studio apartment Khar") is True
    assert _looks_like_listing_candidate("Price 45 lakhs 3 bhk") is True


def test_looks_like_listing_negative() -> None:
    assert _looks_like_listing_candidate("Good morning everyone!") is False
    assert _looks_like_listing_candidate("ok") is False
    assert _looks_like_listing_candidate("Thanks") is False


def test_junk_regex_matches_system_messages() -> None:
    assert JUNK_RE.search("Your security code changed") is not None
    assert JUNK_RE.search("Waiting for this message") is not None
    assert JUNK_RE.search("This message was deleted") is not None
    assert JUNK_RE.search("<Media omitted>") is not None


def test_junk_regex_does_not_match_real_listings() -> None:
    assert JUNK_RE.search("3 bhk for rent in andheri west") is None
    assert JUNK_RE.search("Office 2000 sqft BKC available") is None


def test_keywords_regex_matches_property_terms() -> None:
    assert KEYWORDS_RE.search("2 bhk flat rent") is not None
    assert KEYWORDS_RE.search("sale price 50 lacs") is not None
    assert KEYWORDS_RE.search("furnished studio apartment") is not None
    assert KEYWORDS_RE.search("1200 sqft carpet area") is not None
    assert KEYWORDS_RE.search("commercial office shop") is not None


def test_keywords_regex_does_not_match_noise() -> None:
    assert KEYWORDS_RE.search("hello world") is None
    assert KEYWORDS_RE.search("good morning") is None
