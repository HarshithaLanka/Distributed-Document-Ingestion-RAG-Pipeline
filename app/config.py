# Import Path from pathlib.
# Path helps us work with file and folder paths safely.
from pathlib import Path

# Import os to read environment variables.
import os

# Import load_dotenv to load variables from .env file.
from dotenv import load_dotenv


# BASE_DIR means the root folder of the project.
# Example:
# C:\Users\Harshitha\Documents\Document_Intelligence_RAG
BASE_DIR = Path(__file__).resolve().parent.parent


# Load environment variables from .env file.
# This lets us keep secrets like Pinecone API key outside Python code.
load_dotenv(BASE_DIR / ".env")


# UPLOAD_DIR is where uploaded PDFs are saved.
UPLOAD_DIR = BASE_DIR / "uploads"


# DATA_DIR is where local JSON data is stored.
DATA_DIR = BASE_DIR / "app" / "data"


# DOCUMENTS_JSON_PATH points to our local metadata database.
DOCUMENTS_JSON_PATH = DATA_DIR / "documents.json"


# Create uploads folder if it does not already exist.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Create app/data folder if it does not already exist.
DATA_DIR.mkdir(parents=True, exist_ok=True)


# Pinecone API key.
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")


# Pinecone index name.
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "document-rag-index-384")


# Pinecone cloud provider.
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")


# Pinecone region.
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")


# Pinecone namespace.
# Namespace is like a separate logical space inside the same index.
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "documents")


# Local embedding model name.
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)


# Embedding dimension.
# all-MiniLM-L6-v2 creates 384-dimensional embeddings.
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))


# LLM provider.
# For now, we use Ollama locally.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")


# Ollama base URL.
# Ollama runs locally on port 11434 by default.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# Ollama model name.
# This must match one model from `ollama ls`.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------
# AWS S3 settings
# ---------------------------------------------------------

# AWS_REGION is the AWS region where your S3 bucket exists.
# Your bucket is in Mumbai, so this should be ap-south-1.
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")


# AWS_ACCESS_KEY_ID is the public part of your AWS programmatic credential.
# This allows boto3 to identify your IAM user.
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")


# AWS_SECRET_ACCESS_KEY is the private secret part of your AWS credential.
# Never print this, never commit it, and never share it.
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


# S3_BUCKET_NAME is the private S3 bucket where PDFs will be uploaded.
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")


def is_s3_configured() -> bool:
    """
    Check whether all required S3 settings are available.

    This only checks the .env values.
    It does not contact AWS.
    """

    return all(
        [
            AWS_REGION,
            AWS_ACCESS_KEY_ID,
            AWS_SECRET_ACCESS_KEY,
            S3_BUCKET_NAME,
        ]
    )


def get_missing_s3_settings() -> list[str]:
    """
    Return missing S3 environment variable names.

    This helps us debug setup issues clearly.
    """

    missing_settings = []

    if not AWS_REGION:
        missing_settings.append("AWS_REGION")

    if not AWS_ACCESS_KEY_ID:
        missing_settings.append("AWS_ACCESS_KEY_ID")

    if not AWS_SECRET_ACCESS_KEY:
        missing_settings.append("AWS_SECRET_ACCESS_KEY")

    if not S3_BUCKET_NAME:
        missing_settings.append("S3_BUCKET_NAME")

    return missing_settings

# S3_UPLOAD_ENABLED controls whether uploaded PDFs should also be uploaded to S3.
# During migration, this lets us turn S3 on/off without changing code.
S3_UPLOAD_ENABLED = os.getenv("S3_UPLOAD_ENABLED", "false").lower() == "true"


# Read DynamoDB enabled setting from .env.
# If not present, default is false.
DYNAMODB_ENABLED = os.getenv("DYNAMODB_ENABLED", "false").lower() == "true"

# Read DynamoDB table name from .env.
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")


# Check whether DynamoDB is properly configured.
def is_dynamodb_configured():
    """
    Simple meaning:
    This checks whether all required DynamoDB settings are available.

    DynamoDB needs:
    1. AWS region
    2. AWS access key
    3. AWS secret key
    4. DynamoDB table name
    """

    # Return True only if all required settings exist.
    return all(
        [
            AWS_REGION,
            AWS_ACCESS_KEY_ID,
            AWS_SECRET_ACCESS_KEY,
            DYNAMODB_TABLE_NAME,
        ]
    )


# Return missing DynamoDB settings.
def get_missing_dynamodb_settings():
    """
    Simple meaning:
    If DynamoDB does not work, this tells us which .env values are missing.
    """

    # Create empty list for missing setting names.
    missing_settings = []

    # Check AWS region.
    if not AWS_REGION:
        missing_settings.append("AWS_REGION")

    # Check AWS access key.
    if not AWS_ACCESS_KEY_ID:
        missing_settings.append("AWS_ACCESS_KEY_ID")

    # Check AWS secret key.
    if not AWS_SECRET_ACCESS_KEY:
        missing_settings.append("AWS_SECRET_ACCESS_KEY")

    # Check DynamoDB table name.
    if not DYNAMODB_TABLE_NAME:
        missing_settings.append("DYNAMODB_TABLE_NAME")

    # Return missing settings list.
    return missing_settings