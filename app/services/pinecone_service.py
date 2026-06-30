# This file handles Pinecone vector database operations.
#
# Week 10 upgrade:
# Earlier Pinecone metadata had:
# - document_id
# - chunk_id
# - page_number
# - word_count
# - source_text
#
# Now Pinecone metadata also stores:
# - section_title
# - content_type
# - parser_used
#
# Why?
# This helps retrieval, citations, debugging, and future hybrid search.

# Import time to wait while Pinecone index becomes ready.
import time

# Import Pinecone client and serverless configuration.
from pinecone import Pinecone
from pinecone import ServerlessSpec

# Import Pinecone settings from config.
from app.config import PINECONE_API_KEY
from app.config import PINECONE_INDEX_NAME
from app.config import PINECONE_CLOUD
from app.config import PINECONE_REGION
from app.config import PINECONE_NAMESPACE
from app.config import EMBEDDING_DIMENSION

# Import embedding functions.
from app.services.embedding_service import generate_embedding
from app.services.embedding_service import generate_embeddings_for_texts


# Define a function to create Pinecone client.
def get_pinecone_client() -> Pinecone:
    """
    Create Pinecone client.

    Simple meaning:
    This function connects our Python app to Pinecone using the API key.
    """

    # If Pinecone API key is missing, raise clear error.
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY is missing. Please add it to your .env file.")

    # Create and return Pinecone client.
    return Pinecone(api_key=PINECONE_API_KEY)


# Define a function to make sure Pinecone index exists.
def ensure_pinecone_index():
    """
    Make sure Pinecone index exists.

    Important:
    Your embedding model is all-MiniLM-L6-v2.
    Its embedding dimension is 384.
    So Pinecone index dimension must stay 384.
    """

    # Create Pinecone client.
    pc = get_pinecone_client()

    # Check if index already exists.
    if not pc.has_index(PINECONE_INDEX_NAME):
        # Create Pinecone dense vector index.
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            vector_type="dense",
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION,
            ),
            deletion_protection="disabled",
            tags={
                "environment": "development",
            },
        )

        # Wait until Pinecone index is ready.
        while True:
            # Describe index.
            description = pc.describe_index(PINECONE_INDEX_NAME)

            # Get status from description.
            status = description.status

            # Support both dict-style and object-style status.
            is_ready = status.get("ready", False) if isinstance(status, dict) else status.ready

            # If ready, stop waiting.
            if is_ready:
                break

            # Wait 2 seconds before checking again.
            time.sleep(2)

    # Return Pinecone index object.
    return pc.Index(PINECONE_INDEX_NAME)


# Define a helper to clean string metadata.
def clean_string_metadata(value, default: str = "") -> str:
    """
    Clean string metadata before sending to Pinecone.

    Simple meaning:
    Pinecone metadata should not contain None values.
    So if value is None, we convert it to an empty string.
    """

    # If value is None, return default.
    if value is None:
        return default

    # Convert value to string and return.
    return str(value)


# Define a helper to clean number metadata.
def clean_number_metadata(value, default: int = 0):
    """
    Clean number metadata before sending to Pinecone.

    Simple meaning:
    Page number and word count should be numbers.
    If missing, use 0.
    """

    # If value is None, return default.
    if value is None:
        return default

    # Return original value.
    return value


# Define a function to build Pinecone metadata from one chunk.
def build_chunk_metadata(chunk: dict) -> dict:
    """
    Build Pinecone metadata from one chunk.

    Metadata helps us:
    - filter by document_id
    - build citations using page_number
    - show section_title in results
    - understand whether content came from paragraph/table/heading
    """

    # Build metadata dictionary.
    metadata = {
        # Existing metadata.
        "document_id": clean_string_metadata(chunk.get("document_id")),
        "chunk_id": clean_string_metadata(chunk.get("chunk_id")),

        # Page number is used for citations.
        "page_number": clean_number_metadata(chunk.get("page_number"), 0),

        # Week 10 metadata.
        "section_title": clean_string_metadata(chunk.get("section_title")),
        "content_type": clean_string_metadata(chunk.get("content_type"), "paragraph"),
        "parser_used": clean_string_metadata(chunk.get("parser_used"), "pymupdf"),

        # Existing metadata.
        "word_count": clean_number_metadata(chunk.get("word_count"), 0),
        "source_text": clean_string_metadata(chunk.get("text")),
    }

    # Return metadata.
    return metadata


# Define a function to store document chunks in Pinecone.
def index_document_chunks(chunks_data: dict) -> dict:
    """
    Store document chunks in Pinecone.

    Input example:
    {
        "document_id": "doc_123",
        "parser_used": "docling",
        "chunk_count": 10,
        "chunks": [...]
    }
    """

    # Get chunks list from chunks_data.
    chunks = chunks_data.get("chunks", [])

    # If no chunks found, raise error.
    if not chunks:
        raise ValueError("No chunks found to index.")

    # Extract text from each chunk.
    chunk_texts = [
        chunk["text"]
        for chunk in chunks
    ]

    # Generate embeddings for all chunk texts.
    embeddings = generate_embeddings_for_texts(chunk_texts)

    # Create empty list for Pinecone vector records.
    vectors = []

    # Loop through chunks and embeddings together.
    for chunk, embedding in zip(chunks, embeddings):
        # Create unique vector ID.
        # Example:
        # doc_123_chunk_001
        vector_id = f"{chunk['document_id']}_{chunk['chunk_id']}"

        # Build metadata with Week 10 fields.
        metadata = build_chunk_metadata(chunk)

        # Create Pinecone vector record.
        vector_record = {
            "id": vector_id,
            "values": embedding,
            "metadata": metadata,
        }

        # Add vector record to list.
        vectors.append(vector_record)

    # Get Pinecone index.
    index = ensure_pinecone_index()

    # Store vectors in batches.
    batch_size = 50

    # Loop through vectors in batches.
    for start in range(0, len(vectors), batch_size):
        # Get one batch.
        batch = vectors[start:start + batch_size]

        # Upsert batch into Pinecone namespace.
        index.upsert(
            vectors=batch,
            namespace=PINECONE_NAMESPACE,
        )

    # Return indexing summary.
    return {
        "vector_count": len(vectors),
        "parser_used": chunks_data.get("parser_used", "unknown"),
    }


# Define a function to search similar chunks from Pinecone.
def search_similar_chunks(document_id: str, query: str, top_k: int = 3) -> list[dict]:
    """
    Search similar chunks from Pinecone using a text query.

    This is used by vector search API.
    """

    # Convert user query into embedding.
    query_embedding = generate_embedding(query)

    # Get Pinecone index.
    index = ensure_pinecone_index()

    # Query Pinecone.
    # Metadata filter ensures search happens only inside selected document.
    query_result = index.query(
        namespace=PINECONE_NAMESPACE,
        vector=query_embedding,
        top_k=top_k,
        filter={
            "document_id": {
                "$eq": document_id,
            }
        },
        include_metadata=True,
        include_values=False,
    )

    # Create clean result list.
    results = []

    # Loop through Pinecone matches.
    for match in query_result.matches:
        # Get metadata safely.
        metadata = match.metadata or {}

        # Add clean result.
        results.append(
            {
                "chunk_id": metadata.get("chunk_id"),
                "page_number": metadata.get("page_number"),

                # Week 10 fields.
                "section_title": metadata.get("section_title"),
                "content_type": metadata.get("content_type"),
                "parser_used": metadata.get("parser_used"),

                # Existing fields.
                "score": match.score,
                "text": metadata.get("source_text"),
            }
        )

    # Return search results.
    return results


# Define a function to search Pinecone using an already-created embedding vector.
# This function is mainly used by qa_service.py.
def search_vectors(query_embedding: list[float], document_id: str, top_k: int = 5) -> list[dict]:
    """
    Search Pinecone using an already-created embedding vector.

    This function is mainly used by qa_service.py.
    """

    # Get Pinecone index.
    index = ensure_pinecone_index()

    # Query Pinecone using the provided embedding.
    query_result = index.query(
        namespace=PINECONE_NAMESPACE,
        vector=query_embedding,
        top_k=top_k,
        filter={
            "document_id": {
                "$eq": document_id,
            }
        },
        include_metadata=True,
        include_values=False,
    )

    # Create empty result list.
    results = []

    # Loop through matches.
    for match in query_result.matches:
        # Get metadata safely.
        metadata = match.metadata or {}

        # Add match in format expected by qa_service.py.
        results.append(
            {
                "score": match.score,
                "metadata": {
                    "document_id": metadata.get("document_id"),
                    "chunk_id": metadata.get("chunk_id"),
                    "page_number": metadata.get("page_number"),

                    # Week 10 metadata.
                    "section_title": metadata.get("section_title"),
                    "content_type": metadata.get("content_type"),
                    "parser_used": metadata.get("parser_used"),

                    # Existing metadata.
                    "word_count": metadata.get("word_count"),
                    "source_text": metadata.get("source_text"),
                },
            }
        )

    # Return clean matches.
    return results