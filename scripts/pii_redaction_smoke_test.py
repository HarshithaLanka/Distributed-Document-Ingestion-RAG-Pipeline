# This script tests PII redaction safely.
#
# It does NOT use FastAPI.
# It does NOT use SQS.
# It does NOT use AWS.
# It does NOT use Pinecone.
#
# It only tests:
# chunks.json -> redacted_chunks.json

# Import sys to read command-line arguments and fix Python path.
import sys

# Import Path to work with file paths.
from pathlib import Path


# ---------------------------------------------------------
# Add project root to Python path
# ---------------------------------------------------------

# Current file is scripts/pii_redaction_smoke_test.py
# parent = scripts/
# parent.parent = project root folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root so Python can import app/
sys.path.append(str(PROJECT_ROOT))


# ---------------------------------------------------------
# Import project redaction service
# ---------------------------------------------------------

# Import function that creates redacted_chunks.json.
from app.services.pii_redaction_service import create_redacted_chunks_file

# Import function that reads redacted_chunks.json.
from app.services.pii_redaction_service import load_redacted_chunks

# Import direct text redaction for quick examples.
from app.services.pii_redaction_service import redact_text


def test_fake_text_examples():
    """
    Test redaction on fake text examples.

    Important:
    Use fake PII only.
    Do not test with real private values.
    """

    # Create fake sensitive text.
    fake_text = (
        "Contact John at john.doe@example.com. "
        "Call him at +91 9876543210. "
        "His test SSN is 123-45-6789."
    )

    # Redact fake text.
    result = redact_text(fake_text)

    # Print original text.
    print("\n========== FAKE TEXT BEFORE ==========")
    print(fake_text)

    # Print redacted text.
    print("\n========== FAKE TEXT AFTER ==========")
    print(result["redacted_text"])

    # Print redaction summary.
    print("\n========== FAKE TEXT REDACTION SUMMARY ==========")
    print("redaction_applied:", result["redaction_applied"])
    print("redaction_count:", result["redaction_count"])
    print("redaction_types:", result["redaction_types"])


def test_chunks_file(chunks_path: str):
    """
    Test redaction on a real chunks.json file.
    """

    # Create redacted_chunks.json.
    result = create_redacted_chunks_file(chunks_path)

    # Print result.
    print("\n========== REDACTED CHUNKS RESULT ==========")
    print(result)

    # Load generated redacted_chunks.json.
    redacted_chunks_data = load_redacted_chunks(result["redacted_chunks_path"])

    # Print document-level summary.
    print("\n========== DOCUMENT REDACTION SUMMARY ==========")
    print("chunk_count:", redacted_chunks_data.get("chunk_count"))
    print("redaction_applied:", redacted_chunks_data.get("redaction_applied"))
    print("redaction_count:", redacted_chunks_data.get("redaction_count"))
    print("redaction_types:", redacted_chunks_data.get("redaction_types"))

    # Print first 3 chunks.
    print("\n========== FIRST 3 REDACTED CHUNKS ==========")

    for chunk in redacted_chunks_data.get("chunks", [])[:3]:
        print("\n--- CHUNK ---")
        print("chunk_id:", chunk.get("chunk_id"))
        print("page_number:", chunk.get("page_number"))
        print("section_title:", chunk.get("section_title"))
        print("content_type:", chunk.get("content_type"))
        print("redaction_applied:", chunk.get("redaction_applied"))
        print("redaction_count:", chunk.get("redaction_count"))
        print("redaction_types:", chunk.get("redaction_types"))
        print("text preview:", chunk.get("text", "")[:300])


def main():
    """
    Run PII redaction smoke test.

    Usage:
        python scripts/pii_redaction_smoke_test.py "path/to/chunks.json"
    """

    # Always test fake examples first.
    test_fake_text_examples()

    # If user did not provide chunks.json path, stop after fake test.
    if len(sys.argv) < 2:
        print("\nNo chunks.json path provided. Fake text test completed.")
        print('Usage: python scripts/pii_redaction_smoke_test.py "path/to/chunks.json"')
        return

    # Read chunks.json path.
    chunks_path = sys.argv[1]

    # Test chunks file.
    test_chunks_file(chunks_path)

    # Print final success.
    print("\n========== SUCCESS ==========")
    print("PII redaction smoke test completed.")


# Run main function only when this file is executed directly.
if __name__ == "__main__":
    main()