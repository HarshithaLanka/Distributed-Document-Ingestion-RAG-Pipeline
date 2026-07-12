"""
Integration-style tests for Week 14 QA retrieval flow.

All external systems are mocked:
- Pinecone/BM25/Neo4j hybrid retrieval
- reranking
- Ollama

The purpose is to verify that QA uses reranked context and validates citations.
"""

from app.services import qa_service as service


class FakeRequest:
    """Small request object matching the fields used by answer_question."""

    def __init__(
        self,
        document_id="doc-1",
        question="What is hybrid retrieval?",
        top_k=5,
        min_score=0.0,
    ):
        self.document_id = document_id
        self.question = question
        self.top_k = top_k
        self.min_score = min_score


def _safe_redactor(text):
    """Return the same text in the format expected by QA."""

    return {"redacted_text": text or ""}


def test_answer_question_uses_reranked_context(monkeypatch):
    """QA should send only reranked chunks into the LLM prompt."""

    hybrid_candidates = [
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-a",
            "text": "Weak candidate.",
            "page_number": 1,
            "hybrid_score": 0.8,
            "retrieval_sources": ["vector"],
        },
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-b",
            "text": "Hybrid retrieval combines vector and BM25 search.",
            "page_number": 2,
            "hybrid_score": 0.7,
            "retrieval_sources": ["vector", "keyword"],
        },
    ]

    reranked_candidates = [
        {
            **hybrid_candidates[1],
            "rerank_score": 0.95,
            "original_rank": 2,
            "final_rank": 1,
        }
    ]

    captured = {}

    monkeypatch.setattr(
        service,
        "hybrid_search_document",
        lambda **kwargs: hybrid_candidates,
    )

    def fake_rerank(question, candidates, final_top_k):
        captured["rerank_question"] = question
        captured["rerank_candidates"] = candidates
        return reranked_candidates

    monkeypatch.setattr(
        service,
        "rerank_candidates",
        fake_rerank,
    )
    monkeypatch.setattr(
        service,
        "redact_text",
        _safe_redactor,
    )
    monkeypatch.setattr(
        service,
        "get_summary_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_identity_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_skill_technology_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_keyword_overlap_chunks",
        lambda **kwargs: [],
    )

    def fake_generate_answer(prompt):
        captured["prompt"] = prompt
        return '{"answer":"It combines vector and BM25 search.",' \
               '"used_chunk_ids":["chunk-b"],' \
               '"answer_status":"found"}'

    monkeypatch.setattr(
        service,
        "generate_answer_from_ollama",
        fake_generate_answer,
    )
    monkeypatch.setattr(
        service,
        "parse_llm_json_response",
        lambda raw: {
            "answer": "It combines vector and BM25 search.",
            "used_chunk_ids": ["chunk-b"],
            "answer_status": "found",
        },
    )

    response = service.answer_question(FakeRequest())

    assert captured["rerank_question"] == (
        "What is hybrid retrieval?"
    )
    assert captured["rerank_candidates"] == hybrid_candidates

    assert "chunk-b" in captured["prompt"]
    assert "Hybrid retrieval combines vector and BM25 search." in (
        captured["prompt"]
    )
    assert "chunk-a" not in captured["prompt"]

    assert response.answer_status == "found"
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "chunk-b"


def test_answer_question_returns_not_found_when_no_candidates(
    monkeypatch,
):
    """No retrieved evidence should produce a safe not-found answer."""

    monkeypatch.setattr(
        service,
        "hybrid_search_document",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "rerank_candidates",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "redact_text",
        _safe_redactor,
    )
    monkeypatch.setattr(
        service,
        "get_keyword_overlap_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_identity_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_skill_technology_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_summary_anchor_chunks",
        lambda **kwargs: [],
    )

    response = service.answer_question(
        FakeRequest(question="Unknown fact?")
    )

    assert response.answer_status == "not_found"
    assert response.citations == []


def test_answer_question_rejects_unretrieved_citation(monkeypatch):
    """The LLM cannot cite a chunk that was not in final context."""

    candidate = {
        "document_id": "doc-1",
        "chunk_id": "chunk-valid",
        "text": "The document discusses graph retrieval.",
        "page_number": 3,
        "hybrid_score": 0.8,
        "rerank_score": 0.9,
        "retrieval_sources": ["graph"],
        "original_rank": 1,
        "final_rank": 1,
    }

    monkeypatch.setattr(
        service,
        "hybrid_search_document",
        lambda **kwargs: [candidate],
    )
    monkeypatch.setattr(
        service,
        "rerank_candidates",
        lambda **kwargs: [candidate],
    )
    monkeypatch.setattr(
        service,
        "redact_text",
        _safe_redactor,
    )
    monkeypatch.setattr(
        service,
        "get_keyword_overlap_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_identity_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_skill_technology_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "get_summary_anchor_chunks",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "generate_answer_from_ollama",
        lambda prompt: "{}",
    )
    monkeypatch.setattr(
        service,
        "parse_llm_json_response",
        lambda raw: {
            "answer": "Graph retrieval finds related chunks.",
            "used_chunk_ids": ["chunk-invented"],
            "answer_status": "found",
        },
    )

    response = service.answer_question(
        FakeRequest(question="What is graph retrieval?")
    )

    assert response.answer_status == "not_found"
    assert response.citations == []