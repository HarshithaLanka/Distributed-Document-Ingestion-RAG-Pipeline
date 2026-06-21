# This file controls the shape of API responses.

# Import BaseModel from Pydantic.
from pydantic import BaseModel

# Import Optional for fields that may or may not exist.
from typing import Optional


# This model is used for the upload API response.
class DocumentUploadResponse(BaseModel):
    # Unique ID generated for the uploaded document.
    document_id: str

    # Original filename uploaded by the user.
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

    # Local path where PDF is saved.
    file_path: str

    # Current status: uploaded, extracting, extracted, or failed.
    status: str

    # Number of pages in the PDF.
    # Optional because before extraction, page_count does not exist.
    page_count: Optional[int] = None

    # Local path of extracted_text.json.
    # Optional because before extraction, this does not exist.
    extracted_text_path: Optional[str] = None

    # Error message if extraction fails.
    # Optional because successful documents do not need error message.
    error_message: Optional[str] = None


# This model is used when returning all uploaded documents.
class DocumentListResponse(BaseModel):
    # Total number of uploaded documents.
    total: int

    # List of document metadata records.
    documents: list[DocumentMetadata]


# This model is used for extraction API response.
class DocumentExtractionResponse(BaseModel):
    # Unique ID of the document.
    document_id: str

    # Current status after extraction.
    status: str

    # Number of pages extracted from PDF.
    page_count: int

    # Local path where extracted JSON is saved.
    extracted_text_path: str

    # Human-readable message.
    message: str