"""
This file contains the actual document APIs:

POST /documents/upload
GET /documents
GET /documents/{document_id}

The route receives requests, but it does not directly manage files or JSON logic.
It calls services.
"""

# Import APIRouter to create a separate group of document-related APIs.
from fastapi import APIRouter

# Import UploadFile and File to receive uploaded files.
from fastapi import UploadFile, File

# Import HTTPException to return clean error responses.
from fastapi import HTTPException

# Import response models.
from app.models.document_models import DocumentUploadResponse
from app.models.document_models import DocumentListResponse
from app.models.document_models import DocumentMetadata
from app.models.document_models import DocumentExtractionResponse
from app.services.metadata_service import update_document_metadata
from app.services.pdf_parser_service import extract_text_from_pdf

# Import ID generator function.
from app.utils.id_generator import generate_document_id

# Import storage service.
from app.services.storage_service import save_pdf_locally

# Import metadata service functions.
from app.services.metadata_service import add_document_metadata
from app.services.metadata_service import load_documents
from app.services.metadata_service import get_document_by_id


# Create a router for document APIs.
router = APIRouter(
    # Prefix means all routes in this file will start with /documents.
    prefix="/documents",

    # Tags help group APIs nicely in Swagger UI.
    tags=["Documents"]
)


# Create POST API for uploading a document.
@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...)):
    # Check if the uploaded filename ends with .pdf.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Check if the uploaded file content type is PDF.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a valid PDF."
        )

    # Generate a unique document ID.
    document_id = generate_document_id()

    # Save the uploaded PDF locally.
    saved_file_path = save_pdf_locally(file, document_id)

    # Create metadata record for this document.
    document_metadata = {
        "document_id": document_id,
        "filename": file.filename,
        "file_path": saved_file_path,
        "status": "uploaded"
    }

    # Save metadata in local JSON file.
    add_document_metadata(document_metadata)

    # Return clean response to the user.
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="uploaded",
        message="PDF uploaded successfully."
    )


# Create GET API to list all uploaded documents.
@router.get("", response_model=DocumentListResponse)
def list_documents():
    # Load all documents from local JSON.
    documents = load_documents()

    # Convert each dictionary into a DocumentMetadata model.
    document_items = [
        DocumentMetadata(**document)
        for document in documents
    ]

    # Return total count and documents list.
    return DocumentListResponse(
        total=len(document_items),
        documents=document_items
    )


# Create GET API to fetch one document by ID.
@router.get("/{document_id}", response_model=DocumentMetadata)
def get_document(document_id: str):
    # Search for document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404 Not Found.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Return the matching document.
    return DocumentMetadata(**document)
# Create POST API to extract text from an uploaded PDF.
@router.post("/{document_id}/extract", response_model=DocumentExtractionResponse)
def extract_document(document_id: str):
    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404 error.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    try:
        # Update document status to extracting.
        update_document_metadata(
            document_id,
            {
                "status": "extracting",
                "error_message": None
            }
        )

        # Extract text from PDF using parser service.
        extraction_result = extract_text_from_pdf(
            file_path=document["file_path"],
            document_id=document_id
        )

        # Update document metadata after successful extraction.
        update_document_metadata(
            document_id,
            {
                "status": "extracted",
                "page_count": extraction_result["page_count"],
                "extracted_text_path": extraction_result["extracted_text_path"],
                "error_message": None
            }
        )

        # Return clean response.
        return DocumentExtractionResponse(
            document_id=document_id,
            status="extracted",
            page_count=extraction_result["page_count"],
            extracted_text_path=extraction_result["extracted_text_path"],
            message="Text extracted successfully."
        )

    except Exception as error:
        # If anything fails, update status to failed.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error)
            }
        )

        # Return clean 500 error.
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(error)}"
        )