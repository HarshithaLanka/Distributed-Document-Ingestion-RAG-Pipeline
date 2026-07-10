# Import BM25Okapi from rank_bm25.
# BM25Okapi is the class that builds a BM25 keyword search index.
from rank_bm25 import BM25Okapi


# This function converts text into simple lowercase words.
# BM25 needs tokenized text, not raw paragraph text.
def tokenize(text: str) -> list[str]:
    # lower() makes search case-insensitive.
    # split() breaks the sentence into words using spaces.
    return text.lower().split()


# These are fake document chunks for testing BM25.
# In the real project, these will come from redacted_chunks.json.
chunks = [
    {
        "chunk_id": "chunk_1",
        "text": "Week 13 explains BM25 keyword search and hybrid retrieval.",
    },
    {
        "chunk_id": "chunk_2",
        "text": "Vector search uses embeddings and Pinecone to find semantic meaning.",
    },
    {
        "chunk_id": "chunk_3",
        "text": "SQS sends document processing jobs to the background worker.",
    },
    {
        "chunk_id": "chunk_4",
        "text": "PII redaction replaces email and phone values before embedding.",
    },
]


# Convert every chunk text into tokens.
tokenized_chunks = [tokenize(chunk["text"]) for chunk in chunks]


# Build BM25 index.
# Think of this like preparing a searchable keyword index.
bm25 = BM25Okapi(tokenized_chunks)


# This is the user search query.
query = "BM25 hybrid search"


# Convert query into tokens also.
tokenized_query = tokenize(query)


# Get BM25 scores for every chunk.
scores = bm25.get_scores(tokenized_query)


# Combine each chunk with its score.
results = []

for chunk, score in zip(chunks, scores):
    results.append(
        {
            "chunk_id": chunk["chunk_id"],
            "score": float(score),
            "text": chunk["text"],
        }
    )


# Sort results from highest score to lowest score.
results = sorted(results, key=lambda item: item["score"], reverse=True)


# Print output.
print("Query:", query)
print("\nBM25 Results:")

for result in results:
    print("-" * 60)
    print("Chunk ID:", result["chunk_id"])
    print("Score:", result["score"])
    print("Text:", result["text"])