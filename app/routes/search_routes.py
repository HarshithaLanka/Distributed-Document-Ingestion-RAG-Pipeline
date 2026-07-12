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

# Import reranked search models.
from app.models.search_models import RerankedSearchRequest
from app.models.search_models import RerankedSearchResponse
from app.models.search_models import RerankedSearchResult

# Import vector search service.
from app.services.pinecone_service import search_similar_chunks

# Import BM25 keyword search service.
from app.services.bm25_service import search_document_with_bm25_as_dicts

# Import Week 14 hybrid search service.
from app.services.hybrid_retrieval_service import hybrid_search_document

# Import Week 14 reranking service.
from app.services.reranking_service import rerank_candidates


# Create search router.
router = APIRouter(
    # All routes in this file start with /search.
    prefix="/search",

    # Group name in Swagger UI.
    tags=["Search"],
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
            top_k=request.top_k,
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
            results=result_items,
        )

    except ValueError as error:
        # Return clean validation error.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        # Return clean error response.
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {str(error)}",
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
            top_k=request.top_k,
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
            results=result_items,
        )

    except FileNotFoundError as error:
        # This happens when redacted_chunks.json or chunks.json is missing.
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except ValueError as error:
        # This happens when query is empty or chunks format is invalid.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        # Return clean unexpected error response.
        raise HTTPException(
            status_code=500,
            detail=f"Keyword search failed: {str(error)}",
        )


# Create Week 14 hybrid search API.
@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid_search(request: HybridSearchRequest):
    """
    Search document chunks using Week 14 hybrid retrieval.

    Hybrid retrieval combines:
    - Pinecone vector search
    - BM25 keyword search
    - Neo4j graph retrieval

    Graph retrieval is optional and can be disabled in the request.
    """

    try:
        # Use graph weight only when graph retrieval is enabled.
        graph_weight = (
            request.graph_weight
            if request.include_graph
            else 0.0
        )

        # Calculate total active weight.
        total_weight = (
            request.vector_weight
            + request.keyword_weight
            + graph_weight
        )

        # At least one active retriever must have weight.
        if total_weight <= 0:
            raise ValueError(
                "At least one active retrieval weight must be greater than 0."
            )

        # Normalize weights so they add up to 1.
        vector_weight = request.vector_weight / total_weight
        keyword_weight = request.keyword_weight / total_weight
        normalized_graph_weight = graph_weight / total_weight

        # Run Week 14 hybrid retrieval.
        results = hybrid_search_document(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            graph_weight=normalized_graph_weight,
            include_graph=request.include_graph,
        )

        # Convert dictionaries into response models.
        result_items = [
            HybridSearchResult(**result)
            for result in results
        ]

        # Return clean hybrid search response.
        return HybridSearchResponse(
            document_id=request.document_id,
            query=request.query,
            result_count=len(result_items),
            results=result_items,
        )

    except FileNotFoundError as error:
        # This happens when BM25 chunk files are missing.
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except ValueError as error:
        # This happens for empty query or invalid weights.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        # Return clean unexpected error response.
        raise HTTPException(
            status_code=500,
            detail=f"Hybrid search failed: {str(error)}",
        )


# Create Week 14 reranked search API.
@router.post("/reranked", response_model=RerankedSearchResponse)
def reranked_search(request: RerankedSearchRequest):
    """
    Search document chunks and rerank the final candidates.

    Flow:
    1. Retrieve a wider candidate pool.
    2. Combine vector, BM25, and optional graph results.
    3. Rerank candidates using relevance signals.
    4. Return only the strongest final chunks.

    This endpoint is useful for debugging retrieval quality before QA.
    """

    try:
        # Use graph weight only when graph retrieval is enabled.
        graph_weight = (
            request.graph_weight
            if request.include_graph
            else 0.0
        )

        # Calculate active total weight.
        total_weight = (
            request.vector_weight
            + request.keyword_weight
            + graph_weight
        )

        # At least one active retrieval source is required.
        if total_weight <= 0:
            raise ValueError(
                "At least one active retrieval weight must be greater than 0."
            )

        # Normalize weights.
        vector_weight = request.vector_weight / total_weight
        keyword_weight = request.keyword_weight / total_weight
        normalized_graph_weight = graph_weight / total_weight

        # Retrieve a larger candidate pool first.
        candidates = hybrid_search_document(
            document_id=request.document_id,
            query=request.query,
            top_k=request.candidate_top_k,
            vector_top_k=min(request.candidate_top_k, 20),
            keyword_top_k=min(request.candidate_top_k, 20),
            graph_top_k=min(request.candidate_top_k, 10),
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            graph_weight=normalized_graph_weight,
            include_graph=request.include_graph,
        )

        # Rerank the candidate pool.
        reranked_results = rerank_candidates(
            question=request.query,
            candidates=candidates,
            final_top_k=request.final_top_k,
        )

        # Convert dictionaries into response models.
        result_items = [
            RerankedSearchResult(**result)
            for result in reranked_results
        ]

        # Return clean reranked response.
        return RerankedSearchResponse(
            document_id=request.document_id,
            query=request.query,
            result_count=len(result_items),
            results=result_items,
        )

    except FileNotFoundError as error:
        # This happens when BM25 chunk files are missing.
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except ValueError as error:
        # This happens for empty query or invalid weights.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        # Return clean unexpected error response.
        raise HTTPException(
            status_code=500,
            detail=f"Reranked search failed: {str(error)}",
        )