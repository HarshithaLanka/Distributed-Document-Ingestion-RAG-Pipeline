# This file controls the shape of API responses.

# Import BaseModel from Pydantic.
# BaseModel helps us define clean API request/response structures.
from pydantic import BaseModel

# Import Optional for fields that may not exist in every stage.
from typing import Optional


# ---------------------------------------------------------
# Upload response model
# ---------------------------------------------------------

# This model is used for the upload API response.
class DocumentUploadResponse(BaseModel):
    # Unique ID generated for uploaded document.
    document_id: str

    # Original filename uploaded by user.
    filename: str

    # Current document status.
    status: str

    # Human-readable message.
    message: str

    # Local file path where PDF is saved.
    # Optional because older local-only responses may not have it.
    file_path: Optional[str] = None

    # S3 bucket where the PDF is uploaded.
    # Optional because S3 may be disabled.
    s3_bucket: Optional[str] = None

    # S3 object key/path of uploaded PDF.
    # Example: documents/doc_123/resume.pdf
    s3_key: Optional[str] = None

    # Full readable S3 URI.
    # Example: s3://bucket-name/documents/doc_123/resume.pdf
    s3_uri: Optional[str] = None

    # Shows success, failed, or disabled.
    s3_upload_status: Optional[str] = None


# ---------------------------------------------------------
# Document metadata model
# ---------------------------------------------------------

# This model represents one document metadata record.
class DocumentMetadata(BaseModel):
    # Unique ID of the document.
    document_id: str

    # Original uploaded filename.
    filename: str

    # Local path where uploaded PDF is saved.
    file_path: str

    # Current status of document.
    status: str

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


# ---------------------------------------------------------
# List documents response model
# ---------------------------------------------------------

# This model is used when returning all uploaded documents.
class DocumentListResponse(BaseModel):
    # Total number of documents.
    total: int

    # List of document metadata objects.
    documents: list[DocumentMetadata]


# ---------------------------------------------------------
# Extraction response model
# ---------------------------------------------------------

# This model is used for extraction API response.
class DocumentExtractionResponse(BaseModel):
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

# This model represents one chunk.
class DocumentChunk(BaseModel):
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

# This model is used for chunking API response.
class DocumentChunkingResponse(BaseModel):
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

# This model is used when returning all chunks for one document.
class DocumentChunksResponse(BaseModel):
    # Unique document ID.
    document_id: str

    # Total number of chunks.
    chunk_count: int

    # List of chunks.
    chunks: list[DocumentChunk]


# ---------------------------------------------------------
# Indexing response model
# ---------------------------------------------------------

# This model is used when document chunks are indexed in Pinecone.
class DocumentIndexingResponse(BaseModel):
    # Unique document ID.
    document_id: str

    # Current status after indexing.
    status: str

    # Number of vectors stored in Pinecone.
    vector_count: int

    # Human-readable message.
    message: str