# tests/test_document_status_events.py

"""
Tests for Week 9 document status and event services.

No real AWS calls are made here.
"""

from app.services import document_state_service
from app.services import document_event_service


def test_get_document_status_returns_clean_response(monkeypatch):
    """
    Test that get_document_status returns clean status data.
    """

    # Fake document metadata.
    def fake_get_document_by_id(document_id):
        return {
            "document_id": document_id,
            "filename": "sample.pdf",
            "status": "indexing",
            "current_step": "Indexing chunks into Pinecone",
            "progress_percentage": 85,
            "retry_count": 1,
            "error_message": None,
            "uploaded_at": "time1",
            "queued_at": "time2",
            "started_at": "time3",
            "updated_at": "time4",
        }

    # Replace real metadata call.
    monkeypatch.setattr(document_state_service, "get_document_by_id", fake_get_document_by_id)

    # Run.
    result = document_state_service.get_document_status("doc_123")

    # Assert.
    assert result["document_id"] == "doc_123"
    assert result["filename"] == "sample.pdf"
    assert result["status"] == "indexing"
    assert result["progress_percentage"] == 85
    assert result["retry_count"] == 1


def test_update_document_state_updates_metadata_and_logs_event(monkeypatch):
    """
    Test that update_document_state calls metadata update and event log.
    """

    # Track calls.
    calls = {
        "metadata_updates": [],
        "events": [],
    }

    # Fake current document.
    def fake_get_document_by_id(document_id):
        return {
            "document_id": document_id,
            "status": "queued",
            "retry_count": 0,
        }

    # Fake metadata update.
    def fake_update_document_metadata(document_id, updates):
        calls["metadata_updates"].append((document_id, updates))
        return {
            "document_id": document_id,
            **updates,
        }

    # Fake event log.
    def fake_log_document_event(**kwargs):
        calls["events"].append(kwargs)
        return kwargs

    # Monkeypatch.
    monkeypatch.setattr(document_state_service, "get_document_by_id", fake_get_document_by_id)
    monkeypatch.setattr(document_state_service, "update_document_metadata", fake_update_document_metadata)
    monkeypatch.setattr(document_state_service, "log_document_event", fake_log_document_event)

    # Run.
    result = document_state_service.update_document_state(
        document_id="doc_123",
        status="processing",
        current_step="Worker picked the document",
        event_type="PROCESSING_STARTED",
        event_message="Worker started processing.",
        progress_percentage=20,
    )

    # Assert metadata update happened.
    assert calls["metadata_updates"][0][0] == "doc_123"
    assert calls["metadata_updates"][0][1]["status"] == "processing"
    assert calls["metadata_updates"][0][1]["current_step"] == "Worker picked the document"

    # Assert event log happened.
    assert calls["events"][0]["event_type"] == "PROCESSING_STARTED"

    # Assert return data.
    assert result["status"] == "processing"


def test_update_document_state_increments_retry(monkeypatch):
    """
    Test retry_count increases when increment_retry=True.
    """

    # Fake current failed document.
    def fake_get_document_by_id(document_id):
        return {
            "document_id": document_id,
            "status": "failed",
            "retry_count": 2,
        }

    # Fake metadata update.
    def fake_update_document_metadata(document_id, updates):
        return {
            "document_id": document_id,
            **updates,
        }

    # Fake event log.
    def fake_log_document_event(**kwargs):
        return kwargs

    # Monkeypatch.
    monkeypatch.setattr(document_state_service, "get_document_by_id", fake_get_document_by_id)
    monkeypatch.setattr(document_state_service, "update_document_metadata", fake_update_document_metadata)
    monkeypatch.setattr(document_state_service, "log_document_event", fake_log_document_event)

    # Run.
    result = document_state_service.update_document_state(
        document_id="doc_123",
        status="failed",
        current_step="Document processing failed",
        event_type="DOCUMENT_FAILED",
        event_message="Failed.",
        error_message="fake error",
        increment_retry=True,
    )

    # Assert retry increased from 2 to 3.
    assert result["retry_count"] == 3
    assert result["error_message"] == "fake error"


def test_log_document_event_skips_when_not_configured(monkeypatch):
    """
    If DynamoDB events are not configured, event logging should not crash.
    """

    # Fake config function.
    def fake_is_dynamodb_events_configured():
        return False

    # Monkeypatch config check.
    monkeypatch.setattr(
        document_event_service.config,
        "is_dynamodb_events_configured",
        fake_is_dynamodb_events_configured,
    )

    # Run.
    result = document_event_service.log_document_event(
        document_id="doc_123",
        event_type="DOCUMENT_UPLOADED",
        message="Uploaded.",
    )

    # Assert it skipped persistence safely.
    assert result["skipped_persistence"] is True