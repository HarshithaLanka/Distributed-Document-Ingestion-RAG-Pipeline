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

# =========================
# AWS SQS CONFIGURATION
# =========================

# SQS means Simple Queue Service.
# In our project, SQS stores document processing jobs.
# Example job: "process document_id = doc_123".

# Read whether SQS is enabled from .env.
# If SQS_ENABLED=true, our app is allowed to use SQS.
# If missing, default is false for safety.
SQS_ENABLED = os.getenv("SQS_ENABLED", "false").lower() == "true"


# Read the main SQS queue name.
# This is mostly useful for logs and debugging.
# Example: document-rag-dev-processing-queue
SQS_QUEUE_NAME = os.getenv("SQS_QUEUE_NAME")


# Read the full SQS queue URL.
# boto3 needs QueueUrl to send, receive, and delete messages.
# Example:
# https://sqs.ap-south-1.amazonaws.com/887690967435/document-rag-dev-processing-queue
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")


# Read the dead-letter queue name.
# This queue stores failed jobs after retry limit.
# We do not send normal jobs directly to this queue.
SQS_DLQ_NAME = os.getenv("SQS_DLQ_NAME")


# Read the AWS region for SQS.
# If SQS_REGION is missing, use AWS_REGION.
# If AWS_REGION is also missing, use ap-south-1 because your AWS resources are in Mumbai.
SQS_REGION = os.getenv("SQS_REGION", os.getenv("AWS_REGION", "ap-south-1"))


# Read long polling wait time.
# Long polling means the worker waits for messages instead of checking repeatedly.
# 20 seconds is the maximum value supported by SQS long polling.
SQS_WAIT_TIME_SECONDS = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))


# Read visibility timeout.
# Visibility timeout means:
# once worker receives a message, SQS hides it for this many seconds.
# 300 seconds = 5 minutes.
SQS_VISIBILITY_TIMEOUT_SECONDS = int(os.getenv("SQS_VISIBILITY_TIMEOUT_SECONDS", "300"))


# Read max number of messages to receive at once.
# Keep this as 1 for now because we are learning and processing step by step.
SQS_MAX_MESSAGES = int(os.getenv("SQS_MAX_MESSAGES", "1"))


def is_sqs_configured() -> bool:
    """
    Check whether SQS has all required settings.

    Simple meaning:
    This function tells us whether our .env has enough values
    for the app to talk to AWS SQS safely.
    """

    # If SQS is disabled, return False.
    # This prevents accidental SQS calls.
    if not SQS_ENABLED:
        return False

    # These values are required for real SQS usage.
    required_values = [
        SQS_QUEUE_NAME,
        SQS_QUEUE_URL,
        SQS_REGION,
    ]

    # all(required_values) returns True only if every value exists.
    return all(required_values)


def get_missing_sqs_settings() -> list[str]:
    """
    Return missing SQS settings.

    Simple meaning:
    If something is wrong in .env, this tells exactly what is missing.
    """

    # Create an empty list to store missing setting names.
    missing_settings = []

    # Check if SQS is enabled.
    if not SQS_ENABLED:
        missing_settings.append("SQS_ENABLED")

    # Check if main queue name exists.
    if not SQS_QUEUE_NAME:
        missing_settings.append("SQS_QUEUE_NAME")

    # Check if main queue URL exists.
    if not SQS_QUEUE_URL:
        missing_settings.append("SQS_QUEUE_URL")

    # Check if region exists.
    if not SQS_REGION:
        missing_settings.append("SQS_REGION")

    # Return the final list of missing settings.
    return missing_settings

# Add near your existing DynamoDB settings.

# This controls whether event tracking is enabled.
DYNAMODB_EVENTS_ENABLED = os.getenv("DYNAMODB_EVENTS_ENABLED", "false").lower() == "true"

# This is the DynamoDB table where document event history will be saved.
DYNAMODB_EVENTS_TABLE_NAME = os.getenv("DYNAMODB_EVENTS_TABLE_NAME", "")


def is_dynamodb_events_configured() -> bool:
    """
    Check whether DynamoDB event tracking is configured.

    This is separate from the main documents table.
    Main table = current document metadata.
    Events table = history/timeline of document processing.
    """

    return (
        DYNAMODB_EVENTS_ENABLED
        and bool(AWS_REGION)
        and bool(AWS_ACCESS_KEY_ID)
        and bool(AWS_SECRET_ACCESS_KEY)
        and bool(DYNAMODB_EVENTS_TABLE_NAME)
    )


def get_missing_dynamodb_events_settings() -> list[str]:
    """
    Return missing event-table settings.

    This is helpful for debugging .env issues.
    """

    missing = []

    if not DYNAMODB_EVENTS_ENABLED:
        missing.append("DYNAMODB_EVENTS_ENABLED")

    if not AWS_REGION:
        missing.append("AWS_REGION")

    if not AWS_ACCESS_KEY_ID:
        missing.append("AWS_ACCESS_KEY_ID")

    if not AWS_SECRET_ACCESS_KEY:
        missing.append("AWS_SECRET_ACCESS_KEY")

    if not DYNAMODB_EVENTS_TABLE_NAME:
        missing.append("DYNAMODB_EVENTS_TABLE_NAME")

    return missing