# Import the search route module.
# We need this so we can replace the real search_similar_chunks function during testing.
import app.routes.search_routes as search_routes


# Test 1:
# Check that /search/vector returns search results successfully.
def test_vector_search_api_returns_results(client, monkeypatch):
    # monkeypatch lets us temporarily replace a real function with a fake one.
    # Here we do NOT want to call real Pinecone during tests.

    # Create fake search_similar_chunks function.
    def fake_search_similar_chunks(document_id: str, query: str, top_k: int):
        # Return fake search results matching VectorSearchResult model.
        # Important:
        # Your model expects "text", not "source_text".
        return [
            {
                "chunk_id": "chunk_001",
                "page_number": 9,
                "score": 0.91,
                "text": "Week 6: Clean Architecture, Logging, and Testing."
            }
        ]

    # Replace real search_similar_chunks inside search_routes.py with fake function.
    monkeypatch.setattr(
        search_routes,
        "search_similar_chunks",
        fake_search_similar_chunks
    )

    # Send request to /search/vector.
    response = client.post(
        "/search/vector",
        json={
            "document_id": "test_doc_123",
            "query": "What is Week 6 Plan?",
            "top_k": 5
        }
    )

    # API should return success.
    assert response.status_code == 200

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Check document_id is returned correctly.
    assert data["document_id"] == "test_doc_123"

    # Check query is returned correctly.
    assert data["query"] == "What is Week 6 Plan?"

    # Check top_k is returned correctly.
    assert data["top_k"] == 5

    # Check results field exists.
    assert "results" in data

    # Check one result is returned.
    assert len(data["results"]) == 1

    # Get first result.
    first_result = data["results"][0]

    # Check chunk_id.
    assert first_result["chunk_id"] == "chunk_001"

    # Check page_number.
    assert first_result["page_number"] == 9

    # Check score.
    assert first_result["score"] == 0.91

    # Check text field.
    assert first_result["text"] == "Week 6: Clean Architecture, Logging, and Testing."


# Test 2:
# Check that /search/vector passes request values to the service correctly.
def test_vector_search_api_passes_values_to_service(client, monkeypatch):
    # Create dictionary to capture values passed to fake service.
    captured_values = {}

    # Create fake search function.
    def fake_search_similar_chunks(document_id: str, query: str, top_k: int):
        # Store received values so we can assert them later.
        captured_values["document_id"] = document_id
        captured_values["query"] = query
        captured_values["top_k"] = top_k

        # Return fake result matching VectorSearchResult model.
        return [
            {
                "chunk_id": "chunk_999",
                "page_number": 1,
                "score": 0.88,
                "text": "Fake source text."
            }
        ]

    # Replace real search_similar_chunks with fake function.
    monkeypatch.setattr(
        search_routes,
        "search_similar_chunks",
        fake_search_similar_chunks
    )

    # Send request to /search/vector.
    response = client.post(
        "/search/vector",
        json={
            "document_id": "doc_test_456",
            "query": "Find project overview",
            "top_k": 3
        }
    )

    # API should return success.
    assert response.status_code == 200

    # Check that API passed correct document_id to service.
    assert captured_values["document_id"] == "doc_test_456"

    # Check that API passed correct query to service.
    assert captured_values["query"] == "Find project overview"

    # Check that API passed correct top_k to service.
    assert captured_values["top_k"] == 3


# Test 3:
# Check that invalid top_k returns clean 400 error.
def test_vector_search_api_invalid_top_k_returns_400(client):
    # Send top_k greater than allowed limit.
    response = client.post(
        "/search/vector",
        json={
            "document_id": "test_doc_123",
            "query": "What is this document about?",
            "top_k": 50
        }
    )

    # Your route says top_k must be between 1 and 10.
    assert response.status_code == 422

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Because main.py has global HTTPException handler,
    # response should contain a clean error block.
    assert data["success"] is False

    # Check error exists.
    assert "error" in data

    # Check message contains top_k validation text.
    # Pydantic validates top_k before the route function runs.
# The global RequestValidationError handler returns
# this standard clean validation message.
    assert data["error"]["message"] == "Request validation failed"


# Test 4:
# Check that missing document_id returns validation error.
def test_vector_search_api_missing_document_id_returns_validation_error(client):
    # Send request without document_id.
    response = client.post(
        "/search/vector",
        json={
            "query": "What is Week 6?",
            "top_k": 5
        }
    )

    # Missing document_id should return 422 validation error.
    assert response.status_code == 422

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Because main.py has validation error handler,
    # response should have success false.
    assert data["success"] is False

    # Check error block exists.
    assert "error" in data

    # Check validation error code.
    assert data["error"]["code"] == "VALIDATION_ERROR"


# Test 5:
# Check that Pinecone/search service failure returns clean 500 response.
def test_vector_search_api_service_failure_returns_500(client, monkeypatch):
    # Create fake function that simulates Pinecone failure.
    def fake_search_similar_chunks(document_id: str, query: str, top_k: int):
        # Raise error like Pinecone/service failure.
        raise Exception("Pinecone connection failed")

    # Replace real search function with failing fake function.
    monkeypatch.setattr(
        search_routes,
        "search_similar_chunks",
        fake_search_similar_chunks
    )

    # Send valid request.
    response = client.post(
        "/search/vector",
        json={
            "document_id": "test_doc_123",
            "query": "What is Week 6?",
            "top_k": 5
        }
    )

    # Route catches exception and returns 500.
    assert response.status_code == 500

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Because main.py handles HTTPException,
    # response should contain clean error format.
    assert data["success"] is False

    # Check error block exists.
    assert "error" in data

    # Check error message contains vector search failed.
    assert "Vector search failed" in data["error"]["message"]