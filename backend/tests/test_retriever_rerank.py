from __future__ import annotations

from langchain_core.documents import Document

from backend.src.rag.retriever import HybridQdrantRetriever


def test_lexical_rerank_prefers_exact_location_and_bhk() -> None:
    docs: list[Document] = [
        Document(page_content="2 bhk in khar west", metadata={"location": "Khar West", "bhk": 2.0}),
        Document(page_content="3 bhk in bandra west", metadata={"location": "Bandra West", "bhk": 3.0}),
    ]
    reranked: list[Document] = HybridQdrantRetriever._lexical_rerank(
        docs=docs,
        query="3 bhk bandra west",
        parsed_filters={"bhk": 3.0, "location": "bandra west"},
        top_k=2,
    )
    assert reranked
    assert reranked[0].metadata.get("location") == "Bandra West"
