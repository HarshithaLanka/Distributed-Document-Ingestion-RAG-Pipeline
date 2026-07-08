"""
Entity routes for Document_Intelligence_RAG.

Week 12 purpose:
- Expose Neo4j entities through FastAPI.
- Add endpoint:
    GET /documents/{document_id}/entities

This route reads from Neo4j.
It does not extract entities again.
Entity extraction and graph writing happen in the worker later.
"""

# Import APIRouter to create route group.
from fastapi import APIRouter

# Import HTTPException to return clean API errors.
from fastapi import HTTPException

# Import status so we can use readable HTTP status codes.
from fastapi import status

# Import response model.
from app.models.entity_models import DocumentEntitiesResponse

# Import Neo4j service functions.
from app.services.neo4j_service import get_entities_for_document
from app.services.neo4j_service import is_neo4j_enabled


# Create router.
# prefix="/documents" means every route in this file starts with /documents.
# tags=["entities"] groups this endpoint nicely in Swagger.
router = APIRouter(
    prefix="/documents",
    tags=["entities"],
)


@router.get(
    "/{document_id}/entities",
    response_model=DocumentEntitiesResponse,
    summary="Get entities for a document",
    description="Returns entities extracted from a document and stored in Neo4j.",
)
def get_document_entities(document_id: str) -> DocumentEntitiesResponse:
    """
    Get summarized entities for one document.

    API:
        GET /documents/{document_id}/entities

    Example:
        GET /documents/doc_graph_test_123/entities

    Simple meaning:
        Read Neo4j and show all people, organizations, dates,
        locations, products, etc. found in this document.
    """

    # Validate document_id.
    # If user passes empty spaces, return a clean 400 error.
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id is required.",
        )

    # Check if Neo4j is enabled in .env.
    # This avoids confusing errors if user forgot NEO4J_ENABLED=true.
    if not is_neo4j_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j is disabled. Set NEO4J_ENABLED=true in .env.",
        )

    try:
        # Fetch entities from Neo4j.
        entities = get_entities_for_document(document_id=document_id)

    except Exception as exc:
        # Return a clean API error instead of crashing Swagger.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entities from Neo4j: {str(exc)}",
        ) from exc

    # Return response in clean format.
    return DocumentEntitiesResponse(
        document_id=document_id,
        entity_count=len(entities),
        entities=entities,
    )