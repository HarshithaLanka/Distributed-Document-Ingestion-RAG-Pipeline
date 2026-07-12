# This file defines request and response models for search APIs.

# Import BaseModel and Field from Pydantic.
from pydantic import BaseModel, Field

# Import Optional because some metadata fields may be missing.
from typing import List, Optional


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


# This model defines the request body for Week 14 hybrid search.
class HybridSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User query.
    query: str

    # Final number of merged results to return.
    top_k: int = Field(default=5, ge=1, le=20)

    # Weight for vector search.
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    # Weight for keyword search.
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0)

    # Weight for Neo4j graph retrieval.
    graph_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    # Whether graph retrieval should be included.
    include_graph: bool = True


# This model represents one Week 14 hybrid search result.
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
    vector_score: float = 0.0

    # Normalized keyword score from BM25.
    keyword_score: float = 0.0

    # Graph relevance score from Neo4j.
    graph_score: float = 0.0

    # Final combined retrieval score.
    hybrid_score: float = 0.0

    # Backward-compatible Week 13 field.
    matched_by: str = "multiple"

    # Shows every retriever that returned this chunk.
    retrieval_sources: List[str] = Field(default_factory=list)

    # Entities from the question that matched this chunk in Neo4j.
    matched_entities: List[str] = Field(default_factory=list)


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


# This model defines the request body for reranked search.
class RerankedSearchRequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User query.
    query: str

    # Number of retrieval candidates collected before reranking.
    candidate_top_k: int = Field(default=10, ge=1, le=20)

    # Number of final reranked chunks to return.
    final_top_k: int = Field(default=5, ge=1, le=10)

    # Retrieval source weights.
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    graph_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    # Allows graph retrieval to be turned off safely.
    include_graph: bool = True


# This model represents one reranked result.
class RerankedSearchResult(HybridSearchResult):
    # Rank before reranking.
    original_rank: int

    # Final rank after reranking.
    final_rank: int

    # Query token overlap score.
    query_overlap_score: float = 0.0

    # Exact phrase overlap score.
    exact_phrase_score: float = 0.0

    # Entity overlap score.
    entity_overlap_score: float = 0.0

    # Section-title overlap score.
    section_title_score: float = 0.0

    # Final reranking score.
    rerank_score: float


# This model defines reranked search response.
class RerankedSearchResponse(BaseModel):
    # Document ID searched.
    document_id: str

    # Original query.
    query: str

    # Number of results returned.
    result_count: int

    # Final reranked results.
    results: List[RerankedSearchResult]