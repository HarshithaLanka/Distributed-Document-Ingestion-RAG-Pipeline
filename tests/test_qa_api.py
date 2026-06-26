# Import the QA route module.
# We need this so we can replace the real answer_question function during testing.
import app.routes.qa_routes as qa_routes

# Import QAResponse model so our fake service returns the same type as the real service.
from app.models.qa_models import QAResponse

# Import Citation model so we can create fake citation data.
from app.models.qa_models import Citation


# Test 1:
# Check that /qa returns a successful answer response.
def test_qa_api_returns_answer_with_citation(client, monkeypatch):
    # monkeypatch is a pytest tool.
    # Simple meaning:
    # It lets us temporarily replace real functions during a test.
    # Here we replace real Ollama/Pinecone logic with fake output.

    # Create a fake version of answer_question.
    def fake_answer_question(request):
        # Return fake successful QA response.
        return QAResponse(
            answer="Week 6 is Clean Architecture, Logging, and Testing.",
            citations=[
                Citation(
                    chunk_id="chunk_001",
                    page_number=9,
                    score=1.0,
                    source_preview="Week 6: Clean Architecture, Logging, and Testing"
                )
            ],
            answer_status="found",
            question_type="direct_factual"
        )

    # Replace the real answer_question used inside qa_routes.py with our fake function.
    monkeypatch.setattr(
        qa_routes,
        "answer_question",
        fake_answer_question
    )

    # Send request to /qa endpoint.
    response = client.post(
        "/qa",
        json={
            "document_id": "test_doc_123",
            "question": "What is Week 6 Plan from the document?",
            "top_k": 5,
            "min_score": 0.35
        }
    )

    # Check API status code.
    assert response.status_code == 200

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Check answer exists.
    assert "answer" in data

    # Check answer text.
    assert data["answer"] == "Week 6 is Clean Architecture, Logging, and Testing."

    # Check citations exist.
    assert "citations" in data

    # Check one citation is returned.
    assert len(data["citations"]) == 1

    # Check citation chunk_id.
    assert data["citations"][0]["chunk_id"] == "chunk_001"

    # Check citation page number.
    assert data["citations"][0]["page_number"] == 9

    # Check answer status.
    assert data["answer_status"] == "found"

    # Check question type.
    assert data["question_type"] == "direct_factual"


# Test 2:
# Check that /qa returns clean not_found response.
def test_qa_api_returns_not_found(client, monkeypatch):
    # Create fake answer_question function for not_found case.
    def fake_answer_question(request):
        # Return fake not_found response.
        return QAResponse(
            answer="I could not find this information in the document.",
            citations=[],
            answer_status="not_found",
            question_type="direct_factual"
        )

    # Replace real answer_question with fake not_found function.
    monkeypatch.setattr(
        qa_routes,
        "answer_question",
        fake_answer_question
    )

    # Send request to /qa endpoint.
    response = client.post(
        "/qa",
        json={
            "document_id": "test_doc_123",
            "question": "What is the CEO name?",
            "top_k": 5,
            "min_score": 0.35
        }
    )

    # API should still return 200 because not_found is a valid QA result.
    assert response.status_code == 200

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Check not_found answer.
    assert data["answer"] == "I could not find this information in the document."

    # Check citations are empty.
    assert data["citations"] == []

    # Check answer status.
    assert data["answer_status"] == "not_found"

    # Check question type.
    assert data["question_type"] == "direct_factual"


# Test 3:
# Check that /qa validates required fields.
def test_qa_api_missing_document_id_returns_validation_error(client):
    # Send request without document_id.
    response = client.post(
        "/qa",
        json={
            "question": "What is Week 6?",
            "top_k": 5,
            "min_score": 0.35
        }
    )

    # Missing document_id should return validation error.
    assert response.status_code == 422

    # Convert response JSON into Python dictionary.
    data = response.json()

    # Because we added custom validation handler in main.py,
    # response should contain success false.
    assert data["success"] is False

    # Check error block exists.
    assert "error" in data

    # Check validation error code.
    assert data["error"]["code"] == "VALIDATION_ERROR"


# Test 4:
# Check that /qa passes request values correctly into answer_question.
def test_qa_api_passes_request_values_to_service(client, monkeypatch):
    # Create dictionary to capture request values.
    captured_request = {}

    # Create fake answer_question function.
    def fake_answer_question(request):
        # Store request values so we can check them later.
        captured_request["document_id"] = request.document_id
        captured_request["question"] = request.question
        captured_request["top_k"] = request.top_k
        captured_request["min_score"] = request.min_score

        # Return fake response.
        return QAResponse(
            answer="Test answer.",
            citations=[
                Citation(
                    chunk_id="chunk_999",
                    page_number=1,
                    score=0.99,
                    source_preview="Test source preview."
                )
            ],
            answer_status="found",
            question_type="direct_factual"
        )

    # Replace real answer_question with fake function.
    monkeypatch.setattr(
        qa_routes,
        "answer_question",
        fake_answer_question
    )

    # Send request to /qa.
    response = client.post(
        "/qa",
        json={
            "document_id": "doc_test_456",
            "question": "What is this document about?",
            "top_k": 3,
            "min_score": 0.25
        }
    )

    # Check API status code.
    assert response.status_code == 200

    # Check that request values reached the service correctly.
    assert captured_request["document_id"] == "doc_test_456"
    assert captured_request["question"] == "What is this document about?"
    assert captured_request["top_k"] == 3
    assert captured_request["min_score"] == 0.25