# This file defines request and response models for search APIs.

# Import BaseModel from Pydantic.
from pydantic import BaseModel


# This model defines the request body for vector search.
class VectorSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User's search question.
    query: str

    # Number of matching chunks to return.
    top_k: int = 3


# This model represents one vector search result.
class VectorSearchResult(BaseModel):
    # Matching chunk ID.
    chunk_id: str

    # Page number where the chunk came from.
    page_number: int

    # Similarity score returned by Pinecone.
    score: float

    # Source text from the matching chunk.
    text: str


# This model defines vector search response.
class VectorSearchResponse(BaseModel):
    # Document ID searched.
    document_id: str

    # Original query.
    query: str

    # Number of results requested.
    top_k: int

    # Matching chunks.
    results: list[VectorSearchResult]