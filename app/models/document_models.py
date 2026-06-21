# This file controls the shape of API responses.

# Import BaseModel from Pydantic.
# BaseModel helps us define clean API request/response structures.
from pydantic import BaseModel

# Import Optional for fields that may not exist in every stage.
from typing import Optional


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

    # Path where extracted page-level text JSON is saved.
    extracted_text_path: Optional[str] = None

    # Number of chunks created after chunking.
    chunk_count: Optional[int] = None

    # Path where chunks JSON is saved.
    chunks_path: Optional[str] = None

    # Error message if any processing step fails.
    error_message: Optional[str] = None
    
    # Number of vectors indexed in Pinecone.
vector_count: Optional[int] = None


# This model is used when returning all uploaded documents.
class DocumentListResponse(BaseModel):
    # Total number of documents.
    total: int

    # List of document metadata objects.
    documents: list[DocumentMetadata]


# This model is used for extraction API response.
class DocumentExtractionResponse(BaseModel):
    # Unique document ID.
    document_id: str

    # Status after extraction.
    status: str

    # Total pages extracted.
    page_count: int

    # Path of extracted_text.json.
    extracted_text_path: str

    # Human-readable message.
    message: str


# This model represents one chunk.
class DocumentChunk(BaseModel):
    # Unique chunk ID.
    chunk_id: str

    # Document ID to which this chunk belongs.
    document_id: str

    # Page number from which this chunk came.
    page_number: int

    # Actual chunk text.
    text: str

    # Number of words inside this chunk.
    word_count: int


# This model is used for chunking API response.
class DocumentChunkingResponse(BaseModel):
    # Unique document ID.
    document_id: str

    # Status after chunking.
    status: str

    # Total number of chunks created.
    chunk_count: int

    # Path where chunks.json is saved.
    chunks_path: str

    # Human-readable message.
    message: str


# This model is used when returning all chunks for one document.
class DocumentChunksResponse(BaseModel):
    # Unique document ID.
    document_id: str

    # Total number of chunks.
    chunk_count: int

    # List of chunks.
    chunks: list[DocumentChunk]
    


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