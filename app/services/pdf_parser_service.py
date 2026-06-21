# This file extracts text from uploaded PDF files.

# Import json to save extracted text into a JSON file.
import json

# Import Path to work with file paths safely.
from pathlib import Path

# Import fitz.
# fitz is the Python import name for PyMuPDF.
import fitz


# Define a helper function to clean extracted text.
def clean_page_text(text: str) -> str:
    # Replace Windows-style line endings with normal line endings.
    text = text.replace("\r", "\n")

    # Split text into separate lines.
    lines = text.split("\n")

    # Remove extra spaces from each line.
    cleaned_lines = [line.strip() for line in lines]

    # Remove empty lines.
    non_empty_lines = [line for line in cleaned_lines if line]

    # Join cleaned lines back together.
    cleaned_text = "\n".join(non_empty_lines)

    # Return cleaned text.
    return cleaned_text


# Define a function to extract text from PDF page by page.
def extract_text_from_pdf(file_path: str, document_id: str) -> dict:
    # Convert file_path string into a Path object.
    pdf_path = Path(file_path)

    # Check if the PDF file actually exists.
    if not pdf_path.exists():
        # Raise an error if file is missing.
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Create output path for extracted text.
    # Example: uploads/doc_78d6b080/extracted_text.json
    extracted_text_path = pdf_path.parent / "extracted_text.json"

    # Open the PDF using PyMuPDF.
    pdf_document = fitz.open(str(pdf_path))

    try:
        # Get total number of pages in the PDF.
        page_count = len(pdf_document)

        # Create an empty list to store page-level text.
        pages = []

        # Loop through every page in the PDF.
        for page_index in range(page_count):
            # Load current page.
            page = pdf_document.load_page(page_index)

            # Extract text from the current page.
            raw_text = page.get_text("text")

            # Clean the extracted text.
            cleaned_text = clean_page_text(raw_text)

            # Store page number and text.
            # page_index starts from 0, but real page numbers start from 1.
            pages.append(
                {
                    "page_number": page_index + 1,
                    "text": cleaned_text
                }
            )

        # Create final extracted data structure.
        extracted_data = {
            "document_id": document_id,
            "page_count": page_count,
            "pages": pages
        }

        # Open extracted_text.json in write mode.
        with open(extracted_text_path, "w", encoding="utf-8") as file:
            # Save extracted data into JSON file.
            json.dump(extracted_data, file, indent=4, ensure_ascii=False)

        # Return useful extraction result.
        return {
            "page_count": page_count,
            "extracted_text_path": str(extracted_text_path)
        }

    finally:
        # Always close the PDF file after extraction.
        pdf_document.close()