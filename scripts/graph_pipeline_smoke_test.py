"""
Graph pipeline smoke test.

Purpose:
- Take an existing document_id.
- Load uploads/{document_id}/redacted_chunks.json.
- Extract entities.
- Write graph to Neo4j.
- Read entities back from Neo4j.

Run:
    python scripts/graph_pipeline_smoke_test.py YOUR_DOCUMENT_ID

Example:
    python scripts/graph_pipeline_smoke_test.py doc_b38fd6c9
"""

# Import json for pretty printing.
import json

# Import sys to read command-line arguments.
import sys

# Import Path for safe project path handling.
from pathlib import Path


# Get project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python path.
sys.path.insert(0, str(PROJECT_ROOT))


# Load .env explicitly.
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass


# Import graph pipeline function.
from app.services.graph_pipeline_service import (  # noqa: E402
    build_graph_for_document_from_redacted_chunks,
)

# Import Neo4j read helper.
from app.services.neo4j_service import (  # noqa: E402
    close_neo4j_driver,
    get_entities_for_document,
    verify_neo4j_connection,
)


def main():
    """
    Main smoke test function.
    """

    # Require document_id argument.
    if len(sys.argv) < 2:
        print("Missing document_id.")
        print("Usage: python scripts/graph_pipeline_smoke_test.py YOUR_DOCUMENT_ID")
        sys.exit(1)

    # Read document_id from command line.
    document_id = sys.argv[1]

    # Print what we are testing.
    print(f"Running graph pipeline smoke test for document_id={document_id}")

    # Verify Neo4j connection first.
    print("Checking Neo4j connection...")
    verify_neo4j_connection()
    print("neo4j connection OK")

    # Build graph from local redacted_chunks.json.
    summary = build_graph_for_document_from_redacted_chunks(
        document_id=document_id,
    )

    # Print graph write summary.
    print("\nGraph pipeline summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # Read entities back.
    entities = get_entities_for_document(document_id=document_id)

    # Print first 20 entities only.
    print("\nEntities stored in Neo4j:")
    print(json.dumps(entities[:20], indent=2, ensure_ascii=False))

    # Print final success.
    print("\ngraph pipeline smoke test OK")

    # Close Neo4j driver.
    close_neo4j_driver()


if __name__ == "__main__":
    main()