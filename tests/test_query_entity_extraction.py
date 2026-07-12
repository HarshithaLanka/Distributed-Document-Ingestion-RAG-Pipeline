"""
Tests for Week 14 query entity extraction.

These tests verify that:
- Empty questions return no entities.
- Duplicate entities are removed.
- Technical terms such as BM25 and Neo4j are detected.
- Redaction placeholders are ignored.
"""

from app.services import entity_extraction_service as service


class FakeEntity:
    """Small fake spaCy entity used for testing."""

    def __init__(
        self,
        text: str,
        label: str,
        start_char: int = 0,
        end_char: int = 0,
    ):
        self.text = text
        self.label_ = label
        self.start_char = start_char
        self.end_char = end_char


class FakeDoc:
    """Small fake spaCy document containing entity results."""

    def __init__(self, entities):
        self.ents = entities


class FakeNLP:
    """Fake spaCy model so tests do not load the real language model."""

    def __init__(self, entities):
        self.entities = entities

    def __call__(self, text: str):
        return FakeDoc(self.entities)


def test_extract_query_entities_returns_empty_for_blank_question():
    """Blank questions should not produce graph entities."""

    assert service.extract_query_entities("") == []
    assert service.extract_query_entities("   ") == []


def test_extract_query_entities_detects_spacy_entity(monkeypatch):
    """Normal spaCy entities should be returned in compact query format."""

    fake_nlp = FakeNLP(
        [
            FakeEntity(
                text="Microsoft",
                label="ORG",
                start_char=0,
                end_char=9,
            )
        ]
    )

    monkeypatch.setattr(service, "load_ner_model", lambda: fake_nlp)

    entities = service.extract_query_entities(
        "What did Microsoft build?"
    )

    assert {
        "text": "Microsoft",
        "normalized_text": "microsoft",
        "label": "ORG",
    } in entities


def test_extract_query_entities_detects_technical_tokens(monkeypatch):
    """Technical terms missed by spaCy should be added by regex fallback."""

    monkeypatch.setattr(
        service,
        "load_ner_model",
        lambda: FakeNLP([]),
    )

    entities = service.extract_query_entities(
        "How do Neo4j and BM25 improve AWS search?"
    )

    normalized = {
        entity["normalized_text"]
        for entity in entities
    }

    # Debug output: visible only when pytest runs with -s.
    print("entities:", entities)
    print("normalized:", normalized)

    assert "neo4j" in normalized
    assert "bm25" in normalized
    assert "aws" in normalized


def test_extract_query_entities_removes_duplicates(monkeypatch):
    """The same normalized entity and label should appear only once."""

    fake_nlp = FakeNLP(
        [
            FakeEntity("AWS", "PRODUCT", 0, 3),
            FakeEntity("AWS", "PRODUCT", 10, 13),
        ]
    )

    monkeypatch.setattr(service, "load_ner_model", lambda: fake_nlp)

    entities = service.extract_query_entities(
        "How does AWS work with AWS?"
    )

    matching = [
        entity
        for entity in entities
        if entity["normalized_text"] == "aws"
        and entity["label"] == "PRODUCT"
    ]

    assert len(matching) == 1


def test_extract_query_entities_ignores_redaction_placeholder(monkeypatch):
    """Redaction placeholders must never become graph entities."""

    fake_nlp = FakeNLP(
        [
            FakeEntity(
                "[EMAIL_REDACTED]",
                "ORG",
                0,
                16,
            )
        ]
    )

    monkeypatch.setattr(service, "load_ner_model", lambda: fake_nlp)

    entities = service.extract_query_entities(
        "Contact [EMAIL_REDACTED] about AWS."
    )

    normalized = {
        entity["normalized_text"]
        for entity in entities
    }

    assert "[email_redacted]" not in normalized