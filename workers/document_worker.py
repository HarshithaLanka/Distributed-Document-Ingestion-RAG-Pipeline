# workers/document_worker.py

"""
Week 12 worker.

What this worker does:
1. Keeps running continuously.
2. Reads document processing messages from SQS.
3. Processes queued documents.
4. Updates document state in DynamoDB/local metadata.
5. Logs events into DynamoDB event table.
6. Deletes SQS message only after success.
7. Deletes invalid old/test SQS messages that do not contain document_id.
8. Stops safely when you press CTRL+C.
9. Uses Docling/PyMuPDF parser abstraction from Week 10.
10. Creates redacted_chunks.json before Pinecone indexing.
11. Sends redacted chunks to Pinecone, not raw chunks.
12. Week 12: Extracts entities from redacted chunks and stores graph data in Neo4j.

Run:
    python workers/document_worker.py

Important meanings:

Indexing to Pinecone means:
- generate embeddings for chunk text
- send vector values plus metadata to Pinecone
- Pinecone stores them for semantic search

Graph storage to Neo4j means:
- extract entities from redacted chunks
- create Document, Chunk, and Entity nodes
- create relationships like HAS_CHUNK, MENTIONS, and APPEARS_IN
"""

# Import json to parse SQS message body.
import json

# Import sys so we can add project root to Python path.
import sys

# Import time so worker can sleep briefly after errors.
import time

# Import Path to safely work with file paths.
from pathlib import Path


# ---------------------------------------------------------
# Add project root to Python import path
# ---------------------------------------------------------

# Current file is workers/document_worker.py.
# parent = workers/
# parent.parent = project root folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python import path.
# This allows running worker directly using:
# python workers/document_worker.py
sys.path.append(str(PROJECT_ROOT))


# ---------------------------------------------------------
# Imports from app
# ---------------------------------------------------------

# Import config value for S3 artifact upload.
from app.config import S3_UPLOAD_ENABLED

# Import status constants.
from app.constants.document_status import (
    DocumentStatus,
    ProcessingStep,
    DocumentEventType,
    TERMINAL_SUCCESS_STATUSES,
)

# Import SQS service functions from your existing Week 8 code.
from app.services.sqs_service import (
    ensure_sqs_ready,
    receive_document_processing_messages,
    delete_message,
)

# Import metadata service.
from app.services.metadata_service import get_document_by_id

# Import state updater.
from app.services.document_state_service import update_document_state

# Import artifact resolver functions.
# These functions recover local files from S3 if local cache is missing.
from app.services.artifact_resolver_service import (
    ensure_pdf_available_locally,
    ensure_extracted_text_available_locally,
    ensure_chunks_available_locally,
)

# Import parser abstraction service.
# This uses Docling if enabled and falls back to PyMuPDF if Docling fails.
from app.services.parser_service import parse_document

# Import chunking service.
from app.services.chunking_service import create_chunks_from_extracted_text

# Import PII redaction services.
# create_redacted_chunks_file creates redacted_chunks.json from chunks.json.
# load_redacted_chunks loads that safe redacted file before Pinecone indexing.
from app.services.pii_redaction_service import create_redacted_chunks_file
from app.services.pii_redaction_service import load_redacted_chunks

# Import Week 12 graph pipeline service.
# This extracts entities from redacted chunks and writes graph data to Neo4j.
from app.services.graph_pipeline_service import (
    build_graph_for_document_from_redacted_chunks,
)

# Import Pinecone indexing service.
from app.services.pinecone_service import index_document_chunks

# Import S3 artifact upload services.
from app.services.s3_service import upload_extracted_text_to_s3
from app.services.s3_service import upload_chunks_to_s3
from app.services.s3_service import upload_redacted_chunks_to_s3
from app.services.s3_service import S3ServiceError

# Import logger.
from app.utils.logger import logger


# ---------------------------------------------------------
# SQS message parsing helpers
# ---------------------------------------------------------

def parse_sqs_message(message: dict) -> dict:
    """
    Convert raw SQS message body into a Python dictionary.

    SQS message usually looks like this:

    {
        "Body": "{...json string...}",
        "ReceiptHandle": "..."
    }

    The Body value is a JSON string, so we convert it using json.loads().
    """

    # Get message body string from SQS message.
    body = message.get("Body", "{}")

    # If body is already a dictionary, return it directly.
    # This makes tests easier and safer.
    if isinstance(body, dict):
        return body

    # Convert JSON string into Python dictionary.
    return json.loads(body)


def get_document_id_from_message(message: dict) -> str:
    """
    Extract document_id from SQS message.

    This function is defensive because the queue may contain:
    1. Real document messages:
       {"document_id": "doc_123"}

    2. Old smoke test messages:
       {"test": "hello"}

    3. Slightly different key names:
       {"documentId": "doc_123"}

    4. Nested payload:
       {"payload": {"document_id": "doc_123"}}

    5. Nested detail:
       {"detail": {"document_id": "doc_123"}}

    6. SQS MessageAttributes:
       MessageAttributes.document_id.StringValue

    If no document_id is found, we raise ValueError.
    """

    # Parse SQS message body.
    body = parse_sqs_message(message)

    # Case 1: expected format.
    document_id = body.get("document_id")

    # Case 2: alternate camelCase format.
    if not document_id:
        document_id = body.get("documentId")

    # Case 3: nested payload format.
    if not document_id and isinstance(body.get("payload"), dict):
        document_id = body["payload"].get("document_id")

    # Case 4: nested detail format.
    if not document_id and isinstance(body.get("detail"), dict):
        document_id = body["detail"].get("document_id")

    # Case 5: SQS message attributes.
    if not document_id:
        message_attributes = message.get("MessageAttributes", {})

        # Read document_id attribute.
        document_id_attribute = message_attributes.get("document_id")

        # If present, get StringValue.
        if document_id_attribute:
            document_id = document_id_attribute.get("StringValue")

    # If document_id is still missing, raise error.
    if not document_id:
        raise ValueError(
            f"SQS message does not contain document_id. Body received: {body}"
        )

    # Return document_id.
    return document_id


# ---------------------------------------------------------
# Idempotency helper
# ---------------------------------------------------------

def should_skip_document(document: dict | None) -> bool:
    """
    Decide whether worker should skip processing.

    Idempotency simple meaning:
    If the same SQS message comes again after document is already completed,
    we should not process it again.

    Example:
    If status is completed/indexed, skip extraction/chunking/redaction/indexing.
    """

    # If document metadata does not exist, do not skip.
    if not document:
        return False

    # Get current status.
    status = document.get("status")

    # Skip if status is already indexed/completed.
    return status in TERMINAL_SUCCESS_STATUSES


def get_document_filename(document: dict | None) -> str:
    """
    Safely get filename from document metadata.

    Why:
    Different weeks/files may store filename using slightly different keys.
    This helper prevents worker failure because of one missing filename key.
    """

    # If document is missing, return empty string.
    if not document:
        return ""

    # Try common filename keys.
    return (
        document.get("filename")
        or document.get("original_filename")
        or document.get("file_name")
        or document.get("s3_filename")
        or ""
    )


# ---------------------------------------------------------
# S3 artifact upload helpers
# ---------------------------------------------------------

def upload_extracted_text_artifact_if_enabled(
    document_id: str,
    extracted_text_path: str,
) -> dict:
    """
    Upload extracted_text.json to S3 if S3 is enabled.

    If S3 upload fails, we do not stop the worker.
    The local file still exists, so processing can continue.
    """

    # Default values when S3 is disabled.
    result = {
        "extracted_text_s3_bucket": None,
        "extracted_text_s3_key": None,
        "extracted_text_s3_uri": None,
        "extracted_text_s3_upload_status": "disabled",
        "extracted_text_s3_error_message": None,
    }

    # If S3 is disabled, return defaults.
    if not S3_UPLOAD_ENABLED:
        return result

    try:
        # Upload extracted_text.json to S3.
        s3_result = upload_extracted_text_to_s3(
            local_file_path=extracted_text_path,
            document_id=document_id,
        )

        # Update result on success.
        result["extracted_text_s3_bucket"] = s3_result["bucket"]
        result["extracted_text_s3_key"] = s3_result["s3_key"]
        result["extracted_text_s3_uri"] = s3_result["s3_uri"]
        result["extracted_text_s3_upload_status"] = "success"

    except S3ServiceError as error:
        # Store error but do not crash worker.
        result["extracted_text_s3_upload_status"] = "failed"
        result["extracted_text_s3_error_message"] = str(error)

    # Return upload result fields.
    return result


def upload_chunks_artifact_if_enabled(
    document_id: str,
    chunks_path: str,
) -> dict:
    """
    Upload chunks.json to S3 if S3 is enabled.

    If S3 upload fails, we do not stop the worker.
    Redaction can still continue using local chunks.json.
    """

    # Default values when S3 is disabled.
    result = {
        "chunks_s3_bucket": None,
        "chunks_s3_key": None,
        "chunks_s3_uri": None,
        "chunks_s3_upload_status": "disabled",
        "chunks_s3_error_message": None,
    }

    # If S3 is disabled, return defaults.
    if not S3_UPLOAD_ENABLED:
        return result

    try:
        # Upload chunks.json to S3.
        s3_result = upload_chunks_to_s3(
            local_file_path=chunks_path,
            document_id=document_id,
        )

        # Update result on success.
        result["chunks_s3_bucket"] = s3_result["bucket"]
        result["chunks_s3_key"] = s3_result["s3_key"]
        result["chunks_s3_uri"] = s3_result["s3_uri"]
        result["chunks_s3_upload_status"] = "success"

    except S3ServiceError as error:
        # Store error but do not crash worker.
        result["chunks_s3_upload_status"] = "failed"
        result["chunks_s3_error_message"] = str(error)

    # Return upload result fields.
    return result


def upload_redacted_chunks_artifact_if_enabled(
    document_id: str,
    redacted_chunks_path: str,
) -> dict:
    """
    Upload redacted_chunks.json to S3 if S3 is enabled.

    Actual meaning:
    This stores the privacy-safe chunks artifact in S3.

    If S3 upload fails, we do not stop the worker.
    Pinecone indexing can still continue using local redacted_chunks.json.
    """

    # Default values when S3 is disabled.
    result = {
        "redacted_chunks_s3_bucket": None,
        "redacted_chunks_s3_key": None,
        "redacted_chunks_s3_uri": None,
        "redacted_chunks_s3_upload_status": "disabled",
        "redacted_chunks_s3_error_message": None,
    }

    # If S3 upload is disabled, return default values.
    if not S3_UPLOAD_ENABLED:
        return result

    try:
        # Upload redacted_chunks.json to S3.
        s3_result = upload_redacted_chunks_to_s3(
            local_file_path=redacted_chunks_path,
            document_id=document_id,
        )

        # Store success fields.
        result["redacted_chunks_s3_bucket"] = s3_result["bucket"]
        result["redacted_chunks_s3_key"] = s3_result["s3_key"]
        result["redacted_chunks_s3_uri"] = s3_result["s3_uri"]
        result["redacted_chunks_s3_upload_status"] = "success"

    except S3ServiceError as error:
        # Store error but do not crash worker.
        result["redacted_chunks_s3_upload_status"] = "failed"
        result["redacted_chunks_s3_error_message"] = str(error)

    # Return result fields.
    return result


# ---------------------------------------------------------
# Main document processing function
# ---------------------------------------------------------

def process_document(document_id: str) -> None:
    """
    Process one document end-to-end.

    Pipeline:
    queued
    -> processing
    -> extracting
    -> extracted
    -> chunking
    -> chunked
    -> redacting
    -> redacted
    -> graph pipeline
    -> indexing
    -> indexed
    -> completed

    Important:
    Graph pipeline uses redacted_chunks.json.
    This means Neo4j should not store raw email/phone/SSN values.
    """

    # Load current document metadata.
    document = get_document_by_id(document_id)

    # If document does not exist, fail clearly.
    if document is None:
        raise ValueError(f"Document metadata not found for document_id={document_id}")

    # If document already completed/indexed, skip safely.
    if should_skip_document(document):
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.SKIPPED,
            current_step=ProcessingStep.SKIPPED,
            event_type=DocumentEventType.DOCUMENT_SKIPPED,
            event_message="Document was already processed. Skipping duplicate SQS message.",
            progress_percentage=100,
        )

        # Return without doing extraction/chunking/redaction/indexing again.
        return

    # Mark document as processing.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.PROCESSING,
        current_step=ProcessingStep.PROCESSING,
        event_type=DocumentEventType.PROCESSING_STARTED,
        event_message="Worker picked the document from SQS.",
        progress_percentage=20,
    )

    # ---------------------------------------------------------
    # Step 1: Ensure PDF exists locally.
    # ---------------------------------------------------------

    # Reload latest metadata.
    document = get_document_by_id(document_id)

    # Ensure PDF exists locally.
    # If local PDF is missing, this downloads it from S3.
    pdf_path = ensure_pdf_available_locally(document)

    # ---------------------------------------------------------
    # Step 2: Extract/parse text.
    # ---------------------------------------------------------

    # Mark extraction started.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.EXTRACTING,
        current_step=ProcessingStep.EXTRACTING,
        event_type=DocumentEventType.EXTRACTION_STARTED,
        event_message="Started extracting text from PDF.",
        progress_percentage=35,
    )

    # Parse document using Week 10 parser abstraction.
    # This tries Docling first if DOCLING_ENABLED=true.
    # If Docling fails, parser_service falls back to PyMuPDF.
    extraction_result = parse_document(
        pdf_path=str(pdf_path),
        document_id=document_id,
    )

    # Upload extracted_text.json to S3 if enabled.
    extracted_s3_updates = upload_extracted_text_artifact_if_enabled(
        document_id=document_id,
        extracted_text_path=extraction_result["extracted_text_path"],
    )

    # Mark extraction completed.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.EXTRACTED,
        current_step=ProcessingStep.EXTRACTED,
        event_type=DocumentEventType.EXTRACTION_COMPLETED,
        event_message="Text extraction completed successfully.",
        progress_percentage=50,
        extra_updates={
            "page_count": extraction_result["page_count"],
            "extracted_text_path": extraction_result["extracted_text_path"],
            "parser_used": extraction_result.get("parser_used", "unknown"),
            **extracted_s3_updates,
            "error_message": None,
        },
    )

    # ---------------------------------------------------------
    # Step 3: Chunk extracted text.
    # ---------------------------------------------------------

    # Reload latest metadata after extraction.
    document = get_document_by_id(document_id)

    # Ensure extracted_text.json exists locally.
    extracted_text_path = ensure_extracted_text_available_locally(document_id)

    # Mark chunking started.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.CHUNKING,
        current_step=ProcessingStep.CHUNKING,
        event_type=DocumentEventType.CHUNKING_STARTED,
        event_message="Started creating page-aware chunks.",
        progress_percentage=60,
    )

    # Create chunks from extracted_text.json.
    chunking_result = create_chunks_from_extracted_text(
        extracted_text_path=extracted_text_path,
        document_id=document_id,
        chunk_size=150,
        overlap=30,
    )

    # Upload chunks.json to S3 if enabled.
    chunks_s3_updates = upload_chunks_artifact_if_enabled(
        document_id=document_id,
        chunks_path=chunking_result["chunks_path"],
    )

    # Mark chunking completed.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.CHUNKED,
        current_step=ProcessingStep.CHUNKED,
        event_type=DocumentEventType.CHUNKING_COMPLETED,
        event_message="Chunking completed successfully.",
        progress_percentage=70,
        extra_updates={
            "chunk_count": chunking_result["chunk_count"],
            "chunks_path": chunking_result["chunks_path"],
            "parser_used": chunking_result.get("parser_used", "unknown"),
            **chunks_s3_updates,
            "error_message": None,
        },
    )

    # ---------------------------------------------------------
    # Step 4: Redact PII from chunks.
    # ---------------------------------------------------------

    # Reload latest metadata after chunking.
    document = get_document_by_id(document_id)

    # Ensure chunks.json exists locally.
    chunks_path = ensure_chunks_available_locally(document_id)

    # Mark PII redaction started.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.REDACTING,
        current_step=ProcessingStep.REDACTING,
        event_type=DocumentEventType.PII_REDACTION_STARTED,
        event_message="Started redacting sensitive information from chunks.",
        progress_percentage=75,
    )

    # Create redacted_chunks.json from chunks.json.
    # Actual meaning:
    # This reads original chunks and replaces emails/phones/SSNs with placeholders.
    redaction_result = create_redacted_chunks_file(chunks_path)

    # Upload redacted_chunks.json to S3 if enabled.
    redacted_chunks_s3_updates = upload_redacted_chunks_artifact_if_enabled(
        document_id=document_id,
        redacted_chunks_path=redaction_result["redacted_chunks_path"],
    )

    # Mark PII redaction completed.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.REDACTED,
        current_step=ProcessingStep.REDACTED,
        event_type=DocumentEventType.PII_REDACTION_COMPLETED,
        event_message="PII redaction completed successfully.",
        progress_percentage=80,
        extra_updates={
            "redacted_chunks_path": redaction_result["redacted_chunks_path"],
            "redaction_applied": redaction_result["redaction_applied"],
            "redaction_count": redaction_result["redaction_count"],
            "redaction_types": redaction_result["redaction_types"],
            **redacted_chunks_s3_updates,
            "error_message": None,
        },
    )

    # ---------------------------------------------------------
    # Step 5: Week 12 graph pipeline using Neo4j.
    # ---------------------------------------------------------

    # Default graph metadata values.
    # These are stored later in document metadata after completion.
    graph_processed = False
    graph_written = False
    graph_unique_entities_count = 0
    graph_entity_mentions_count = 0
    graph_error_message = None

    try:
        # Reload latest metadata after redaction.
        document = get_document_by_id(document_id)

        # Get filename safely.
        filename = get_document_filename(document)

        # Get parser used.
        # Prefer chunking_result parser_used because chunks are produced from parsed output.
        parser_used = (
            chunking_result.get("parser_used")
            or extraction_result.get("parser_used")
            or "unknown"
        )

        # Log graph pipeline start.
        logger.info(
            "Starting Week 12 graph pipeline. document_id=%s redacted_chunks_path=%s",
            document_id,
            redaction_result["redacted_chunks_path"],
        )

        # Build Neo4j graph from redacted chunks.
        # Important:
        # This uses redacted_chunks.json, not raw chunks.json.
        graph_summary = build_graph_for_document_from_redacted_chunks(
            document_id=document_id,
            redacted_chunks_path=redaction_result["redacted_chunks_path"],
            filename=filename,
            parser_used=parser_used,
        )

        # Read useful graph summary values.
        graph_processed = True
        graph_written = bool(graph_summary.get("graph_written", False))
        graph_unique_entities_count = int(
            graph_summary.get("unique_entities_stored", 0) or 0
        )
        graph_entity_mentions_count = int(
            graph_summary.get("entity_mentions_extracted", 0) or 0
        )

        # Log graph pipeline success.
        logger.info(
            "Week 12 graph pipeline completed. document_id=%s graph_written=%s "
            "entity_mentions=%s unique_entities=%s",
            document_id,
            graph_written,
            graph_entity_mentions_count,
            graph_unique_entities_count,
        )

    except Exception as graph_error:
        # Important production decision:
        # Graph failure should not break normal RAG processing.
        # Pinecone indexing and Q&A should still work even if Neo4j is temporarily down.
        graph_processed = False
        graph_written = False
        graph_error_message = str(graph_error)

        # Log graph pipeline failure with full traceback.
        logger.error(
            "Week 12 graph pipeline failed. document_id=%s error=%s",
            document_id,
            graph_error_message,
            exc_info=True,
        )

    # ---------------------------------------------------------
    # Step 6: Index redacted chunks into Pinecone.
    # ---------------------------------------------------------

    # Load redacted_chunks.json.
    # Important:
    # Pinecone receives redacted chunks, not raw chunks.
    redacted_chunks_data = load_redacted_chunks(
        redaction_result["redacted_chunks_path"]
    )

    # Mark indexing started.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.INDEXING,
        current_step=ProcessingStep.INDEXING,
        event_type=DocumentEventType.INDEXING_STARTED,
        event_message="Started indexing redacted chunks into Pinecone.",
        progress_percentage=85,
    )

    # Store redacted chunk embeddings in Pinecone.
    # Actual meaning:
    # The embedding model sees redacted text.
    # Pinecone source_text also becomes redacted text.
    indexing_result = index_document_chunks(redacted_chunks_data)

    # Mark indexing completed.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.INDEXED,
        current_step=ProcessingStep.INDEXED,
        event_type=DocumentEventType.INDEXING_COMPLETED,
        event_message="Redacted chunk vector indexing completed successfully.",
        progress_percentage=95,
        extra_updates={
            "vector_count": indexing_result["vector_count"],
            "parser_used": indexing_result.get("parser_used", "unknown"),
            "privacy_processed": True,
            "graph_processed": graph_processed,
            "graph_written": graph_written,
            "graph_unique_entities_count": graph_unique_entities_count,
            "graph_entity_mentions_count": graph_entity_mentions_count,
            "graph_error_message": graph_error_message,
            "error_message": None,
        },
    )

    # Mark full document completed.
    update_document_state(
        document_id=document_id,
        status=DocumentStatus.COMPLETED,
        current_step=ProcessingStep.COMPLETED,
        event_type=DocumentEventType.DOCUMENT_COMPLETED,
        event_message="Document processing completed successfully.",
        progress_percentage=100,
        extra_updates={
            "graph_processed": graph_processed,
            "graph_written": graph_written,
            "graph_unique_entities_count": graph_unique_entities_count,
            "graph_entity_mentions_count": graph_entity_mentions_count,
            "graph_error_message": graph_error_message,
        },
    )


# ---------------------------------------------------------
# SQS message processing
# ---------------------------------------------------------

def process_sqs_message(message: dict) -> bool:
    """
    Process one SQS message.

    Returns:
    - True: message can be deleted from SQS.
    - False: message should stay in SQS for retry/DLQ.

    Important:
    If a message has no document_id, it is an invalid/old test message.
    In development, we delete it so it does not block the queue forever.
    """

    try:
        # Extract document_id from SQS message.
        document_id = get_document_id_from_message(message)

    except ValueError as error:
        # This means the message itself is invalid.
        # Example: old smoke test message with no document_id.
        logger.error(
            "Invalid SQS message. Deleting it so queue is not blocked. error=%s",
            str(error),
        )

        # Return True so run_worker_once deletes this bad message.
        return True

    try:
        # Log which document is being processed.
        logger.info("Processing SQS document message. document_id=%s", document_id)

        # Process the document.
        process_document(document_id)

        # Return True so caller deletes message from SQS.
        return True

    except Exception as error:
        # Log error in backend logs.
        logger.exception(
            "Worker failed to process SQS message. document_id=%s error=%s",
            document_id,
            str(error),
        )

        # Update document metadata as failed.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.FAILED,
            current_step=ProcessingStep.FAILED,
            event_type=DocumentEventType.DOCUMENT_FAILED,
            event_message="Document processing failed inside worker.",
            error_message=str(error),
            increment_retry=True,
            progress_percentage=100,
        )

        # Return False so valid document messages are NOT deleted on processing failure.
        # SQS will retry them and eventually move them to DLQ.
        return False


# ---------------------------------------------------------
# Worker loop helpers
# ---------------------------------------------------------

def run_worker_once() -> int:
    """
    Receive and process one batch of SQS messages.

    Returns:
    - number of messages processed.
    """

    # Receive messages from SQS.
    messages = receive_document_processing_messages()

    # If no messages, return 0.
    if not messages:
        logger.info("No SQS messages found.")
        return 0

    # Count processed messages.
    processed_count = 0

    # Process each message.
    for message in messages:
        # Process message safely.
        should_delete = process_sqs_message(message)

        # If processing succeeded OR message was invalid, delete message from SQS.
        if should_delete:
            receipt_handle = message.get("ReceiptHandle")

            if receipt_handle:
                delete_message(receipt_handle)
                logger.info("SQS message deleted after successful/invalid processing.")

        # Increase count.
        processed_count += 1

    # Return count.
    return processed_count


def run_worker_forever() -> None:
    """
    Keep worker running continuously.

    Press CTRL+C to stop safely.
    """

    # Check SQS config and access before starting loop.
    ensure_sqs_ready()

    # Print startup message.
    logger.info("Document worker started. Press CTRL+C to stop.")

    # Keep running until CTRL+C.
    while True:
        try:
            # Process one batch.
            run_worker_once()

        except KeyboardInterrupt:
            # This runs when user presses CTRL+C.
            logger.info("CTRL+C received. Document worker stopping safely.")
            break

        except Exception as error:
            # Log unexpected worker loop errors.
            logger.exception("Unexpected worker loop error: %s", str(error))

            # Sleep a little so it does not spam errors quickly.
            time.sleep(5)


# ---------------------------------------------------------
# Script entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    run_worker_forever()