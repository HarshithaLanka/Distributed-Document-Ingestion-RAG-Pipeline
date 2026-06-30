# app/routes/document_routes.py

"""
This file contains document APIs:

POST /documents/upload
GET /documents
GET /documents/{document_id}
GET /documents/{document_id}/status
GET /documents/{document_id}/events
POST /documents/{document_id}/extract
POST /documents/{document_id}/chunk
GET /documents/{document_id}/chunks
POST /documents/{document_id}/index

Week 9 updates:
- Added document status API.
- Added document events API.
- Added current_step and progress_percentage updates.
- Added event logging.
- Added retry/error tracking fields.
"""

# Import datetime/timezone to store timestamps in UTC.
from datetime import datetime, timezone

# Import APIRouter to create a separate group of document-related APIs.
from fastapi import APIRouter

# Import UploadFile and File to receive uploaded files.
from fastapi import UploadFile, File

# Import HTTPException to return clean error responses.
from fastapi import HTTPException

# Import full config module for SQS queue name fallback.
from app import config

# Import config values that control cloud features.
from app.config import S3_UPLOAD_ENABLED, SQS_ENABLED

# Import Week 9 status/event constants.
from app.constants.document_status import DocumentStatus
from app.constants.document_status import ProcessingStep
from app.constants.document_status import DocumentEventType

# Import artifact resolver functions.
# These functions restore missing local files from S3 when local cache is missing.
from app.services.artifact_resolver_service import (
    ensure_pdf_available_locally,
    ensure_extracted_text_available_locally,
    ensure_chunks_available_locally,
)

# Import response models.
from app.models.document_models import DocumentUploadResponse
from app.models.document_models import DocumentListResponse
from app.models.document_models import DocumentMetadata
from app.models.document_models import DocumentExtractionResponse
from app.models.document_models import DocumentChunkingResponse
from app.models.document_models import DocumentChunksResponse
from app.models.document_models import DocumentChunk
from app.models.document_models import DocumentIndexingResponse
from app.models.document_models import DocumentStatusResponse
from app.models.document_models import DocumentEventsResponse

# Import ID generator function.
from app.utils.id_generator import generate_document_id

# Import local storage service.
from app.services.storage_service import save_pdf_locally

# Import S3 service functions.
from app.services.s3_service import upload_pdf_to_s3
from app.services.s3_service import upload_extracted_text_to_s3
from app.services.s3_service import upload_chunks_to_s3
from app.services.s3_service import S3ServiceError

# Import SQS service function.
from app.services.sqs_service import send_document_processing_message

# Import metadata service functions.
from app.services.metadata_service import add_document_metadata
from app.services.metadata_service import load_documents
from app.services.metadata_service import get_document_by_id
from app.services.metadata_service import update_document_metadata

# Import Week 9 state/event services.
from app.services.document_state_service import get_document_status
from app.services.document_state_service import update_document_state
from app.services.document_event_service import get_document_events
from app.services.document_event_service import log_document_event

# Import PDF extraction service.
from app.services.pdf_parser_service import extract_text_from_pdf

# Import chunking services.
from app.services.chunking_service import create_chunks_from_extracted_text
from app.services.chunking_service import load_chunks

# Import Pinecone indexing service.
from app.services.pinecone_service import index_document_chunks


# Create a router for document APIs.
router = APIRouter(
    # Prefix means all routes in this file will start with /documents.
    prefix="/documents",

    # Tags help group APIs nicely in Swagger UI.
    tags=["Documents"],
)


def utc_now() -> str:
    """
    Return current UTC time as ISO string.

    UTC is best for backend timestamps because it avoids timezone confusion.
    """

    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------

@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document.

    Week 9 behavior:
    1. Save PDF locally.
    2. If S3_UPLOAD_ENABLED=true, upload PDF to S3.
    3. Save metadata as uploaded.
    4. Log DOCUMENT_UPLOADED event.
    5. If SQS_ENABLED=true, send document_id to SQS.
    6. Update metadata as queued.
    7. Log DOCUMENT_QUEUED event.
    8. Return quickly.

    Important:
    This endpoint does NOT extract, chunk, or index the PDF.
    The background worker does that.
    """

    # Check if uploaded filename exists.
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have a filename.",
        )

    # Check if uploaded filename ends with .pdf.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    # Check if uploaded file content type is PDF.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a valid PDF.",
        )

    # Generate a unique document ID.
    document_id = generate_document_id()

    # Store upload timestamp.
    uploaded_at = utc_now()

    # Save uploaded PDF locally.
    saved_file_path = save_pdf_locally(file, document_id)

    # Create default S3 metadata values.
    s3_bucket = None
    s3_key = None
    s3_uri = None
    s3_upload_status = "disabled"
    s3_error_message = None

    # If S3 upload is enabled in .env, upload the locally saved PDF to S3.
    if S3_UPLOAD_ENABLED:
        try:
            # Open the locally saved PDF in binary read mode.
            with open(saved_file_path, "rb") as pdf_file:
                # Upload the PDF to S3.
                s3_result = upload_pdf_to_s3(
                    file_obj=pdf_file,
                    document_id=document_id,
                    filename=file.filename,
                )

            # Store S3 upload result.
            s3_bucket = s3_result["bucket"]
            s3_key = s3_result["s3_key"]
            s3_uri = s3_result["s3_uri"]
            s3_upload_status = "success"

        except S3ServiceError as error:
            # During migration, do not break local upload if S3 fails.
            s3_upload_status = "failed"
            s3_error_message = str(error)

    # Create metadata record for this document.
    document_metadata = {
        "document_id": document_id,
        "filename": file.filename,
        "file_path": str(saved_file_path),
        "status": DocumentStatus.UPLOADED,
        "current_step": ProcessingStep.UPLOADED,
        "progress_percentage": 5,
        "retry_count": 0,
        "uploaded_at": uploaded_at,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "updated_at": uploaded_at,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "s3_uri": s3_uri,
        "s3_upload_status": s3_upload_status,
        "s3_error_message": s3_error_message,
        "sqs_message_id": None,
        "sqs_queue_name": None,
        "sqs_send_status": "disabled",
        "queued_at": None,
        "queue_error": None,
        "queue_failed_at": None,
        "error_message": None,
    }

    # Save initial metadata to DynamoDB/local cache.
    add_document_metadata(document_metadata)

    # Log upload event.
    log_document_event(
        document_id=document_id,
        event_type=DocumentEventType.DOCUMENT_UPLOADED,
        message="PDF uploaded successfully.",
        status=DocumentStatus.UPLOADED,
        current_step=ProcessingStep.UPLOADED,
        progress_percentage=5,
        details={
            "filename": file.filename,
            "s3_upload_status": s3_upload_status,
            "s3_key": s3_key,
        },
    )

    # If SQS is enabled, send this document as a background processing job.
    if SQS_ENABLED:
        try:
            # Send only document_id to SQS.
            sqs_result = send_document_processing_message(
                document_id=document_id,
            )

            # Store queued timestamp.
            queued_at = utc_now()

            # Get queue name from SQS response or config fallback.
            sqs_queue_name = sqs_result.get(
                "queue_name",
                getattr(config, "SQS_QUEUE_NAME", None),
            )

            # Update document state to queued and log event.
            updated_document = update_document_state(
                document_id=document_id,
                status=DocumentStatus.QUEUED,
                current_step=ProcessingStep.QUEUED,
                event_type=DocumentEventType.DOCUMENT_QUEUED,
                event_message="Document sent to SQS queue successfully.",
                progress_percentage=10,
                extra_updates={
                    "sqs_message_id": sqs_result.get("message_id"),
                    "sqs_queue_name": sqs_queue_name,
                    "sqs_send_status": "success",
                    "queued_at": queued_at,
                    "queue_error": None,
                    "queue_failed_at": None,
                    "error_message": None,
                },
            )

            # Update local response dictionary.
            document_metadata.update(updated_document)

        except Exception as error:
            # Queue failure timestamp.
            queue_failed_at = utc_now()

            # Update metadata as queue_failed and log failure event.
            update_document_state(
                document_id=document_id,
                status=DocumentStatus.QUEUE_FAILED,
                current_step="Failed to send document to SQS queue",
                event_type=DocumentEventType.DOCUMENT_FAILED,
                event_message="Document upload succeeded but SQS queue send failed.",
                progress_percentage=100,
                error_message=str(error),
                extra_updates={
                    "sqs_send_status": "failed",
                    "queue_error": str(error),
                    "queue_failed_at": queue_failed_at,
                },
            )

            # Return a clean Swagger error.
            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "Document uploaded, but failed to send processing job to SQS."
                    ),
                    "document_id": document_id,
                    "error": str(error),
                },
            )

    # Return clean upload response.
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status=document_metadata["status"],
        message=(
            "PDF uploaded successfully and queued for background processing."
            if document_metadata["status"] == DocumentStatus.QUEUED
            else "PDF uploaded successfully."
        ),
        file_path=str(saved_file_path),
        current_step=document_metadata.get("current_step"),
        progress_percentage=document_metadata.get("progress_percentage"),
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        s3_uri=s3_uri,
        s3_upload_status=s3_upload_status,
        sqs_message_id=document_metadata.get("sqs_message_id"),
        sqs_queue_name=document_metadata.get("sqs_queue_name"),
        sqs_send_status=document_metadata.get("sqs_send_status"),
        uploaded_at=document_metadata.get("uploaded_at"),
        queued_at=document_metadata.get("queued_at"),
    )


# ---------------------------------------------------------
# GET /documents
# ---------------------------------------------------------

@router.get("", response_model=DocumentListResponse)
def list_documents():
    """
    List all uploaded documents from metadata storage.

    metadata_service decides actual source:
    DynamoDB primary + local JSON backup/cache.
    """

    # Load all documents.
    documents = load_documents()

    # Convert each dictionary into DocumentMetadata model.
    document_items = [
        DocumentMetadata(**document)
        for document in documents
    ]

    # Return total count and documents list.
    return DocumentListResponse(
        total=len(document_items),
        documents=document_items,
    )


# ---------------------------------------------------------
# GET /documents/{document_id}/status
# ---------------------------------------------------------

@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_processing_status(document_id: str):
    """
    Get current processing status of one document.

    This is useful for:
    queued -> processing -> extracting -> chunking -> indexing -> completed
    """

    # Load current status from metadata.
    status_data = get_document_status(document_id)

    # If document does not exist, return 404.
    if not status_data:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Return clean status response.
    return status_data


# ---------------------------------------------------------
# GET /documents/{document_id}/events
# ---------------------------------------------------------

@router.get("/{document_id}/events", response_model=DocumentEventsResponse)
def get_document_processing_events(document_id: str):
    """
    Get full event timeline for one document.

    This is useful for debugging and demo:
    uploaded -> queued -> extraction started -> extraction completed -> etc.
    """

    # First check if document exists.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Load events from DynamoDB events table.
    events = get_document_events(document_id)

    # Return response.
    return DocumentEventsResponse(
        document_id=document_id,
        event_count=len(events),
        events=events,
    )


# ---------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------

@router.get("/{document_id}", response_model=DocumentMetadata)
def get_document(document_id: str):
    """
    Get one document metadata record using document_id.
    """

    # Search document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Return matching document.
    return DocumentMetadata(**document)


# ---------------------------------------------------------
# POST /documents/{document_id}/extract
# ---------------------------------------------------------

@router.post("/{document_id}/extract", response_model=DocumentExtractionResponse)
def extract_document(document_id: str):
    """
    Extract page-wise text from a locally saved PDF.

    S3 behavior:
    If local PDF is missing, recover it from S3.
    After extracted_text.json is created locally, upload it to S3 also.
    """

    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        # Update state to extracting.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.EXTRACTING,
            current_step=ProcessingStep.EXTRACTING,
            event_type=DocumentEventType.EXTRACTION_STARTED,
            event_message="Started extracting text from PDF.",
            progress_percentage=35,
            extra_updates={
                "error_message": None,
            },
        )

        # Ensure PDF exists locally.
        pdf_path = ensure_pdf_available_locally(document)

        # Extract text from PDF.
        extraction_result = extract_text_from_pdf(
            pdf_path,
            document_id,
        )

        # Create default S3 values for extracted_text.json.
        extracted_text_s3_bucket = None
        extracted_text_s3_key = None
        extracted_text_s3_uri = None
        extracted_text_s3_upload_status = "disabled"
        extracted_text_s3_error_message = None

        # Upload extracted_text.json to S3 if enabled.
        if S3_UPLOAD_ENABLED:
            try:
                # Upload generated extracted_text.json to S3.
                extracted_s3_result = upload_extracted_text_to_s3(
                    local_file_path=extraction_result["extracted_text_path"],
                    document_id=document_id,
                )

                # Store S3 result.
                extracted_text_s3_bucket = extracted_s3_result["bucket"]
                extracted_text_s3_key = extracted_s3_result["s3_key"]
                extracted_text_s3_uri = extracted_s3_result["s3_uri"]
                extracted_text_s3_upload_status = "success"

            except S3ServiceError as error:
                # Do not fail extraction if only S3 artifact upload fails.
                extracted_text_s3_upload_status = "failed"
                extracted_text_s3_error_message = str(error)

        # Update state after successful extraction.
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
                "extracted_text_s3_bucket": extracted_text_s3_bucket,
                "extracted_text_s3_key": extracted_text_s3_key,
                "extracted_text_s3_uri": extracted_text_s3_uri,
                "extracted_text_s3_upload_status": extracted_text_s3_upload_status,
                "extracted_text_s3_error_message": extracted_text_s3_error_message,
                "error_message": None,
            },
        )

        # Return extraction response.
        return DocumentExtractionResponse(
            document_id=document_id,
            status=DocumentStatus.EXTRACTED,
            page_count=extraction_result["page_count"],
            extracted_text_path=extraction_result["extracted_text_path"],
            message="Text extracted successfully.",
            extracted_text_s3_key=extracted_text_s3_key,
            extracted_text_s3_uri=extracted_text_s3_uri,
            extracted_text_s3_upload_status=extracted_text_s3_upload_status,
        )

    except Exception as error:
        # Update state to failed if extraction fails.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.FAILED,
            current_step=ProcessingStep.FAILED,
            event_type=DocumentEventType.DOCUMENT_FAILED,
            event_message="Text extraction failed.",
            progress_percentage=100,
            error_message=str(error),
        )

        # Return clean 500 error.
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(error)}",
        )


# ---------------------------------------------------------
# POST /documents/{document_id}/chunk
# ---------------------------------------------------------

@router.post("/{document_id}/chunk", response_model=DocumentChunkingResponse)
def chunk_document(document_id: str):
    """
    Create page-aware chunks from extracted_text.json.

    S3 behavior:
    If local extracted_text.json is missing, recover it from S3.
    After chunks.json is created locally, upload it to S3 also.
    """

    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Check if text extraction has already happened.
    if document.get("extracted_text_path") is None and document.get("extracted_text_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Text extraction must be completed before chunking.",
        )

    try:
        # Update state to chunking.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.CHUNKING,
            current_step=ProcessingStep.CHUNKING,
            event_type=DocumentEventType.CHUNKING_STARTED,
            event_message="Started creating page-aware chunks.",
            progress_percentage=60,
            extra_updates={
                "error_message": None,
            },
        )

        # Ensure extracted_text.json exists locally.
        extracted_text_path = ensure_extracted_text_available_locally(document)

        # Create chunks from extracted_text.json.
        chunking_result = create_chunks_from_extracted_text(
            extracted_text_path=extracted_text_path,
            document_id=document_id,
            chunk_size=150,
            overlap=30,
        )

        # Create default S3 values for chunks.json.
        chunks_s3_bucket = None
        chunks_s3_key = None
        chunks_s3_uri = None
        chunks_s3_upload_status = "disabled"
        chunks_s3_error_message = None

        # Upload chunks.json to S3 if enabled.
        if S3_UPLOAD_ENABLED:
            try:
                # Upload generated chunks.json to S3.
                chunks_s3_result = upload_chunks_to_s3(
                    local_file_path=chunking_result["chunks_path"],
                    document_id=document_id,
                )

                # Store S3 result.
                chunks_s3_bucket = chunks_s3_result["bucket"]
                chunks_s3_key = chunks_s3_result["s3_key"]
                chunks_s3_uri = chunks_s3_result["s3_uri"]
                chunks_s3_upload_status = "success"

            except S3ServiceError as error:
                # Do not fail chunking if only S3 artifact upload fails.
                chunks_s3_upload_status = "failed"
                chunks_s3_error_message = str(error)

        # Update state after successful chunking.
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
                "chunks_s3_bucket": chunks_s3_bucket,
                "chunks_s3_key": chunks_s3_key,
                "chunks_s3_uri": chunks_s3_uri,
                "chunks_s3_upload_status": chunks_s3_upload_status,
                "chunks_s3_error_message": chunks_s3_error_message,
                "error_message": None,
            },
        )

        # Return clean chunking response.
        return DocumentChunkingResponse(
            document_id=document_id,
            status=DocumentStatus.CHUNKED,
            chunk_count=chunking_result["chunk_count"],
            chunks_path=chunking_result["chunks_path"],
            message="Document chunked successfully.",
            chunks_s3_key=chunks_s3_key,
            chunks_s3_uri=chunks_s3_uri,
            chunks_s3_upload_status=chunks_s3_upload_status,
        )

    except Exception as error:
        # Update state to failed if chunking fails.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.FAILED,
            current_step=ProcessingStep.FAILED,
            event_type=DocumentEventType.DOCUMENT_FAILED,
            event_message="Chunking failed.",
            progress_percentage=100,
            error_message=str(error),
        )

        # Return clean 500 error.
        raise HTTPException(
            status_code=500,
            detail=f"Chunking failed: {str(error)}",
        )


# ---------------------------------------------------------
# GET /documents/{document_id}/chunks
# ---------------------------------------------------------

@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(document_id: str):
    """
    Return chunks created for a document.

    S3 behavior:
    If local chunks.json is missing, recover it from S3.
    """

    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Check if chunks are already created.
    if document.get("chunks_path") is None and document.get("chunks_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks are not created yet.",
        )

    # Ensure chunks.json exists locally.
    chunks_path = ensure_chunks_available_locally(document)

    # Load chunks from chunks.json.
    chunks_data = load_chunks(chunks_path)

    # Convert chunk dictionaries into DocumentChunk models.
    chunk_items = [
        DocumentChunk(**chunk)
        for chunk in chunks_data["chunks"]
    ]

    # Return chunks response.
    return DocumentChunksResponse(
        document_id=document_id,
        chunk_count=chunks_data["chunk_count"],
        chunks=chunk_items,
    )


# ---------------------------------------------------------
# POST /documents/{document_id}/index
# ---------------------------------------------------------

@router.post("/{document_id}/index", response_model=DocumentIndexingResponse)
def index_document(document_id: str):
    """
    Index document chunks into Pinecone.

    S3 behavior:
    If local chunks.json is missing, recover it from S3.
    """

    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Check if chunks are created before indexing.
    if document.get("chunks_path") is None and document.get("chunks_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks must be created before indexing.",
        )

    try:
        # Update state to indexing.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.INDEXING,
            current_step=ProcessingStep.INDEXING,
            event_type=DocumentEventType.INDEXING_STARTED,
            event_message="Started indexing chunks into Pinecone.",
            progress_percentage=85,
            extra_updates={
                "error_message": None,
            },
        )

        # Ensure chunks.json exists locally.
        chunks_path = ensure_chunks_available_locally(document)

        # Load chunks from chunks.json.
        chunks_data = load_chunks(chunks_path)

        # Store chunk embeddings in Pinecone.
        indexing_result = index_document_chunks(chunks_data)

        # Update state after successful indexing.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.INDEXED,
            current_step=ProcessingStep.INDEXED,
            event_type=DocumentEventType.INDEXING_COMPLETED,
            event_message="Vector indexing completed successfully.",
            progress_percentage=95,
            extra_updates={
                "vector_count": indexing_result["vector_count"],
                "error_message": None,
            },
        )

        # Also mark document as completed.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.COMPLETED,
            current_step=ProcessingStep.COMPLETED,
            event_type=DocumentEventType.DOCUMENT_COMPLETED,
            event_message="Document processing completed successfully.",
            progress_percentage=100,
        )

        # Return clean response.
        return DocumentIndexingResponse(
            document_id=document_id,
            status=DocumentStatus.COMPLETED,
            vector_count=indexing_result["vector_count"],
            message="Document chunks indexed successfully.",
        )

    except Exception as error:
        # Update state to failed if indexing fails.
        update_document_state(
            document_id=document_id,
            status=DocumentStatus.FAILED,
            current_step=ProcessingStep.FAILED,
            event_type=DocumentEventType.DOCUMENT_FAILED,
            event_message="Indexing failed.",
            progress_percentage=100,
            error_message=str(error),
        )

        # Return clean error.
        raise HTTPException(
            status_code=500,
            detail=f"Indexing failed: {str(error)}",
        )