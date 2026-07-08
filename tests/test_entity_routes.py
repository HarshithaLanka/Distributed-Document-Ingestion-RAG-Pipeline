"""
Tests for Week 12 entity routes.

These tests do not call real Neo4j.
We monkeypatch the Neo4j service function.

New word:
Monkeypatch means temporarily replacing a real function during a test.

Why:
We do not want pytest to depend on a live Neo4j database.
"""

# Import TestClient to test FastAPI routes.
from fastapi.testclient import TestClient

# Import FastAPI app.
from app.main import app

# Import the route module so we can monkeypatch functions inside it.
import app.routes.entity_routes as entity_routes


# Create test client.
client = TestClient(app)


def test_get_document_entities_success(monkeypatch):
    """
    Test successful entity response.

    We fake Neo4j response using monkeypatch.
    """

    # Fake Neo4j enabled.
    def fake_is_neo4j_enabled():
        return True

    # Fake entities returned from Neo4j.
    def fake_get_entities_for_document(document_id: str):
        return [
            {
                "name": "Andhra University",
                "normalized_text": "andhra university",
                "label": "ORG",
                "mention_count": 2,
                "pages": [1, 2],
                "chunk_ids": ["chunk_1", "chunk_2"],
                "sections": ["Intro"],
            }
        ]

    # Replace real functions with fake functions.
    monkeypatch.setattr(entity_routes, "is_neo4j_enabled", fake_is_neo4j_enabled)
    monkeypatch.setattr(
        entity_routes,
        "get_entities_for_document",
        fake_get_entities_for_document,
    )

    # Call API.
    response = client.get("/documents/doc_test/entities")

    # Check status code.
    assert response.status_code == 200

    # Read JSON response.
    data = response.json()

    # Check response values.
    assert data["document_id"] == "doc_test"
    assert data["entity_count"] == 1
    assert data["entities"][0]["name"] == "Andhra University"
    assert data["entities"][0]["label"] == "ORG"


def test_get_document_entities_when_neo4j_disabled(monkeypatch):
    """
    If Neo4j is disabled, API should return 503.
    """

    # Fake Neo4j disabled.
    def fake_is_neo4j_enabled():
        return False

    # Replace real enabled check.
    monkeypatch.setattr(entity_routes, "is_neo4j_enabled", fake_is_neo4j_enabled)

    # Call API.
    response = client.get("/documents/doc_test/entities")

    # Check service unavailable.
    assert response.status_code == 503

    # Check error message.
    assert "Neo4j is disabled" in response.json()["detail"]


def test_get_document_entities_handles_neo4j_error(monkeypatch):
    """
    If Neo4j service fails, API should return 500 cleanly.
    """

    # Fake Neo4j enabled.
    def fake_is_neo4j_enabled():
        return True

    # Fake Neo4j failure.
    def fake_get_entities_for_document(document_id: str):
        raise RuntimeError("Neo4j connection failed")

    # Replace functions.
    monkeypatch.setattr(entity_routes, "is_neo4j_enabled", fake_is_neo4j_enabled)
    monkeypatch.setattr(
        entity_routes,
        "get_entities_for_document",
        fake_get_entities_for_document,
    )

    # Call API.
    response = client.get("/documents/doc_test/entities")

    # Check server error.
    assert response.status_code == 500

    # Check clean detail.
    assert "Failed to fetch entities from Neo4j" in response.json()["detail"]