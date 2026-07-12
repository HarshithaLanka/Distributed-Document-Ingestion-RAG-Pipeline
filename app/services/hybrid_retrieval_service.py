# This file combines Pinecone vector search and BM25 keyword search.

# Import re for fallback PII redaction.
import re

# Import Optional because some metadata values may be missing.
from typing import Optional

# Import vector search service.
from app.services.pinecone_service import search_similar_chunks

# Import BM25 keyword search service.
from app.services.bm25_service import search_document_with_bm25_as_dicts

# Import query entity extraction for Week 14 graph retrieval.
from app.services.entity_extraction_service import extract_query_entities

# Import Neo4j graph search for Week 14.
from app.services.neo4j_service import search_chunks_by_entities


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



def create_base_candidate(
    document_id: str,
    chunk_id: str,
    result: dict,
) -> dict:
    """
    Create one common candidate format.

    Why:
    Vector, BM25, and Neo4j may return slightly different dictionaries.
    This function converts them into one shared structure.
    """

    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "text": safe_get_text(result),
        "page_number": safe_get_metadata(result, "page_number"),
        "section_title": safe_get_metadata(result, "section_title"),
        "content_type": safe_get_metadata(result, "content_type"),
        "parser_used": safe_get_metadata(result, "parser_used"),
        "word_count": safe_get_metadata(result, "word_count"),
        "vector_score": 0.0,
        "keyword_score": 0.0,
        "graph_score": 0.0,
        "hybrid_score": 0.0,
        "retrieval_sources": [],
        "matched_entities": [],
    }


def fill_missing_metadata(target: dict, source: dict) -> None:
    """
    Fill missing fields in an already merged candidate.

    Example:
    Pinecone may have text but BM25 may have section_title.
    We keep the best available metadata from all retrieval sources.
    """

    # Fill text only if missing.
    if not target.get("text"):
        target["text"] = safe_get_text(source)

    # Fill other metadata only when target does not already have it.
    for key in [
        "page_number",
        "section_title",
        "content_type",
        "parser_used",
        "word_count",
    ]:
        if target.get(key) in (None, ""):
            target[key] = safe_get_metadata(source, key)


def merge_retrieval_results(
    document_id: str,
    vector_results: list[dict],
    keyword_results: list[dict],
    graph_results: list[dict],
    vector_weight: float = 0.5,
    keyword_weight: float = 0.3,
    graph_weight: float = 0.2,
) -> list[dict]:
    """
    Merge vector, BM25, and Neo4j results using chunk_id.

    Deduplication rule:
    If the same chunk is returned by more than one retriever,
    keep one result and preserve all individual scores.

    Final score:
    hybrid_score =
        vector_score * vector_weight
        + keyword_score * keyword_weight
        + graph_score * graph_weight
    """

    # Weights cannot be negative.
    if min(vector_weight, keyword_weight, graph_weight) < 0:
        raise ValueError("retrieval weights cannot be negative")

    # At least one weight must be positive.
    total_weight = vector_weight + keyword_weight + graph_weight

    if total_weight <= 0:
        raise ValueError(
            "at least one retrieval weight must be greater than 0"
        )

    # Normalize weights so they always sum to 1.
    vector_weight = vector_weight / total_weight
    keyword_weight = keyword_weight / total_weight
    graph_weight = graph_weight / total_weight

    # Store unique results by chunk_id.
    merged = {}

    def get_or_create_candidate(result: dict):
        """
        Return the merged candidate for one result.
        Create it when this chunk_id is seen for the first time.
        """

        chunk_id = safe_get_chunk_id(result)

        if not chunk_id:
            return None

        if chunk_id not in merged:
            merged[chunk_id] = create_base_candidate(
                document_id=document_id,
                chunk_id=chunk_id,
                result=result,
            )
        else:
            fill_missing_metadata(
                target=merged[chunk_id],
                source=result,
            )

        return merged[chunk_id]

    # Add vector scores.
    for result in vector_results:
        candidate = get_or_create_candidate(result)

        if candidate is None:
            continue

        candidate["vector_score"] = float(
            result.get("normalized_score", 0.0)
        )

        if "vector" not in candidate["retrieval_sources"]:
            candidate["retrieval_sources"].append("vector")

    # Add keyword scores.
    for result in keyword_results:
        candidate = get_or_create_candidate(result)

        if candidate is None:
            continue

        candidate["keyword_score"] = float(
            result.get("normalized_score", 0.0)
        )

        if "keyword" not in candidate["retrieval_sources"]:
            candidate["retrieval_sources"].append("keyword")

    # Add graph scores and matched entities.
    for result in graph_results:
        candidate = get_or_create_candidate(result)

        if candidate is None:
            continue

        candidate["graph_score"] = float(
            result.get("graph_score", 0.0)
        )

        candidate["matched_entities"] = list(
            result.get("matched_entities") or []
        )

        if "graph" not in candidate["retrieval_sources"]:
            candidate["retrieval_sources"].append("graph")

    # Calculate final weighted score.
    for candidate in merged.values():
        candidate["hybrid_score"] = (
            candidate["vector_score"] * vector_weight
            + candidate["keyword_score"] * keyword_weight
            + candidate["graph_score"] * graph_weight
        )

        # Keep old matched_by field for Week 13 compatibility.
        sources = candidate["retrieval_sources"]

        if sources == ["vector"]:
            candidate["matched_by"] = "vector"
        elif sources == ["keyword"]:
            candidate["matched_by"] = "keyword"
        elif sources == ["graph"]:
            candidate["matched_by"] = "graph"
        else:
            candidate["matched_by"] = "multiple"

    # Convert dictionary to list.
    final_results = list(merged.values())

    # Sort strongest results first.
    final_results.sort(
        key=lambda item: (
            item.get("hybrid_score", 0.0),
            len(item.get("retrieval_sources", [])),
        ),
        reverse=True,
    )

    return final_results


def merge_vector_and_keyword_results(
    document_id: str,
    vector_results: list[dict],
    keyword_results: list[dict],
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[dict]:
    """
    Backward-compatible Week 13 wrapper.

    Existing Week 13 tests and code can continue calling this function.
    Internally, it now uses the new three-source merge function with
    graph_weight set to 0.
    """

    return merge_retrieval_results(
        document_id=document_id,
        vector_results=vector_results,
        keyword_results=keyword_results,
        graph_results=[],
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
        graph_weight=0.0,
    )


def hybrid_search_document(
    document_id: str,
    query: str,
    top_k: int = 5,
    vector_top_k: Optional[int] = None,
    keyword_top_k: Optional[int] = None,
    graph_top_k: Optional[int] = None,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.3,
    graph_weight: float = 0.2,
    include_graph: bool = True,
) -> list[dict]:
    """
    Search a document using Week 14 hybrid retrieval.

    Flow:
    1. Run Pinecone vector search.
    2. Run BM25 keyword search.
    3. Extract entities from the user query.
    4. Run Neo4j graph retrieval.
    5. Normalize vector and BM25 scores.
    6. Merge all results by chunk_id.
    7. Return strongest top_k candidates.
    """

    # Validate document ID.
    if not document_id:
        raise ValueError("document_id cannot be empty")

    # Validate query.
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    # Keep top_k inside a safe range.
    top_k = min(max(top_k, 1), 20)

    # Retrieve more candidates before merging.
    if vector_top_k is None:
        vector_top_k = min(top_k * 2, 20)

    if keyword_top_k is None:
        keyword_top_k = min(top_k * 2, 20)

    if graph_top_k is None:
        graph_top_k = min(top_k, 10)

    # Keep source-specific limits safe.
    vector_top_k = min(max(vector_top_k, 1), 20)
    keyword_top_k = min(max(keyword_top_k, 1), 20)
    graph_top_k = min(max(graph_top_k, 1), 20)

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

    # Normalize vector scores.
    vector_results = normalize_scores(
        results=vector_results,
        score_key="score",
    )

    # Normalize BM25 scores.
    keyword_results = normalize_scores(
        results=keyword_results,
        score_key="score",
    )

    # Start with no graph results.
    graph_results = []

    # Graph retrieval is optional so the core system still works
    # when Neo4j is disabled or no entities are found.
    if include_graph and graph_weight > 0:
        # Extract entities from the user's query.
        query_entities = extract_query_entities(query)

        # Neo4j search only needs normalized entity names.
        normalized_entity_names = [
            entity.get("normalized_text")
            for entity in query_entities
            if entity.get("normalized_text")
        ]

        # Retrieve graph-connected chunks.
        graph_results = search_chunks_by_entities(
            document_id=document_id,
            entities=normalized_entity_names,
            top_k=graph_top_k,
        )

    # Merge and deduplicate vector, BM25, and graph candidates.
    merged_results = merge_retrieval_results(
        document_id=document_id,
        vector_results=vector_results,
        keyword_results=keyword_results,
        graph_results=graph_results,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
        graph_weight=graph_weight if include_graph else 0.0,
    )

    # Return final top_k candidates.
    return merged_results[:top_k]
