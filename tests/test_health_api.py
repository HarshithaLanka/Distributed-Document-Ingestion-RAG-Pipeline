# Test the /health endpoint.
def test_health_check(client):
    # Call GET /health.
    response = client.get("/health")

    # Check status code.
    assert response.status_code == 200

    # Convert response to JSON.
    data = response.json()

    # Check response content.
    assert data["status"] == "ok"
    assert "message" in data