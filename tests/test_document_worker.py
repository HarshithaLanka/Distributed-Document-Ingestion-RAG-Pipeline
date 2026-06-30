# tests/test_document_worker.py

"""
Tests for Week 9 worker logic.

Important:
These tests do NOT call real AWS.
They use monkeypatch to replace SQS/S3/DynamoDB/Pinecone behavior.
"""

# Import worker module.
import workers.document_worker as worker


def test_worker_skips_already_completed_document(monkeypatch):
    """
    If document is already completed, worker should skip duplicate processing.

    Why?
    SQS can sometimes deliver the same message again.
    """

    # Track which fake functions were called.
    calls = {
        "state_updates": [],
        "extract_called": False,
        "chunk_called": False,
        "index_called": False,
    }

    # Fake document already completed.
    def fake_get_document_by_id(document_id):
        return {
            "document_id": document_id,
            "status": "completed",
        }

    # Fake state update.
    def fake_update_document_state(**kwargs):
        calls["state_updates"].append(kwargs)
        return kwargs

    # Fake extraction should not be called.
    def fake_extract_text_from_pdf(*args, **kwargs):
        calls["extract_called"] = True

    # Fake chunking should not be called.
    def fake_create_chunks_from_extracted_text(*args, **kwargs):
        calls["chunk_called"] = True

    # Fake indexing should not be called.
    def fake_index_document_chunks(*args, **kwargs):
        calls["index_called"] = True

    # Replace real functions with fake functions.
    monkeypatch.setattr(worker, "get_document_by_id", fake_get_document_by_id)
    monkeypatch.setattr(worker, "update_document_state", fake_update_document_state)
    monkeypatch.setattr(worker, "extract_text_from_pdf", fake_extract_text_from_pdf)
    monkeypatch.setattr(worker, "create_chunks_from_extracted_text", fake_create_chunks_from_extracted_text)
    monkeypatch.setattr(worker, "index_document_chunks", fake_index_document_chunks)

    # Run processing.
    worker.process_document("doc_123")

    # Assert processing steps were skipped.
    assert calls["extract_called"] is False
    assert calls["chunk_called"] is False
    assert calls["index_called"] is False

    # Assert skipped status was written.
    assert calls["state_updates"][0]["status"] == "skipped"


def test_worker_processes_queued_document_successfully(monkeypatch):
    """
    If document is queued, worker should run:
    ensure PDF -> extract -> ensure extracted text -> chunk -> ensure chunks -> load chunks -> index -> completed.
    """

    # Track call order.
    calls = []

    # Fake metadata changes by returning a usable document every time.
    def fake_get_document_by_id(document_id):
        return {
            "document_id": document_id,
            "status": "queued",
            "file_path": "fake/path/sample.pdf",
            "extracted_text_path": "fake/path/extracted_text.json",
            "chunks_path": "fake/path/chunks.json",
        }

    # Fake state update.
    def fake_update_document_state(**kwargs):
        calls.append(("state", kwargs["status"]))
        return kwargs

    # Fake PDF resolver.
    def fake_ensure_pdf_available_locally(document):
        calls.append(("ensure_pdf", document["document_id"]))
        return "fake/path/sample.pdf"

    # Fake extraction.
    def fake_extract_text_from_pdf(pdf_path, document_id):
        calls.append(("extract", document_id, pdf_path))
        return {
            "document_id": document_id,
            "page_count": 2,
            "extracted_text_path": "fake/path/extracted_text.json",
        }

    # Fake extracted text resolver.
    def fake_ensure_extracted_text_available_locally(document):
        calls.append(("ensure_extracted", document["document_id"]))
        return "fake/path/extracted_text.json"

    # Fake chunking.
    def fake_create_chunks_from_extracted_text(extracted_text_path, document_id, chunk_size, overlap):
        calls.append(("chunk", document_id, extracted_text_path, chunk_size, overlap))
        return {
            "document_id": document_id,
            "chunk_count": 3,
            "chunks_path": "fake/path/chunks.json",
        }

    # Fake chunks resolver.
    def fake_ensure_chunks_available_locally(document):
        calls.append(("ensure_chunks", document["document_id"]))
        return "fake/path/chunks.json"

    # Fake load chunks.
    def fake_load_chunks(chunks_path):
        calls.append(("load_chunks", chunks_path))
        return {
            "document_id": "doc_123",
            "chunk_count": 3,
            "chunks": [
                {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_123",
                    "page_number": 1,
                    "text": "sample text",
                    "word_count": 2,
                }
            ],
        }

    # Fake indexing.
    def fake_index_document_chunks(chunks_data):
        calls.append(("index", chunks_data["document_id"]))
        return {
            "vector_count": 3,
        }

    # Fake S3 artifact upload helpers.
    def fake_upload_extracted_text_artifact_if_enabled(document_id, extracted_text_path):
        calls.append(("upload_extracted_s3", document_id))
        return {}

    def fake_upload_chunks_artifact_if_enabled(document_id, chunks_path):
        calls.append(("upload_chunks_s3", document_id))
        return {}

    # Monkeypatch real functions.
    monkeypatch.setattr(worker, "get_document_by_id", fake_get_document_by_id)
    monkeypatch.setattr(worker, "update_document_state", fake_update_document_state)
    monkeypatch.setattr(worker, "ensure_pdf_available_locally", fake_ensure_pdf_available_locally)
    monkeypatch.setattr(worker, "extract_text_from_pdf", fake_extract_text_from_pdf)
    monkeypatch.setattr(worker, "ensure_extracted_text_available_locally", fake_ensure_extracted_text_available_locally)
    monkeypatch.setattr(worker, "create_chunks_from_extracted_text", fake_create_chunks_from_extracted_text)
    monkeypatch.setattr(worker, "ensure_chunks_available_locally", fake_ensure_chunks_available_locally)
    monkeypatch.setattr(worker, "load_chunks", fake_load_chunks)
    monkeypatch.setattr(worker, "index_document_chunks", fake_index_document_chunks)
    monkeypatch.setattr(worker, "upload_extracted_text_artifact_if_enabled", fake_upload_extracted_text_artifact_if_enabled)
    monkeypatch.setattr(worker, "upload_chunks_artifact_if_enabled", fake_upload_chunks_artifact_if_enabled)

    # Run processing.
    worker.process_document("doc_123")

    # Get only status updates.
    statuses = [item[1] for item in calls if item[0] == "state"]

    # Check important statuses.
    assert "processing" in statuses
    assert "extracting" in statuses
    assert "extracted" in statuses
    assert "chunking" in statuses
    assert "chunked" in statuses
    assert "indexing" in statuses
    assert "indexed" in statuses
    assert "completed" in statuses

    # Check processing functions were called.
    assert ("ensure_pdf", "doc_123") in calls
    assert ("extract", "doc_123", "fake/path/sample.pdf") in calls
    assert ("ensure_extracted", "doc_123") in calls
    assert ("chunk", "doc_123", "fake/path/extracted_text.json", 150, 30) in calls
    assert ("ensure_chunks", "doc_123") in calls
    assert ("load_chunks", "fake/path/chunks.json") in calls
    assert ("index", "doc_123") in calls


def test_process_sqs_message_returns_true_on_success(monkeypatch):
    """
    If document processing succeeds, process_sqs_message should return True.

    True means:
    delete SQS message.
    """

    # Fake process_document success.
    def fake_process_document(document_id):
        return None

    # Replace real process_document.
    monkeypatch.setattr(worker, "process_document", fake_process_document)

    # Fake SQS message.
    message = {
        "Body": '{"document_id": "doc_123"}',
        "ReceiptHandle": "fake_receipt",
    }

    # Run.
    result = worker.process_sqs_message(message)

    # Assert message should be deleted.
    assert result is True


def test_process_sqs_message_returns_false_on_failure(monkeypatch):
    """
    If document processing fails, process_sqs_message should return False.

    False means:
    do not delete SQS message.
    Let SQS retry or move to DLQ.
    """

    # Track failed state update.
    calls = []

    # Fake process_document failure.
    def fake_process_document(document_id):
        raise RuntimeError("fake indexing error")

    # Fake state update.
    def fake_update_document_state(**kwargs):
        calls.append(kwargs)
        return kwargs

    # Replace real functions.
    monkeypatch.setattr(worker, "process_document", fake_process_document)
    monkeypatch.setattr(worker, "update_document_state", fake_update_document_state)

    # Fake SQS message.
    message = {
        "Body": '{"document_id": "doc_123"}',
        "ReceiptHandle": "fake_receipt",
    }

    # Run.
    result = worker.process_sqs_message(message)

    # Assert message should NOT be deleted.
    assert result is False

    # Assert failed status was written.
    assert calls[0]["status"] == "failed"

    # Assert retry count increment was requested.
    assert calls[0]["increment_retry"] is True


def test_run_worker_once_deletes_message_after_success(monkeypatch):
    """
    run_worker_once should delete SQS message only after success.
    """

    # Track deleted messages.
    deleted = []

    # Fake receiving one message.
    def fake_receive_document_processing_messages():
        return [
            {
                "Body": '{"document_id": "doc_123"}',
                "ReceiptHandle": "fake_receipt",
            }
        ]

    # Fake process success.
    def fake_process_sqs_message(message):
        return True

    # Fake delete.
    def fake_delete_message(receipt_handle):
        deleted.append(receipt_handle)

    # Monkeypatch.
    monkeypatch.setattr(worker, "receive_document_processing_messages", fake_receive_document_processing_messages)
    monkeypatch.setattr(worker, "process_sqs_message", fake_process_sqs_message)
    monkeypatch.setattr(worker, "delete_message", fake_delete_message)

    # Run.
    count = worker.run_worker_once()

    # Assert one message processed.
    assert count == 1

    # Assert message deleted.
    assert deleted == ["fake_receipt"]


def test_run_worker_once_does_not_delete_message_after_failure(monkeypatch):
    """
    run_worker_once should NOT delete SQS message after failure.
    """

    # Track deleted messages.
    deleted = []

    # Fake receiving one message.
    def fake_receive_document_processing_messages():
        return [
            {
                "Body": '{"document_id": "doc_123"}',
                "ReceiptHandle": "fake_receipt",
            }
        ]

    # Fake process failure.
    def fake_process_sqs_message(message):
        return False

    # Fake delete.
    def fake_delete_message(receipt_handle):
        deleted.append(receipt_handle)

    # Monkeypatch.
    monkeypatch.setattr(worker, "receive_document_processing_messages", fake_receive_document_processing_messages)
    monkeypatch.setattr(worker, "process_sqs_message", fake_process_sqs_message)
    monkeypatch.setattr(worker, "delete_message", fake_delete_message)

    # Run.
    count = worker.run_worker_once()

    # Assert one message was attempted.
    assert count == 1

    # Assert message was not deleted.
    assert deleted == []