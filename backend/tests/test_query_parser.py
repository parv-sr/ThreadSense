from __future__ import annotations

from backend.src.rag.query_parser import QueryConstraints, parse_query_constraints


def test_parse_query_constraints_extracts_bhk_and_location() -> None:
    constraints: QueryConstraints = parse_query_constraints("3bhk in bandra")
    assert constraints.normalized_query == "3 bhk in bandra"
    assert constraints.filters.get("bhk") == 3.0
    assert constraints.filters.get("location") == "bandra"


def test_parse_query_constraints_extracts_transaction_and_budget() -> None:
    constraints: QueryConstraints = parse_query_constraints("need office lease in bkc under 2.5 cr")
    assert constraints.filters.get("transaction_type") == "RENT"
    assert constraints.filters.get("property_type") == "COMMERCIAL"
    assert constraints.filters.get("location") is not None
    assert constraints.filters.get("max_price") == 25_000_000.0
