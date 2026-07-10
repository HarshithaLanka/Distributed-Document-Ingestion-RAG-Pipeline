# This file tests BM25 keyword search service.

# Import json to create fake chunks files.
import json

# Import pytest for test assertions and error testing.
import pytest

# Import bm25_service module so we can test its functions.
from app.services import bm25_service


def test_tokenize_text_keeps_useful_tokens():
    # Input text with technical words, number, and mixed case.
    text = "Week 13: BM25 Keyword Search with Section 4.2"

    # Tokenize text.
    tokens = bm25_service.tokenize_text(text)

    # Check important tokens are preserved.
    assert "week" in tokens
    assert "13" in tokens
    assert "bm25" in tokens
    assert "keyword" in tokens
    assert "search" in tokens
    assert "4.2" in tokens


def test_bm25_search_uses_redacted_chunks(tmp_path, monkeypatch):
    # Create fake uploads folder.
    uploads_dir = tmp_path / "uploads"

    # Create fake document folder.
    document_id = "doc_test_bm25"
    document_folder = uploads_dir / document_id
    document_folder.mkdir(parents=True)

    # Create fake redacted chunks.
    # Important:
    # We use more than 2 chunks because BM25 scores can become 0
    # when the test corpus is too tiny.
    chunks = [
        {
            "document_id": document_id,
            "chunk_id": "chunk_001",
            "text": "Week 13 explains BM25 keyword search and hybrid retrieval.",
            "page_number": 1,
            "section_title": "Week 13",
            "content_type": "paragraph",
            "parser_used": "docling",
            "word_count": 9,
        },
        {
            "document_id": document_id,
            "chunk_id": "chunk_002",
            "text": "Vector search uses embeddings and Pinecone for semantic search.",
            "page_number": 2,
            "section_title": "Vector Search",
            "content_type": "paragraph",
            "parser_used": "docling",
            "word_count": 9,
        },
        {
            "document_id": document_id,
            "chunk_id": "chunk_003",
            "text": "SQS sends document jobs to the background worker.",
            "page_number": 3,
            "section_title": "Worker",
            "content_type": "paragraph",
            "parser_used": "docling",
            "word_count": 8,
        },
        {
            "document_id": document_id,
            "chunk_id": "chunk_004",
            "text": "PII redaction replaces email and phone values before indexing.",
            "page_number": 4,
            "section_title": "Privacy",
            "content_type": "paragraph",
            "parser_used": "docling",
            "word_count": 9,
        },
    ]

    # Write redacted_chunks.json.
    redacted_chunks_path = document_folder / "redacted_chunks.json"
    redacted_chunks_path.write_text(
        json.dumps({"redacted_chunks": chunks}),
        encoding="utf-8",
    )

    # Tell bm25_service to use our fake uploads folder.
    monkeypatch.setattr(bm25_service, "UPLOAD_DIR", str(uploads_dir))

    # Run BM25 search.
    results = bm25_service.search_document_with_bm25_as_dicts(
        document_id=document_id,
        query="BM25 hybrid retrieval",
        top_k=5,
    )

    # We should get at least one result.
    assert len(results) >= 1

    # Best result should be chunk_001 because it has exact BM25/hybrid words.
    assert results[0]["chunk_id"] == "chunk_001"

    # Score should be positive.
    assert results[0]["score"] > 0


def test_bm25_missing_chunks_file_raises_error(tmp_path, monkeypatch):
    # Create fake uploads folder without chunks file.
    uploads_dir = tmp_path / "uploads"

    # Create empty fake document folder.
    document_id = "doc_missing_chunks"
    document_folder = uploads_dir / document_id
    document_folder.mkdir(parents=True)

    # Tell bm25_service to use our fake uploads folder.
    monkeypatch.setattr(bm25_service, "UPLOAD_DIR", str(uploads_dir))

    # Since no chunks.json/redacted_chunks.json exists, this should fail clearly.
    with pytest.raises(FileNotFoundError):
        bm25_service.search_document_with_bm25_as_dicts(
            document_id=document_id,
            query="anything",
            top_k=5,
        )