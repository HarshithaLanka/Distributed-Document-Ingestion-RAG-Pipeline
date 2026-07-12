"""
Tests for Week 14 Neo4j graph retrieval.

The Neo4j driver is mocked, so these tests do not contact a real database.
"""

from app.services import neo4j_service as service


class FakeRecord(dict):
    """Dictionary-like Neo4j record."""

    def __getitem__(self, key):
        return self.get(key)


class FakeResult:
    """Iterable Neo4j result."""

    def __init__(self, records):
        self.records = records

    def __iter__(self):
        return iter(self.records)


class FakeSession:
    """Context-manager compatible fake Neo4j session."""

    def __init__(self, records):
        self.records = records
        self.last_query = None
        self.last_parameters = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def run(self, query, **parameters):
        self.last_query = query
        self.last_parameters = parameters
        return FakeResult(self.records)


class FakeDriver:
    """Fake Neo4j driver returning one fake session."""

    def __init__(self, session):
        self.session_object = session
        self.database = None

    def session(self, database=None):
        self.database = database
        return self.session_object


def test_search_chunks_by_entities_returns_empty_when_disabled(
    monkeypatch,
):
    """Graph search should safely skip when Neo4j is disabled."""

    monkeypatch.setattr(
        service,
        "is_neo4j_enabled",
        lambda: False,
    )

    results = service.search_chunks_by_entities(
        document_id="doc-1",
        entities=["neo4j"],
        top_k=5,
    )

    assert results == []


def test_search_chunks_by_entities_requires_document_id():
    """Document scoping is required to prevent cross-document leakage."""

    try:
        service.search_chunks_by_entities(
            document_id="",
            entities=["neo4j"],
            top_k=5,
        )
    except ValueError as error:
        assert "document_id" in str(error)
    else:
        raise AssertionError("ValueError was not raised")


def test_search_chunks_by_entities_returns_empty_for_no_entities(
    monkeypatch,
):
    """No query entities means there is nothing to search in the graph."""

    monkeypatch.setattr(
        service,
        "is_neo4j_enabled",
        lambda: True,
    )

    results = service.search_chunks_by_entities(
        document_id="doc-1",
        entities=[],
        top_k=5,
    )

    assert results == []


def test_search_chunks_by_entities_calculates_graph_score(
    monkeypatch,
):
    """Graph score should equal matched entities divided by query entities."""

    records = [
        FakeRecord(
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-7",
                "page_number": 4,
                "section_title": "Hybrid Retrieval",
                "content_type": "paragraph",
                "word_count": 120,
                "text": "Neo4j and BM25 improve retrieval.",
                "matched_entities": ["neo4j", "bm25"],
                "graph_match_count": 2,
            }
        )
    ]

    fake_session = FakeSession(records)
    fake_driver = FakeDriver(fake_session)

    monkeypatch.setattr(
        service,
        "is_neo4j_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        service,
        "get_neo4j_driver",
        lambda: fake_driver,
    )
    monkeypatch.setattr(
        service,
        "get_neo4j_database",
        lambda: "neo4j",
    )

    results = service.search_chunks_by_entities(
        document_id="doc-1",
        entities=["neo4j", "bm25", "pinecone"],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-7"
    assert results[0]["graph_match_count"] == 2
    assert results[0]["graph_score"] == 2 / 3
    assert results[0]["matched_entities"] == [
        "neo4j",
        "bm25",
    ]

    assert fake_session.last_parameters["document_id"] == "doc-1"
    assert set(fake_session.last_parameters["entities"]) == {
        "neo4j",
        "bm25",
        "pinecone",
    }


def test_search_chunks_by_entities_limits_top_k(monkeypatch):
    """The service should cap top_k at 20."""

    fake_session = FakeSession([])
    fake_driver = FakeDriver(fake_session)

    monkeypatch.setattr(
        service,
        "is_neo4j_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        service,
        "get_neo4j_driver",
        lambda: fake_driver,
    )
    monkeypatch.setattr(
        service,
        "get_neo4j_database",
        lambda: "neo4j",
    )

    service.search_chunks_by_entities(
        document_id="doc-1",
        entities=["neo4j"],
        top_k=100,
    )

    assert fake_session.last_parameters["top_k"] == 20