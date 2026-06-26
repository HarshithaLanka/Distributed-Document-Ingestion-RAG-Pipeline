# Import json so we can create fake extracted_text.json and chunks.json files during tests.
import json

# Import pytest so we can test expected errors like FileNotFoundError.
import pytest

# Import chunk_text from your chunking service.
from app.services.chunking_service import chunk_text

# Import create_chunks_from_extracted_text from your chunking service.
from app.services.chunking_service import create_chunks_from_extracted_text

# Import load_chunks from your chunking service.
from app.services.chunking_service import load_chunks


# Test 1:
# Check that empty text returns an empty list.
def test_chunk_text_empty_text():
    # Call chunk_text with empty text.
    chunks = chunk_text("")

    # Empty text should not create any chunks.
    assert chunks == []


# Test 2:
# Check that small text creates only one chunk.
def test_chunk_text_small_text_creates_one_chunk():
    # Create a small text sample.
    text = "This is a small document."

    # Chunk the text using a large chunk size.
    chunks = chunk_text(
        text=text,
        chunk_size=50,
        overlap=10
    )

    # Since the text is small, only one chunk should be created.
    assert len(chunks) == 1

    # The chunk text should be the same as the original text.
    assert chunks[0] == text


# Test 3:
# Check that large text creates multiple chunks.
def test_chunk_text_large_text_creates_multiple_chunks():
    # Create sample text with 25 words.
    text = " ".join([f"word{i}" for i in range(1, 26)])

    # Chunk the text with chunk size 10 and overlap 2.
    chunks = chunk_text(
        text=text,
        chunk_size=10,
        overlap=2
    )

    # More than one chunk should be created.
    assert len(chunks) > 1

    # First chunk should contain exactly 10 words.
    assert len(chunks[0].split()) == 10

    # Second chunk should not be empty.
    assert len(chunks[1].split()) > 0


# Test 4:
# Check that overlap is working correctly.
def test_chunk_text_overlap_is_working():
    # Create sample text with 15 words.
    text = " ".join([f"word{i}" for i in range(1, 16)])

    # Chunk the text with chunk size 10 and overlap 3.
    chunks = chunk_text(
        text=text,
        chunk_size=10,
        overlap=3
    )

    # Get words from the first chunk.
    first_chunk_words = chunks[0].split()

    # Get words from the second chunk.
    second_chunk_words = chunks[1].split()

    # The last 3 words of the first chunk should match
    # the first 3 words of the second chunk.
    assert first_chunk_words[-3:] == second_chunk_words[:3]


# Test 5:
# Check that create_chunks_from_extracted_text creates chunks.json correctly.
def test_create_chunks_from_extracted_text_creates_chunks_json(tmp_path):
    # tmp_path is a temporary test folder created by pytest.
    # Simple meaning:
    # We can create test files safely without touching real uploads/ data.

    # Create fake document ID.
    document_id = "test_document_123"

    # Create fake extracted text data in the same format as extracted_text.json.
    extracted_data = {
        "document_id": document_id,
        "page_count": 2,
        "pages": [
            {
                "page_number": 1,
                "text": "This is page one text for testing chunk creation."
            },
            {
                "page_number": 2,
                "text": "This is page two text for testing page number preservation."
            }
        ]
    }

    # Create temporary extracted_text.json path.
    extracted_text_path = tmp_path / "extracted_text.json"

    # Write fake extracted text data into extracted_text.json.
    with open(extracted_text_path, "w", encoding="utf-8") as file:
        json.dump(extracted_data, file, indent=4)

    # Call your actual chunk creation function.
    result = create_chunks_from_extracted_text(
        extracted_text_path=str(extracted_text_path),
        document_id=document_id,
        chunk_size=5,
        overlap=1
    )

    # Check that result has chunk_count.
    assert "chunk_count" in result

    # Check that result has chunks_path.
    assert "chunks_path" in result

    # At least one chunk should be created.
    assert result["chunk_count"] > 0

    # chunks.json should be created in the same temporary folder.
    chunks_path = tmp_path / "chunks.json"

    # Check that chunks.json exists.
    assert chunks_path.exists()

    # Load the created chunks.json file.
    with open(chunks_path, "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    # Check top-level document_id.
    assert chunks_data["document_id"] == document_id

    # Check chunk_count matches actual chunks list length.
    assert chunks_data["chunk_count"] == len(chunks_data["chunks"])

    # Get the first chunk.
    first_chunk = chunks_data["chunks"][0]

    # Check that important metadata fields exist.
    assert "chunk_id" in first_chunk
    assert "document_id" in first_chunk
    assert "page_number" in first_chunk
    assert "text" in first_chunk
    assert "word_count" in first_chunk

    # Check that chunk_id starts correctly.
    assert first_chunk["chunk_id"] == "chunk_001"

    # Check document_id is preserved inside the chunk.
    assert first_chunk["document_id"] == document_id

    # Check page number is preserved for citations.
    assert first_chunk["page_number"] == 1

    # Check chunk text is not empty.
    assert first_chunk["text"].strip() != ""

    # Check word_count is correct.
    assert first_chunk["word_count"] == len(first_chunk["text"].split())


# Test 6:
# Check that load_chunks reads chunks.json correctly.
def test_load_chunks_reads_chunks_json(tmp_path):
    # Create fake chunks data.
    chunks_data = {
        "document_id": "test_document_123",
        "chunk_count": 1,
        "chunks": [
            {
                "chunk_id": "chunk_001",
                "document_id": "test_document_123",
                "page_number": 1,
                "text": "This is a test chunk.",
                "word_count": 5
            }
        ]
    }

    # Create temporary chunks.json path.
    chunks_path = tmp_path / "chunks.json"

    # Write fake chunks data into chunks.json.
    with open(chunks_path, "w", encoding="utf-8") as file:
        json.dump(chunks_data, file, indent=4)

    # Call your actual load_chunks function.
    loaded_data = load_chunks(str(chunks_path))

    # Check document_id was loaded correctly.
    assert loaded_data["document_id"] == "test_document_123"

    # Check chunk_count was loaded correctly.
    assert loaded_data["chunk_count"] == 1

    # Check first chunk ID.
    assert loaded_data["chunks"][0]["chunk_id"] == "chunk_001"

    # Check page number.
    assert loaded_data["chunks"][0]["page_number"] == 1


# Test 7:
# Check that missing extracted_text.json raises FileNotFoundError.
def test_create_chunks_from_missing_extracted_text_raises_error(tmp_path):
    # Create a path that does not exist.
    missing_file_path = tmp_path / "missing_extracted_text.json"

    # The function should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        create_chunks_from_extracted_text(
            extracted_text_path=str(missing_file_path),
            document_id="test_document_123"
        )


# Test 8:
# Check that missing chunks.json raises FileNotFoundError.
def test_load_chunks_missing_file_raises_error(tmp_path):
    # Create a path that does not exist.
    missing_chunks_path = tmp_path / "missing_chunks.json"

    # The function should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        load_chunks(str(missing_chunks_path))