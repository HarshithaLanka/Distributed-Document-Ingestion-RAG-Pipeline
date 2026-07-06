# Import BytesIO so we can handle downloaded S3 files as in-memory bytes.
from io import BytesIO

# Import Path so we can safely work with local file paths.
from pathlib import Path

# Import Optional so some function arguments can be optional.
from typing import Optional

# Import boto3 so Python can communicate with AWS S3.
import boto3

# Import AWS-related exceptions so we can catch S3 errors cleanly.
from botocore.exceptions import ClientError, BotoCoreError

# Import S3 configuration values from config.py.
from app.config import (
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    S3_BUCKET_NAME,
    is_s3_configured,
    get_missing_s3_settings,
)

def upload_redacted_chunks_to_s3(
    local_file_path: str,
    document_id: str,
) -> dict:
    """
    Upload redacted_chunks.json to S3.

    Actual meaning:
    This stores the privacy-safe chunk artifact in S3.

    Original chunks.json:
        May contain raw emails/phones.

    redacted_chunks.json:
        Contains [EMAIL_REDACTED], [PHONE_REDACTED], etc.
    """

    # Build S3 key for redacted_chunks.json.
    s3_key = build_document_artifact_s3_key(
        document_id=document_id,
        artifact_filename="redacted_chunks.json",
    )

    # Upload local JSON file to S3.
    return upload_local_file_to_s3(
        local_file_path=local_file_path,
        s3_key=s3_key,
        content_type="application/json",
    )
# Create a custom exception for S3-related service errors.
class S3ServiceError(Exception):
    """
    Custom error used when something goes wrong in S3 service operations.
    """

    pass


def create_s3_client():
    """
    Create and return a boto3 S3 client.

    A boto3 client is a Python object that can call AWS S3 APIs.
    """

    # Check whether required S3 settings exist in .env.
    if not is_s3_configured():
        # Get the missing environment variable names.
        missing_settings = get_missing_s3_settings()

        # Raise a clean error instead of failing silently.
        raise S3ServiceError(
            f"S3 is not configured properly. Missing settings: {missing_settings}"
        )

    # Create and return the S3 client using values from .env.
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def build_document_s3_key(document_id: str, filename: Optional[str] = None) -> str:
    """
    Build a clean S3 object key for an uploaded document PDF.

    Example:
    documents/doc_123/original.pdf
    """

    # If filename is not provided, use original.pdf.
    safe_filename = filename or "original.pdf"

    # Replace Windows backslashes with forward slashes.
    safe_filename = safe_filename.replace("\\", "/")

    # Keep only the actual filename if a path was accidentally passed.
    safe_filename = safe_filename.split("/")[-1]

    # Store the PDF inside documents/{document_id}/.
    return f"documents/{document_id}/{safe_filename}"


def build_document_artifact_s3_key(document_id: str, artifact_filename: str) -> str:
    """
    Build an S3 key for generated pipeline files.

    Examples:
    documents/doc_123/extracted_text.json
    documents/doc_123/chunks.json
    """

    # Remove any accidental folder path from artifact_filename.
    safe_artifact_filename = artifact_filename.replace("\\", "/").split("/")[-1]

    # Store all generated files inside the document folder in S3.
    return f"documents/{document_id}/{safe_artifact_filename}"


def build_s3_uri(s3_key: str) -> str:
    """
    Build a readable S3 URI.

    Example:
    s3://bucket-name/documents/doc_123/original.pdf
    """

    # Return the standard S3 URI format.
    return f"s3://{S3_BUCKET_NAME}/{s3_key}"


def upload_fileobj_to_s3(
    file_obj,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> dict:
    """
    Upload a file-like object to S3.

    file_obj can be:
    - FastAPI UploadFile.file
    - BytesIO object
    - a normal file opened in binary mode
    """

    # Create S3 client.
    s3_client = create_s3_client()

    try:
        # Move file pointer to the beginning before upload.
        file_obj.seek(0)

        # Upload the file object to S3.
        s3_client.upload_fileobj(
            file_obj,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ContentType": content_type
            },
        )

        # Return useful upload information.
        return {
            "bucket": S3_BUCKET_NAME,
            "s3_key": s3_key,
            "s3_uri": build_s3_uri(s3_key),
            "content_type": content_type,
        }

    except (ClientError, BotoCoreError) as error:
        # Raise a clean custom service error.
        raise S3ServiceError(f"Failed to upload file to S3: {str(error)}") from error


def upload_local_file_to_s3(
    local_file_path: str,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> dict:
    """
    Upload a local file from disk to S3.

    This is useful for files generated by the pipeline:
    - extracted_text.json
    - chunks.json
    """

    # Convert the file path into a Path object.
    file_path = Path(local_file_path)

    # Check if the file exists locally before uploading.
    if not file_path.exists():
        raise S3ServiceError(f"Local file does not exist: {local_file_path}")

    # Open the local file in binary read mode.
    with open(file_path, "rb") as file_obj:
        # Upload the local file object to S3.
        return upload_fileobj_to_s3(
            file_obj=file_obj,
            s3_key=s3_key,
            content_type=content_type,
        )


def upload_pdf_to_s3(
    file_obj,
    document_id: str,
    filename: str = "original.pdf",
) -> dict:
    """
    Upload a PDF file to S3 for a specific document.

    This is used by /documents/upload.
    """

    # Build document-specific S3 key.
    s3_key = build_document_s3_key(
        document_id=document_id,
        filename=filename,
    )

    # Upload the file as application/pdf.
    return upload_fileobj_to_s3(
        file_obj=file_obj,
        s3_key=s3_key,
        content_type="application/pdf",
    )


def upload_extracted_text_to_s3(
    local_file_path: str,
    document_id: str,
) -> dict:
    """
    Upload extracted_text.json to S3.

    This is used after successful text extraction.
    """

    # Build S3 key for extracted_text.json.
    s3_key = build_document_artifact_s3_key(
        document_id=document_id,
        artifact_filename="extracted_text.json",
    )

    # Upload local JSON file to S3.
    return upload_local_file_to_s3(
        local_file_path=local_file_path,
        s3_key=s3_key,
        content_type="application/json",
    )


def upload_chunks_to_s3(
    local_file_path: str,
    document_id: str,
) -> dict:
    """
    Upload chunks.json to S3.

    This is used after successful chunking.
    """

    # Build S3 key for chunks.json.
    s3_key = build_document_artifact_s3_key(
        document_id=document_id,
        artifact_filename="chunks.json",
    )

    # Upload local JSON file to S3.
    return upload_local_file_to_s3(
        local_file_path=local_file_path,
        s3_key=s3_key,
        content_type="application/json",
    )


def download_file_from_s3(s3_key: str) -> bytes:
    """
    Download a file from S3 and return it as bytes.

    This will be useful later when extraction reads PDFs from S3.
    """

    # Create S3 client.
    s3_client = create_s3_client()

    try:
        # Get object from S3.
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
        )

        # Read and return file bytes.
        return response["Body"].read()

    except (ClientError, BotoCoreError) as error:
        # Raise clean error if download fails.
        raise S3ServiceError(f"Failed to download file from S3: {str(error)}") from error


def download_file_as_bytesio(s3_key: str) -> BytesIO:
    """
    Download a file from S3 and return it as a BytesIO object.

    BytesIO behaves like a file in memory.
    """

    # Download raw bytes from S3.
    file_bytes = download_file_from_s3(s3_key)

    # Convert bytes into an in-memory file-like object.
    return BytesIO(file_bytes)


def delete_file_from_s3(s3_key: str) -> dict:
    """
    Delete a file from S3.

    This is useful for cleanup or failed uploads.
    """

    # Create S3 client.
    s3_client = create_s3_client()

    try:
        # Delete object from S3.
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
        )

        # Return delete confirmation.
        return {
            "bucket": S3_BUCKET_NAME,
            "s3_key": s3_key,
            "deleted": True,
        }

    except (ClientError, BotoCoreError) as error:
        # Raise clean error if delete fails.
        raise S3ServiceError(f"Failed to delete file from S3: {str(error)}") from error


def check_file_exists_in_s3(s3_key: str) -> bool:
    """
    Check whether a file exists in S3.

    This does not download the file.
    It only checks metadata.
    """

    # Create S3 client.
    s3_client = create_s3_client()

    try:
        # head_object checks if the object exists.
        s3_client.head_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
        )

        # If no error happens, the file exists.
        return True

    except ClientError as error:
        # Get AWS error code.
        error_code = error.response.get("Error", {}).get("Code", "")

        # If S3 says 404 or NoSuchKey, file does not exist.
        if error_code in ["404", "NoSuchKey", "NotFound"]:
            return False

        # For other errors, raise a clean service error.
        raise S3ServiceError(f"Failed to check file in S3: {str(error)}") from error

    except BotoCoreError as error:
        # Handle lower-level boto3/botocore errors.
        raise S3ServiceError(f"Failed to check file in S3: {str(error)}") from error