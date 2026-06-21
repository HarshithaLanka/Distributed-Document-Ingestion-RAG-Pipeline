# This file handles chunking extracted PDF text.

# Import json to read extracted_text.json and write chunks.json.
import json

# Import Path to work with file paths safely.
from pathlib import Path

# Import List for type hints.
from typing import List


# Define a function to split text into word-based chunks.
def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> List[str]:
    # Split the text into words.
    words = text.split()

    # Create an empty list to store chunks.
    chunks = []

    # If text has no words, return empty chunk list.
    if not words:
        return chunks

    # Start from first word.
    start = 0

    # Continue until we reach the end of words.
    while start < len(words):
        # Calculate end position for current chunk.
        end = start + chunk_size

        # Take words from start to end.
        chunk_words = words[start:end]

        # Join words back into text.
        chunk = " ".join(chunk_words)

        # Add chunk to chunks list.
        chunks.append(chunk)

        # Move start forward.
        # We subtract overlap so some words repeat in next chunk.
        start = end - overlap

        # Safety check:
        # If overlap is greater than or equal to chunk_size, avoid infinite loop.
        if start < 0:
            start = end

    # Return all created chunks.
    return chunks


# Define a function to create chunks from extracted_text.json.
def create_chunks_from_extracted_text(
    extracted_text_path: str,
    document_id: str,
    chunk_size: int = 150,
    overlap: int = 30
) -> dict:
    # Convert extracted_text_path string into Path object.
    extracted_path = Path(extracted_text_path)

    # Check if extracted_text.json exists.
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted text file not found: {extracted_text_path}")

    # Open extracted_text.json in read mode.
    with open(extracted_path, "r", encoding="utf-8") as file:
        # Load extracted JSON data into Python dictionary.
        extracted_data = json.load(file)

    # Get pages from extracted data.
    pages = extracted_data.get("pages", [])

    # Create empty list to store all chunks.
    all_chunks = []

    # Create chunk counter.
    chunk_counter = 1

    # Loop through each page.
    for page in pages:
        # Get page number.
        page_number = page.get("page_number")

        # Get page text.
        page_text = page.get("text", "")

        # Create chunks for this page text.
        page_chunks = chunk_text(
            text=page_text,
            chunk_size=chunk_size,
            overlap=overlap
        )

        # Loop through chunks created from this page.
        for chunk in page_chunks:
            # Count words in this chunk.
            word_count = len(chunk.split())

            # Create chunk ID.
            # Example: chunk_001, chunk_002
            chunk_id = f"chunk_{chunk_counter:03d}"

            # Create chunk metadata.
            chunk_record = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "page_number": page_number,
                "text": chunk,
                "word_count": word_count
            }

            # Add chunk record to all_chunks list.
            all_chunks.append(chunk_record)

            # Increase chunk counter by 1.
            chunk_counter += 1

    # Create chunks.json path in same folder as extracted_text.json.
    chunks_path = extracted_path.parent / "chunks.json"

    # Create final chunks data.
    chunks_data = {
        "document_id": document_id,
        "chunk_count": len(all_chunks),
        "chunks": all_chunks
    }

    # Save chunks data into chunks.json.
    with open(chunks_path, "w", encoding="utf-8") as file:
        json.dump(chunks_data, file, indent=4, ensure_ascii=False)

    # Return useful result.
    return {
        "chunk_count": len(all_chunks),
        "chunks_path": str(chunks_path)
    }


# Define a function to read chunks from chunks.json.
def load_chunks(chunks_path: str) -> dict:
    # Convert chunks_path string into Path object.
    path = Path(chunks_path)

    # Check if chunks.json exists.
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    # Open chunks.json in read mode.
    with open(path, "r", encoding="utf-8") as file:
        # Load chunks JSON data.
        chunks_data = json.load(file)

    # Return chunks data.
    return chunks_data