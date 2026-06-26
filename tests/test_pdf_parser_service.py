# Import json so we can read the extracted_text.json file created by the parser.
import json

# Import pytest so we can test expected errors like FileNotFoundError.
import pytest

# Import fitz.
# fitz is the Python import name for PyMuPDF.
# We use it here to create small temporary PDFs for testing.
import fitz

# Import clean_page_text from your PDF parser service.
from app.services.pdf_parser_service import clean_page_text

# Import extract_text_from_pdf from your PDF parser service.
from app.services.pdf_parser_service import extract_text_from_pdf


# Helper function to create a temporary PDF for testing.
def create_test_pdf(pdf_path, page_texts):
    # Create a new empty PDF document.
    pdf_document = fitz.open()

    # Loop through every text item in page_texts.
    for text in page_texts:
        # Create a new page.
        page = pdf_document.new_page()

        # Insert text into the page.
        page.insert_text(
            (72, 72),
            text
        )

    # Save the PDF to the given path.
    pdf_document.save(str(pdf_path))

    # Close the PDF document.
    pdf_document.close()


# Test 1:
# Check that clean_page_text removes extra spaces and empty lines.
def test_clean_page_text_removes_empty_lines_and_extra_spaces():
    # Create messy text with spaces, empty lines, and Windows-style line endings.
    messy_text = "   Hello World   \r\n\n   This is a test.   \n\n"

    # Clean the text using your actual function.
    cleaned_text = clean_page_text(messy_text)

    # Expected cleaned output.
    expected_text = "Hello World\nThis is a test."

    # Check that cleaning worked correctly.
    assert cleaned_text == expected_text


# Test 2:
# Check that clean_page_text returns empty string for empty input.
def test_clean_page_text_empty_input():
    # Call clean_page_text with empty text.
    cleaned_text = clean_page_text("")

    # Empty input should remain empty.
    assert cleaned_text == ""


# Test 3:
# Check that extract_text_from_pdf extracts text from a one-page PDF.
def test_extract_text_from_single_page_pdf(tmp_path):
    # tmp_path is a temporary folder created by pytest.
    # Simple meaning:
    # We can create test PDFs safely without touching real uploads/ files.

    # Create fake document ID.
    document_id = "test_doc_single_page"

    # Create temporary PDF path.
    pdf_path = tmp_path / "single_page_test.pdf"

    # Create a PDF with one page.
    create_test_pdf(
        pdf_path=pdf_path,
        page_texts=[
            "This is a test PDF for parser testing."
        ]
    )

    # Call your actual PDF extraction function.
    result = extract_text_from_pdf(
        file_path=str(pdf_path),
        document_id=document_id
    )

    # Check that page_count exists in result.
    assert "page_count" in result

    # Check that extracted_text_path exists in result.
    assert "extracted_text_path" in result

    # One-page PDF should return page_count as 1.
    assert result["page_count"] == 1

    # extracted_text.json should be created in the same folder.
    extracted_text_path = tmp_path / "extracted_text.json"

    # Check that extracted_text.json exists.
    assert extracted_text_path.exists()

    # Open and read extracted_text.json.
    with open(extracted_text_path, "r", encoding="utf-8") as file:
        extracted_data = json.load(file)

    # Check document_id is saved correctly.
    assert extracted_data["document_id"] == document_id

    # Check page_count is saved correctly.
    assert extracted_data["page_count"] == 1

    # Check pages list has one page.
    assert len(extracted_data["pages"]) == 1

    # Check page number starts from 1.
    assert extracted_data["pages"][0]["page_number"] == 1

    # Check extracted text contains expected content.
    assert "test PDF for parser testing" in extracted_data["pages"][0]["text"]


# Test 4:
# Check that extract_text_from_pdf preserves page numbers for multi-page PDFs.
def test_extract_text_from_multi_page_pdf_preserves_page_numbers(tmp_path):
    # Create fake document ID.
    document_id = "test_doc_multi_page"

    # Create temporary PDF path.
    pdf_path = tmp_path / "multi_page_test.pdf"

    # Create a PDF with two pages.
    create_test_pdf(
        pdf_path=pdf_path,
        page_texts=[
            "This is page one content.",
            "This is page two content."
        ]
    )

    # Call your actual PDF extraction function.
    result = extract_text_from_pdf(
        file_path=str(pdf_path),
        document_id=document_id
    )

    # Two-page PDF should return page_count as 2.
    assert result["page_count"] == 2

    # Build extracted_text.json path.
    extracted_text_path = tmp_path / "extracted_text.json"

    # Open and read extracted_text.json.
    with open(extracted_text_path, "r", encoding="utf-8") as file:
        extracted_data = json.load(file)

    # Check page_count.
    assert extracted_data["page_count"] == 2

    # Check first page number is 1.
    assert extracted_data["pages"][0]["page_number"] == 1

    # Check second page number is 2.
    assert extracted_data["pages"][1]["page_number"] == 2

    # Check first page text.
    assert "page one content" in extracted_data["pages"][0]["text"]

    # Check second page text.
    assert "page two content" in extracted_data["pages"][1]["text"]


# Test 5:
# Check that missing PDF file raises FileNotFoundError.
def test_extract_text_from_missing_pdf_raises_error(tmp_path):
    # Create path for a PDF that does not exist.
    missing_pdf_path = tmp_path / "missing.pdf"

    # The function should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf(
            file_path=str(missing_pdf_path),
            document_id="test_doc_missing"
        )