# app/services/document_state_service.py

"""
This file manages the CURRENT STATE of a document.

Simple meaning:
- document_state_service.py tells us where the document is right now.
- document_event_service.py tells us the full history/timeline.

Example:
Current state:
    status = "indexing"
    current_step = "Indexing chunks into Pinecone"
    progress_percentage = 85

Event history:
    DOCUMENT_UPLOADED
    DOCUMENT_QUEUED
    PROCESSING_STARTED
    EXTRACTION_STARTED
    EXTRACTION_COMPLETED
    CHUNKING_STARTED
    CHUNKING_COMPLETED
    INDEXING_STARTED
"""

# Import datetime/timezone to create UTC timestamps.
from datetime import datetime, timezone

# Import Optional for return type hints.
from typing import Optional

# Import status progress helper.
from app.constants.document_status import get_progress_for_status

# Import metadata functions.
# Your metadata_service already saves to DynamoDB primary + local JSON backup/cache.
from app.services.metadata_service import get_document_by_id
from app.services.metadata_service import update_document_metadata

# Import event logging helper.
from app.services.document_event_service import log_document_event

# Import logger.
from app.utils.logger import logger


def get_current_utc_time() -> str:
    """
    Return the current UTC time as an ISO string.

    Why UTC?
    Backend systems usually store time in UTC to avoid timezone confusion.
    """

    return datetime.now(timezone.utc).isoformat()


def get_document_status(document_id: str) -> Optional[dict]:
    """
    Get the current processing status of one document.

    This function is used by:
    GET /documents/{document_id}/status

    It reads metadata from your existing metadata_service.
    That metadata_service decides whether to read from DynamoDB or local JSON fallback.
    """

    # Get document metadata by document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return None.
    if document is None:
        return None

    # Return only the important status fields.
    # This keeps /status response clean.
    return {
        "document_id": document.get("document_id"),
        "filename": document.get("filename"),
        "status": document.get("status"),
        "current_step": document.get("current_step"),
        "progress_percentage": int(document.get("progress_percentage", 0) or 0),
        "retry_count": int(document.get("retry_count", 0) or 0),
        "error_message": document.get("error_message"),
        "uploaded_at": document.get("uploaded_at"),
        "queued_at": document.get("queued_at"),
        "started_at": document.get("started_at"),
        "completed_at": document.get("completed_at"),
        "failed_at": document.get("failed_at"),
        "updated_at": document.get("updated_at"),
    }


def update_document_state(
    document_id: str,
    status: str,
    current_step: str,
    event_type: Optional[str] = None,
    event_message: Optional[str] = None,
    progress_percentage: Optional[int] = None,
    error_message: Optional[str] = None,
    increment_retry: bool = False,
    extra_updates: Optional[dict] = None,
) -> dict:
    """
    Update current document state.

    This function updates fields like:
    - status
    - current_step
    - progress_percentage
    - retry_count
    - error_message
    - started_at
    - completed_at
    - failed_at
    - updated_at

    It can also log an event into the event table if event_type is provided.
    """

    # Load current document metadata.
    current_document = get_document_by_id(document_id)

    # If document is missing, still create a minimal dictionary.
    # This prevents the function from crashing immediately.
    if current_document is None:
        current_document = {
            "document_id": document_id,
            "retry_count": 0,
        }

    # If caller did not pass progress_percentage,
    # get default progress using status.
    if progress_percentage is None:
        progress_percentage = get_progress_for_status(status)

    # Get current timestamp once.
    now = get_current_utc_time()

    # Get current retry count safely.
    current_retry_count = int(current_document.get("retry_count", 0) or 0)

    # Increase retry count only when caller asks.
    if increment_retry:
        new_retry_count = current_retry_count + 1
    else:
        new_retry_count = current_retry_count

    # Build update dictionary.
    updates = {
        "status": status,
        "current_step": current_step,
        "progress_percentage": progress_percentage,
        "retry_count": new_retry_count,
        "updated_at": now,
    }

    # If processing started for first time, save started_at.
    if status == "processing" and not current_document.get("started_at"):
        updates["started_at"] = now

    # If document completed, save completed_at.
    if status == "completed":
        updates["completed_at"] = now
        updates["failed_at"] = None
        updates["error_message"] = None

    # If document failed, save failed_at and error message.
    if status == "failed":
        updates["failed_at"] = now
        updates["error_message"] = error_message or "Unknown processing error"

    # If queue failed, save error message too.
    if status == "queue_failed":
        updates["failed_at"] = now
        updates["error_message"] = error_message or "Failed to send message to SQS"

    # For normal non-failed states, clear error only if caller passed no error.
    if status not in {"failed", "queue_failed"} and error_message is not None:
        updates["error_message"] = error_message

    # Add any extra metadata updates.
    # Example:
    # sqs_message_id, queued_at, page_count, chunks_path, vector_count
    if extra_updates:
        updates.update(extra_updates)

    # Save updates using existing metadata service.
    updated_document = update_document_metadata(document_id, updates)

    # If update_document_metadata returns None, build fallback response.
    if updated_document is None:
        updated_document = {
            **current_document,
            **updates,
        }

    # Log event if event_type is provided.
    if event_type:
        log_document_event(
            document_id=document_id,
            event_type=event_type,
            message=event_message or current_step,
            status=status,
            current_step=current_step,
            progress_percentage=progress_percentage,
            details={
                "retry_count": new_retry_count,
                "error_message": updates.get("error_message"),
            },
        )

    # Write backend log.
    logger.info(
        "Document state updated. document_id=%s status=%s step=%s progress=%s",
        document_id,
        status,
        current_step,
        progress_percentage,
    )

    # Return updated document metadata.
    return updated_document


def mark_document_failed(
    document_id: str,
    error_message: str,
    event_type: Optional[str] = None,
    event_message: Optional[str] = None,
) -> dict:
    """
    Helper function to mark a document as failed.

    This is useful for worker failures.
    """

    return update_document_state(
        document_id=document_id,
        status="failed",
        current_step="Document processing failed",
        event_type=event_type,
        event_message=event_message or "Document processing failed.",
        progress_percentage=100,
        error_message=error_message,
        increment_retry=True,
    )


def mark_document_completed(
    document_id: str,
    event_type: Optional[str] = None,
    event_message: Optional[str] = None,
) -> dict:
    """
    Helper function to mark a document as completed.

    This is useful after indexing finishes.
    """

    return update_document_state(
        document_id=document_id,
        status="completed",
        current_step="Document processing completed",
        event_type=event_type,
        event_message=event_message or "Document processing completed successfully.",
        progress_percentage=100,
    )