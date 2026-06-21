# This file handles Pinecone vector database operations.

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
    # If Pinecone API key is missing, raise clear error.
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY is missing. Please add it to your .env file.")

    # Create and return Pinecone client.
    return Pinecone(api_key=PINECONE_API_KEY)


# Define a function to make sure Pinecone index exists.
def ensure_pinecone_index():
    # Create Pinecone client.
    pc = get_pinecone_client()

    # Check if index already exists.
    if not pc.has_index(PINECONE_INDEX_NAME):
        # Create Pinecone dense vector index.
        # Dimension must match the embedding model dimension.
        # all-MiniLM-L6-v2 gives 384-dimensional vectors.
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            vector_type="dense",
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION
            ),
            deletion_protection="disabled",
            tags={
                "environment": "development"
            }
        )

        # Wait until Pinecone index is ready.
        while True:
            # Describe index status.
            description = pc.describe_index(PINECONE_INDEX_NAME)

            # Get status from description.
            status = description.status

            # Check if index is ready.
            is_ready = status.get("ready", False) if isinstance(status, dict) else status.ready

            # If ready, stop waiting.
            if is_ready:
                break

            # Wait 2 seconds before checking again.
            time.sleep(2)

    # Return Pinecone index object.
    return pc.Index(PINECONE_INDEX_NAME)


# Define a function to store document chunks in Pinecone.
def index_document_chunks(chunks_data: dict) -> dict:
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

    # Create an empty list for Pinecone vector records.
    vectors = []

    # Loop through chunks and embeddings together.
    for chunk, embedding in zip(chunks, embeddings):
        # Create unique vector ID.
        # Example: doc_123_chunk_001
        vector_id = f"{chunk['document_id']}_{chunk['chunk_id']}"

        # Create metadata.
        # Metadata helps us filter and later build citations.
        metadata = {
            "document_id": chunk["document_id"],
            "chunk_id": chunk["chunk_id"],
            "page_number": chunk["page_number"],
            "word_count": chunk["word_count"],
            "source_text": chunk["text"]
        }

        # Create Pinecone vector record.
        vector_record = {
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
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
            namespace=PINECONE_NAMESPACE
        )

    # Return indexing summary.
    return {
        "vector_count": len(vectors)
    }


# Define a function to search similar chunks from Pinecone.
def search_similar_chunks(document_id: str, query: str, top_k: int = 3) -> list[dict]:
    # Convert user query into embedding.
    query_embedding = generate_embedding(query)

    # Get Pinecone index.
    index = ensure_pinecone_index()

    # Query Pinecone.
    # Metadata filter ensures search happens only inside the selected document.
    query_result = index.query(
        namespace=PINECONE_NAMESPACE,
        vector=query_embedding,
        top_k=top_k,
        filter={
            "document_id": {
                "$eq": document_id
            }
        },
        include_metadata=True,
        include_values=False
    )

    # Get matches from Pinecone response.
    matches = query_result.matches

    # Create clean result list.
    results = []

    # Loop through matches.
    for match in matches:
        # Get metadata from match.
        metadata = match.metadata

        # Add clean result.
        results.append(
            {
                "chunk_id": metadata.get("chunk_id"),
                "page_number": metadata.get("page_number"),
                "score": match.score,
                "text": metadata.get("source_text")
            }
        )

    # Return search results.
    return results