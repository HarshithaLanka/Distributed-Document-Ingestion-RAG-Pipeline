# Import io so we can create file-like objects in memory.
# Simple meaning: we can create a fake PDF without storing it manually first.
import io

# Import fitz from PyMuPDF.
# We use this to dynamically create a small valid PDF for testing.
import fitz


# Helper function to create a small valid PDF as bytes.
def create_test_pdf_bytes():
    # Create a new empty PDF document.
    pdf_document = fitz.open()

    # Add one blank page to the PDF.
    page = pdf_document.new_page()

    # Insert sample text into the page.
    page.insert_text(
        (72, 72),
        "This is a test PDF for Document Intelligence RAG upload testing."
    )

    # Convert the PDF document into bytes.
    pdf_bytes = pdf_document.tobytes()

    # Close the PDF document to free memory.
    pdf_document.close()

    # Return the PDF bytes.
    return pdf_bytes


# Test that a valid PDF can be uploaded successfully.
def test_upload_valid_pdf(client):
    # Create a small valid PDF in memory.
    pdf_bytes = create_test_pdf_bytes()

    # Send POST request to the upload API.
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "test_upload.pdf",
                io.BytesIO(pdf_bytes),
                "application/pdf"
            )
        }
    )

    # The upload API should return success.
    # Some APIs use 200, some use 201 for created resources.
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

    # Check that filename is not empty.
    assert data["filename"] is not None


# Test that non-PDF files are rejected.
def test_upload_rejects_non_pdf(client):
    # Create fake text file content.
    fake_text_file = io.BytesIO(b"This is not a PDF file.")

    # Send POST request with a .txt file.
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "not_a_pdf.txt",
                fake_text_file,
                "text/plain"
            )
        }
    )

    # The API should reject non-PDF files.
    # 400 means bad request.
    # 422 means validation error.
    assert response.status_code in [400, 422]

    # Convert response JSON into a Python dictionary.
    data = response.json()

    # Make sure response is JSON.
    assert isinstance(data, dict)