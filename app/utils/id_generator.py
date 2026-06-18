# Import uuid module.
# uuid helps us generate unique IDs.
import uuid


# Define a function to generate unique document IDs.
def generate_document_id() -> str:
    # uuid.uuid4() creates a random unique ID.
    # Example: "8f32a91c4b6d4e4d9a1f..."
    unique_part = uuid.uuid4().hex[:8]

    # Add "doc_" prefix so we know this ID belongs to a document.
    # Example final output: "doc_8f32a91c"
    return f"doc_{unique_part}"