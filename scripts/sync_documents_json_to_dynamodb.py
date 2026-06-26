"""
Sync local documents.json metadata to DynamoDB.

Simple meaning:
This script copies all existing document metadata records from:

app/data/documents.json

into:

DynamoDB table document-rag-dev-documents

Why this is needed:
Some documents may have been uploaded before DynamoDB was added.
Before making DynamoDB primary, we must make sure DynamoDB has all metadata.
"""

# Import sys so we can add project root to Python import path.
import sys

# Import Path for safe path handling.
from pathlib import Path

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import metadata loader from local JSON service.
from app.services.metadata_service import load_documents

# Import DynamoDB save function.
from app.services.dynamodb_service import put_document_metadata

# Import custom DynamoDB error.
from app.services.dynamodb_service import DynamoDBServiceError


# Define the main sync function.
def sync_documents_to_dynamodb():
    """
    Simple meaning:
    1. Read all documents from local documents.json.
    2. Save each document into DynamoDB.
    3. Print success/failure count.
    """

    # Load all documents from app/data/documents.json.
    documents = load_documents()

    # If no documents exist locally, stop.
    if not documents:
        print("No local documents found in app/data/documents.json.")
        return

    # Track successful sync count.
    success_count = 0

    # Track failed sync count.
    failed_count = 0

    # Loop through every local document record.
    for document in documents:
        # Get document_id for logging.
        document_id = document.get("document_id")

        # If document_id is missing, skip this record.
        if not document_id:
            print("Skipping record because document_id is missing.")
            failed_count += 1
            continue

        try:
            # Save document metadata into DynamoDB.
            put_document_metadata(document)

            # Increase success count.
            success_count += 1

            # Print success message.
            print(f"✅ Synced document to DynamoDB: {document_id}")

        except DynamoDBServiceError as error:
            # Increase failed count.
            failed_count += 1

            # Print error message.
            print(f"❌ Failed to sync document: {document_id}")
            print(str(error))

    # Print final summary.
    print("\nSync completed.")
    print(f"Successful records: {success_count}")
    print(f"Failed records: {failed_count}")
    print(f"Total records checked: {len(documents)}")


# Run sync only when script is executed directly.
if __name__ == "__main__":
    sync_documents_to_dynamodb()