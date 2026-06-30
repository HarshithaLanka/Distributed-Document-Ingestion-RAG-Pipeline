# This file handles chunking extracted PDF text.
#
# Week 10 upgrade:
# Earlier chunks had only:
# - chunk_id
# - document_id
# - page_number
# - text
# - word_count
#
# Now chunks also support:
# - section_title
# - content_type
# - parser_used
#
# This file supports both formats:
#
# 1. Old PyMuPDF format:
#    {
#        "page_number": 1,
#        "text": "plain page text..."
#    }
#
# 2. New Docling layout-aware format:
#    {
#        "page_number": 1,
#        "text": "combined page text...",
#        "blocks": [
#            {
#                "content_type": "heading",
#                "section_title": "Introduction",
#                "text": "Introduction"
#            },
#            {
#                "content_type": "paragraph",
#                "section_title": "Introduction",
#                "text": "This document explains..."
#            }
#        ]
#    }


# Import json to read extracted_text.json and write chunks.json.
import json

# Import Path to work with file paths safely.
from pathlib import Path

# Import List for type hints.
from typing import List


# Define a function to split text into word-based chunks.
def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> List[str]:
    """
    Split text into word-based chunks.

    Simple meaning:
    Large document text cannot be embedded or sent to the LLM all at once.
    So we split it into smaller searchable pieces.

    chunk_size:
    Number of words in each chunk.

    overlap:
    Number of words repeated between two chunks.
    This helps avoid losing meaning at chunk boundaries.
    """

    # If chunk_size is invalid, raise clear error.
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")

    # If overlap is negative, raise clear error.
    if overlap < 0:
        raise ValueError("overlap cannot be negative.")

    # If overlap is equal to or bigger than chunk_size, chunking can loop forever.
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    # Split text into words.
    words = text.split()

    # Create empty list to store chunk strings.
    chunks = []

    # If text has no words, return empty list.
    if not words:
        return chunks

    # Start from first word.
    start = 0

    # Continue until we reach the end of the word list.
    while start < len(words):
        # Calculate where this chunk should end.
        end = start + chunk_size

        # Take words from start to end.
        chunk_words = words[start:end]

        # Join words back into one text chunk.
        chunk = " ".join(chunk_words)

        # Add this chunk to the result list.
        chunks.append(chunk)

        # If this chunk reached the end, stop.
        if end >= len(words):
            break

        # Move start forward but keep overlap words.
        start = end - overlap

    # Return all chunks.
    return chunks


# Define a helper function to create one chunk record.
def create_chunk_record(
    chunk_id: str,
    document_id: str,
    page_number: int | None,
    text: str,
    section_title: str | None,
    content_type: str,
    parser_used: str,
) -> dict:
    """
    Create one standard chunk dictionary.

    Simple meaning:
    Whether the chunk came from PyMuPDF or Docling,
    we want the final chunk format to be consistent.
    """

    # Count words inside chunk.
    word_count = len(text.split())

    # Return one chunk record.
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_number": page_number,
        "section_title": section_title,
        "content_type": content_type,
        "parser_used": parser_used,
        "text": text,
        "word_count": word_count,
    }


# Define a function to chunk old PyMuPDF-style page text.
def chunk_plain_page(
    page: dict,
    document_id: str,
    chunk_counter: int,
    parser_used: str,
    chunk_size: int,
    overlap: int,
) -> tuple[list[dict], int]:
    """
    Chunk old PyMuPDF-style page text.

    Old input format:
    {
        "page_number": 1,
        "text": "..."
    }

    This keeps PyMuPDF fallback working.
    """

    # Get page number.
    page_number = page.get("page_number")

    # Get page text.
    page_text = page.get("text", "")

    # Split page text into chunks.
    page_chunks = chunk_text(
        text=page_text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    # Create empty list for chunk records.
    chunk_records = []

    # Loop through chunks created from this page.
    for chunk in page_chunks:
        # Create chunk ID.
        chunk_id = f"chunk_{chunk_counter:03d}"

        # Create chunk record.
        chunk_record = create_chunk_record(
            chunk_id=chunk_id,
            document_id=document_id,
            page_number=page_number,
            text=chunk,
            section_title=None,
            content_type="paragraph",
            parser_used=parser_used,
        )

        # Add chunk record to list.
        chunk_records.append(chunk_record)

        # Increase chunk counter.
        chunk_counter += 1

    # Return chunk records and updated counter.
    return chunk_records, chunk_counter


# Define a function to chunk Docling layout-aware blocks.
def chunk_layout_blocks(
    page: dict,
    document_id: str,
    chunk_counter: int,
    parser_used: str,
    chunk_size: int,
    overlap: int,
) -> tuple[list[dict], int]:
    """
    Chunk new Docling-style layout blocks.

    New input format:
    {
        "page_number": 1,
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
    """

    # Get page number.
    page_number = page.get("page_number")

    # Get layout blocks.
    blocks = page.get("blocks", [])

    # Create empty list for chunk records.
    chunk_records = []

    # Track current section title.
    # If a paragraph has no section_title, we use the latest heading.
    current_section_title = None

    # Loop through blocks.
    for block in blocks:
        # Get block text.
        block_text = block.get("text", "")

        # Skip empty blocks.
        if not block_text.strip():
            continue

        # Get content type.
        # Possible values: heading, paragraph, table.
        content_type = block.get("content_type", "paragraph")

        # Get section title from block.
        section_title = block.get("section_title")

        # If current block is a heading, update current section.
        if content_type == "heading":
            current_section_title = block_text.strip()
            section_title = current_section_title

        # If section title is missing, use current section title.
        if not section_title:
            section_title = current_section_title

        # Split block text into chunks.
        # For short headings/tables, this usually creates one chunk.
        block_chunks = chunk_text(
            text=block_text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        # Loop through chunks from this block.
        for chunk in block_chunks:
            # Create chunk ID.
            chunk_id = f"chunk_{chunk_counter:03d}"

            # Create chunk record.
            chunk_record = create_chunk_record(
                chunk_id=chunk_id,
                document_id=document_id,
                page_number=page_number,
                text=chunk,
                section_title=section_title,
                content_type=content_type,
                parser_used=parser_used,
            )

            # Add chunk record.
            chunk_records.append(chunk_record)

            # Increase counter.
            chunk_counter += 1

    # Return chunks and updated counter.
    return chunk_records, chunk_counter


# Define a function to create chunks from extracted_text.json.
def create_chunks_from_extracted_text(
    extracted_text_path: str,
    document_id: str,
    chunk_size: int = 150,
    overlap: int = 30,
) -> dict:
    """
    Create chunks from extracted_text.json.

    Supports:
    1. Old PyMuPDF extracted_text.json with page["text"]
    2. New Docling extracted_text.json with page["blocks"]

    Output file:
    uploads/{document_id}/chunks.json
    """

    # Convert extracted_text_path string into Path object.
    extracted_path = Path(extracted_text_path)

    # Check if extracted_text.json exists.
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted text file not found: {extracted_text_path}")

    # Open extracted_text.json.
    with open(extracted_path, "r", encoding="utf-8") as file:
        extracted_data = json.load(file)

    # Read parser used.
    # If old PyMuPDF file does not have parser_used, default to pymupdf.
    parser_used = extracted_data.get("parser_used", "pymupdf")

    # Get pages.
    pages = extracted_data.get("pages", [])

    # Create empty list to store all chunks.
    all_chunks = []

    # Create chunk counter.
    chunk_counter = 1

    # Loop through pages.
    for page in pages:
        # If page has layout blocks, use Docling-style chunking.
        if page.get("blocks"):
            page_chunks, chunk_counter = chunk_layout_blocks(
                page=page,
                document_id=document_id,
                chunk_counter=chunk_counter,
                parser_used=parser_used,
                chunk_size=chunk_size,
                overlap=overlap,
            )

        # Otherwise use old plain page text chunking.
        else:
            page_chunks, chunk_counter = chunk_plain_page(
                page=page,
                document_id=document_id,
                chunk_counter=chunk_counter,
                parser_used=parser_used,
                chunk_size=chunk_size,
                overlap=overlap,
            )

        # Add page chunks to all chunks.
        all_chunks.extend(page_chunks)

    # Create chunks.json path in same folder as extracted_text.json.
    chunks_path = extracted_path.parent / "chunks.json"

    # Create final chunks data.
    chunks_data = {
        "document_id": document_id,
        "parser_used": parser_used,
        "chunk_count": len(all_chunks),
        "chunks": all_chunks,
    }

    # Save chunks.json.
    with open(chunks_path, "w", encoding="utf-8") as file:
        json.dump(chunks_data, file, indent=4, ensure_ascii=False)

    # Return useful result.
    return {
        "chunk_count": len(all_chunks),
        "chunks_path": str(chunks_path),
        "parser_used": parser_used,
    }


# Define a function to read chunks from chunks.json.
def load_chunks(chunks_path: str) -> dict:
    """
    Read chunks from chunks.json.
    """

    # Convert chunks_path string into Path object.
    path = Path(chunks_path)

    # Check if chunks.json exists.
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    # Open chunks.json.
    with open(path, "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    # Return chunks data.
    return chunks_data