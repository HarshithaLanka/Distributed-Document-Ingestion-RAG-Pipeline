# app/models/document_models.py

"""
This file controls the shape of API responses.

Simple meaning:
FastAPI uses these Pydantic models to decide what JSON response should look like.

Week 9 updates added here:
- current_step
- progress_percentage
- retry_count
- uploaded_at
- started_at
- completed_at
- failed_at
- updated_at
- DocumentStatusResponse
- DocumentEventsResponse
"""

# Import Any for flexible details field in event response.
from typing import Any

# Import Optional for fields that may not exist in every stage.
from typing import Optional

# Import BaseModel from Pydantic.
# BaseModel helps us define clean API request/response structures.
from pydantic import BaseModel


# ---------------------------------------------------------
# Upload response model
# ---------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    """
    This model is used for POST /documents/upload response.
    """

    # Unique ID generated for uploaded document.
    document_id: str

    # Original filename uploaded by user.
    filename: str

    # Current document status.
    status: str

    # Human-readable message.
    message: str

    # Local file path where PDF is saved.
    file_path: Optional[str] = None

    # Current processing step.
    current_step: Optional[str] = None

    # Progress percentage for UI/status tracking.
    progress_percentage: Optional[int] = None

    # S3 bucket where the PDF is uploaded.
    s3_bucket: Optional[str] = None

    # S3 object key/path of uploaded PDF.
    s3_key: Optional[str] = None

    # Full readable S3 URI.
    s3_uri: Optional[str] = None

    # Shows success, failed, or disabled.
    s3_upload_status: Optional[str] = None

    # SQS message ID returned by AWS after sending the processing job.
    sqs_message_id: Optional[str] = None

    # SQS queue name where this document job was sent.
    sqs_queue_name: Optional[str] = None

    # Shows whether SQS sending succeeded, failed, or was disabled.
    sqs_send_status: Optional[str] = None

    # Time when this document was uploaded.
    uploaded_at: Optional[str] = None

    # Time when this document was queued for background processing.
    queued_at: Optional[str] = None


# ---------------------------------------------------------
# Document metadata model
# ---------------------------------------------------------

class DocumentMetadata(BaseModel):
    """
    This model represents one document metadata record.

    This is used for:
    GET /documents
    GET /documents/{document_id}
    """

    # Unique ID of the document.
    document_id: str

    # Original uploaded filename.
    filename: str

    # Local path where uploaded PDF is saved.
    file_path: str

    # Current status of document.
    status: str

    # Current step message.
    current_step: Optional[str] = None

    # Progress percentage.
    progress_percentage: Optional[int] = 0

    # Retry count for worker failures.
    retry_count: Optional[int] = 0

    # Number of pages in PDF after extraction.
    page_count: Optional[int] = None

    # Path where extracted page-level text JSON is saved locally.
    extracted_text_path: Optional[str] = None

    # Number of chunks created after chunking.
    chunk_count: Optional[int] = None

    # Path where chunks JSON is saved locally.
    chunks_path: Optional[str] = None

    # Number of vectors indexed in Pinecone.
    vector_count: Optional[int] = None

    # Error message if any processing step fails.
    error_message: Optional[str] = None

    # Time when PDF was uploaded.
    uploaded_at: Optional[str] = None

    # Time when SQS queued the job.
    queued_at: Optional[str] = None

    # Time when worker started processing.
    started_at: Optional[str] = None

    # Time when full processing completed.
    completed_at: Optional[str] = None

    # Time when processing failed.
    failed_at: Optional[str] = None

    # Time when metadata was last updated.
    updated_at: Optional[str] = None

    # S3 bucket where original PDF is uploaded.
    s3_bucket: Optional[str] = None

    # S3 key for original uploaded PDF.
    s3_key: Optional[str] = None

    # S3 URI for original uploaded PDF.
    s3_uri: Optional[str] = None

    # S3 upload status for original PDF.
    s3_upload_status: Optional[str] = None

    # S3 upload error message for original PDF, if any.
    s3_error_message: Optional[str] = None

    # S3 bucket for extracted_text.json.
    extracted_text_s3_bucket: Optional[str] = None

    # S3 key for extracted_text.json.
    extracted_text_s3_key: Optional[str] = None

    # S3 URI for extracted_text.json.
    extracted_text_s3_uri: Optional[str] = None

    # S3 upload status for extracted_text.json.
    extracted_text_s3_upload_status: Optional[str] = None

    # S3 upload error message for extracted_text.json, if any.
    extracted_text_s3_error_message: Optional[str] = None

    # S3 bucket for chunks.json.
    chunks_s3_bucket: Optional[str] = None

    # S3 key for chunks.json.
    chunks_s3_key: Optional[str] = None

    # S3 URI for chunks.json.
    chunks_s3_uri: Optional[str] = None

    # S3 upload status for chunks.json.
    chunks_s3_upload_status: Optional[str] = None

    # S3 upload error message for chunks.json, if any.
    chunks_s3_error_message: Optional[str] = None

    # SQS message ID created when upload API sends document_id to SQS.
    sqs_message_id: Optional[str] = None

    # SQS queue name used for this document processing job.
    sqs_queue_name: Optional[str] = None

    # SQS send status: success, failed, or disabled.
    sqs_send_status: Optional[str] = None

    # Error message if sending to SQS failed.
    queue_error: Optional[str] = None

    # Time when queue sending failed.
    queue_failed_at: Optional[str] = None


# ---------------------------------------------------------
# List documents response model
# ---------------------------------------------------------

class DocumentListResponse(BaseModel):
    """
    This model is used when returning all uploaded documents.
    """

    # Total number of documents.
    total: int

    # List of document metadata objects.
    documents: list[DocumentMetadata]


# ---------------------------------------------------------
# Extraction response model
# ---------------------------------------------------------

class DocumentExtractionResponse(BaseModel):
    """
    This model is used for extraction API response.
    """

    # Unique document ID.
    document_id: str

    # Current status after extraction.
    status: str

    # Total page count found in PDF.
    page_count: int

    # Local path where extracted_text.json is saved.
    extracted_text_path: str

    # Human-readable message.
    message: str

    # S3 key for extracted_text.json.
    extracted_text_s3_key: Optional[str] = None

    # S3 URI for extracted_text.json.
    extracted_text_s3_uri: Optional[str] = None

    # S3 upload status for extracted_text.json.
    extracted_text_s3_upload_status: Optional[str] = None


# ---------------------------------------------------------
# Chunk model
# ---------------------------------------------------------

class DocumentChunk(BaseModel):
    """
    This model represents one chunk.
    """

    # Unique chunk ID.
    chunk_id: str

    # Document ID this chunk belongs to.
    document_id: str

    # Page number where this chunk came from.
    page_number: int

    # Actual chunk text.
    text: str

    # Number of words in this chunk.
    word_count: int


# ---------------------------------------------------------
# Chunking response model
# ---------------------------------------------------------

class DocumentChunkingResponse(BaseModel):
    """
    This model is used for chunking API response.
    """

    # Unique document ID.
    document_id: str

    # Status after chunking.
    status: str

    # Total number of chunks created.
    chunk_count: int

    # Local path where chunks.json is saved.
    chunks_path: str

    # Human-readable message.
    message: str

    # S3 key for chunks.json.
    chunks_s3_key: Optional[str] = None

    # S3 URI for chunks.json.
    chunks_s3_uri: Optional[str] = None

    # S3 upload status for chunks.json.
    chunks_s3_upload_status: Optional[str] = None


# ---------------------------------------------------------
# Chunks list response model
# ---------------------------------------------------------

class DocumentChunksResponse(BaseModel):
    """
    This model is used when returning all chunks for one document.
    """

    # Unique document ID.
    document_id: str

    # Total number of chunks.
    chunk_count: int

    # List of chunks.
    chunks: list[DocumentChunk]


# ---------------------------------------------------------
# Indexing response model
# ---------------------------------------------------------

class DocumentIndexingResponse(BaseModel):
    """
    This model is used when document chunks are indexed in Pinecone.
    """

    # Unique document ID.
    document_id: str

    # Current status after indexing.
    status: str

    # Number of vectors stored in Pinecone.
    vector_count: int

    # Human-readable message.
    message: str


# ---------------------------------------------------------
# Week 9 status response model
# ---------------------------------------------------------

class DocumentStatusResponse(BaseModel):
    """
    This model is used for:
    GET /documents/{document_id}/status

    It gives the current live processing status.
    """

    # Unique document ID.
    document_id: str

    # Original filename.
    filename: Optional[str] = None

    # Current status.
    status: Optional[str] = None

    # Current human-readable step.
    current_step: Optional[str] = None

    # Progress percentage.
    progress_percentage: int = 0

    # How many times this document failed/retried.
    retry_count: int = 0

    # Error message if failed.
    error_message: Optional[str] = None

    # Upload timestamp.
    uploaded_at: Optional[str] = None

    # Queue timestamp.
    queued_at: Optional[str] = None

    # Worker start timestamp.
    started_at: Optional[str] = None

    # Completion timestamp.
    completed_at: Optional[str] = None

    # Failure timestamp.
    failed_at: Optional[str] = None

    # Last updated timestamp.
    updated_at: Optional[str] = None


# ---------------------------------------------------------
# Week 9 event item model
# ---------------------------------------------------------

class DocumentEventItem(BaseModel):
    """
    This model represents one event in the document timeline.
    """

    # Document ID this event belongs to.
    document_id: str

    # Event ID.
    event_id: str

    # Event type.
    event_type: str

    # Human-readable event message.
    message: str

    # Event creation time.
    created_at: str

    # Optional status at event time.
    status: Optional[str] = None

    # Optional current step at event time.
    current_step: Optional[str] = None

    # Optional progress at event time.
    progress_percentage: Optional[int] = None

    # Optional extra event details.
    details: Optional[dict[str, Any]] = None


# ---------------------------------------------------------
# Week 9 events response model
# ---------------------------------------------------------

class DocumentEventsResponse(BaseModel):
    """
    This model is used for:
    GET /documents/{document_id}/events

    It gives the full document processing timeline.
    """

    # Unique document ID.
    document_id: str

    # Total number of events.
    event_count: int

    # List of events.
    events: list[DocumentEventItem]