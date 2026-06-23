# This file contains Q&A API routes.

# Import APIRouter to create route group.
from fastapi import APIRouter

# Import HTTPException for clean API errors.
from fastapi import HTTPException

# Import QA request and response models.
from app.models.qa_models import QARequest
from app.models.qa_models import QAResponse
from app.models.qa_models import Citation

# Import metadata service to check if document exists.
from app.services.metadata_service import get_document_by_id

# Import RAG service.
from app.services.qa_service import answer_question_from_document


# Create QA router.
router = APIRouter(
    # Route prefix.
    prefix="/qa",

    # Swagger group name.
    tags=["Q&A"]
)


# Create Q&A endpoint.
@router.post("", response_model=QAResponse)
def ask_question(request: QARequest):
    # Validate top_k value.
    if request.top_k < 1 or request.top_k > 10:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 10."
        )

    # Check if document exists in metadata.
    document = get_document_by_id(request.document_id)

    # If document is not found, return 404.
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Check if document is indexed in Pinecone.
    if document.get("status") != "indexed":
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before Q&A."
        )

    try:
        # Run full RAG Q&A flow.
        result = answer_question_from_document(
    document_id=request.document_id,
    question=request.question,
    top_k=request.top_k,
    min_score=request.min_score
)

        # Convert citation dictionaries into Citation models.
        citation_items = [
            Citation(**citation)
            for citation in result["citations"]
        ]

        # Return final Q&A response.
        return QAResponse(
            document_id=request.document_id,
            question=request.question,
            answer=result["answer"],
            citations=citation_items
        )

    except Exception as error:
        # Return clean error response.
        raise HTTPException(
            status_code=500,
            detail=f"Q&A failed: {str(error)}"
        )