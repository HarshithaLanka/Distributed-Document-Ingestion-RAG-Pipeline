# Import json so we can read chunks from redacted_chunks.json.
import json

# Import re so we can tokenize text more cleanly than simple split().
import re

# Import Path so paths work safely on Windows and other systems.
from pathlib import Path

# Import Optional so some function inputs can be optional.
from typing import Optional

# Import BM25Okapi from rank_bm25.
from rank_bm25 import BM25Okapi


# Try to import UPLOAD_DIR from your config.
# If your config does not have UPLOAD_DIR, we safely fall back to "uploads".
try:
    from app.config import UPLOAD_DIR
except Exception:
    UPLOAD_DIR = "uploads"


# This class is a simple BM25 search result object.
# We use a class instead of raw dictionary so the result format is clean.
class BM25SearchResult:
    def __init__(
        self,
        document_id: str,
        chunk_id: str,
        text: str,
        score: float,
        page_number: Optional[int] = None,
        section_title: Optional[str] = None,
        content_type: Optional[str] = None,
        parser_used: Optional[str] = None,
        word_count: Optional[int] = None,
    ):
        # Store document ID.
        self.document_id = document_id

        # Store chunk ID.
        self.chunk_id = chunk_id

        # Store chunk text.
        self.text = text

        # Store BM25 score.
        self.score = score

        # Store page number for citations.
        self.page_number = page_number

        # Store section title if available from Week 10 Docling parsing.
        self.section_title = section_title

        # Store content type like paragraph/table/heading.
        self.content_type = content_type

        # Store parser name like docling or pymupdf.
        self.parser_used = parser_used

        # Store word count if available.
        self.word_count = word_count

    def to_dict(self) -> dict:
        # Convert result object into JSON-friendly dictionary.
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "content_type": self.content_type,
            "parser_used": self.parser_used,
            "word_count": self.word_count,
        }


def tokenize_text(text: str) -> list[str]:
    """
    Convert text into searchable tokens.

    New concept:
    Tokenization means splitting text into small searchable words.

    Example:
    "Week 13: BM25 Search"
    becomes:
    ["week", "13", "bm25", "search"]
    """

    # If text is None or empty, return an empty list.
    if not text:
        return []

    # Convert text to lowercase so BM25 search is case-insensitive.
    text = text.lower()

    # Find words, numbers, and mixed tokens like bm25, sqs, section 4.2.
    # This keeps useful technical terms better than normal split().
    tokens = re.findall(r"[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?", text)

    # Return only non-empty tokens.
    return [token.strip() for token in tokens if token.strip()]


def get_document_folder(document_id: str) -> Path:
    """
    Return local folder path for one document.

    Example:
    uploads/doc_abc123
    """

    # Convert UPLOAD_DIR to a Path object.
    upload_root = Path(UPLOAD_DIR)

    # Return document-specific folder.
    return upload_root / document_id


def get_chunks_file_path(document_id: str) -> Path:
    """
    Find the best chunks file for BM25.

    Privacy rule:
    Week 11 created redacted_chunks.json so sensitive values are not indexed.
    BM25 should prefer redacted_chunks.json.

    Fallback:
    If redacted_chunks.json is not present, use chunks.json.
    """

    # Get folder for this document.
    document_folder = get_document_folder(document_id)

    # This is the privacy-safe chunks file.
    redacted_chunks_path = document_folder / "redacted_chunks.json"

    # This is the older raw chunks file.
    chunks_path = document_folder / "chunks.json"

    # Prefer redacted chunks if available.
    if redacted_chunks_path.exists():
        return redacted_chunks_path

    # Fallback to normal chunks.
    if chunks_path.exists():
        return chunks_path

    # If neither file exists, raise a clear error.
    raise FileNotFoundError(
        f"No chunks file found for document_id={document_id}. "
        f"Expected {redacted_chunks_path} or {chunks_path}."
    )


def load_chunks_for_bm25(document_id: str) -> list[dict]:
    """
    Load chunks from local JSON file.

    Expected file:
    uploads/{document_id}/redacted_chunks.json

    Fallback file:
    uploads/{document_id}/chunks.json
    """

    # Find chunks file path.
    chunks_file_path = get_chunks_file_path(document_id)

    # Open JSON file using utf-8 encoding.
    with open(chunks_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Some projects store chunks directly as a list.
    if isinstance(data, list):
        chunks = data

    # Some projects store chunks inside {"chunks": [...]}.
    elif isinstance(data, dict) and "chunks" in data:
        chunks = data["chunks"]

    # Some projects store chunks inside {"redacted_chunks": [...]}.
    elif isinstance(data, dict) and "redacted_chunks" in data:
        chunks = data["redacted_chunks"]

    # If format is unknown, raise clear error.
    else:
        raise ValueError(
            f"Unsupported chunks JSON format in {chunks_file_path}. "
            "Expected list, {'chunks': [...]}, or {'redacted_chunks': [...]}."
        )

    # Keep only chunks that have useful text.
    cleaned_chunks = []

    for chunk in chunks:
        # Get text from common possible keys.
        text = (
            chunk.get("text")
            or chunk.get("source_text")
            or chunk.get("redacted_text")
            or ""
        )

        # Skip empty chunks.
        if not text.strip():
            continue

        # Add normalized text field so later code can rely on chunk["text"].
        normalized_chunk = dict(chunk)
        normalized_chunk["text"] = text

        cleaned_chunks.append(normalized_chunk)

    return cleaned_chunks


def build_bm25_index(chunks: list[dict]) -> BM25Okapi:
    """
    Build a BM25 index from chunks.

    BM25 does not store vectors.
    It stores tokenized words and uses them to score keyword matches.
    """

    # Convert every chunk text into tokens.
    tokenized_corpus = [tokenize_text(chunk.get("text", "")) for chunk in chunks]

    # Create BM25 index.
    return BM25Okapi(tokenized_corpus)


def search_document_with_bm25(
    document_id: str,
    query: str,
    top_k: int = 5,
) -> list[BM25SearchResult]:
    """
    Search one document using BM25 keyword search.

    Input:
    - document_id: which document to search
    - query: user question/search text
    - top_k: how many chunks to return

    Output:
    - list of BM25SearchResult objects
    """

    # Validate query.
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    # Keep top_k within safe range.
    if top_k <= 0:
        top_k = 5

    if top_k > 20:
        top_k = 20

    # Load redacted chunks if available.
    chunks = load_chunks_for_bm25(document_id)

    # If no chunks exist, return empty results.
    if not chunks:
        return []

    # Build BM25 index from chunks.
    bm25_index = build_bm25_index(chunks)

    # Tokenize user query.
    tokenized_query = tokenize_text(query)

    # If tokenization gives no words, return empty results.
    if not tokenized_query:
        return []

    # Get BM25 score for every chunk.
    scores = bm25_index.get_scores(tokenized_query)

    # Combine each chunk with its score.
    scored_results = []

    for chunk, score in zip(chunks, scores):
        # BM25 can return zero score for chunks that do not match.
        # We keep only positive matches to avoid noisy results.
        if float(score) <= 0:
            continue

        # Create clean result object.
        result = BM25SearchResult(
            document_id=document_id,
            chunk_id=chunk.get("chunk_id", ""),
            text=chunk.get("text", ""),
            score=float(score),
            page_number=chunk.get("page_number"),
            section_title=chunk.get("section_title"),
            content_type=chunk.get("content_type"),
            parser_used=chunk.get("parser_used"),
            word_count=chunk.get("word_count"),
        )

        scored_results.append(result)

    # Sort highest BM25 score first.
    scored_results.sort(key=lambda result: result.score, reverse=True)

    # Return only top_k results.
    return scored_results[:top_k]


def search_document_with_bm25_as_dicts(
    document_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Same as search_document_with_bm25,
    but returns dictionaries for FastAPI JSON responses.
    """

    # Get result objects.
    results = search_document_with_bm25(
        document_id=document_id,
        query=query,
        top_k=top_k,
    )

    # Convert each result object to dictionary.
    return [result.to_dict() for result in results]