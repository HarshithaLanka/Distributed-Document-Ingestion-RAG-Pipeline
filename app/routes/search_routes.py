# This file contains search-related APIs.

# Import APIRouter to create search routes.
from fastapi import APIRouter

# Import HTTPException to return clean errors.
from fastapi import HTTPException

# Import vector search models.
from app.models.search_models import VectorSearchRequest
from app.models.search_models import VectorSearchResponse
from app.models.search_models import VectorSearchResult

# Import keyword search models.
from app.models.search_models import KeywordSearchRequest
from app.models.search_models import KeywordSearchResponse
from app.models.search_models import KeywordSearchResult

# Import hybrid search models.
from app.models.search_models import HybridSearchRequest
from app.models.search_models import HybridSearchResponse
from app.models.search_models import HybridSearchResult

# Import vector search service.
from app.services.pinecone_service import search_similar_chunks

# Import BM25 keyword search service.
from app.services.bm25_service import search_document_with_bm25_as_dicts

# Import hybrid search service.
from app.services.hybrid_retrieval_service import hybrid_search_document


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
    """
    Search document chunks using Pinecone vector search.
    """

    try:
        # Search similar chunks using Pinecone.
        results = search_similar_chunks(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k
        )

        # Convert result dictionaries into Pydantic response models.
        result_items = [
            VectorSearchResult(**result)
            for result in results
        ]

        # Return clean vector search response.
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


# Create BM25 keyword search API.
@router.post("/keyword", response_model=KeywordSearchResponse)
def keyword_search(request: KeywordSearchRequest):
    """
    Search document chunks using BM25 keyword search.
    """

    try:
        # Search document chunks using BM25.
        results = search_document_with_bm25_as_dicts(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k
        )

        # Convert result dictionaries into Pydantic response models.
        result_items = [
            KeywordSearchResult(**result)
            for result in results
        ]

        # Return clean keyword search response.
        return KeywordSearchResponse(
            document_id=request.document_id,
            query=request.query,
            result_count=len(result_items),
            results=result_items
        )

    except FileNotFoundError as error:
        # This happens when redacted_chunks.json or chunks.json is missing.
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except ValueError as error:
        # This happens when query is empty or chunks format is invalid.
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        # Return clean unexpected error response.
        raise HTTPException(
            status_code=500,
            detail=f"Keyword search failed: {str(error)}"
        )


# Create hybrid search API.
@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid_search(request: HybridSearchRequest):
    """
    Search document chunks using hybrid retrieval.

    Hybrid retrieval combines:
    - Pinecone vector search
    - BM25 keyword search

    This is useful because:
    - Vector search understands meaning.
    - BM25 catches exact words, names, acronyms, codes, and section numbers.
    """

    try:
        # Optional safety check.
        total_weight = request.vector_weight + request.keyword_weight

        # The weights should not both be zero.
        if total_weight == 0:
            raise ValueError("vector_weight and keyword_weight cannot both be 0.")

        # Normalize weights so they add up to 1.
        vector_weight = request.vector_weight / total_weight
        keyword_weight = request.keyword_weight / total_weight

        # Run hybrid retrieval.
        results = hybrid_search_document(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
        )

        # Convert result dictionaries into Pydantic response models.
        result_items = [
            HybridSearchResult(**result)
            for result in results
        ]

        # Return clean hybrid search response.
        return HybridSearchResponse(
            document_id=request.document_id,
            query=request.query,
            result_count=len(result_items),
            results=result_items
        )

    except FileNotFoundError as error:
        # This happens when BM25 chunks file is missing.
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except ValueError as error:
        # This happens for empty query or invalid weights.
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        # Return clean unexpected error response.
        raise HTTPException(
            status_code=500,
            detail=f"Hybrid search failed: {str(error)}"
        )