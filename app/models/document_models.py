# This file controls the shape of API responses.

# Import BaseModel from Pydantic.
# BaseModel lets us create structured request/response models.
from pydantic import BaseModel


# This model is used for the upload API response.
class DocumentUploadResponse(BaseModel):
    # Unique ID generated for the uploaded document.
    document_id: str

    # Original filename uploaded by the user.
    filename: str

    # Current document status.
    status: str

    # Human-readable message for the user.
    message: str


# This model represents one document metadata record.
class DocumentMetadata(BaseModel):
    # Unique ID of the document.
    document_id: str

    # Original uploaded filename.
    filename: str

    # Local path where the PDF is saved.
    file_path: str

    # Current status of the document.
    status: str


# This model is used when returning all uploaded documents.
class DocumentListResponse(BaseModel):
    # Total number of uploaded documents.
    total: int

    # List of document metadata records.
    documents: list[DocumentMetadata]