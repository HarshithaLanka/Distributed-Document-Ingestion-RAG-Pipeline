# app/services/sqs_service.py

"""
This file contains all AWS SQS helper functions.

SQS simple meaning:
SQS is a queue. The upload API puts a small job message into the queue.
The worker reads that job message later and processes the document.

Important:
The SQS message should contain document_id.

Example message body:
{
    "job_id": "...",
    "job_type": "process_document",
    "document_id": "doc_123",
    "pipeline_steps": ["extract", "chunk", "index"],
    "created_at": "..."
}

Important Week 9 fix:
receive_document_processing_messages() now returns BOTH formats:

1. AWS-style keys used by worker:
   - Body
   - ReceiptHandle
   - MessageId

2. Clean keys useful for debugging/tests:
   - body
   - receipt_handle
   - message_id

This prevents the worker from reading empty Body = {}.
"""

# Import json because SQS message body must be a string.
# We convert Python dictionary -> JSON string before sending.
import json

# Import uuid to create a unique job_id for every queue message.
import uuid

# Import logging so we can print useful backend logs.
import logging

# Import datetime/timezone to store created_at time in UTC.
from datetime import datetime, timezone

# Import typing helpers for cleaner code.
from typing import Any, Dict, List, Optional

# Import boto3 because boto3 is AWS Python SDK.
# It allows Python to talk to AWS services like S3, DynamoDB, SQS.
import boto3

# Import AWS error classes so we can catch AWS failures cleanly.
from botocore.exceptions import BotoCoreError, ClientError

# Import SQS values from config.py.
# These values come from your .env file.
from app.config import (
    SQS_ENABLED,
    SQS_QUEUE_NAME,
    SQS_QUEUE_URL,
    SQS_REGION,
    SQS_WAIT_TIME_SECONDS,
    SQS_VISIBILITY_TIMEOUT_SECONDS,
    SQS_MAX_MESSAGES,
    is_sqs_configured,
    get_missing_sqs_settings,
)


# Create logger for this file.
# Logs help debug SQS send/receive/delete behavior.
logger = logging.getLogger(__name__)


def get_sqs_client():
    """
    Create boto3 SQS client.

    Simple meaning:
    This client is the Python object used to call AWS SQS.
    """

    # Create SQS client in your selected region.
    # boto3 automatically uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    # from environment variables loaded by your app/config setup.
    return boto3.client("sqs", region_name=SQS_REGION)


def ensure_sqs_ready() -> None:
    """
    Check whether SQS is enabled and properly configured.

    Simple meaning:
    Before calling AWS, confirm .env has required SQS values.
    """

    # If SQS_ENABLED=false, stop.
    if not SQS_ENABLED:
        raise RuntimeError("SQS is disabled. Set SQS_ENABLED=true in .env.")

    # If required SQS settings are missing, stop with clear error.
    if not is_sqs_configured():
        missing_settings = get_missing_sqs_settings()

        raise RuntimeError(
            "SQS is not configured correctly. Missing settings: "
            + ", ".join(missing_settings)
        )


def build_document_processing_message(
    document_id: str,
    pipeline_steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build the message that will go into SQS.

    Simple meaning:
    This creates the instruction for the worker.

    Example:
    {
        "job_id": "...",
        "job_type": "process_document",
        "document_id": "doc_123",
        "pipeline_steps": ["extract", "chunk", "index"],
        "created_at": "..."
    }
    """

    # If no steps are given, use normal RAG processing steps.
    if pipeline_steps is None:
        pipeline_steps = ["extract", "chunk", "index"]

    # Return the message as a Python dictionary.
    return {
        # Unique job ID for this queue message.
        # This is not the same as document_id.
        "job_id": str(uuid.uuid4()),

        # Job type tells worker what kind of work to do.
        "job_type": "process_document",

        # document_id tells worker which document to process.
        "document_id": document_id,

        # Steps worker should run later.
        "pipeline_steps": pipeline_steps,

        # Store created time in UTC for debugging.
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def send_document_processing_message(
    document_id: str,
    pipeline_steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send document processing job to SQS.

    Simple meaning:
    FastAPI upload API calls this function after upload.
    """

    # Validate document_id.
    if not document_id:
        raise ValueError("document_id is required to send SQS message.")

    # Check SQS config before calling AWS.
    ensure_sqs_ready()

    # Build message dictionary.
    message_body = build_document_processing_message(
        document_id=document_id,
        pipeline_steps=pipeline_steps,
    )

    # Convert dictionary to JSON string because SQS MessageBody must be text.
    message_body_json = json.dumps(message_body)

    try:
        # Create SQS client.
        sqs_client = get_sqs_client()

        # Send message to main SQS queue.
        response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_body_json,
        )

        # Log successful send.
        logger.info(
            "SQS message sent. document_id=%s message_id=%s body=%s",
            document_id,
            response.get("MessageId"),
            message_body,
        )

        # Return useful details.
        return {
            "success": True,
            "queue_name": SQS_QUEUE_NAME,
            "queue_url": SQS_QUEUE_URL,
            "message_id": response.get("MessageId"),
            "md5_of_body": response.get("MD5OfMessageBody"),
            "message_body": message_body,
        }

    except (BotoCoreError, ClientError) as error:
        # Log full error.
        logger.exception("Failed to send SQS message for document_id=%s", document_id)

        # Raise clean error.
        raise RuntimeError(f"Failed to send SQS message: {str(error)}") from error


def receive_document_processing_messages(
    max_messages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Receive messages from SQS.

    Simple meaning:
    Worker calls this to get document processing jobs.

    Important:
    Receiving a message does NOT delete it.
    We must delete it only after processing succeeds.

    Week 9 important fix:
    The worker expects AWS-style keys:
    - Body
    - ReceiptHandle

    So this function now returns those keys.
    It also includes lowercase helper keys for debugging.
    """

    # Check SQS config.
    ensure_sqs_ready()

    # If max_messages not given, use config value.
    if max_messages is None:
        max_messages = SQS_MAX_MESSAGES

    try:
        # Create SQS client.
        sqs_client = get_sqs_client()

        # Receive messages from SQS.
        response = sqs_client.receive_message(
            # Main queue URL.
            QueueUrl=SQS_QUEUE_URL,

            # Number of messages to receive.
            MaxNumberOfMessages=max_messages,

            # Long polling wait time.
            # SQS waits up to this many seconds for a message.
            WaitTimeSeconds=SQS_WAIT_TIME_SECONDS,

            # Visibility timeout.
            # After receiving, message is hidden for this many seconds.
            VisibilityTimeout=SQS_VISIBILITY_TIMEOUT_SECONDS,

            # Ask SQS to return message attributes.
            AttributeNames=["All"],

            # Ask SQS to return custom message attributes.
            MessageAttributeNames=["All"],
        )

        # Get raw messages.
        # If queue is empty, "Messages" key may not exist.
        raw_messages = response.get("Messages", [])

        # Store cleaned compatible messages here.
        compatible_messages = []

        # Loop through messages.
        for raw_message in raw_messages:
            # Get raw body string exactly as AWS returned it.
            raw_body = raw_message.get("Body", "{}")

            # Convert JSON text to Python dictionary for debugging/helper use.
            try:
                parsed_body = json.loads(raw_body)
            except json.JSONDecodeError:
                parsed_body = {
                    "raw_body": raw_body,
                    "parse_error": "Message body is not valid JSON.",
                }

            # Build one message dictionary that supports both:
            # 1. Worker AWS-style keys: Body, ReceiptHandle, MessageId
            # 2. Debug-friendly keys: body, receipt_handle, message_id
            compatible_message = {
                # AWS-style keys expected by workers/document_worker.py
                "MessageId": raw_message.get("MessageId"),
                "ReceiptHandle": raw_message.get("ReceiptHandle"),
                "Body": raw_body,
                "Attributes": raw_message.get("Attributes", {}),
                "MessageAttributes": raw_message.get("MessageAttributes", {}),

                # Lowercase helper keys for debugging/tests.
                "message_id": raw_message.get("MessageId"),
                "receipt_handle": raw_message.get("ReceiptHandle"),
                "body": parsed_body,
                "attributes": raw_message.get("Attributes", {}),
                "message_attributes": raw_message.get("MessageAttributes", {}),
            }

            # Add to list.
            compatible_messages.append(compatible_message)

        # Log count.
        logger.info("Received %s SQS message(s).", len(compatible_messages))

        # Return compatible messages.
        return compatible_messages

    except (BotoCoreError, ClientError) as error:
        # Log receive error.
        logger.exception("Failed to receive SQS messages.")

        # Raise clean error.
        raise RuntimeError(f"Failed to receive SQS messages: {str(error)}") from error


def delete_message(receipt_handle: str) -> Dict[str, Any]:
    """
    Delete message from SQS after successful processing.

    Simple meaning:
    This is ACK. It tells SQS: job is completed, do not retry.
    """

    # Receipt handle is required.
    # SQS deletes using receipt_handle, not message_id.
    if not receipt_handle:
        raise ValueError("receipt_handle is required to delete SQS message.")

    # Check SQS config.
    ensure_sqs_ready()

    try:
        # Create SQS client.
        sqs_client = get_sqs_client()

        # Delete message.
        sqs_client.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle,
        )

        # Log success.
        logger.info("SQS message deleted successfully.")

        # Return clean result.
        return {
            "success": True,
            "message": "SQS message deleted successfully.",
        }

    except (BotoCoreError, ClientError) as error:
        # Log delete error.
        logger.exception("Failed to delete SQS message.")

        # Raise clean error.
        raise RuntimeError(f"Failed to delete SQS message: {str(error)}") from error


def get_queue_attributes() -> Dict[str, Any]:
    """
    Get queue attributes from SQS.

    Simple meaning:
    This checks whether our app can access the queue.
    Used in smoke test.
    """

    # Check SQS config.
    ensure_sqs_ready()

    try:
        # Create SQS client.
        sqs_client = get_sqs_client()

        # Ask SQS for all queue attributes.
        response = sqs_client.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["All"],
        )

        # Return attributes dictionary.
        return response.get("Attributes", {})

    except (BotoCoreError, ClientError) as error:
        # Log error.
        logger.exception("Failed to get SQS queue attributes.")

        # Raise clean error.
        raise RuntimeError(f"Failed to get SQS queue attributes: {str(error)}") from error