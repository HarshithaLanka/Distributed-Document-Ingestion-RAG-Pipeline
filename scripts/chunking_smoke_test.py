# This script tests Week 10 chunking directly.
#
# It does NOT use FastAPI.
# It does NOT use SQS.
# It does NOT use AWS.
# It does NOT use Pinecone.
#
# It only reads extracted_text.json and creates chunks.json.

# Import sys to read command-line arguments and update Python path.
import sys

# Import Path to work with file paths safely.
from pathlib import Path


# ---------------------------------------------------------
# Add project root to Python import path
# ---------------------------------------------------------

# Current file is scripts/chunking_smoke_test.py
# parent = scripts/
# parent.parent = project root folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python path.
# This allows Python to find the app/ folder.
sys.path.append(str(PROJECT_ROOT))


# ---------------------------------------------------------
# Import project services AFTER fixing sys.path
# ---------------------------------------------------------

# Import chunking function.
from app.services.chunking_service import create_chunks_from_extracted_text

# Import chunks loader.
from app.services.chunking_service import load_chunks


def main():
    """
    Run chunking smoke test.

    Usage:
        python scripts/chunking_smoke_test.py "path/to/extracted_text.json" document_id
    """

    # Check if user provided both required arguments.
    if len(sys.argv) < 3:
        print(
            'Usage: python scripts/chunking_smoke_test.py '
            '"path/to/extracted_text.json" document_id'
        )
        return

    # Read extracted_text.json path from command line.
    extracted_text_path = sys.argv[1]

    # Read document_id from command line.
    document_id = sys.argv[2]

    # Create chunks from extracted_text.json.
    result = create_chunks_from_extracted_text(
        extracted_text_path=extracted_text_path,
        document_id=document_id,
        chunk_size=150,
        overlap=30,
    )

    # Print chunking result.
    print("\n========== CHUNKING RESULT ==========")
    print(result)

    # Load generated chunks.json.
    chunks_data = load_chunks(result["chunks_path"])

    # Print chunk summary.
    print("\n========== CHUNKS SUMMARY ==========")
    print("parser_used:", chunks_data.get("parser_used"))
    print("chunk_count:", chunks_data.get("chunk_count"))

    # Print first 3 chunks.
    print("\n========== FIRST 3 CHUNKS ==========")

    for chunk in chunks_data.get("chunks", [])[:3]:
        print("\n--- CHUNK ---")
        print("chunk_id:", chunk.get("chunk_id"))
        print("page_number:", chunk.get("page_number"))
        print("section_title:", chunk.get("section_title"))
        print("content_type:", chunk.get("content_type"))
        print("parser_used:", chunk.get("parser_used"))
        print("word_count:", chunk.get("word_count"))
        print("text preview:", chunk.get("text", "")[:300])

    # Print success message.
    print("\n========== SUCCESS ==========")
    print("Week 10 chunking works.")


# Run main function only when this file is executed directly.
if __name__ == "__main__":
    main()