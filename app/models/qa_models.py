# This file defines request and response models for RAG Q&A.

# Import BaseModel from Pydantic.
from pydantic import BaseModel


# Request body for /qa.
class QARequest(BaseModel):
    # Document ID to search inside.
    document_id: str

    # User question.
    question: str

    # Number of chunks to retrieve.
    top_k: int = 3

    # Minimum Pinecone similarity score.
    min_score: float = 0.35


# One citation object.
class Citation(BaseModel):
    # Chunk ID used as source.
    chunk_id: str

    # Page number from PDF.
    page_number: int

    # Pinecone similarity score.
    score: float

    # Short source text preview.
    source_preview: str


# Response body for /qa.
class QAResponse(BaseModel):
    # Document ID.
    document_id: str

    # User question.
    question: str

    # Final generated answer.
    answer: str

    # Citations.
    citations: list[Citation]