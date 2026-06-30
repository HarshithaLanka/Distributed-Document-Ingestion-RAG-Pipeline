# This script tests indexing chunks into Pinecone.
#
# It directly reads chunks.json and sends vectors to Pinecone.
# Use this only after chunking smoke test works.

# Import sys to read command-line arguments and fix Python path.
import sys

# Import Path to work with file paths safely.
from pathlib import Path


# ---------------------------------------------------------
# Add project root to Python import path
# ---------------------------------------------------------

# Current file is scripts/pinecone_index_smoke_test.py.
# parent = scripts/
# parent.parent = project root folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python path.
sys.path.append(str(PROJECT_ROOT))


# ---------------------------------------------------------
# Import project services AFTER fixing sys.path
# ---------------------------------------------------------

# Import chunk loader.
from app.services.chunking_service import load_chunks

# Import Pinecone indexing function.
from app.services.pinecone_service import index_document_chunks


def main():
    """
    Run Pinecone indexing smoke test.

    Usage:
        python scripts/pinecone_index_smoke_test.py "path/to/chunks.json"
    """

    # Check if user provided chunks.json path.
    if len(sys.argv) < 2:
        print('Usage: python scripts/pinecone_index_smoke_test.py "path/to/chunks.json"')
        return

    # Read chunks path.
    chunks_path = sys.argv[1]

    # Load chunks from chunks.json.
    chunks_data = load_chunks(chunks_path)

    # Index chunks into Pinecone.
    result = index_document_chunks(chunks_data)

    # Print indexing result.
    print("\n========== PINECONE INDEX RESULT ==========")
    print(result)

    # Print success.
    print("\n========== SUCCESS ==========")
    print("Chunks indexed into Pinecone with Week 10 metadata.")


# Run main function only when file is executed directly.
if __name__ == "__main__":
    main()