# This file handles Docling-based PDF parsing.
#
# Week 10 goal:
# Use Docling to extract more structured document content:
# - headings
# - paragraphs
# - tables where possible
# - section_title
# - content_type
#
# Important:
# We are NOT doing OCR in Week 10.
# Scanned PDF/OCR support is paused.
# So OCR is disabled here.

# Import os first so Hugging Face settings are applied before Docling imports.
import os

# Disable Hugging Face symlinks on Windows.
# This avoids WinError 1314: required privilege not held by client.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

# Disable symlink warning because we intentionally disabled symlinks.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Import json to save extracted_text.json.
import json

# Import Path to safely work with file paths.
from pathlib import Path

# Import Any for flexible type hints.
from typing import Any

# Import InputFormat so we can configure Docling PDF behavior.
from docling.datamodel.base_models import InputFormat

# Import PdfPipelineOptions to disable OCR and keep table structure.
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Import DocumentConverter and PdfFormatOption from Docling.
from docling.document_converter import DocumentConverter, PdfFormatOption


def create_docling_converter_without_ocr() -> DocumentConverter:
    """
    Create a Docling converter with OCR disabled.

    Simple meaning:
    Docling can use OCR for scanned PDFs.
    But in Week 10, we are working only with readable PDFs.
    So we disable OCR to avoid RapidOCR errors.
    """

    # Create PDF pipeline options.
    pipeline_options = PdfPipelineOptions()

    # Disable OCR.
    # This prevents RapidOCR from starting.
    pipeline_options.do_ocr = False

    # Keep table structure extraction enabled.
    # This helps preserve tables where possible.
    pipeline_options.do_table_structure = True

    # Create Docling converter with PDF-specific options.
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )

    # Return configured converter.
    return converter


def clean_text(text: str) -> str:
    """
    Clean text by removing extra spaces and empty lines.

    Simple meaning:
    PDF text can have messy spaces and line breaks.
    This makes it cleaner before chunking.
    """

    # If text is missing, return empty string.
    if not text:
        return ""

    # Split text into lines.
    lines = text.splitlines()

    # Remove spaces around each line and skip empty lines.
    cleaned_lines = [
        line.strip()
        for line in lines
        if line.strip()
    ]

    # Join cleaned lines back.
    return "\n".join(cleaned_lines)


def get_docling_document_dict(docling_document: Any) -> dict:
    """
    Convert DoclingDocument into a Python dictionary.

    Why this helper exists:
    Different Docling versions may expose different methods.
    So we try multiple safe options.
    """

    # Option 1: Some versions support export_to_dict().
    if hasattr(docling_document, "export_to_dict"):
        return docling_document.export_to_dict()

    # Option 2: Pydantic v2 style.
    if hasattr(docling_document, "model_dump"):
        return docling_document.model_dump()

    # Option 3: Pydantic v1 style.
    if hasattr(docling_document, "dict"):
        return docling_document.dict()

    # If no dictionary export method exists, return empty dictionary.
    return {}


def get_page_number_from_item(item: dict) -> int:
    """
    Get page number from a Docling item.

    Docling often stores original source info in "prov".
    prov means provenance.
    Simple meaning: where this text came from in the original PDF.
    """

    # Get provenance list.
    prov_list = item.get("prov", [])

    # Check if provenance exists.
    if isinstance(prov_list, list) and prov_list:
        # Take first provenance record.
        first_prov = prov_list[0]

        # Try common Docling page number key.
        page_number = first_prov.get("page_no")

        # If found, return it.
        if page_number:
            return int(page_number)

    # Safe fallback if page number is not found.
    return 1


def classify_docling_label(label: str) -> str:
    """
    Convert Docling labels into our project content types.

    Our project uses simple content types:
    - heading
    - paragraph
    - table
    """

    # Normalize label.
    normalized_label = (label or "").lower()

    # Common heading-like labels.
    heading_labels = {
        "title",
        "section_header",
        "heading",
        "header",
    }

    # If label looks like heading, return heading.
    if normalized_label in heading_labels:
        return "heading"

    # If label contains table, return table.
    if "table" in normalized_label:
        return "table"

    # Everything else becomes paragraph.
    return "paragraph"


def add_block_to_pages(
    pages_by_number: dict,
    page_number: int,
    text: str,
    content_type: str,
    section_title: str | None,
) -> None:
    """
    Add one parsed block to the correct page.

    A block means one meaningful document unit:
    - heading
    - paragraph
    - table
    """

    # Clean text.
    cleaned_text = clean_text(text)

    # Skip empty text.
    if not cleaned_text:
        return

    # If page does not exist yet, create it.
    if page_number not in pages_by_number:
        pages_by_number[page_number] = {
            "page_number": page_number,

            # Keep text for backward compatibility with old chunking logic.
            "text": "",

            # New Week 10 layout-aware blocks.
            "blocks": [],
        }

    # Create one block.
    block = {
        "content_type": content_type,
        "section_title": section_title,
        "text": cleaned_text,
    }

    # Add block to page.
    pages_by_number[page_number]["blocks"].append(block)

    # Also update page-level text.
    # This makes extracted_text.json compatible with older code too.
    if pages_by_number[page_number]["text"]:
        pages_by_number[page_number]["text"] += "\n\n" + cleaned_text
    else:
        pages_by_number[page_number]["text"] = cleaned_text


def extract_tables_from_docling_dict(
    document_dict: dict,
    pages_by_number: dict,
    current_section_title: str | None,
) -> None:
    """
    Extract table-like content from Docling dictionary.

    Important:
    Table extraction does not need to be perfect in Week 10.
    Goal:
    Preserve table text/JSON as a table block.
    """

    # Get table items.
    table_items = document_dict.get("tables", [])

    # Loop through tables.
    for table_index, table_item in enumerate(table_items, start=1):
        # Get page number.
        page_number = get_page_number_from_item(table_item)

        # Try simple text/caption first.
        table_text = table_item.get("text") or table_item.get("caption")

        # If no simple text exists, store compact JSON form.
        if not table_text:
            table_text = json.dumps(
                table_item,
                ensure_ascii=False,
                default=str,
            )

        # Add table block.
        add_block_to_pages(
            pages_by_number=pages_by_number,
            page_number=page_number,
            text=table_text,
            content_type="table",
            section_title=current_section_title or f"Table {table_index}",
        )


def extract_text_with_docling(pdf_path: str, document_id: str) -> dict:
    """
    Extract structured text from PDF using Docling.

    Output:
    {
        "document_id": "...",
        "parser_used": "docling",
        "page_count": 3,
        "pages": [
            {
                "page_number": 1,
                "text": "...",
                "blocks": [
                    {
                        "content_type": "heading",
                        "section_title": "Introduction",
                        "text": "Introduction"
                    },
                    {
                        "content_type": "paragraph",
                        "section_title": "Introduction",
                        "text": "This document explains..."
                    }
                ]
            }
        ],
        "extracted_text_path": "..."
    }
    """

    # Convert string path into Path object.
    pdf_file_path = Path(pdf_path)

    # Check if PDF exists.
    if not pdf_file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Create Docling converter with OCR disabled.
    converter = create_docling_converter_without_ocr()

    # Convert PDF using Docling.
    conversion_result = converter.convert(str(pdf_file_path))

    # Get Docling document.
    docling_document = conversion_result.document

    # Convert Docling document into dictionary.
    document_dict = get_docling_document_dict(docling_document)

    # Store pages by page number.
    pages_by_number = {}

    # Track latest heading.
    # Paragraphs after a heading will use this as section_title.
    current_section_title = None

    # Get text items from Docling dictionary.
    text_items = document_dict.get("texts", [])

    # Loop through text items.
    for item in text_items:
        # Get actual text.
        text = item.get("text", "")

        # Get Docling label.
        label = item.get("label", "")

        # Convert label to our content type.
        content_type = classify_docling_label(label)

        # Get page number.
        page_number = get_page_number_from_item(item)

        # If this item is heading, update current section.
        if content_type == "heading":
            current_section_title = clean_text(text)

        # Use current section title for this block.
        section_title = current_section_title

        # Add block to page.
        add_block_to_pages(
            pages_by_number=pages_by_number,
            page_number=page_number,
            text=text,
            content_type=content_type,
            section_title=section_title,
        )

    # Extract tables where possible.
    extract_tables_from_docling_dict(
        document_dict=document_dict,
        pages_by_number=pages_by_number,
        current_section_title=current_section_title,
    )

    # If no structured text was found, use Markdown as emergency Docling output.
    # If this also fails to produce useful text, parser_service will fallback to PyMuPDF.
    if not pages_by_number:
        markdown_text = clean_text(docling_document.export_to_markdown())

        if markdown_text:
            add_block_to_pages(
                pages_by_number=pages_by_number,
                page_number=1,
                text=markdown_text,
                content_type="paragraph",
                section_title=None,
            )

    # If still no pages, fail clearly.
    # parser_service.py will catch this and fallback to PyMuPDF.
    if not pages_by_number:
        raise ValueError("Docling did not return usable text.")

    # Convert page dictionary into sorted list.
    pages = [
        pages_by_number[page_number]
        for page_number in sorted(pages_by_number.keys())
    ]

    # Count pages.
    page_count = len(pages)

    # Save extracted_text.json in same folder as PDF.
    extracted_text_path = pdf_file_path.parent / "extracted_text.json"

    # Create final extracted data.
    extracted_data = {
        "document_id": document_id,
        "parser_used": "docling",
        "page_count": page_count,
        "pages": pages,
    }

    # Write extracted_text.json.
    with open(extracted_text_path, "w", encoding="utf-8") as file:
        json.dump(extracted_data, file, indent=4, ensure_ascii=False)

    # Return result expected by worker.
    return {
        "document_id": document_id,
        "parser_used": "docling",
        "page_count": page_count,
        "extracted_text_path": str(extracted_text_path),
    }