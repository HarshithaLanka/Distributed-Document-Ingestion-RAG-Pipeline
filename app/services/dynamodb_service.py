"""
DynamoDB service for document metadata.

Simple meaning:
This file talks to AWS DynamoDB.

DynamoDB will store metadata like:
- document_id
- filename
- status
- page_count
- s3_key
- extracted_text_s3_key
- chunks_s3_key
- vector_count

For now, this service is tested separately using a smoke test.
We will connect it to the real API after the smoke test passes.
"""

# Import Decimal because DynamoDB prefers Decimal for numeric values.
from decimal import Decimal

# Import boto3 to communicate with AWS services.
import boto3

# Import ClientError to catch AWS errors cleanly.
from botocore.exceptions import ClientError

# Import FastAPI HTTPException for clean API-style errors if needed later.
from fastapi import HTTPException

# Import DynamoDB and AWS settings from config.
from app.config import AWS_REGION
from app.config import AWS_ACCESS_KEY_ID
from app.config import AWS_SECRET_ACCESS_KEY
from app.config import DYNAMODB_ENABLED
from app.config import DYNAMODB_TABLE_NAME
from app.config import is_dynamodb_configured
from app.config import get_missing_dynamodb_settings


# Create custom DynamoDB error.
class DynamoDBServiceError(Exception):
    """
    Simple meaning:
    This is our own error type for DynamoDB problems.

    Instead of showing messy AWS errors everywhere,
    we wrap them in this cleaner error.
    """

    pass


# Check whether DynamoDB is enabled.
def is_dynamodb_enabled() -> bool:
    """
    Simple meaning:
    This returns True only when DYNAMODB_ENABLED=true in .env.
    """

    # Return DynamoDB enabled value.
    return DYNAMODB_ENABLED


# Create DynamoDB resource/client connection.
def get_dynamodb_resource():
    """
    Simple meaning:
    This creates the connection between your Python backend and DynamoDB.

    boto3.resource("dynamodb") gives us a high-level DynamoDB object.
    """

    # If DynamoDB is disabled, stop here.
    if not is_dynamodb_enabled():
        raise DynamoDBServiceError(
            "DynamoDB is disabled. Set DYNAMODB_ENABLED=true in .env."
        )

    # If required config values are missing, show exactly what is missing.
    if not is_dynamodb_configured():
        missing_settings = get_missing_dynamodb_settings()

        raise DynamoDBServiceError(
            f"DynamoDB configuration is incomplete. Missing: {missing_settings}"
        )

    # Create and return DynamoDB resource.
    return boto3.resource(
        "dynamodb",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


# Get DynamoDB table object.
def get_documents_table():
    """
    Simple meaning:
    This returns your table:

    document-rag-dev-documents
    """

    # Get DynamoDB resource.
    dynamodb = get_dynamodb_resource()

    # Return the table object.
    return dynamodb.Table(DYNAMODB_TABLE_NAME)


# Convert Python values into DynamoDB-safe values.
def make_dynamodb_safe(value):
    """
    Simple meaning:
    DynamoDB handles numbers carefully.

    Python float values like 0.35 can cause issues.
    DynamoDB prefers Decimal("0.35").

    This function recursively converts:
    - float -> Decimal
    - dict values -> safe values
    - list values -> safe values
    """

    # If value is a float, convert it to Decimal.
    if isinstance(value, float):
        return Decimal(str(value))

    # If value is a dictionary, clean each key-value pair.
    if isinstance(value, dict):
        return {
            key: make_dynamodb_safe(inner_value)
            for key, inner_value in value.items()
        }

    # If value is a list, clean each item.
    if isinstance(value, list):
        return [
            make_dynamodb_safe(item)
            for item in value
        ]

    # For strings, ints, bools, None, return as-is.
    return value


# Clean metadata before saving to DynamoDB.
def prepare_item_for_dynamodb(document_metadata: dict) -> dict:
    """
    Simple meaning:
    This prepares a document metadata dictionary for DynamoDB.

    It removes empty keys if needed and converts floats safely.
    """

    # Create a clean dictionary.
    clean_item = {}

    # Loop through metadata fields.
    for key, value in document_metadata.items():
        # Skip keys that are None? No.
        # We allow None because DynamoDB can store NULL.
        clean_item[key] = make_dynamodb_safe(value)

    # Return cleaned item.
    return clean_item


# Save a full document metadata record into DynamoDB.
def put_document_metadata(document_metadata: dict) -> dict:
    """
    Simple meaning:
    Save one complete document metadata item in DynamoDB.

    This is similar to adding one object into documents.json.
    """

    # Validate document_id exists.
    if not document_metadata.get("document_id"):
        raise DynamoDBServiceError("document_id is required to save metadata.")

    try:
        # Get table.
        table = get_documents_table()

        # Prepare item for DynamoDB.
        item = prepare_item_for_dynamodb(document_metadata)

        # Save item in DynamoDB.
        table.put_item(Item=item)

        # Return saved item.
        return item

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to put document metadata in DynamoDB: {error}"
        )


# Get one document metadata record from DynamoDB.
def get_document_metadata(document_id: str):
    """
    Simple meaning:
    Fetch one document metadata item using document_id.
    """

    try:
        # Get table.
        table = get_documents_table()

        # Fetch item by partition key.
        response = table.get_item(
            Key={
                "document_id": document_id
            }
        )

        # Return item if it exists.
        return response.get("Item")

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to get document metadata from DynamoDB: {error}"
        )


# Update selected fields of one document metadata record.
def update_document_metadata_in_dynamodb(document_id: str, updates: dict):
    """
    Simple meaning:
    Update only selected fields for a document.

    Example:
    document_id = doc_123
    updates = {"status": "indexed", "vector_count": 20}

    This updates only status and vector_count.
    """

    # If no updates were passed, return existing item.
    if not updates:
        return get_document_metadata(document_id)

    # SET expressions are used for fields with real values.
    set_expressions = []

    # REMOVE expressions are used for fields with None values.
    remove_expressions = []

    # Attribute names avoid conflicts with DynamoDB reserved words.
    expression_attribute_names = {}

    # Attribute values store the actual values to update.
    expression_attribute_values = {}

    # Loop over update fields.
    for index, (field_name, field_value) in enumerate(updates.items()):
        # Do not update the primary key.
        if field_name == "document_id":
            continue

        # Create safe placeholders.
        name_placeholder = f"#field_{index}"
        value_placeholder = f":value_{index}"

        # Map placeholder to real field name.
        expression_attribute_names[name_placeholder] = field_name

        # If value is None, remove that field from DynamoDB.
        if field_value is None:
            remove_expressions.append(name_placeholder)

        else:
            # Convert value to DynamoDB-safe format.
            safe_value = make_dynamodb_safe(field_value)

            # Store value placeholder.
            expression_attribute_values[value_placeholder] = safe_value

            # Add SET expression.
            set_expressions.append(f"{name_placeholder} = {value_placeholder}")

    # Create update expression parts.
    update_expression_parts = []

    # Add SET section if there are set expressions.
    if set_expressions:
        update_expression_parts.append("SET " + ", ".join(set_expressions))

    # Add REMOVE section if there are remove expressions.
    if remove_expressions:
        update_expression_parts.append("REMOVE " + ", ".join(remove_expressions))

    # If nothing is left to update, return current item.
    if not update_expression_parts:
        return get_document_metadata(document_id)

    # Join update expression.
    update_expression = " ".join(update_expression_parts)

    try:
        # Get table.
        table = get_documents_table()

        # Update item.
        response = table.update_item(
            Key={
                "document_id": document_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values if expression_attribute_values else None,
            ReturnValues="ALL_NEW",
        )

        # Return updated item.
        return response.get("Attributes")

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to update document metadata in DynamoDB: {error}"
        )


# Delete one document metadata record from DynamoDB.
def delete_document_metadata(document_id: str):
    """
    Simple meaning:
    Delete one document metadata item from DynamoDB.
    """

    try:
        # Get table.
        table = get_documents_table()

        # Delete item by document_id.
        table.delete_item(
            Key={
                "document_id": document_id
            }
        )

        # Return success response.
        return {
            "document_id": document_id,
            "deleted": True,
        }

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to delete document metadata from DynamoDB: {error}"
        )


# List document metadata records from DynamoDB.
def list_document_metadata(limit: int = 50):
    """
    Simple meaning:
    Fetch multiple document metadata records.

    For now we use scan because this is a small dev project.
    Later, for production scale, we may add better query patterns/indexes.
    """

    try:
        # Get table.
        table = get_documents_table()

        # Scan table.
        response = table.scan(
            Limit=limit
        )

        # Return items.
        return response.get("Items", [])

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to list document metadata from DynamoDB: {error}"
        )


# Check if DynamoDB table is reachable.
def check_dynamodb_table_access():
    """
    Simple meaning:
    This checks whether your AWS credentials can access the table.
    """

    try:
        # Get table.
        table = get_documents_table()

        # Load table metadata from AWS.
        table.load()

        # Return table info.
        return {
            "table_name": table.table_name,
            "table_status": table.table_status,
            "accessible": True,
        }

    except ClientError as error:
        # Convert AWS error into clean project error.
        raise DynamoDBServiceError(
            f"Failed to access DynamoDB table: {error}"
        )