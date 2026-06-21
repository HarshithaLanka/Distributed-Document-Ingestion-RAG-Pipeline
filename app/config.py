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
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "document-rag-index")


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