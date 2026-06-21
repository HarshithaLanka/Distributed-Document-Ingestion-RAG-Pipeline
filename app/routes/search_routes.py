# This file contains search-related APIs.

# Import APIRouter to create search routes.
from fastapi import APIRouter

# Import HTTPException to return clean errors.
from fastapi import HTTPException

# Import search request and response models.
from app.models.search_models import VectorSearchRequest
from app.models.search_models import VectorSearchResponse
from app.models.search_models import VectorSearchResult

# Import vector search service.
from app.services.pinecone_service import search_similar_chunks


# Create search router.
router = APIRouter(
    # All routes in this file start with /search.
    prefix="/search",

    # Group name in Swagger UI.
    tags=["Search"]
)


# Create vector search API.
@router.post("/vector", response_model=VectorSearchResponse)
def vector_search(request: VectorSearchRequest):
    # Validate top_k.
    if request.top_k < 1 or request.top_k > 10:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 10."
        )

    try:
        # Search similar chunks using Pinecone.
        results = search_similar_chunks(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k
        )

        # Convert result dictionaries into Pydantic models.
        result_items = [
            VectorSearchResult(**result)
            for result in results
        ]

        # Return clean response.
        return VectorSearchResponse(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k,
            results=result_items
        )

    except Exception as error:
        # Return clean error response.
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {str(error)}"
        )