# tests/test_upload_api.py

"""
Tests for document upload API.

Important:
These tests should NOT call real AWS services.

So we monkeypatch:
- S3 upload disabled
- SQS upload disabled
- document event logging disabled/faked

Why?
Pytest should test backend logic safely.
Swagger/manual testing can test real AWS end-to-end.
"""

# Import io so we can create file-like objects in memory.
import io

# Import fitz from PyMuPDF.
# We use this to dynamically create a small valid PDF for testing.
import fitz

# Import document_routes module so we can monkeypatch route-level variables.
import app.routes.document_routes as document_routes


def create_test_pdf_bytes():
    """
    Create a small valid PDF as bytes.

    Simple meaning:
    Instead of keeping a test PDF file manually,
    this function creates one in memory during the test.
    """

    # Create a new empty PDF document.
    pdf_document = fitz.open()

    # Add one blank page to the PDF.
    page = pdf_document.new_page()

    # Insert sample text into the page.
    page.insert_text(
        (72, 72),
        "This is a test PDF for Document Intelligence RAG upload testing.",
    )

    # Convert the PDF document into bytes.
    pdf_bytes = pdf_document.tobytes()

    # Close the PDF document to free memory.
    pdf_document.close()

    # Return the PDF bytes.
    return pdf_bytes


def test_upload_valid_pdf(client, monkeypatch):
    """
    Test that a valid PDF can be uploaded successfully.

    We disable AWS calls here because this is an automated unit/API test.
    """

    # Disable S3 inside document_routes.py.
    # Important: document_routes imported S3_UPLOAD_ENABLED directly,
    # so we patch document_routes.S3_UPLOAD_ENABLED, not only app.config.
    monkeypatch.setattr(document_routes, "S3_UPLOAD_ENABLED", False)

    # Disable SQS inside document_routes.py.
    # This prevents real AWS SQS SendMessage during pytest.
    monkeypatch.setattr(document_routes, "SQS_ENABLED", False)

    # Fake event logging so pytest does not call real DynamoDB Events table.
    def fake_log_document_event(*args, **kwargs):
        return {
            "event_log_mocked": True,
        }

    # Replace real event logger with fake logger.
    monkeypatch.setattr(
        document_routes,
        "log_document_event",
        fake_log_document_event,
    )

    # Create a small valid PDF in memory.
    pdf_bytes = create_test_pdf_bytes()

    # Send POST request to the upload API.
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "test_upload.pdf",
                io.BytesIO(pdf_bytes),
                "application/pdf",
            )
        },
    )

    # The upload API should return success.
    assert response.status_code in [200, 201]

    # Convert response JSON into a Python dictionary.
    data = response.json()

    # Check that document_id is present.
    assert "document_id" in data

    # Check that filename is present.
    assert "filename" in data

    # Check that status is present.
    assert "status" in data

    # Check that document_id is not empty.
    assert data["document_id"] is not None

    # Check that filename is correct.
    assert data["filename"] == "test_upload.pdf"

    # Since SQS is disabled in this test, status should stay uploaded.
    assert data["status"] == "uploaded"

    # Since SQS is disabled, sqs_send_status should be disabled.
    assert data["sqs_send_status"] == "disabled"


def test_upload_rejects_non_pdf(client):
    """
    Test that non-PDF files are rejected.
    """

    # Create fake text file content.
    fake_text_file = io.BytesIO(b"This is not a PDF file.")

    # Send POST request with a .txt file.
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "not_a_pdf.txt",
                fake_text_file,
                "text/plain",
            )
        },
    )

    # The API should reject non-PDF files.
    assert response.status_code in [400, 422]

    # Convert response JSON into a Python dictionary.
    data = response.json()

    # Make sure response is JSON.
    assert isinstance(data, dict)