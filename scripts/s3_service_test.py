# Import sys so we can add project root to Python path.
import sys

# Import Path so we can work with paths safely.
from pathlib import Path

# Import BytesIO so we can create a fake PDF-like file in memory.
from io import BytesIO


# PROJECT_ROOT points to your main project folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to Python import path.
sys.path.append(str(PROJECT_ROOT))


# Import S3 service functions from your real backend service file.
from app.services.s3_service import (
    build_document_s3_key,
    upload_pdf_to_s3,
    check_file_exists_in_s3,
    download_file_from_s3,
    delete_file_from_s3,
)


def main():
    """
    Test the real S3 service functions.
    """

    # Create a fake test document id.
    document_id = "s3-service-test-doc"

    # Create a fake PDF filename.
    filename = "original.pdf"

    # Create fake PDF-like content.
    # This is not a real PDF, but enough to test upload/download/delete.
    fake_pdf_content = b"%PDF-1.4\nFake PDF content for S3 service test.\n%%EOF"

    # Convert bytes into a file-like object.
    fake_pdf_file = BytesIO(fake_pdf_content)

    # Build the expected S3 key.
    s3_key = build_document_s3_key(
        document_id=document_id,
        filename=filename,
    )

    # Print the key that will be used.
    print(f"S3 key: {s3_key}")

    # Upload fake PDF to S3.
    upload_result = upload_pdf_to_s3(
        file_obj=fake_pdf_file,
        document_id=document_id,
        filename=filename,
    )

    # Print upload result.
    print("Upload result:", upload_result)

    # Check if file exists in S3.
    exists = check_file_exists_in_s3(s3_key)

    # Print existence check result.
    print("File exists after upload:", exists)

    # Download file from S3.
    downloaded_content = download_file_from_s3(s3_key)

    # Compare uploaded and downloaded content.
    if downloaded_content == fake_pdf_content:
        print("Download successful. Content matched.")
    else:
        print("Download failed. Content did not match.")

    # Delete test file from S3.
    delete_result = delete_file_from_s3(s3_key)

    # Print delete result.
    print("Delete result:", delete_result)

    # Check if file exists after delete.
    exists_after_delete = check_file_exists_in_s3(s3_key)

    # Print final existence check.
    print("File exists after delete:", exists_after_delete)


# Run main only if this file is executed directly.
if __name__ == "__main__":
    main()