"""
Graph pipeline service for Document_Intelligence_RAG.

Week 12 purpose:
This service connects entity extraction with Neo4j graph storage.

Flow:
    redacted_chunks.json
        -> extract entities
        -> write Document, Chunk, Entity nodes to Neo4j
        -> create HAS_CHUNK, MENTIONS, APPEARS_IN relationships

Important privacy rule:
We use redacted_chunks.json, not raw chunks.json.

Why:
The graph should not store raw private values like email/phone/SSN.
"""

# Import annotations for cleaner type hints.
from __future__ import annotations

# Import Path for safe file path handling.
from pathlib import Path

# Import typing helpers.
from typing import Any, Dict, List, Optional

# Import entity extraction helpers from Week 12 Day 1.
from app.services.entity_extraction_service import (
    extract_entities_from_chunks,
    load_chunks_from_json_file,
)

# Import Neo4j graph write service from Week 12 Day 2/3.
from app.services.neo4j_service import (
    get_entities_for_document,
    is_neo4j_enabled,
    upsert_document_graph,
)

# Import logger.
from app.utils.logger import get_logger


# Create logger for this file.
logger = get_logger(__name__)


def get_default_redacted_chunks_path(document_id: str) -> Path:
    """
    Build the default local redacted_chunks.json path.

    Example:
        document_id = doc_abc123

    Returns:
        uploads/doc_abc123/redacted_chunks.json

    Simple meaning:
        This tells the service where to find the safe redacted chunks file.
    """

    # Return local path for redacted chunks.
    return Path("uploads") / document_id / "redacted_chunks.json"


def infer_parser_used_from_chunks(chunks: List[Dict[str, Any]]) -> str:
    """
    Infer parser_used from chunk metadata.

    Week 10 added parser_used to chunks/Pinecone metadata.
    But older chunks may not have it.

    If parser_used is missing, we return "unknown".
    """

    # Loop through chunks.
    for chunk in chunks:
        # Read parser_used if present.
        parser_used = chunk.get("parser_used")

        # If found, return it.
        if parser_used:
            return str(parser_used)

    # Fallback if no chunk has parser_used.
    return "unknown"


def build_document_metadata(
    document_id: str,
    chunks: List[Dict[str, Any]],
    filename: Optional[str] = None,
    parser_used: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build metadata for the Neo4j Document node.

    Neo4j Document node needs:
    - document_id
    - filename
    - parser_used

    We keep it simple for Week 12.
    """

    # If parser_used was not passed, infer it from chunks.
    final_parser_used = parser_used or infer_parser_used_from_chunks(chunks)

    # Build document dictionary.
    document = {
        "document_id": document_id,
        "filename": filename or "",
        "parser_used": final_parser_used,
    }

    # Return document metadata.
    return document


def build_graph_for_document_from_chunks(
    document_id: str,
    chunks: List[Dict[str, Any]],
    filename: Optional[str] = None,
    parser_used: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build Neo4j graph from already-loaded redacted chunks.

    Parameters:
    - document_id: document ID
    - chunks: list of redacted chunk dictionaries
    - filename: optional PDF filename
    - parser_used: optional parser name like docling/pymupdf

    Returns:
    A summary dictionary.

    Simple meaning:
    This function is the main bridge:
        chunks -> entities -> Neo4j graph
    """

    # If document_id is missing, fail clearly.
    if not document_id:
        raise ValueError("document_id is required")

    # If Neo4j is disabled, skip safely.
    if not is_neo4j_enabled():
        logger.warning(
            "Neo4j graph pipeline skipped because NEO4J_ENABLED is false"
        )

        return {
            "neo4j_enabled": False,
            "document_id": document_id,
            "chunks_loaded": len(chunks),
            "entity_mentions_extracted": 0,
            "graph_written": False,
        }

    # If chunks list is empty, return a safe summary.
    if not chunks:
        logger.warning(
            f"No chunks found for graph pipeline | document_id={document_id}"
        )

        return {
            "neo4j_enabled": True,
            "document_id": document_id,
            "chunks_loaded": 0,
            "entity_mentions_extracted": 0,
            "graph_written": False,
            "message": "No chunks found.",
        }

    # Log start.
    logger.info(
        f"Starting entity extraction for graph pipeline | "
        f"document_id={document_id} | chunks={len(chunks)}"
    )

    # Extract entity mentions from redacted chunks.
    entity_mentions = extract_entities_from_chunks(chunks)

    # Log entity count.
    logger.info(
        f"Entity extraction completed | document_id={document_id} | "
        f"entity_mentions={len(entity_mentions)}"
    )

    # Build Document node metadata.
    document = build_document_metadata(
        document_id=document_id,
        chunks=chunks,
        filename=filename,
        parser_used=parser_used,
    )

    # Write document graph to Neo4j.
    graph_summary = upsert_document_graph(
        document=document,
        chunks=chunks,
        entity_mentions=entity_mentions,
    )

    # Fetch summarized entities after writing.
    stored_entities = get_entities_for_document(document_id=document_id)

    # Build final summary.
    summary = {
        "neo4j_enabled": True,
        "document_id": document_id,
        "chunks_loaded": len(chunks),
        "entity_mentions_extracted": len(entity_mentions),
        "unique_entities_stored": len(stored_entities),
        "graph_written": True,
        "graph_summary": graph_summary,
    }

    # Log final summary.
    logger.info(
        f"Graph pipeline completed | document_id={document_id} | "
        f"unique_entities={len(stored_entities)}"
    )

    # Return summary.
    return summary


def build_graph_for_document_from_redacted_chunks(
    document_id: str,
    redacted_chunks_path: Optional[str | Path] = None,
    filename: Optional[str] = None,
    parser_used: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build Neo4j graph from redacted_chunks.json.

    Parameters:
    - document_id: document ID
    - redacted_chunks_path: optional exact path to redacted_chunks.json
    - filename: optional PDF filename
    - parser_used: optional parser name

    If redacted_chunks_path is not given, this function uses:
        uploads/{document_id}/redacted_chunks.json
    """

    # If document_id is missing, fail clearly.
    if not document_id:
        raise ValueError("document_id is required")

    # Use provided path or default path.
    path = Path(redacted_chunks_path) if redacted_chunks_path else get_default_redacted_chunks_path(document_id)

    # If file does not exist, fail clearly.
    if not path.exists():
        raise FileNotFoundError(
            f"redacted_chunks.json not found for document_id={document_id}. "
            f"Expected path: {path}"
        )

    # Log file loading.
    logger.info(
        f"Loading redacted chunks for graph pipeline | "
        f"document_id={document_id} | path={path}"
    )

    # Load chunks from JSON file.
    chunks = load_chunks_from_json_file(path)

    # Build graph using loaded chunks.
    return build_graph_for_document_from_chunks(
        document_id=document_id,
        chunks=chunks,
        filename=filename,
        parser_used=parser_used,
    )