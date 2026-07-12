"""
Entity extraction service for Document_Intelligence_RAG.

Week 12 purpose:
- Read chunk text.
- Detect important named entities like people, organizations, dates, locations.
- Return entities with document_id, chunk_id, page_number, and section_title.
- Later, these entities will be stored in Neo4j.

Important privacy rule:
- We should run this on redacted chunks, not raw chunks.
- We also ignore placeholders like [EMAIL_REDACTED].
"""

# Import annotations so type hints work cleanly in older/newer Python versions.
from __future__ import annotations

# Import json because smoke tests or helper functions may load chunk JSON files.
import json

# Import re because we need small regex cleanup checks.
import re

# Import Path for safe file path handling.
from pathlib import Path

# Import Any, Dict, List, Optional for readable type hints.
from typing import Any, Dict, List, Optional

# Import spacy, the NLP library used for Named Entity Recognition.
import spacy

# Import Language type only for type hints.
from spacy.language import Language


# Name of the spaCy English model we are using.
# Simple meaning:
# This model knows how to detect common English entities.
SPACY_MODEL_NAME = "en_core_web_sm"


# This global variable stores the loaded spaCy model.
# Simple meaning:
# Loading spaCy is a little heavy, so we load it once and reuse it.
_NLP_MODEL: Optional[Language] = None


# Entity labels we want to keep.
# spaCy detects many labels. We keep the useful ones for document intelligence.
ALLOWED_ENTITY_LABELS = {
    "PERSON",       # Person name
    "ORG",          # Organization/company/university
    "GPE",          # Country, city, state
    "LOC",          # Location
    "DATE",         # Date
    "TIME",         # Time
    "PRODUCT",      # Product/tool name
    "EVENT",        # Event name
    "WORK_OF_ART",  # Book, paper, report title, etc.
    "LAW",          # Legal clause/law name
    "FAC",          # Facility/building
    "NORP",         # Nationality/religious/political group label from spaCy
}


# Redaction placeholders from Week 11.
# We do not want these to become graph entities.
REDACTION_PLACEHOLDERS = {
    "[EMAIL_REDACTED]",
    "[PHONE_REDACTED]",
    "[SSN_REDACTED]",
}


# Week 14 addition:
# The small spaCy English model can miss technical terms such as AWS, SQS,
# BM25, PII, Neo4j, and GPT-4. This regex detects common technical tokens.
TECHNICAL_TOKEN_PATTERN = re.compile(
    r"\b(?:"
    r"[A-Z][A-Z0-9_-]{1,}"              # AWS, SQS, BM25, PII
    r"|[A-Za-z]+\d+[A-Za-z0-9]*"        # Neo4j, Python3, GPT4o
    r"|[A-Za-z]+(?:\.[A-Za-z0-9]+)+"    # Dotted technical names
    r")\b"
)


def load_ner_model() -> Language:
    """
    Load the spaCy NER model.

    New word:
    NER means Named Entity Recognition.

    Simple meaning:
    This function loads the NLP model that can detect people,
    organizations, dates, locations, and similar entities.
    """

    # Tell Python we want to update/use the global model variable.
    global _NLP_MODEL

    # If the model is already loaded, return it directly.
    if _NLP_MODEL is not None:
        return _NLP_MODEL

    try:
        # Load the spaCy English model.
        _NLP_MODEL = spacy.load(SPACY_MODEL_NAME)

    except OSError as exc:
        # This happens if the user installed spaCy but forgot to download the model.
        raise RuntimeError(
            "spaCy model is not installed. Run this command first: "
            "python -m spacy download en_core_web_sm"
        ) from exc

    # Return the loaded model.
    return _NLP_MODEL


def normalize_entity_text(text: str) -> str:
    """
    Normalize entity text.

    New word:
    Normalize means convert text into a cleaner standard format.

    Example:
    '  Andhra   University  ' becomes 'Andhra University'

    Why:
    Neo4j should not store duplicate-looking entities just because spacing differs.
    """

    # If text is None or empty, return an empty string.
    if not text:
        return ""

    # Replace multiple spaces/newlines/tabs with one space.
    cleaned_text = re.sub(r"\s+", " ", text)

    # Remove extra spaces from beginning and end.
    cleaned_text = cleaned_text.strip()

    # Return cleaned text.
    return cleaned_text


def is_redaction_placeholder(text: str) -> bool:
    """
    Check if text is a Week 11 redaction placeholder.

    Simple meaning:
    We do not want [EMAIL_REDACTED] to appear as a real entity in Neo4j.
    """

    # Normalize the text before checking.
    normalized_text = normalize_entity_text(text)

    # Return True if text exactly matches one of our placeholders.
    if normalized_text in REDACTION_PLACEHOLDERS:
        return True

    # Return True if it contains REDACTED inside square brackets.
    if re.fullmatch(r"\[[A-Z_]*REDACTED\]", normalized_text):
        return True

    # Otherwise, it is not a redaction placeholder.
    return False


def should_keep_entity(entity_text: str, entity_label: str) -> bool:
    """
    Decide whether an entity should be kept.

    Simple meaning:
    spaCy may detect small/noisy things. This function filters bad entities.
    """

    # Normalize the entity text.
    normalized_text = normalize_entity_text(entity_text)

    # Remove empty entities.
    if not normalized_text:
        return False

    # Remove very short entities like single characters.
    if len(normalized_text) < 2:
        return False

    # Remove redacted values.
    if is_redaction_placeholder(normalized_text):
        return False

    # Keep only labels we care about.
    if entity_label not in ALLOWED_ENTITY_LABELS:
        return False

    # Avoid keeping entities that are only punctuation.
    if not re.search(r"[A-Za-z0-9]", normalized_text):
        return False

    # If it passed all checks, keep it.
    return True


def extract_entities_from_text(
    text: str,
    document_id: Optional[str] = None,
    chunk_id: Optional[str] = None,
    page_number: Optional[int] = None,
    section_title: Optional[str] = None,
    content_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Extract entities from one text string.

    Parameters:
    - text: chunk text
    - document_id: which document this text belongs to
    - chunk_id: which chunk this text belongs to
    - page_number: page number for citations
    - section_title: Docling section title if available
    - content_type: paragraph/table/heading if available

    Returns:
    A list of entity dictionaries.
    """

    # If text is empty, return no entities.
    if not text:
        return []

    # Load the spaCy model.
    nlp = load_ner_model()

    # Run NLP over the text.
    # Simple meaning:
    # spaCy reads the text and fills doc.ents with detected entities.
    doc = nlp(text)

    # This list will store final extracted entities.
    entities: List[Dict[str, Any]] = []

    # Go through every entity detected by spaCy.
    for entity in doc.ents:
        # Clean the entity text.
        entity_text = normalize_entity_text(entity.text)

        # Get the entity label, like PERSON, ORG, DATE.
        entity_label = entity.label_

        # Skip noisy or unsafe entities.
        if not should_keep_entity(entity_text, entity_label):
            continue

        # Add a clean entity dictionary.
        entities.append(
            {
                "text": entity_text,
                "normalized_text": entity_text.lower(),
                "label": entity_label,
                "start_char": entity.start_char,
                "end_char": entity.end_char,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "page_number": page_number,
                "section_title": section_title,
                "content_type": content_type,
            }
        )

    # Remove duplicate entities detected inside the same text.
    entities = deduplicate_entities(entities)

    # Return all useful entities.
    return entities



def deduplicate_entities(
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove duplicate entities while preserving their first occurrence.

    Simple meaning:
    If spaCy and the technical-token fallback both detect the same entity,
    we should return it only once.

    Deduplication key:
    normalized_text + label
    """

    # Final unique entities.
    unique_entities: List[Dict[str, Any]] = []

    # Store entity keys already seen.
    seen_keys = set()

    # Loop through all entities.
    for entity in entities:
        # Read and clean normalized text.
        normalized_text = str(
            entity.get("normalized_text", "")
        ).strip().lower()

        # Read and clean label.
        label = str(entity.get("label", "")).strip().upper()

        # Skip invalid entities.
        if not normalized_text or not label:
            continue

        # Build a stable duplicate-checking key.
        key = (normalized_text, label)

        # Skip duplicate entity.
        if key in seen_keys:
            continue

        # Remember this entity.
        seen_keys.add(key)

        # Keep the entity.
        unique_entities.append(entity)

    # Return unique entities.
    return unique_entities


def extract_query_entities(question: str) -> List[Dict[str, Any]]:
    """
    Extract entities from a user's question for Week 14 graph retrieval.

    This function is different from extract_entities_from_text():

    - extract_entities_from_text() is used while processing document chunks.
    - extract_query_entities() is used every time the user asks a question.

    Example question:
    "How does Neo4j improve BM25 and Pinecone retrieval?"

    Possible result:
    [
        {
            "text": "Neo4j",
            "normalized_text": "neo4j",
            "label": "PRODUCT"
        },
        {
            "text": "BM25",
            "normalized_text": "bm25",
            "label": "PRODUCT"
        }
    ]

    Only the fields required for graph retrieval are returned.
    """

    # Empty questions have no entities.
    if not question or not question.strip():
        return []

    # First run normal spaCy entity extraction.
    detected_entities = extract_entities_from_text(text=question)

    # Store compact query entity dictionaries.
    query_entities: List[Dict[str, Any]] = []

    # Convert normal entity output into query entity output.
    for entity in detected_entities:
        query_entities.append(
            {
                "text": entity.get("text", ""),
                "normalized_text": entity.get("normalized_text", ""),
                "label": entity.get("label", ""),
            }
        )

    # Add technical words that spaCy may miss.
    for match in TECHNICAL_TOKEN_PATTERN.finditer(question):
        # Clean detected technical token.
        technical_text = normalize_entity_text(match.group(0))

        # Skip empty or redacted text.
        if not technical_text:
            continue

        if is_redaction_placeholder(technical_text):
            continue

        # Add it as a PRODUCT-style entity.
        query_entities.append(
            {
                "text": technical_text,
                "normalized_text": technical_text.lower(),
                "label": "PRODUCT",
            }
        )

    # Remove duplicates before returning.
    return deduplicate_entities(query_entities)


def extract_entities_from_chunks(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract entities from many chunks.

    Simple meaning:
    This function loops over redacted_chunks.json content and extracts entities
    from each chunk's text.
    """

    # Store all entity mentions from all chunks.
    all_entities: List[Dict[str, Any]] = []

    # Loop over each chunk.
    for chunk in chunks:
        # Get chunk text.
        # Some files may use "text", Pinecone metadata may use "source_text".
        text = chunk.get("text") or chunk.get("source_text") or ""

        # Get metadata from the chunk.
        document_id = chunk.get("document_id")
        chunk_id = chunk.get("chunk_id")
        page_number = chunk.get("page_number")
        section_title = chunk.get("section_title")
        content_type = chunk.get("content_type")

        # Extract entities from this one chunk.
        chunk_entities = extract_entities_from_text(
            text=text,
            document_id=document_id,
            chunk_id=chunk_id,
            page_number=page_number,
            section_title=section_title,
            content_type=content_type,
        )

        # Add this chunk's entities to the full list.
        all_entities.extend(chunk_entities)

    # Return all extracted entities.
    return all_entities


def summarize_entities(
    entity_mentions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Summarize repeated entity mentions.

    Example:
    If 'Andhra University' appears in 3 chunks, this returns one summary row:
    {
        name: 'Andhra University',
        label: 'ORG',
        mention_count: 3,
        pages: [1, 2],
        chunk_ids: [...]
    }

    This summary is useful for GET /documents/{document_id}/entities later.
    """

    # Dictionary for grouping entities.
    grouped: Dict[str, Dict[str, Any]] = {}

    # Loop through each entity mention.
    for mention in entity_mentions:
        # Build a unique grouping key using normalized text and label.
        key = f"{mention.get('normalized_text')}::{mention.get('label')}"

        # If this entity is not already in grouped, create it.
        if key not in grouped:
            grouped[key] = {
                "name": mention.get("text"),
                "normalized_text": mention.get("normalized_text"),
                "label": mention.get("label"),
                "mention_count": 0,
                "pages": set(),
                "chunk_ids": set(),
                "sections": set(),
            }

        # Increase mention count.
        grouped[key]["mention_count"] += 1

        # Add page number if present.
        if mention.get("page_number") is not None:
            grouped[key]["pages"].add(mention.get("page_number"))

        # Add chunk ID if present.
        if mention.get("chunk_id"):
            grouped[key]["chunk_ids"].add(mention.get("chunk_id"))

        # Add section title if present.
        if mention.get("section_title"):
            grouped[key]["sections"].add(mention.get("section_title"))

    # Convert sets into sorted lists because JSON cannot store Python sets.
    summaries: List[Dict[str, Any]] = []

    # Loop through grouped entities.
    for item in grouped.values():
        # Convert pages to sorted list.
        pages = sorted(item["pages"])

        # Convert chunk IDs to sorted list.
        chunk_ids = sorted(item["chunk_ids"])

        # Convert sections to sorted list.
        sections = sorted(item["sections"])

        # Add clean summary.
        summaries.append(
            {
                "name": item["name"],
                "normalized_text": item["normalized_text"],
                "label": item["label"],
                "mention_count": item["mention_count"],
                "pages": pages,
                "chunk_ids": chunk_ids,
                "sections": sections,
            }
        )

    # Sort most mentioned entities first.
    summaries.sort(key=lambda item: item["mention_count"], reverse=True)

    # Return final summaries.
    return summaries


def load_chunks_from_json_file(file_path: str | Path) -> List[Dict[str, Any]]:
    """
    Load chunks from a JSON file.

    Supports both formats:
    1. Direct list:
       [ {chunk1}, {chunk2} ]

    2. Dictionary:
       { "chunks": [ {chunk1}, {chunk2} ] }
    """

    # Convert file path into a Path object.
    path = Path(file_path)

    # Open and read JSON file.
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # If JSON is already a list, return it.
    if isinstance(data, list):
        return data

    # If JSON is a dictionary with chunks key, return data["chunks"].
    if isinstance(data, dict) and isinstance(data.get("chunks"), list):
        return data["chunks"]

    # If format is unsupported, raise clear error.
    raise ValueError(
        "Unsupported chunks JSON format. Expected a list or a dictionary with a 'chunks' key."
    )