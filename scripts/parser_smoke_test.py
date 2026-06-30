# This script tests the new Week 10 parser abstraction.
#
# It directly calls parse_document().
# It does NOT use FastAPI.
# It does NOT use SQS.
# It does NOT use DynamoDB.
# It does NOT use Pinecone.
#
# This keeps testing simple and safe.

# Import sys to read command-line arguments.
import sys

# Import Path to work with file paths.
from pathlib import Path

# Import project root path handling.
import os

# Disable Hugging Face symlinks on Windows.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Import parse_document from our new parser service.
from app.services.parser_service import parse_document


def main():
    """
    Run parser smoke test.

    Usage:
        python scripts/parser_smoke_test.py "path/to/file.pdf" doc_test_001
    """

    # Check if user provided PDF path.
    if len(sys.argv) < 2:
        print("Usage: python scripts/parser_smoke_test.py \"path/to/file.pdf\" optional_document_id")
        return

    # Read PDF path.
    pdf_path = Path(sys.argv[1])

    # Read optional document_id.
    document_id = sys.argv[2] if len(sys.argv) >= 3 else "doc_parser_smoke_test"

    # Check if PDF exists.
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    # Call parser abstraction.
    result = parse_document(
        pdf_path=str(pdf_path),
        document_id=document_id,
    )

    # Print result.
    print("\n========== PARSER RESULT ==========")
    print(result)

    # Get extracted file path.
    extracted_path = result.get("extracted_text_path")

    # Print where extracted_text.json was saved.
    print("\n========== EXTRACTED TEXT PATH ==========")
    print(extracted_path)

    # Show success.
    print("\n========== SUCCESS ==========")
    print(f"Parser used: {result.get('parser_used')}")


if __name__ == "__main__":
    main()