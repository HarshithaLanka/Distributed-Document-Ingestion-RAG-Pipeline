"""
This file contains document APIs:

POST /documents/upload
GET /documents
GET /documents/{document_id}
POST /documents/{document_id}/extract
POST /documents/{document_id}/chunk
GET /documents/{document_id}/chunks
POST /documents/{document_id}/index

The route receives requests, but it does not directly manage all business logic.
It calls services for storage, parsing, metadata, chunking, indexing, S3 upload,
S3 fallback recovery, and SQS queue submission.
"""

# Import datetime/timezone to store queued_at and queue_failed_at timestamps in UTC.
from datetime import datetime, timezone

# Import APIRouter to create a separate group of document-related APIs.
from fastapi import APIRouter

# Import UploadFile and File to receive uploaded files.
from fastapi import UploadFile, File

# Import HTTPException to return clean error responses.
from fastapi import HTTPException

# Import config values that control cloud features.
# S3_UPLOAD_ENABLED controls whether uploaded PDFs/artifacts go to S3.
# SQS_ENABLED controls whether upload API sends processing jobs to SQS.
from app.config import S3_UPLOAD_ENABLED, SQS_ENABLED

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
# This lets the upload API send only document_id to SQS.
# The PDF itself stays in S3/local storage; SQS only stores the job instruction.
from app.services.sqs_service import send_document_processing_message

# Import metadata service functions.
from app.services.metadata_service import add_document_metadata
from app.services.metadata_service import load_documents
from app.services.metadata_service import get_document_by_id
from app.services.metadata_service import update_document_metadata

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


# Create POST API for uploading a document.
@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document.

    Week 8 behavior:
    1. Save PDF locally.
    2. If S3_UPLOAD_ENABLED=true, also upload the PDF to S3.
    3. Save metadata to DynamoDB primary + local JSON backup/cache.
    4. If SQS_ENABLED=true, send document_id to SQS.
    5. Return quickly with status queued.

    Important:
    This endpoint does NOT extract, chunk, or index the PDF.
    A background worker will do extraction, chunking, and indexing later.
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

    # Save uploaded PDF locally.
    saved_file_path = save_pdf_locally(file, document_id)

    # Create default S3 metadata values.
    # These defaults are used when S3 is disabled or S3 upload fails.
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
            # The document is still saved locally.
            s3_upload_status = "failed"
            s3_error_message = str(error)

    # Create metadata record for this document.
    # This record is first saved as uploaded.
    # Then, if SQS succeeds, we update it to queued.
    document_metadata = {
        "document_id": document_id,
        "filename": file.filename,
        "file_path": str(saved_file_path),
        "status": "uploaded",
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

    # Save initial metadata.
    # This saves upload information before attempting SQS.
    # Your metadata_service writes to DynamoDB primary + local documents.json backup/cache.
    add_document_metadata(document_metadata)

    # If SQS is enabled, send this document as a background processing job.
    if SQS_ENABLED:
        try:
            # Send only document_id to SQS.
            #
            # We do NOT send the PDF file to SQS.
            # The PDF already exists locally and in S3.
            # Later, the worker will read document_id from SQS
            # and use that document_id to find the PDF/artifacts.
            sqs_result = send_document_processing_message(
                document_id=document_id
            )

            # Store current UTC time.
            # UTC is preferred for backend systems because it avoids timezone confusion.
            queued_at = datetime.now(timezone.utc).isoformat()

            # Create fields that should be updated after successful SQS send.
            queued_update = {
                "status": "queued",
                "sqs_message_id": sqs_result.get("message_id"),
                "sqs_queue_name": sqs_result.get("queue_name"),
                "sqs_send_status": "success",
                "queued_at": queued_at,
                "queue_error": None,
                "queue_failed_at": None,
                "error_message": None,
            }

            # Update metadata in DynamoDB/local cache.
            update_document_metadata(document_id, queued_update)

            # Also update the local dictionary used for the API response.
            # Without this, the response may still show old status="uploaded".
            document_metadata.update(queued_update)

        except Exception as error:
            # If SQS sending fails, the uploaded PDF is not lost.
            # It is already saved locally and maybe uploaded to S3.
            #
            # But background processing cannot start because no queue message was created.
            # So we mark this document as queue_failed.
            queue_failed_update = {
                "status": "queue_failed",
                "sqs_send_status": "failed",
                "queue_error": str(error),
                "queue_failed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(error),
            }

            # Save failed queue status.
            update_document_metadata(document_id, queue_failed_update)

            # Return a clean Swagger error.
            #
            # This tells us:
            # Upload succeeded, but SQS job creation failed.
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
    #
    # Because DocumentUploadResponse includes SQS fields,
    # FastAPI will show them in Swagger response.
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status=document_metadata["status"],
        message=(
            "PDF uploaded successfully and queued for background processing."
            if document_metadata["status"] == "queued"
            else "PDF uploaded successfully."
        ),
        file_path=str(saved_file_path),
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        s3_uri=s3_uri,
        s3_upload_status=s3_upload_status,
        sqs_message_id=document_metadata.get("sqs_message_id"),
        sqs_queue_name=document_metadata.get("sqs_queue_name"),
        sqs_send_status=document_metadata.get("sqs_send_status"),
        queued_at=document_metadata.get("queued_at"),
    )


# Create GET API to list all uploaded documents.
@router.get("", response_model=DocumentListResponse)
def list_documents():
    """
    List all uploaded documents from metadata storage.

    Your metadata_service decides the actual source:
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


# Create GET API to fetch one document by ID.
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


# Create POST API to extract text from uploaded PDF.
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
        # Update status to extracting.
        update_document_metadata(
            document_id,
            {
                "status": "extracting",
                "error_message": None,
            },
        )

        # Ensure PDF exists locally.
        # If local PDF is missing, this downloads it from S3.
        pdf_path = ensure_pdf_available_locally(document)

        # Extract text from PDF.
        # We pass pdf_path as a positional argument because
        # extract_text_from_pdf() does not have a parameter named "pdf_path".
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

        # Update metadata after successful extraction.
        update_document_metadata(
            document_id,
            {
                "status": "extracted",
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
            status="extracted",
            page_count=extraction_result["page_count"],
            extracted_text_path=extraction_result["extracted_text_path"],
            message="Text extracted successfully.",
            extracted_text_s3_key=extracted_text_s3_key,
            extracted_text_s3_uri=extracted_text_s3_uri,
            extracted_text_s3_upload_status=extracted_text_s3_upload_status,
        )

    except Exception as error:
        # Update status to failed if extraction fails.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error),
            },
        )

        # Return clean 500 error.
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(error)}",
        )


# Create POST API to create chunks from extracted text.
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
    # We allow either local path or S3 key/URI, because local file may be missing.
    if document.get("extracted_text_path") is None and document.get("extracted_text_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Text extraction must be completed before chunking.",
        )

    try:
        # Update status to chunking.
        update_document_metadata(
            document_id,
            {
                "status": "chunking",
                "error_message": None,
            },
        )

        # Ensure extracted_text.json exists locally.
        # If local extracted_text.json is missing, this downloads it from S3.
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

        # Update metadata after successful chunking.
        update_document_metadata(
            document_id,
            {
                "status": "chunked",
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
            status="chunked",
            chunk_count=chunking_result["chunk_count"],
            chunks_path=chunking_result["chunks_path"],
            message="Document chunked successfully.",
            chunks_s3_key=chunks_s3_key,
            chunks_s3_uri=chunks_s3_uri,
            chunks_s3_upload_status=chunks_s3_upload_status,
        )

    except Exception as error:
        # Update status to failed if chunking fails.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error),
            },
        )

        # Return clean 500 error.
        raise HTTPException(
            status_code=500,
            detail=f"Chunking failed: {str(error)}",
        )


# Create GET API to view chunks for a document.
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
    # We allow either local path or S3 key/URI, because local file may be missing.
    if document.get("chunks_path") is None and document.get("chunks_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks are not created yet.",
        )

    # Ensure chunks.json exists locally.
    # If local chunks.json is missing, this downloads it from S3.
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


# Create POST API to index document chunks into Pinecone.
@router.post("/{document_id}/index", response_model=DocumentIndexingResponse)
def index_document(document_id: str):
    """
    Index document chunks into Pinecone.

    S3 behavior:
    If local chunks.json is missing, recover it from S3.
    S3 is used as cloud storage backup for PDF/extracted text/chunks.
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
    # We allow either local path or S3 key/URI, because local file may be missing.
    if document.get("chunks_path") is None and document.get("chunks_s3_key") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks must be created before indexing.",
        )

    try:
        # Update document status to indexing.
        update_document_metadata(
            document_id,
            {
                "status": "indexing",
                "error_message": None,
            },
        )

        # Ensure chunks.json exists locally.
        # If local chunks.json is missing, this downloads it from S3.
        chunks_path = ensure_chunks_available_locally(document)

        # Load chunks from chunks.json.
        chunks_data = load_chunks(chunks_path)

        # Store chunk embeddings in Pinecone.
        indexing_result = index_document_chunks(chunks_data)

        # Update metadata after successful indexing.
        update_document_metadata(
            document_id,
            {
                "status": "indexed",
                "vector_count": indexing_result["vector_count"],
                "error_message": None,
            },
        )

        # Return clean response.
        return DocumentIndexingResponse(
            document_id=document_id,
            status="indexed",
            vector_count=indexing_result["vector_count"],
            message="Document chunks indexed successfully.",
        )

    except Exception as error:
        # Update status to failed if indexing fails.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error),
            },
        )

        # Return clean error.
        raise HTTPException(
            status_code=500,
            detail=f"Indexing failed: {str(error)}",
        )
