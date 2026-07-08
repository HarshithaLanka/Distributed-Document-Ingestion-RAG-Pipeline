"""
Smoke test for entity extraction.

Purpose:
- Test Week 12 entity extraction without touching worker, S3, SQS, Pinecone, or Neo4j.
- This script uses fake redacted chunks first.
- You can also pass a real redacted_chunks.json path.

Run fake test:
    python scripts/entity_extraction_smoke_test.py

Run with real redacted chunks:
    python scripts/entity_extraction_smoke_test.py uploads/YOUR_DOCUMENT_ID/redacted_chunks.json
"""

# Import json so we can print readable JSON output.
import json

# Import sys so we can read command-line arguments.
import sys

# Import Path so we can safely add project root to Python path.
from pathlib import Path


# Get project root.
# Current file is scripts/entity_extraction_smoke_test.py
# parent = scripts/
# parent.parent = project root/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python import path.
# This makes "from app.services..." work when running the script directly.
sys.path.insert(0, str(PROJECT_ROOT))


# Import our Week 12 service functions.
from app.services.entity_extraction_service import (  # noqa: E402
    extract_entities_from_chunks,
    load_chunks_from_json_file,
    summarize_entities,
)


def build_fake_redacted_chunks():
    """
    Create fake chunks for testing.

    Important:
    These chunks include [EMAIL_REDACTED] to confirm we do not treat it
    as a real entity.
    """

    # Return a list of fake chunk dictionaries.
    return [
        {
            "document_id": "doc_test_123",
            "chunk_id": "chunk_1",
            "page_number": 1,
            "section_title": "Professor Details",
            "content_type": "paragraph",
            "text": (
                "Professor Soujanya works at Andhra University in India. "
                "Her email is [EMAIL_REDACTED]."
            ),
        },
        {
            "document_id": "doc_test_123",
            "chunk_id": "chunk_2",
            "page_number": 2,
            "section_title": "Project Details",
            "content_type": "paragraph",
            "text": (
                "The Document Intelligence RAG project uses FastAPI, Pinecone, "
                "Neo4j, AWS S3, DynamoDB, and SQS."
            ),
        },
        {
            "document_id": "doc_test_123",
            "chunk_id": "chunk_3",
            "page_number": 3,
            "section_title": "Timeline",
            "content_type": "paragraph",
            "text": (
                "The project roadmap continues in July 2026 with graph storage "
                "and hybrid retrieval."
            ),
        },
    ]


def main():
    """
    Main smoke test function.
    """

    # If user gave a file path, load chunks from that JSON file.
    if len(sys.argv) > 1:
        chunks_path = sys.argv[1]
        print(f"Loading chunks from: {chunks_path}")
        chunks = load_chunks_from_json_file(chunks_path)

    # Otherwise, use fake chunks.
    else:
        print("No chunks file provided. Using fake redacted chunks.")
        chunks = build_fake_redacted_chunks()

    # Extract entity mentions from chunks.
    entity_mentions = extract_entities_from_chunks(chunks)

    # Summarize repeated entities.
    entity_summary = summarize_entities(entity_mentions)

    # Print raw mentions.
    print("\nRaw entity mentions:")
    print(json.dumps(entity_mentions, indent=2, ensure_ascii=False))

    # Print summary.
    print("\nEntity summary:")
    print(json.dumps(entity_summary, indent=2, ensure_ascii=False))

    # Print final success line.
    print("\nentity extraction smoke test OK")


# Run main function only when this file is executed directly.
if __name__ == "__main__":
    main()