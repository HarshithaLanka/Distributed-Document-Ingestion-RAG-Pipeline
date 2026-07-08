"""
Tests for Week 12 entity_extraction_service.py.

These tests check helper logic first.
They do not require Neo4j, AWS, Pinecone, or Ollama.
"""

# Import pytest for test helpers.
import pytest

# Import functions we want to test.
from app.services.entity_extraction_service import (
    extract_entities_from_text,
    is_redaction_placeholder,
    normalize_entity_text,
    should_keep_entity,
    summarize_entities,
)


def test_normalize_entity_text_removes_extra_spaces():
    """
    Extra spaces should be cleaned.

    Example:
    ' Andhra   University ' becomes 'Andhra University'
    """

    # Arrange + Act
    result = normalize_entity_text("  Andhra   University  ")

    # Assert
    assert result == "Andhra University"


def test_redaction_placeholders_are_detected():
    """
    Week 11 placeholders should be detected.
    """

    # Assert known placeholders.
    assert is_redaction_placeholder("[EMAIL_REDACTED]") is True
    assert is_redaction_placeholder("[PHONE_REDACTED]") is True
    assert is_redaction_placeholder("[SSN_REDACTED]") is True


def test_redaction_placeholders_are_not_kept_as_entities():
    """
    Redacted placeholders should not become Neo4j entities.
    """

    # Act
    result = should_keep_entity("[EMAIL_REDACTED]", "ORG")

    # Assert
    assert result is False


def test_allowed_entity_label_is_kept():
    """
    Normal useful entities should be kept.
    """

    # Act
    result = should_keep_entity("Andhra University", "ORG")

    # Assert
    assert result is True


def test_disallowed_entity_label_is_removed():
    """
    Unsupported labels should be removed.
    """

    # Act
    result = should_keep_entity("123", "CARDINAL")

    # Assert
    assert result is False


def test_summarize_entities_groups_repeated_mentions():
    """
    If the same entity appears multiple times, summary should group it.
    """

    # Arrange
    mentions = [
        {
            "text": "Andhra University",
            "normalized_text": "andhra university",
            "label": "ORG",
            "page_number": 1,
            "chunk_id": "chunk_1",
            "section_title": "Intro",
        },
        {
            "text": "Andhra University",
            "normalized_text": "andhra university",
            "label": "ORG",
            "page_number": 2,
            "chunk_id": "chunk_2",
            "section_title": "Details",
        },
    ]

    # Act
    summary = summarize_entities(mentions)

    # Assert
    assert len(summary) == 1
    assert summary[0]["name"] == "Andhra University"
    assert summary[0]["label"] == "ORG"
    assert summary[0]["mention_count"] == 2
    assert summary[0]["pages"] == [1, 2]
    assert summary[0]["chunk_ids"] == ["chunk_1", "chunk_2"]


def test_extract_entities_from_text_ignores_redacted_email():
    """
    Entity extraction should not return [EMAIL_REDACTED].
    """

    # Arrange
    text = "Professor Soujanya works at Andhra University. Email: [EMAIL_REDACTED]."

    try:
        # Act
        entities = extract_entities_from_text(
            text=text,
            document_id="doc_test",
            chunk_id="chunk_test",
            page_number=1,
        )

    except RuntimeError as exc:
        # If spaCy model is not installed, skip this one test with a clear reason.
        pytest.skip(str(exc))

    # Assert
    entity_texts = [entity["text"] for entity in entities]

    assert "[EMAIL_REDACTED]" not in entity_texts