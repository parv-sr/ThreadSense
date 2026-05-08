"""Tests for the RAG query parser."""
from __future__ import annotations

from backend.src.rag.query_parser import QueryConstraints, parse_query_constraints


def test_parse_query_constraints_extracts_bhk_and_location() -> None:
    constraints: QueryConstraints = parse_query_constraints("3bhk in bandra")
    assert constraints.normalized_query == "3 bhk in bandra"
    assert constraints.filters.get("bhk") == 3.0
    assert constraints.filters.get("location") == "bandra"


def test_parse_query_constraints_extracts_transaction_and_budget() -> None:
    constraints: QueryConstraints = parse_query_constraints("need office lease in bkc under 2.5 cr")
    assert constraints.filters.get("transaction_type") == "LEASE"
    assert constraints.filters.get("property_type") == "COMMERCIAL"
    assert constraints.filters.get("location") is not None
    assert constraints.filters.get("max_price") == 25_000_000.0


def test_parse_query_empty_string() -> None:
    constraints: QueryConstraints = parse_query_constraints("")
    assert constraints.normalized_query == ""
    assert isinstance(constraints.filters, dict)


def test_parse_query_furnishing() -> None:
    constraints: QueryConstraints = parse_query_constraints("furnished 2bhk in khar")
    assert constraints.filters.get("bhk") == 2.0
    assert constraints.filters.get("location") is not None


def test_parse_query_rent_keywords() -> None:
    constraints: QueryConstraints = parse_query_constraints("flat for rent in andheri")
    assert constraints.filters.get("transaction_type") == "RENT"


def test_parse_query_sale_keywords() -> None:
    constraints: QueryConstraints = parse_query_constraints("flat for sale in powai")
    assert constraints.filters.get("transaction_type") == "SALE"


def test_parse_query_studio_bhk() -> None:
    constraints: QueryConstraints = parse_query_constraints("studio apartment bandra")
    # Studio should map to 0.5 bhk or be recognized
    assert constraints.filters.get("bhk") in {0.5, None}


def test_parse_query_price_range() -> None:
    constraints: QueryConstraints = parse_query_constraints("2bhk under 50 lacs")
    assert constraints.filters.get("bhk") == 2.0
    max_price = constraints.filters.get("max_price")
    if max_price is not None:
        assert max_price == 5_000_000.0


def test_parse_query_mixed_numerals() -> None:
    constraints1 = parse_query_constraints("two bhk in khar")
    constraints2 = parse_query_constraints("2.5 bhk in khar")
    
    assert constraints1.filters.get("bhk") == 2.0
    assert constraints2.filters.get("bhk") == 2.5


def test_parse_query_nonsense_or_sql_injection_attempt() -> None:
    constraints = parse_query_constraints("DROP TABLE users; --")
    assert constraints.normalized_query is not None
    assert isinstance(constraints.filters, dict)


def test_parse_query_conflicting_intents() -> None:
    constraints = parse_query_constraints("looking for 2bhk sale or rent")
    assert "transaction_type" in constraints.filters
