"""
Tests for Week 14 reranking service.
"""

from app.services import reranking_service as service


def test_rerank_candidates_returns_empty_for_no_candidates():
    """No candidates means no reranked results."""

    assert service.rerank_candidates(
        question="What is BM25?",
        candidates=[],
        final_top_k=5,
    ) == []


def test_rerank_candidates_rejects_empty_question():
    """A meaningful user question is required."""

    try:
        service.rerank_candidates(
            question="",
            candidates=[],
            final_top_k=5,
        )
    except ValueError as error:
        assert "question" in str(error)
    else:
        raise AssertionError("ValueError was not raised")


def test_rerank_candidates_places_more_relevant_chunk_first(
    monkeypatch,
):
    """A chunk containing the full answer should outrank a weak match."""

    monkeypatch.setattr(
        service,
        "extract_query_entities",
        lambda question: [
            {
                "text": "BM25",
                "normalized_text": "bm25",
                "label": "PRODUCT",
            }
        ],
    )

    candidates = [
        {
            "chunk_id": "weak",
            "text": "This section briefly mentions search.",
            "section_title": "Overview",
            "hybrid_score": 0.8,
            "retrieval_sources": ["vector"],
        },
        {
            "chunk_id": "strong",
            "text": (
                "BM25 is a keyword ranking algorithm used for "
                "exact lexical retrieval."
            ),
            "section_title": "BM25 Keyword Search",
            "hybrid_score": 0.7,
            "retrieval_sources": [
                "vector",
                "keyword",
            ],
            "matched_entities": ["bm25"],
        },
    ]

    results = service.rerank_candidates(
        question="What is BM25 keyword search?",
        candidates=candidates,
        final_top_k=2,
    )

    assert results[0]["chunk_id"] == "strong"
    assert results[0]["final_rank"] == 1
    assert results[1]["final_rank"] == 2


def test_rerank_candidates_preserves_original_input(monkeypatch):
    """Reranking should not mutate the original candidate dictionary."""

    monkeypatch.setattr(
        service,
        "extract_query_entities",
        lambda question: [],
    )

    candidate = {
        "chunk_id": "chunk-1",
        "text": "Hybrid retrieval combines search methods.",
        "hybrid_score": 0.5,
        "retrieval_sources": ["vector"],
    }

    original_copy = dict(candidate)

    service.rerank_candidates(
        question="Explain hybrid retrieval",
        candidates=[candidate],
        final_top_k=1,
    )

    assert candidate == original_copy


def test_rerank_score_stays_between_zero_and_one(monkeypatch):
    """The final score must remain normalized."""

    monkeypatch.setattr(
        service,
        "extract_query_entities",
        lambda question: [],
    )

    results = service.rerank_candidates(
        question="Explain reranking",
        candidates=[
            {
                "chunk_id": "chunk-1",
                "text": "Reranking reorders retrieved chunks.",
                "hybrid_score": 5.0,
                "retrieval_sources": ["vector"],
            }
        ],
        final_top_k=1,
    )

    assert 0.0 <= results[0]["rerank_score"] <= 1.0


def test_rerank_candidates_respects_final_top_k(monkeypatch):
    """Only the requested number of final chunks should be returned."""

    monkeypatch.setattr(
        service,
        "extract_query_entities",
        lambda question: [],
    )

    candidates = [
        {
            "chunk_id": f"chunk-{index}",
            "text": f"Candidate {index}",
            "hybrid_score": index / 10,
            "retrieval_sources": ["vector"],
        }
        for index in range(10)
    ]

    results = service.rerank_candidates(
        question="candidate",
        candidates=candidates,
        final_top_k=3,
    )

    assert len(results) == 3
    assert [item["final_rank"] for item in results] == [1, 2, 3]