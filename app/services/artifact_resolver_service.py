# Import Path so we can safely work with file and folder paths.
from pathlib import Path

# Import HTTPException so we can return clean API errors if a file is missing.
from fastapi import HTTPException

# Import project Import HTTPException so we can return clean API errors if a file is missing.
from fastapi import HTTPException

# Import project config values.
from app.config import UPLOAD_DIR, S3_UPLOAD_ENABLED

# Import the full s3_service module.
# We import the module instead of individual functions so monkeypatch testing is easier later.
from app.services import s3_service


# Convert UPLOAD_DIR into a Path object.
# This makes path joining safer across Windows/Linux.
UPLOAD_ROOT = Path(UPLOAD_DIR)


# Define a helper to read values from either dict metadata or Pydantic-style objects.
def get_metadata_value(document_metadata, possible_keys):
    """
    Simple meaning:
    Metadata may be a normal dictionary or a Pydantic object.

    This helper checks multiple possible field names safely.
    """

    # If document_metadata is None, return None.
    if document_metadata is None:
        return None

    # If metadata is a dictionary, use dictionary access.
    if isinstance(document_metadata, dict):
        # Loop through possible field names.
        for key in possible_keys:
            # If this key exists and has a value, return it.
            if document_metadata.get(key):
                return document_metadata.get(key)

        # If no key matched, return None.
        return None

    # If metadata is an object, use getattr.
    for key in possible_keys:
        # Get the attribute value if it exists.
        value = getattr(document_metadata, key, None)

        # If value exists, return it.
        if value:
            return value

    # If nothing matched, return None.
    return None


# Build the local folder path for one document.
def get_document_local_folder(document_id: str) -> Path:
    """
    Example:
    uploads/doc_abc123/
    """

    # Return the local document folder path.
    return UPLOAD_ROOT / document_id


# Build the default local PDF path.
def get_default_local_pdf_path(document_id: str) -> Path:
    """
    Example:
    uploads/doc_abc123/uploaded_file.pdf
    """

    # Return default local PDF path.
    return get_document_local_folder(document_id) / "uploaded_file.pdf"


# Build the default extracted text path.
def get_default_extracted_text_path(document_id: str) -> Path:
    """
    Example:
    uploads/doc_abc123/extracted_text.json
    """

    # Return extracted_text.json path.
    return get_document_local_folder(document_id) / "extracted_text.json"


# Build the default chunks path.
def get_default_chunks_path(document_id: str) -> Path:
    """
    Example:
    uploads/doc_abc123/chunks.json
    """

    # Return chunks.json path.
    return get_document_local_folder(document_id) / "chunks.json"


# Build the default S3 key for the uploaded PDF.
def get_default_pdf_s3_key(document_id: str) -> str:
    """
    Example:
    documents/doc_abc123/uploaded_file.pdf
    """

    # Return the S3 key for the original uploaded PDF.
    return f"documents/{document_id}/uploaded_file.pdf"


# Build the default S3 key for extracted text.
def get_default_extracted_text_s3_key(document_id: str) -> str:
    """
    Example:
    documents/doc_abc123/extracted_text.json
    """

    # Return the S3 key for extracted text.
    return f"documents/{document_id}/extracted_text.json"


# Build the default S3 key for chunks.
def get_default_chunks_s3_key(document_id: str) -> str:
    """
    Example:
    documents/doc_abc123/chunks.json
    """

    # Return the S3 key for chunks.
    return f"documents/{document_id}/chunks.json"


# Download one artifact from S3 if possible.
def download_artifact_from_s3(s3_key: str, local_path: Path) -> Path:
    """
    Simple meaning:
    This function restores a missing local file from S3.
    """

    # If S3 is disabled, do not try to download.
    if not S3_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="Local file is missing and S3 fallback is disabled.",
        )

    # Create the parent folder if it does not exist.
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the file exists in S3 before downloading.
    file_exists = s3_service.check_file_exists_in_s3(s3_key)

    # If file does not exist in S3, return a clean API error.
    if not file_exists:
        raise HTTPException(
            status_code=404,
            detail=f"File is missing locally and not found in S3: {s3_key}",
        )

    # Download the file from S3 to the local path.
    s3_service.download_file_from_s3(
        s3_key=s3_key,
        local_file_path=str(local_path),
    )

    # Return the restored local path.
    return local_path


# Ensure the uploaded PDF exists locally.
def ensure_pdf_available_locally(document_metadata) -> str:
    """
    Used by:
    POST /documents/{document_id}/extract

    Flow:
    1. Check local PDF.
    2. If missing, download uploaded_file.pdf from S3.
    3. Return local PDF path.
    """

    # Get document_id from metadata.
    document_id = get_metadata_value(document_metadata, ["document_id", "id"])

    # If document_id is missing, return a clean error.
    if not document_id:
        raise HTTPException(
            status_code=400,
            detail="document_id is missing from document metadata.",
        )

    # Try to find the local PDF path from metadata.
    local_pdf_path = get_metadata_value(
        document_metadata,
        ["file_path", "local_file_path", "pdf_path", "uploaded_file_path"],
    )

    # If metadata does not have local path, use default local path.
    if not local_pdf_path:
        local_pdf_path = get_default_local_pdf_path(document_id)

    # Convert local path to Path object.
    local_pdf_path = Path(local_pdf_path)

    # If local PDF exists, return it.
    if local_pdf_path.exists():
        return str(local_pdf_path)

    # Try to find S3 key from metadata.
    s3_key = get_metadata_value(
        document_metadata,
        ["s3_key", "pdf_s3_key", "uploaded_file_s3_key", "original_pdf_s3_key"],
    )

    # If metadata does not have S3 key, use default S3 path.
    if not s3_key:
        s3_key = get_default_pdf_s3_key(document_id)

    # Download PDF from S3.
    restored_path = download_artifact_from_s3(
        s3_key=s3_key,
        local_path=local_pdf_path,
    )

    # Return restored PDF path.
    return str(restored_path)


# Ensure extracted_text.json exists locally.
def ensure_extracted_text_available_locally(document_id: str, document_metadata=None) -> str:
    """
    Used by:
    POST /documents/{document_id}/chunk

    Flow:
    1. Check local extracted_text.json.
    2. If missing, download extracted_text.json from S3.
    3. Return local extracted text path.
    """

    # Try to get local extracted text path from metadata.
    local_extracted_path = get_metadata_value(
        document_metadata,
        ["extracted_text_path", "local_extracted_text_path"],
    )

    # If metadata does not have path, use default local path.
    if not local_extracted_path:
        local_extracted_path = get_default_extracted_text_path(document_id)

    # Convert to Path object.
    local_extracted_path = Path(local_extracted_path)

    # If local extracted text exists, return it.
    if local_extracted_path.exists():
        return str(local_extracted_path)

    # Try to get S3 key from metadata.
    s3_key = get_metadata_value(
        document_metadata,
        ["extracted_text_s3_key", "s3_extracted_text_key"],
    )

    # If metadata does not have S3 key, use default.
    if not s3_key:
        s3_key = get_default_extracted_text_s3_key(document_id)

    # Download extracted_text.json from S3.
    restored_path = download_artifact_from_s3(
        s3_key=s3_key,
        local_path=local_extracted_path,
    )

    # Return restored file path.
    return str(restored_path)


# Ensure chunks.json exists locally.
def ensure_chunks_available_locally(document_id: str, document_metadata=None) -> str:
    """
    Used by:
    POST /documents/{document_id}/index

    Flow:
    1. Check local chunks.json.
    2. If missing, download chunks.json from S3.
    3. Return local chunks path.
    """

    # Try to get local chunks path from metadata.
    local_chunks_path = get_metadata_value(
        document_metadata,
        ["chunks_path", "local_chunks_path"],
    )

    # If metadata does not have path, use default local path.
    if not local_chunks_path:
        local_chunks_path = get_default_chunks_path(document_id)

    # Convert to Path object.
    local_chunks_path = Path(local_chunks_path)

    # If local chunks file exists, return it.
    if local_chunks_path.exists():
        return str(local_chunks_path)

    # Try to get S3 key from metadata.
    s3_key = get_metadata_value(
        document_metadata,
        ["chunks_s3_key", "s3_chunks_key"],
    )

    # If metadata does not have S3 key, use default.
    if not s3_key:
        s3_key = get_default_chunks_s3_key(document_id)

    # Download chunks.json from S3.
    restored_path = download_artifact_from_s3(
        s3_key=s3_key,
        local_path=local_chunks_path,
    )

    # Return restored chunks file path.
    return str(restored_path)