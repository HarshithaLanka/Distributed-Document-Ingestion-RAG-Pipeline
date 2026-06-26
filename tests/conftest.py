# Import os so we can control environment variables during tests.
import os

# Disable S3 during tests.
# Simple meaning:
# Pytest should not upload real files to AWS S3.
os.environ["S3_UPLOAD_ENABLED"] = "false"

# Disable DynamoDB during tests.
# Simple meaning:
# Pytest should not write real metadata to AWS DynamoDB.
os.environ["DYNAMODB_ENABLED"] = "false"

# Add fake AWS settings so config does not fail if any code checks them.
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "fake-test-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "fake-test-secret-key"
os.environ["S3_BUCKET_NAME"] = "fake-test-bucket"
os.environ["DYNAMODB_TABLE_NAME"] = "fake-test-table"


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


# Import the FastAPI app AFTER setting test environment variables.
# This is very important.
# If we import app first, config.py may read real .env values.
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