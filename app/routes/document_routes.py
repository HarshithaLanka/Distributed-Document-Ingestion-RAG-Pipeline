"""
This file contains document APIs:

POST /documents/upload
GET /documents
GET /documents/{document_id}
POST /documents/{document_id}/extract
POST /documents/{document_id}/chunk
GET /documents/{document_id}/chunks

The route receives requests, but it does not directly manage file storage,
PDF parsing, metadata updates, or chunking logic.
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
from app.models.document_models import DocumentChunkingResponse
from app.models.document_models import DocumentChunksResponse
from app.models.document_models import DocumentChunk
from app.models.document_models import DocumentIndexingResponse
from app.services.pinecone_service import index_document_chunks
from app.services.chunking_service import load_chunks

# Import ID generator function.
from app.utils.id_generator import generate_document_id

# Import storage service.
from app.services.storage_service import save_pdf_locally

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
    # Check if uploaded filename ends with .pdf.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Check if uploaded file content type is PDF.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a valid PDF."
        )

    # Generate a unique document ID.
    document_id = generate_document_id()

    # Save uploaded PDF locally.
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

    # Return clean upload response.
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

    # Convert each dictionary into DocumentMetadata model.
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
    # Search document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Return matching document.
    return DocumentMetadata(**document)


# Create POST API to extract text from uploaded PDF.
@router.post("/{document_id}/extract", response_model=DocumentExtractionResponse)
def extract_document(document_id: str):
    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    try:
        # Update status to extracting.
        update_document_metadata(
            document_id,
            {
                "status": "extracting",
                "error_message": None
            }
        )

        # Extract text from PDF.
        extraction_result = extract_text_from_pdf(
            file_path=document["file_path"],
            document_id=document_id
        )

        # Update metadata after successful extraction.
        update_document_metadata(
            document_id,
            {
                "status": "extracted",
                "page_count": extraction_result["page_count"],
                "extracted_text_path": extraction_result["extracted_text_path"],
                "error_message": None
            }
        )

        # Return extraction response.
        return DocumentExtractionResponse(
            document_id=document_id,
            status="extracted",
            page_count=extraction_result["page_count"],
            extracted_text_path=extraction_result["extracted_text_path"],
            message="Text extracted successfully."
        )

    except Exception as error:
        # Update status to failed if extraction fails.
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


# Create POST API to create chunks from extracted text.
@router.post("/{document_id}/chunk", response_model=DocumentChunkingResponse)
def chunk_document(document_id: str):
    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Check if text extraction has already happened.
    if document.get("extracted_text_path") is None:
        raise HTTPException(
            status_code=400,
            detail="Text extraction must be completed before chunking."
        )

    try:
        # Update status to chunking.
        update_document_metadata(
            document_id,
            {
                "status": "chunking",
                "error_message": None
            }
        )

        # Create chunks from extracted_text.json.
        chunking_result = create_chunks_from_extracted_text(
            extracted_text_path=document["extracted_text_path"],
            document_id=document_id,
            chunk_size=150,
            overlap=30
        )

        # Update metadata after successful chunking.
        update_document_metadata(
            document_id,
            {
                "status": "chunked",
                "chunk_count": chunking_result["chunk_count"],
                "chunks_path": chunking_result["chunks_path"],
                "error_message": None
            }
        )

        # Return clean chunking response.
        return DocumentChunkingResponse(
            document_id=document_id,
            status="chunked",
            chunk_count=chunking_result["chunk_count"],
            chunks_path=chunking_result["chunks_path"],
            message="Document chunked successfully."
        )

    except Exception as error:
        # Update status to failed if chunking fails.
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
            detail=f"Chunking failed: {str(error)}"
        )


# Create GET API to view chunks for a document.
@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(document_id: str):
    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Check if chunks are already created.
    if document.get("chunks_path") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks are not created yet."
        )

    # Load chunks from chunks.json.
    chunks_data = load_chunks(document["chunks_path"])

    # Convert chunk dictionaries into DocumentChunk models.
    chunk_items = [
        DocumentChunk(**chunk)
        for chunk in chunks_data["chunks"]
    ]

    # Return chunks response.
    return DocumentChunksResponse(
        document_id=document_id,
        chunk_count=chunks_data["chunk_count"],
        chunks=chunk_items
    )
    
    
# Create POST API to index document chunks into Pinecone.
@router.post("/{document_id}/index", response_model=DocumentIndexingResponse)
def index_document(document_id: str):
    # Find document metadata using document_id.
    document = get_document_by_id(document_id)

    # If document does not exist, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Check if chunks are created before indexing.
    if document.get("chunks_path") is None:
        raise HTTPException(
            status_code=400,
            detail="Chunks must be created before indexing."
        )

    try:
        # Update document status to indexing.
        update_document_metadata(
            document_id,
            {
                "status": "indexing",
                "error_message": None
            }
        )

        # Load chunks from chunks.json.
        chunks_data = load_chunks(document["chunks_path"])

        # Store chunk embeddings in Pinecone.
        indexing_result = index_document_chunks(chunks_data)

        # Update metadata after successful indexing.
        update_document_metadata(
            document_id,
            {
                "status": "indexed",
                "vector_count": indexing_result["vector_count"],
                "error_message": None
            }
        )

        # Return clean response.
        return DocumentIndexingResponse(
            document_id=document_id,
            status="indexed",
            vector_count=indexing_result["vector_count"],
            message="Document chunks indexed successfully."
        )

    except Exception as error:
        # Update status to failed if indexing fails.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error)
            }
        )

        # Return clean error.
        raise HTTPException(
            status_code=500,
            detail=f"Indexing failed: {str(error)}"
        )