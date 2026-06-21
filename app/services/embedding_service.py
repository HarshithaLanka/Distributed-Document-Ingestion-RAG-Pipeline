# This file handles local text-to-embedding conversion.

# Import SentenceTransformer.
# SentenceTransformer loads embedding models.
from sentence_transformers import SentenceTransformer

# Import embedding model name from config.
from app.config import EMBEDDING_MODEL


# Create a global variable to store the model.
# We use None first because we want to load the model only when needed.
embedding_model = None


# Define a function to load the embedding model.
def get_embedding_model():
    # Use the global variable declared above.
    global embedding_model

    # If the model is not loaded yet, load it now.
    if embedding_model is None:
        # This downloads/loads the model.
        # First run may take some time.
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)

    # Return the loaded model.
    return embedding_model


# Define a function to generate embedding for one text.
def generate_embedding(text: str) -> list[float]:
    # Clean the text by replacing line breaks with spaces.
    cleaned_text = text.replace("\n", " ").strip()

    # If text is empty, we cannot create an embedding.
    if not cleaned_text:
        raise ValueError("Cannot create embedding for empty text.")

    # Load the embedding model.
    model = get_embedding_model()

    # Convert text into embedding.
    embedding = model.encode(cleaned_text)

    # Convert NumPy array into normal Python list.
    # Pinecone needs normal list of floats.
    return embedding.tolist()


# Define a function to generate embeddings for many texts.
def generate_embeddings_for_texts(texts: list[str]) -> list[list[float]]:
    # Clean all text values.
    cleaned_texts = [
        text.replace("\n", " ").strip()
        for text in texts
        if text and text.strip()
    ]

    # If no valid text exists, raise an error.
    if not cleaned_texts:
        raise ValueError("No valid text found for embedding.")

    # Load the embedding model.
    model = get_embedding_model()

    # Convert all texts into embeddings.
    embeddings = model.encode(cleaned_texts)

    # Convert NumPy arrays into normal Python lists.
    return embeddings.tolist()