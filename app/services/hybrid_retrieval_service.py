# This file combines Pinecone vector search and BM25 keyword search.

# Import re for fallback PII redaction.
import re

# Import Optional because some metadata values may be missing.
from typing import Optional

# Import vector search service.
from app.services.pinecone_service import search_similar_chunks

# Import BM25 keyword search service.
from app.services.bm25_service import search_document_with_bm25_as_dicts


# Try to import your Week 11 redaction function.
# If it fails, we will use our fallback redaction below.
try:
    from app.services.pii_redaction_service import redact_text as project_redact_text
except Exception:
    project_redact_text = None


def fallback_redact_text(text: str) -> str:
    """
    Basic fallback redaction.

    This keeps hybrid search safe even if the main pii_redaction_service
    has a different function format.
    """

    # If text is empty, return empty string.
    if not text:
        return ""

    # Redact email addresses.
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL_REDACTED]",
        text,
    )

    # Redact phone numbers.
    text = re.sub(
        r"(\+?\d[\d\s\-()]{8,}\d)",
        "[PHONE_REDACTED]",
        text,
    )

    # Redact SSN-like values.
    text = re.sub(
        r"\b\d{3}-\d{2}-\d{4}\b",
        "[SSN_REDACTED]",
        text,
    )

    return text


def safe_redact_text(text: str) -> str:
    """
    Redact text safely.

    Why this function exists:
    Your project redaction function may return:
    - string
    - dictionary
    - tuple
    - None

    FastAPI response expects text to be a plain string.
    So this function always returns a string.
    """

    # If text is empty, return empty string.
    if not text:
        return ""

    # Convert text to string safely.
    text = str(text)

    # If project redaction function is not available, use fallback.
    if project_redact_text is None:
        return fallback_redact_text(text)

    try:
        # Call your Week 11 redaction function.
        redacted = project_redact_text(text)

        # Best case: it returns a string.
        if isinstance(redacted, str):
            return redacted

        # If it returns a dictionary, try common keys.
        if isinstance(redacted, dict):
            return (
                redacted.get("redacted_text")
                or redacted.get("text")
                or redacted.get("output")
                or fallback_redact_text(text)
            )

        # If it returns a tuple/list, use the first string item.
        if isinstance(redacted, (tuple, list)):
            for item in redacted:
                if isinstance(item, str):
                    return item

        # Last fallback.
        return fallback_redact_text(text)

    except Exception:
        # If project redaction crashes, do not crash hybrid search.
        return fallback_redact_text(text)


def normalize_scores(results: list[dict], score_key: str) -> list[dict]:
    """
    Normalize scores into 0 to 1 range.

    Vector search and BM25 scores are different.

    Example:
    Pinecone score may be 0.82
    BM25 score may be 9.18

    So we convert both into a common 0 to 1 scale.
    """

    # If there are no results, return empty list.
    if not results:
        return []

    # Get all scores safely.
    scores = []

    for result in results:
        try:
            scores.append(float(result.get(score_key, 0.0)))
        except Exception:
            scores.append(0.0)

    # Find max score.
    max_score = max(scores)

    # If max score is 0, all normalized scores should be 0.
    if max_score <= 0:
        for result in results:
            result["normalized_score"] = 0.0
        return results

    # Divide each score by max score.
    for result in results:
        try:
            raw_score = float(result.get(score_key, 0.0))
        except Exception:
            raw_score = 0.0

        result["normalized_score"] = raw_score / max_score

    return results


def safe_get_text(result: dict) -> str:
    """
    Get text from different possible result formats and redact it.

    Pinecone result may use:
    - text
    - source_text
    - source_preview

    BM25 result usually uses:
    - text
    """

    # Get text from possible keys.
    text = (
        result.get("text")
        or result.get("source_text")
        or result.get("source_preview")
        or ""
    )

    # Always return a redacted plain string.
    return safe_redact_text(text)


def safe_get_chunk_id(result: dict) -> Optional[str]:
    """
    Get chunk_id safely.

    Some vector services may return chunk_id directly.
    Some may store it inside metadata.
    """

    # First try direct chunk_id.
    chunk_id = result.get("chunk_id")

    # If not found, try metadata.
    if not chunk_id and isinstance(result.get("metadata"), dict):
        chunk_id = result["metadata"].get("chunk_id")

    return chunk_id


def safe_get_metadata(result: dict, key: str):
    """
    Get metadata safely from direct result or nested metadata.
    """

    # First try direct key.
    if key in result:
        return result.get(key)

    # Then try metadata dictionary.
    if isinstance(result.get("metadata"), dict):
        return result["metadata"].get(key)

    return None


def merge_vector_and_keyword_results(
    document_id: str,
    vector_results: list[dict],
    keyword_results: list[dict],
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[dict]:
    """
    Merge vector search results and BM25 keyword search results.

    Deduplication:
    If the same chunk appears in both Pinecone and BM25,
    we keep one result and combine the scores.
    """

    # This dictionary stores final results by chunk_id.
    merged = {}

    # Process vector search results first.
    for result in vector_results:
        # Get chunk ID safely.
        chunk_id = safe_get_chunk_id(result)

        # Skip result if chunk_id is missing.
        if not chunk_id:
            continue

        # Get normalized vector score.
        vector_score = float(result.get("normalized_score", 0.0))

        # Create merged result.
        merged[chunk_id] = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "text": safe_get_text(result),
            "page_number": safe_get_metadata(result, "page_number"),
            "section_title": safe_get_metadata(result, "section_title"),
            "content_type": safe_get_metadata(result, "content_type"),
            "parser_used": safe_get_metadata(result, "parser_used"),
            "word_count": safe_get_metadata(result, "word_count"),
            "vector_score": vector_score,
            "keyword_score": 0.0,
            "hybrid_score": vector_score * vector_weight,
            "matched_by": "vector",
        }

    # Process BM25 keyword results.
    for result in keyword_results:
        # Get chunk ID safely.
        chunk_id = safe_get_chunk_id(result)

        # Skip result if chunk_id is missing.
        if not chunk_id:
            continue

        # Get normalized keyword score.
        keyword_score = float(result.get("normalized_score", 0.0))

        # If chunk already came from vector search, update same result.
        if chunk_id in merged:
            merged[chunk_id]["keyword_score"] = keyword_score

            # Combine vector and keyword scores.
            merged[chunk_id]["hybrid_score"] = (
                merged[chunk_id]["vector_score"] * vector_weight
                + keyword_score * keyword_weight
            )

            # Mark that both retrievers found this chunk.
            merged[chunk_id]["matched_by"] = "both"

            # Prefer BM25 redacted text if vector text is empty.
            if not merged[chunk_id].get("text"):
                merged[chunk_id]["text"] = safe_get_text(result)

            # Fill missing metadata from BM25 result.
            if merged[chunk_id].get("page_number") is None:
                merged[chunk_id]["page_number"] = safe_get_metadata(result, "page_number")

            if not merged[chunk_id].get("section_title"):
                merged[chunk_id]["section_title"] = safe_get_metadata(result, "section_title")

            if not merged[chunk_id].get("content_type"):
                merged[chunk_id]["content_type"] = safe_get_metadata(result, "content_type")

            if not merged[chunk_id].get("parser_used"):
                merged[chunk_id]["parser_used"] = safe_get_metadata(result, "parser_used")

            if merged[chunk_id].get("word_count") is None:
                merged[chunk_id]["word_count"] = safe_get_metadata(result, "word_count")

        # If chunk only came from BM25, add it.
        else:
            merged[chunk_id] = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "text": safe_get_text(result),
                "page_number": safe_get_metadata(result, "page_number"),
                "section_title": safe_get_metadata(result, "section_title"),
                "content_type": safe_get_metadata(result, "content_type"),
                "parser_used": safe_get_metadata(result, "parser_used"),
                "word_count": safe_get_metadata(result, "word_count"),
                "vector_score": 0.0,
                "keyword_score": keyword_score,
                "hybrid_score": keyword_score * keyword_weight,
                "matched_by": "keyword",
            }

    # Convert dictionary values into list.
    final_results = list(merged.values())

    # Sort by hybrid score from highest to lowest.
    final_results.sort(
        key=lambda item: item.get("hybrid_score", 0.0),
        reverse=True,
    )

    return final_results


def hybrid_search_document(
    document_id: str,
    query: str,
    top_k: int = 5,
    vector_top_k: Optional[int] = None,
    keyword_top_k: Optional[int] = None,
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[dict]:
    """
    Search document using both vector search and BM25 keyword search.

    Flow:
    1. Run Pinecone vector search.
    2. Run BM25 keyword search.
    3. Normalize both scores.
    4. Merge results.
    5. Remove duplicate chunk IDs.
    6. Return final top_k results.
    """

    # Validate query.
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    # Keep top_k safe.
    if top_k <= 0:
        top_k = 5

    if top_k > 20:
        top_k = 20

    # Retrieve more candidates before merging.
    if vector_top_k is None:
        vector_top_k = min(top_k * 2, 20)

    if keyword_top_k is None:
        keyword_top_k = min(top_k * 2, 20)

    # Run Pinecone vector search.
    vector_results = search_similar_chunks(
        document_id=document_id,
        query=query,
        top_k=vector_top_k,
    )

    # Run BM25 keyword search.
    keyword_results = search_document_with_bm25_as_dicts(
        document_id=document_id,
        query=query,
        top_k=keyword_top_k,
    )

    # Normalize Pinecone scores.
    vector_results = normalize_scores(
        results=vector_results,
        score_key="score",
    )

    # Normalize BM25 scores.
    keyword_results = normalize_scores(
        results=keyword_results,
        score_key="score",
    )

    # Merge and deduplicate results.
    merged_results = merge_vector_and_keyword_results(
        document_id=document_id,
        vector_results=vector_results,
        keyword_results=keyword_results,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
    )

    # Return final top_k.
    return merged_results[:top_k]