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
