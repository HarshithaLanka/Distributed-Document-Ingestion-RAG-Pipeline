# This file tests hybrid retrieval service.

# Import hybrid retrieval service module.
from app.services import hybrid_retrieval_service


def test_hybrid_search_merges_and_deduplicates(monkeypatch):
    # Fake vector search results.
    fake_vector_results = [
        {
            "document_id": "doc_test",
            "chunk_id": "chunk_001",
            "text": "BM25 keyword search and hybrid retrieval.",
            "score": 0.90,
            "page_number": 1,
            "section_title": "Week 13",
            "content_type": "paragraph",
            "parser_used": "docling",
        },
        {
            "document_id": "doc_test",
            "chunk_id": "chunk_002",
            "text": "Vector search uses embeddings.",
            "score": 0.70,
            "page_number": 2,
            "section_title": "Vector Search",
            "content_type": "paragraph",
            "parser_used": "docling",
        },
    ]

    # Fake BM25 keyword results.
    # chunk_001 appears again, so hybrid should deduplicate it.
    fake_keyword_results = [
        {
            "document_id": "doc_test",
            "chunk_id": "chunk_001",
            "text": "BM25 keyword search and hybrid retrieval.",
            "score": 10.0,
            "page_number": 1,
            "section_title": "Week 13",
            "content_type": "paragraph",
            "parser_used": "docling",
        },
        {
            "document_id": "doc_test",
            "chunk_id": "chunk_003",
            "text": "Exact section numbers are useful for BM25.",
            "score": 8.0,
            "page_number": 3,
            "section_title": "BM25",
            "content_type": "paragraph",
            "parser_used": "docling",
        },
    ]

    # Replace real Pinecone call with fake vector results.
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "search_similar_chunks",
        lambda document_id, query, top_k: fake_vector_results,
    )

    # Replace real BM25 call with fake keyword results.
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "search_document_with_bm25_as_dicts",
        lambda document_id, query, top_k: fake_keyword_results,
    )

    # Run hybrid search.
    results = hybrid_retrieval_service.hybrid_search_document(
    document_id="doc_test",
    query="BM25 hybrid retrieval",
    top_k=5,
    vector_weight=0.6,
    keyword_weight=0.4,
    graph_weight=0.0,
    include_graph=False,
)

    # Extract chunk IDs.
    chunk_ids = [result["chunk_id"] for result in results]

    # chunk_001 should appear only once.
    assert chunk_ids.count("chunk_001") == 1

    # chunk_001 should be marked as both because vector and BM25 found it.
    chunk_001 = next(result for result in results if result["chunk_id"] == "chunk_001")
    assert chunk_001["matched_by"] == "both"

    # Hybrid score fields should exist.
    assert "vector_score" in chunk_001
    assert "keyword_score" in chunk_001
    assert "hybrid_score" in chunk_001

    # We should also keep vector-only and keyword-only results.
    assert "chunk_002" in chunk_ids
    assert "chunk_003" in chunk_ids


def test_hybrid_search_redacts_vector_text(monkeypatch):
    # Fake vector result with raw PII.
    fake_vector_results = [
        {
            "document_id": "doc_test",
            "chunk_id": "chunk_001",
            "text": "Contact harshitha@example.com or +91 8008486999.",
            "score": 0.9,
            "page_number": 1,
        }
    ]

    # No BM25 results needed for this test.
    fake_keyword_results = []

    # Replace real Pinecone call.
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "search_similar_chunks",
        lambda document_id, query, top_k: fake_vector_results,
    )

    # Replace real BM25 call.
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "search_document_with_bm25_as_dicts",
        lambda document_id, query, top_k: fake_keyword_results,
    )

    # Run hybrid search.
    results = hybrid_retrieval_service.hybrid_search_document(
        document_id="doc_test",
        query="contact",
        top_k=5,
    )

    # Get returned text.
    returned_text = results[0]["text"]

    # Email and phone should not leak.
    assert "harshitha@example.com" not in returned_text
    assert "8008486999" not in returned_text

    # Placeholders should appear.
    assert "[EMAIL_REDACTED]" in returned_text
    assert "[PHONE_REDACTED]" in returned_text