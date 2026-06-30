# Import os to set Hugging Face cache settings before Docling loads.
import os

# Disable Hugging Face symlinks on Windows.
# This avoids WinError 1314: required privilege not held by client.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

# Hide symlink warning because we already know we disabled symlinks.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# This script is only for testing whether Docling works.
# It is NOT part of the main FastAPI pipeline.

# Import sys so we can read command-line arguments.
import sys

# Import Path to safely work with file paths.
from pathlib import Path

# Import InputFormat so we can tell Docling this config is for PDFs.
from docling.datamodel.base_models import InputFormat

# Import PdfPipelineOptions to customize Docling PDF processing.
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Import DocumentConverter and PdfFormatOption.
from docling.document_converter import DocumentConverter, PdfFormatOption


def create_docling_converter_without_ocr() -> DocumentConverter:
    """
    Create a Docling converter with OCR disabled.

    Why?
    Your error came from RapidOCR:
    Unsupported configuration: torch.PP-OCRv6.det.small

    For Week 10, we are not doing scanned PDF/OCR yet.
    So we disable OCR and process readable PDFs only.
    """

    # Create PDF pipeline options.
    pipeline_options = PdfPipelineOptions()

    # Disable OCR.
    # This prevents Docling from starting RapidOCR.
    pipeline_options.do_ocr = False

    # Keep table structure enabled.
    # This helps Docling preserve tables where possible.
    pipeline_options.do_table_structure = True

    # Create and return DocumentConverter with PDF-specific options.
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )

    # Return converter.
    return converter


def main():
    """
    Run a simple Docling conversion test.

    Usage:
        python scripts/docling_smoke_test.py "path/to/sample.pdf"
    """

    # Check whether user gave a PDF path.
    if len(sys.argv) < 2:
        print("Usage: python scripts/docling_smoke_test.py \"path/to/sample.pdf\"")
        return

    # Convert the given path string into a Path object.
    pdf_path = Path(sys.argv[1])

    # Check if file exists.
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    # Create Docling converter with OCR disabled.
    converter = create_docling_converter_without_ocr()

    # Convert PDF into Docling document.
    result = converter.convert(str(pdf_path))

    # Export converted document to Markdown.
    markdown_text = result.document.export_to_markdown()

    # Print first 3000 characters.
    print("\n========== DOCLING MARKDOWN PREVIEW ==========\n")
    print(markdown_text[:3000])

    # Print success message.
    print("\n========== SUCCESS ==========")
    print("Docling conversion worked with OCR disabled.")


# Run main function when script is executed directly.
if __name__ == "__main__":
    main()