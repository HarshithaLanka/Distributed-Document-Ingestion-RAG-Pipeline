"""
DynamoDB smoke test.

Simple meaning:
This script checks whether your backend can talk to DynamoDB.

It tests:
1. Table access
2. Put item
3. Get item
4. Update item
5. List items
6. Delete item

Run:
python scripts/dynamodb_smoke_test.py
"""

# Import sys so we can add project root to import path.
import sys

# Import Path for safe folder path handling.
from pathlib import Path

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import datetime to create a timestamp.
from datetime import datetime, timezone

# Import DynamoDB service functions.
from app.services.dynamodb_service import check_dynamodb_table_access
from app.services.dynamodb_service import put_document_metadata
from app.services.dynamodb_service import get_document_metadata
from app.services.dynamodb_service import update_document_metadata_in_dynamodb
from app.services.dynamodb_service import list_document_metadata
from app.services.dynamodb_service import delete_document_metadata
from app.services.dynamodb_service import DynamoDBServiceError


# Main function for smoke test.
def run_smoke_test():
    """
    Simple meaning:
    This function runs all DynamoDB checks step by step.
    """

    # Create a test document ID.
    test_document_id = "doc_dynamodb_smoke_test"

    # Create fake metadata item.
    test_metadata = {
        "document_id": test_document_id,
        "filename": "dynamodb_smoke_test.pdf",
        "status": "uploaded",
        "file_path": "uploads/doc_dynamodb_smoke_test/uploaded_file.pdf",
        "s3_bucket": "test-bucket",
        "s3_key": "documents/doc_dynamodb_smoke_test/uploaded_file.pdf",
        "s3_uri": "s3://test-bucket/documents/doc_dynamodb_smoke_test/uploaded_file.pdf",
        "page_count": 1,
        "chunk_count": 0,
        "vector_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Check table access.
        table_info = check_dynamodb_table_access()
        print("✅ DynamoDB table access successful.")
        print(table_info)

        # Put item.
        put_document_metadata(test_metadata)
        print("✅ PutItem successful.")

        # Get item.
        fetched_item = get_document_metadata(test_document_id)
        print("✅ GetItem successful.")
        print(fetched_item)

        # Confirm fetched item exists.
        if fetched_item is None:
            raise RuntimeError("GetItem failed. Item was not found after PutItem.")

        # Update item.
        updated_item = update_document_metadata_in_dynamodb(
            document_id=test_document_id,
            updates={
                "status": "indexed",
                "chunk_count": 5,
                "vector_count": 5,
                "error_message": None,
            },
        )
        print("✅ UpdateItem successful.")
        print(updated_item)

        # List items.
        items = list_document_metadata(limit=10)
        print("✅ Scan/List successful.")
        print(f"Items returned: {len(items)}")

        # Delete test item.
        delete_result = delete_document_metadata(test_document_id)
        print("✅ DeleteItem successful.")
        print(delete_result)

        # Confirm item is deleted.
        deleted_item = get_document_metadata(test_document_id)

        # If deleted item still exists, raise error.
        if deleted_item is not None:
            raise RuntimeError("DeleteItem failed. Item still exists.")

        print("✅ Delete verification successful.")
        print("🎉 DynamoDB smoke test passed successfully.")

    except DynamoDBServiceError as error:
        # Print clean service error.
        print("❌ DynamoDB service error:")
        print(str(error))

    except Exception as error:
        # Print unexpected error.
        print("❌ Unexpected error:")
        print(str(error))


# Run smoke test when file is executed directly.
if __name__ == "__main__":
    run_smoke_test()