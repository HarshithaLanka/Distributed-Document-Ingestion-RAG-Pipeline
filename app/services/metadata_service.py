"""
Metadata service for documents.

Current production-style migration behavior:

1. DynamoDB is the primary metadata store when DYNAMODB_ENABLED=true.
2. Local documents.json is still kept as a local backup/cache.
3. Reads try DynamoDB first.
4. If DynamoDB is disabled, empty, or unavailable, reads fallback to local JSON.
5. Writes go to DynamoDB and also update local JSON backup.

Simple meaning:
We are now treating DynamoDB as the main metadata database,
but we are not deleting local JSON yet.
"""

# Import json so we can read/write documents.json.
import json

# Import Path for safe file/folder handling.
from pathlib import Path

# Import datetime to store created_at and updated_at timestamps.
from datetime import datetime, timezone

# Import Decimal because DynamoDB may return numbers as Decimal.
from decimal import Decimal

# Import DynamoDB enabled setting.
from app.config import DYNAMODB_ENABLED

# Import DynamoDB functions and custom error.
from app.services.dynamodb_service import put_document_metadata
from app.services.dynamodb_service import update_document_metadata_in_dynamodb
from app.services.dynamodb_service import delete_document_metadata
from app.services.dynamodb_service import get_document_metadata
from app.services.dynamodb_service import list_document_metadata
from app.services.dynamodb_service import DynamoDBServiceError


# Build path to app/data folder.
DATA_DIR = Path("app/data")

# Build path to local metadata JSON file.
DOCUMENTS_FILE = DATA_DIR / "documents.json"


# Ensure metadata folder and file exist.
def ensure_metadata_file_exists():
    """
    Simple meaning:
    Before reading or writing metadata, make sure:

    app/data/ exists
    app/data/documents.json exists
    """

    # Create app/data folder if it does not exist.
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create documents.json with empty list if missing.
    if not DOCUMENTS_FILE.exists():
        DOCUMENTS_FILE.write_text("[]", encoding="utf-8")


# Get current UTC timestamp.
def get_current_timestamp():
    """
    Simple meaning:
    This gives a standard timestamp for created_at and updated_at.
    """

    # Return current UTC timestamp as text.
    return datetime.now(timezone.utc).isoformat()


# Convert DynamoDB Decimal values into normal Python values.
def convert_decimal_to_python(value):
    """
    Simple meaning:
    DynamoDB returns numbers as Decimal.

    Example:
    Decimal("5") should become 5.
    Decimal("0.35") should become 0.35.

    FastAPI/Pydantic works better with normal int/float values.
    """

    # If value is Decimal, convert it.
    if isinstance(value, Decimal):
        # If number has no decimal part, convert to int.
        if value % 1 == 0:
            return int(value)

        # Otherwise convert to float.
        return float(value)

    # If value is dictionary, convert values inside it.
    if isinstance(value, dict):
        return {
            key: convert_decimal_to_python(inner_value)
            for key, inner_value in value.items()
        }

    # If value is list, convert every item.
    if isinstance(value, list):
        return [
            convert_decimal_to_python(item)
            for item in value
        ]

    # Return strings, bools, and None as-is.
    return value


# Load documents only from local JSON.
def load_documents_from_local():
    """
    Simple meaning:
    Read records only from app/data/documents.json.

    This is local backup/cache reading.
    """

    # Make sure file exists.
    ensure_metadata_file_exists()

    # Read local JSON.
    with open(DOCUMENTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# Save documents only to local JSON.
def save_documents(documents):
    """
    Simple meaning:
    Save the full documents list to local documents.json.

    This function is kept because other files/tests may already use it.
    """

    # Make sure file exists.
    ensure_metadata_file_exists()

    # Write formatted JSON.
    with open(DOCUMENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(documents, file, indent=4)


# Upsert one document into local JSON backup.
def upsert_document_locally(document_metadata):
    """
    Simple meaning:
    Upsert means:

    If document exists locally → update it.
    If document does not exist locally → add it.

    This keeps documents.json as a local backup/cache.
    """

    # Load local documents only.
    documents = load_documents_from_local()

    # Get document_id.
    document_id = document_metadata.get("document_id")

    # If document_id is missing, do nothing.
    if not document_id:
        return None

    # Track whether document exists.
    found = False

    # Loop through local documents.
    for index, document in enumerate(documents):
        # If matching document found, replace it.
        if document.get("document_id") == document_id:
            documents[index] = document_metadata
            found = True
            break

    # If not found, append as new record.
    if not found:
        documents.append(document_metadata)

    # Save local backup.
    save_documents(documents)

    # Return saved metadata.
    return document_metadata


# Delete one document from local JSON backup.
def delete_document_locally(document_id):
    """
    Simple meaning:
    Remove one document record from local documents.json.
    """

    # Load local documents only.
    documents = load_documents_from_local()

    # Keep every document except the target one.
    remaining_documents = [
        document
        for document in documents
        if document.get("document_id") != document_id
    ]

    # Save remaining documents.
    save_documents(remaining_documents)

    # Return whether anything was removed.
    return len(remaining_documents) != len(documents)


# Save document metadata to DynamoDB if enabled.
def save_document_to_dynamodb_if_enabled(document_metadata):
    """
    Simple meaning:
    If DynamoDB is enabled, save metadata to DynamoDB.
    """

    # If DynamoDB is disabled, skip.
    if not DYNAMODB_ENABLED:
        return {
            "dynamodb_write_status": "disabled",
            "dynamodb_error_message": None,
        }

    try:
        # Save full metadata to DynamoDB.
        put_document_metadata(document_metadata)

        # Return success.
        return {
            "dynamodb_write_status": "success",
            "dynamodb_error_message": None,
        }

    except DynamoDBServiceError as error:
        # Return failure without crashing local backup write.
        return {
            "dynamodb_write_status": "failed",
            "dynamodb_error_message": str(error),
        }


# Update document metadata in DynamoDB if enabled.
def update_document_in_dynamodb_if_enabled(document_id, updates):
    """
    Simple meaning:
    If DynamoDB is enabled, update metadata fields in DynamoDB.
    """

    # If DynamoDB is disabled, skip.
    if not DYNAMODB_ENABLED:
        return {
            "dynamodb_write_status": "disabled",
            "dynamodb_error_message": None,
        }

    try:
        # Update selected fields in DynamoDB.
        update_document_metadata_in_dynamodb(
            document_id=document_id,
            updates=updates,
        )

        # Return success.
        return {
            "dynamodb_write_status": "success",
            "dynamodb_error_message": None,
        }

    except DynamoDBServiceError as error:
        # Return failure without crashing local backup write.
        return {
            "dynamodb_write_status": "failed",
            "dynamodb_error_message": str(error),
        }


# Fetch one document from DynamoDB if enabled.
def get_document_from_dynamodb_if_enabled(document_id):
    """
    Simple meaning:
    Read one document from DynamoDB.
    """

    # If DynamoDB is disabled, return None.
    if not DYNAMODB_ENABLED:
        return None

    try:
        # Fetch document from DynamoDB.
        document = get_document_metadata(document_id)

        # If not found, return None.
        if document is None:
            return None

        # Convert DynamoDB number types into normal Python numbers.
        return convert_decimal_to_python(document)

    except DynamoDBServiceError:
        # If DynamoDB has an issue, fallback will use local JSON.
        return None


# List documents from DynamoDB if enabled.
def list_documents_from_dynamodb_if_enabled(limit: int = 50):
    """
    Simple meaning:
    Read document list from DynamoDB.
    """

    # If DynamoDB is disabled, return empty list.
    if not DYNAMODB_ENABLED:
        return []

    try:
        # Fetch documents from DynamoDB.
        documents = list_document_metadata(limit=limit)

        # Convert DynamoDB number types into normal Python numbers.
        return convert_decimal_to_python(documents)

    except DynamoDBServiceError:
        # If DynamoDB fails, fallback will use local JSON.
        return []


# Load all document metadata records.
def load_documents():
    """
    Simple meaning:
    This is now the main list function.

    Current behavior:
    1. Try DynamoDB first.
    2. If DynamoDB has records, return them.
    3. If DynamoDB is disabled/empty/unavailable, return local documents.json.
    """

    # Try DynamoDB first.
    dynamodb_documents = list_documents_from_dynamodb_if_enabled(limit=50)

    # If DynamoDB has records, return them.
    if dynamodb_documents:
        return dynamodb_documents

    # Fallback to local JSON backup.
    return load_documents_from_local()


# Add one new document metadata record.
def add_document_metadata(document_metadata):
    """
    Simple meaning:
    Add a new document metadata record.

    Current behavior:
    1. Add timestamps.
    2. Save to DynamoDB if enabled.
    3. Save/update local documents.json backup.
    """

    # Add created_at if missing.
    document_metadata.setdefault("created_at", get_current_timestamp())

    # Always update updated_at.
    document_metadata["updated_at"] = get_current_timestamp()

    # Save to DynamoDB first.
    dynamodb_result = save_document_to_dynamodb_if_enabled(document_metadata)

    # Store DynamoDB sync status.
    document_metadata["dynamodb_write_status"] = dynamodb_result["dynamodb_write_status"]
    document_metadata["dynamodb_error_message"] = dynamodb_result["dynamodb_error_message"]

    # Save/update local backup.
    upsert_document_locally(document_metadata)

    # Return document metadata.
    return document_metadata


# Get one document by document_id.
def get_document_by_id(document_id):
    """
    Simple meaning:
    Find one document metadata record.

    Current behavior:
    1. Try DynamoDB first.
    2. If not found in DynamoDB, fallback to local documents.json.
    """

    # Try DynamoDB first.
    dynamodb_document = get_document_from_dynamodb_if_enabled(document_id)

    # If found in DynamoDB, return it.
    if dynamodb_document is not None:
        return dynamodb_document

    # Fallback to local JSON backup.
    local_documents = load_documents_from_local()

    # Search local documents.
    for document in local_documents:
        # If matching document is found, return it.
        if document.get("document_id") == document_id:
            return document

    # Return None if not found anywhere.
    return None


# Update metadata for one document.
def update_document_metadata(document_id, updates):
    """
    Simple meaning:
    Update selected fields for one document.

    Current behavior:
    1. Check if document exists in DynamoDB/local.
    2. Update DynamoDB if enabled.
    3. Update local backup.
    """

    # Get existing document from DynamoDB first, then local fallback.
    existing_document = get_document_by_id(document_id)

    # If document does not exist anywhere, return None.
    if existing_document is None:
        return None

    # Add updated_at timestamp.
    updates["updated_at"] = get_current_timestamp()

    # Update DynamoDB if enabled.
    dynamodb_result = update_document_in_dynamodb_if_enabled(
        document_id=document_id,
        updates=updates,
    )

    # Merge old metadata with new updates.
    updated_document = {
        **existing_document,
        **updates,
    }

    # Store DynamoDB sync result.
    updated_document["dynamodb_write_status"] = dynamodb_result["dynamodb_write_status"]
    updated_document["dynamodb_error_message"] = dynamodb_result["dynamodb_error_message"]

    # Save/update local backup.
    upsert_document_locally(updated_document)

    # Return updated metadata.
    return updated_document


# Delete metadata for one document.
def delete_document_metadata_by_id(document_id):
    """
    Simple meaning:
    Delete one document metadata record.

    Current behavior:
    1. Delete from DynamoDB if enabled.
    2. Delete from local documents.json backup.
    """

    # Track whether DynamoDB delete was attempted successfully.
    dynamodb_delete_success = False

    # Delete from DynamoDB if enabled.
    if DYNAMODB_ENABLED:
        try:
            # Delete from DynamoDB.
            delete_document_metadata(document_id)

            # Mark success.
            dynamodb_delete_success = True

        except DynamoDBServiceError:
            # Do not crash local delete if DynamoDB delete fails.
            dynamodb_delete_success = False

    # Delete from local backup.
    local_delete_success = delete_document_locally(document_id)

    # Return True if deleted from either place.
    return dynamodb_delete_success or local_delete_success