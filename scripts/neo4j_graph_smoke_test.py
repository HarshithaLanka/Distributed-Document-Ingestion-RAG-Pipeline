"""
Neo4j graph smoke test for Week 12.

Purpose:
- Test storing Document, Chunk, and Entity nodes in Neo4j.
- Test relationships:
    Document -[:HAS_CHUNK]-> Chunk
    Chunk -[:MENTIONS]-> Entity
    Entity -[:APPEARS_IN]-> Document

Run:
    python scripts/neo4j_graph_smoke_test.py
"""

# Import json to print clean output.
import json

# Import sys to modify Python import path.
import sys

# Import Path for project path handling.
from pathlib import Path


# Get project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to import path.
sys.path.insert(0, str(PROJECT_ROOT))


# Import entity extraction service.
from app.services.entity_extraction_service import extract_entities_from_chunks  # noqa: E402

# Import Neo4j service functions.
from app.services.neo4j_service import (  # noqa: E402
    close_neo4j_driver,
    delete_document_graph,
    get_entities_for_document,
    upsert_document_graph,
    verify_neo4j_connection,
)


def build_fake_chunks():
    """
    Build fake redacted chunks.

    Important:
    We are using redacted-safe text.
    No real private data.
    """

    # Return fake chunks.
    return [
        {
            "document_id": "doc_graph_test_123",
            "chunk_id": "doc_graph_test_123_chunk_1",
            "page_number": 1,
            "section_title": "Professor Details",
            "content_type": "paragraph",
            "word_count": 15,
            "text": (
                "Professor Soujanya works at Andhra University in India. "
                "Email is [EMAIL_REDACTED]."
            ),
        },
        {
            "document_id": "doc_graph_test_123",
            "chunk_id": "doc_graph_test_123_chunk_2",
            "page_number": 2,
            "section_title": "Technology Stack",
            "content_type": "paragraph",
            "word_count": 20,
            "text": (
                "The Document Intelligence RAG project uses FastAPI, Pinecone, "
                "Neo4j, AWS S3, DynamoDB, and SQS."
            ),
        },
        {
            "document_id": "doc_graph_test_123",
            "chunk_id": "doc_graph_test_123_chunk_3",
            "page_number": 3,
            "section_title": "Roadmap",
            "content_type": "paragraph",
            "word_count": 15,
            "text": (
                "The project continues in July 2026 with graph storage, "
                "BM25 retrieval, and evaluation."
            ),
        },
    ]


def main():
    """
    Main smoke test function.
    """

    # Define fake document metadata.
    document = {
        "document_id": "doc_graph_test_123",
        "filename": "week_12_graph_test.pdf",
        "parser_used": "docling",
    }

    # Build fake redacted chunks.
    chunks = build_fake_chunks()

    # Print connection check message.
    print("Checking Neo4j connection...")

    # Verify connection.
    verify_neo4j_connection()

    # Print success message.
    print("neo4j connection OK")

    # Clean old test graph if it exists.
    print("Deleting old test graph if present...")

    # Delete previous test graph.
    delete_document_graph(document["document_id"])

    # Extract entities from chunks.
    print("Extracting entities from fake chunks...")

    # Use our Week 12 Day 1 entity extraction service.
    entity_mentions = extract_entities_from_chunks(chunks)

    # Print extracted entity count.
    print(f"Extracted entity mentions: {len(entity_mentions)}")

    # Store graph in Neo4j.
    print("Writing graph to Neo4j...")

    # Upsert document graph.
    summary = upsert_document_graph(
        document=document,
        chunks=chunks,
        entity_mentions=entity_mentions,
    )

    # Print write summary.
    print("\nWrite summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # Read entities back from Neo4j.
    print("\nReading entities back from Neo4j...")

    # Fetch entities.
    entities = get_entities_for_document(document["document_id"])

    # Print entities.
    print(json.dumps(entities, indent=2, ensure_ascii=False))

    # Final success message.
    print("\nneo4j graph smoke test OK")

    # Close driver.
    close_neo4j_driver()


if __name__ == "__main__":
    main()