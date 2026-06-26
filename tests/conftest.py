# Import sys so we can add the project root to Python's import path.
import sys

# Import Path so we can safely work with folder paths.
from pathlib import Path

# Import pytest so we can create reusable fixtures.
import pytest

# Import TestClient from FastAPI.
# TestClient lets us test API routes without opening Swagger.
from fastapi.testclient import TestClient


# Get the project root folder.
# Current file is tests/conftest.py
# parent = tests/
# parent.parent = Document_Intelligence_RAG/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Add project root to Python import path.
# This helps Python find the app/ folder.
sys.path.insert(0, str(PROJECT_ROOT))


# Import the FastAPI app from app/main.py.
from app.main import app


# Create a reusable test client fixture.
# Simple meaning:
# Any test function that asks for "client" will receive this TestClient.
@pytest.fixture
def client():
    # Create FastAPI test client.
    test_client = TestClient(app)

    # Return the test client to the test function.
    return test_client