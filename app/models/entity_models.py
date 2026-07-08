"""
Entity response models for Document_Intelligence_RAG.

Week 12 purpose:
- Define the response shape for entity APIs.
- These models are used by FastAPI to return clean Swagger responses.

New word:
Pydantic model means a Python class that describes the structure of request/response JSON.
"""

# Import List because some fields are lists.
from typing import List

# Import BaseModel and Field from Pydantic.
# BaseModel creates structured API response models.
# Field lets us add examples/descriptions/default values.
from pydantic import BaseModel, Field


class EntitySummary(BaseModel):
    """
    One summarized entity found in a document.

    Example:
    Andhra University may appear 3 times across 2 pages.
    This model represents that summary.
    """

    # Original entity name as it should be shown to user.
    name: str = Field(
        ...,
        description="Entity name found in the document.",
        example="Andhra University",
    )

    # Lowercase normalized form used internally for deduplication.
    normalized_text: str = Field(
        ...,
        description="Normalized lowercase entity text.",
        example="andhra university",
    )

    # Entity type/label detected by spaCy.
    label: str = Field(
        ...,
        description="Entity label such as PERSON, ORG, GPE, DATE, PRODUCT.",
        example="ORG",
    )

    # Number of times this entity was mentioned.
    mention_count: int = Field(
        ...,
        description="How many times this entity was mentioned in the document.",
        example=3,
    )

    # Pages where this entity appeared.
    pages: List[int] = Field(
        default_factory=list,
        description="Page numbers where this entity appeared.",
        example=[1, 2],
    )

    # Chunk IDs where this entity appeared.
    chunk_ids: List[str] = Field(
        default_factory=list,
        description="Chunk IDs where this entity appeared.",
        example=["chunk_1", "chunk_2"],
    )

    # Section titles where this entity appeared.
    sections: List[str] = Field(
        default_factory=list,
        description="Section titles where this entity appeared.",
        example=["Introduction", "Professor Details"],
    )


class DocumentEntitiesResponse(BaseModel):
    """
    Response model for:
    GET /documents/{document_id}/entities
    """

    # Document ID requested by user.
    document_id: str = Field(
        ...,
        description="Document ID whose entities are returned.",
        example="doc_graph_test_123",
    )

    # Total number of unique summarized entities.
    entity_count: int = Field(
        ...,
        description="Number of unique entities found for this document.",
        example=8,
    )

    # List of summarized entities.
    entities: List[EntitySummary] = Field(
        default_factory=list,
        description="Entities found in this document.",
    )