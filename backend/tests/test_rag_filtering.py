"""Tests for the RAG hard-filtering tool."""
from __future__ import annotations

import pytest
from langchain_core.documents import Document

from backend.src.rag.tools import filter_listings


@pytest.mark.asyncio
async def test_filter_listings_partial_location_and_numeric_bhk() -> None:
    docs: list[Document] = [
        Document(
            page_content="listing-a",
            metadata={"location": "Bandra W Reclamation", "bhk": 3.0, "price_numeric": 250000},
        ),
        Document(
            page_content="listing-b",
            metadata={"location": "Khar West", "bhk": 2.0, "price_numeric": 115000},
        ),
    ]

    filtered: list[Document] = await filter_listings.ainvoke(
        {"docs": docs, "criteria": {"location": "bandra", "bhk": 3, "max_price": 300000}}
    )

    assert len(filtered) == 1
    assert filtered[0].metadata["location"] == "Bandra W Reclamation"


@pytest.mark.asyncio
async def test_filter_by_price_range() -> None:
    docs: list[Document] = [
        Document(page_content="cheap", metadata={"price": 20000, "location": "Andheri"}),
        Document(page_content="mid", metadata={"price": 50000, "location": "Andheri"}),
        Document(page_content="expensive", metadata={"price": 150000, "location": "Andheri"}),
    ]

    filtered = await filter_listings.ainvoke(
        {"docs": docs, "criteria": {"min_price": 30000, "max_price": 100000}}
    )

    assert len(filtered) == 1
    assert filtered[0].page_content == "mid"


@pytest.mark.asyncio
async def test_filter_case_insensitive_location() -> None:
    docs: list[Document] = [
        Document(page_content="a", metadata={"location": "BANDRA WEST", "bhk": 2.0}),
        Document(page_content="b", metadata={"location": "khar east", "bhk": 2.0}),
    ]

    filtered = await filter_listings.ainvoke(
        {"docs": docs, "criteria": {"location": "bandra"}}
    )

    assert len(filtered) == 1
    assert "BANDRA" in filtered[0].metadata["location"]


@pytest.mark.asyncio
async def test_filter_returns_empty_when_no_match() -> None:
    docs: list[Document] = [
        Document(page_content="a", metadata={"location": "Pune", "bhk": 1.0}),
    ]

    filtered = await filter_listings.ainvoke(
        {"docs": docs, "criteria": {"location": "mumbai", "bhk": 3}}
    )

    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_filter_with_no_criteria_returns_all() -> None:
    docs: list[Document] = [
        Document(page_content="a", metadata={"location": "Andheri"}),
        Document(page_content="b", metadata={"location": "Bandra"}),
    ]

    filtered = await filter_listings.ainvoke(
        {"docs": docs, "criteria": {}}
    )

    assert len(filtered) == 2
