# app/services/document_event_service.py

"""
This service stores document processing events in DynamoDB.

Simple meaning:
- Metadata table tells the current state.
- Event table tells the full history.

Example:
Metadata:
    status = completed

Events:
    DOCUMENT_UPLOADED
    DOCUMENT_QUEUED
    EXTRACTION_STARTED
    EXTRACTION_COMPLETED
    CHUNKING_STARTED
    CHUNKING_COMPLETED
    INDEXING_STARTED
    INDEXING_COMPLETED
    DOCUMENT_COMPLETED
"""

# Import datetime to create timestamps.
from datetime import datetime, timezone

# Import uuid to create unique event IDs.
from uuid import uuid4

# Import boto3 to talk to DynamoDB.
import boto3

# Import boto3 ClientError for clean error handling.
from botocore.exceptions import ClientError

# Import project config values.
from app import config

# Import logger if your project already has it.
from app.utils.logger import logger


def get_current_utc_time() -> str:
    """
    Return current UTC time in ISO format.

    Example:
    2026-06-29T10:30:45.123456+00:00
    """

    return datetime.now(timezone.utc).isoformat()


def get_events_table():
    """
    Return the DynamoDB Events table object.

    This function creates a boto3 DynamoDB resource and points to your events table.
    """

    # Create a DynamoDB resource using credentials from .env/config.py.
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=config.AWS_REGION,
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
    )

    # Return the table object using table name from .env.
    return dynamodb.Table(config.DYNAMODB_EVENTS_TABLE_NAME)


def build_event_id() -> str:
    """
    Build a sortable unique event ID.

    Why timestamp first?
    Because events will appear in time order when sorted by event_id.

    Example:
    2026-06-29T10:30:45.123456+00:00#abc123
    """

    return f"{get_current_utc_time()}#{uuid4().hex}"


def log_document_event(
    document_id: str,
    event_type: str,
    message: str,
    status: str | None = None,
    current_step: str | None = None,
    progress_percentage: int | None = None,
    details: dict | None = None,
) -> dict:
    """
    Save one event record into DynamoDB.

    Parameters:
    - document_id: Which document this event belongs to.
    - event_type: Machine-readable event name.
    - message: Human-readable message.
    - status: Optional document status at this moment.
    - current_step: Optional processing step.
    - progress_percentage: Optional progress number.
    - details: Optional extra information.

    Returns:
    - event item that was saved.
    """

    # If event tracking is not configured, do not crash the app.
    if not config.is_dynamodb_events_configured():
        logger.warning(
            "DynamoDB events not configured. Skipping event log for document_id=%s event_type=%s",
            document_id,
            event_type,
        )

        return {
            "document_id": document_id,
            "event_type": event_type,
            "message": message,
            "skipped_persistence": True,
        }

    # Build event item.
    event_item = {
        "document_id": document_id,
        "event_id": build_event_id(),
        "event_type": event_type,
        "message": message,
        "created_at": get_current_utc_time(),
    }

    # Add status only if provided.
    if status is not None:
        event_item["status"] = status

    # Add current_step only if provided.
    if current_step is not None:
        event_item["current_step"] = current_step

    # Add progress only if provided.
    if progress_percentage is not None:
        event_item["progress_percentage"] = progress_percentage

    # Add details only if provided.
    if details is not None:
        event_item["details"] = details

    try:
        # Get DynamoDB events table.
        table = get_events_table()

        # Save event item.
        table.put_item(Item=event_item)

        # Log success.
        logger.info(
            "Document event logged. document_id=%s event_type=%s",
            document_id,
            event_type,
        )

        return event_item

    except ClientError as error:
        # Log AWS error but do not crash main processing.
        logger.error(
            "Failed to log document event. document_id=%s event_type=%s error=%s",
            document_id,
            event_type,
            str(error),
        )

        return {
            "document_id": document_id,
            "event_type": event_type,
            "message": message,
            "event_log_failed": True,
            "error": str(error),
        }


def get_document_events(document_id: str) -> list[dict]:
    """
    Get all events for one document from DynamoDB.

    This powers:
    GET /documents/{document_id}/events
    """

    # If config is missing, return empty list instead of crashing.
    if not config.is_dynamodb_events_configured():
        logger.warning("DynamoDB events not configured. Cannot load events.")
        return []

    try:
        # Get DynamoDB events table.
        table = get_events_table()

        # Query all events with this document_id.
        response = table.query(
            KeyConditionExpression="document_id = :document_id",
            ExpressionAttributeValues={
                ":document_id": document_id,
            },
            ScanIndexForward=True,
        )

        # Return events list.
        return response.get("Items", [])

    except ClientError as error:
        # Log the error.
        logger.error(
            "Failed to get document events. document_id=%s error=%s",
            document_id,
            str(error),
        )

        # Return empty list for clean API behavior.
        return []