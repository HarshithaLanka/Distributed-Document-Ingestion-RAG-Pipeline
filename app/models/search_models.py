# This file defines request and response models for search APIs.

# Import BaseModel from Pydantic.
from pydantic import BaseModel

# Import Field from Pydantic.
from pydantic import Field

# Import Optional because some metadata fields may be missing.
from typing import Optional

# Import List because responses return lists.
from typing import List


# This model defines the request body for vector search.
class VectorSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User's search question.
    query: str

    # Number of matching chunks to return.
    top_k: int = Field(default=3, ge=1, le=10)


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

    # Optional section title.
    section_title: Optional[str] = None

    # Optional content type.
    content_type: Optional[str] = None

    # Optional parser used.
    parser_used: Optional[str] = None


# This model defines vector search response.
class VectorSearchResponse(BaseModel):
    # Document ID searched.
    document_id: str

    # Original query.
    query: str

    # Number of results requested.
    top_k: int

    # Matching chunks.
    results: List[VectorSearchResult]


# This model defines the request body for BM25 keyword search.
class KeywordSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User's keyword search question.
    query: str

    # Number of matching chunks to return.
    top_k: int = Field(default=5, ge=1, le=20)


# This model represents one BM25 keyword search result.
class KeywordSearchResult(BaseModel):
    # Document ID of the matched chunk.
    document_id: str

    # Matching chunk ID.
    chunk_id: str

    # Matching chunk text.
    text: str

    # BM25 keyword score.
    score: float

    # Page number.
    page_number: Optional[int] = None

    # Section title.
    section_title: Optional[str] = None

    # Content type.
    content_type: Optional[str] = None

    # Parser used.
    parser_used: Optional[str] = None

    # Word count.
    word_count: Optional[int] = None


# This model defines BM25 keyword search response.
class KeywordSearchResponse(BaseModel):
    # Document ID searched.
    document_id: str

    # Original keyword query.
    query: str

    # Number of results returned.
    result_count: int

    # Matching BM25 keyword search results.
    results: List[KeywordSearchResult]


# This model defines the request body for hybrid search.
class HybridSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User query.
    query: str

    # Final number of merged results to return.
    top_k: int = Field(default=5, ge=1, le=20)

    # Weight for vector search.
    # 0.6 means vector search contributes 60% to final score.
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)

    # Weight for keyword search.
    # 0.4 means BM25 contributes 40% to final score.
    keyword_weight: float = Field(default=0.4, ge=0.0, le=1.0)


# This model represents one hybrid search result.
class HybridSearchResult(BaseModel):
    # Document ID.
    document_id: str

    # Matching chunk ID.
    chunk_id: str

    # Chunk text.
    text: str

    # Page number.
    page_number: Optional[int] = None

    # Section title.
    section_title: Optional[str] = None

    # Content type.
    content_type: Optional[str] = None

    # Parser used.
    parser_used: Optional[str] = None

    # Word count.
    word_count: Optional[int] = None

    # Normalized vector score from Pinecone.
    vector_score: float

    # Normalized keyword score from BM25.
    keyword_score: float

    # Final combined score.
    hybrid_score: float

    # Shows whether result came from vector, keyword, or both.
    matched_by: str


# This model defines hybrid search response.
class HybridSearchResponse(BaseModel):
    # Document ID searched.
    document_id: str

    # Original query.
    query: str

    # Number of results returned.
    result_count: int

    # Final merged search results.
    results: List[HybridSearchResult]