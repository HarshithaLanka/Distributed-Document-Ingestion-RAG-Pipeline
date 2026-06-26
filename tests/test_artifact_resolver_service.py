# Import json so we can create fake JSON files during tests.
import json

# Import pytest so we can write tests and check exceptions.
import pytest

# Import HTTPException so we can verify clean API errors.
from fastapi import HTTPException

# Import artifact resolver service.
from app.services import artifact_resolver_service as resolver


# Test 1:
# If a local file already exists, the resolver should return that file path.
# It should NOT call S3.
def test_pdf_resolver_uses_local_file_when_available(tmp_path, monkeypatch):
    # Set resolver upload root to temporary test folder.
    monkeypatch.setattr(resolver, "UPLOAD_ROOT", tmp_path)

    # Create fake document ID.
    document_id = "doc_test_001"

    # Create local document folder.
    document_folder = tmp_path / document_id

    # Create the folder.
    document_folder.mkdir(parents=True, exist_ok=True)

    # Create fake local PDF path.
    local_pdf_path = document_folder / "uploaded_file.pdf"

    # Write fake PDF bytes.
    local_pdf_path.write_bytes(b"%PDF-1.4 fake pdf content")

    # Create fake metadata.
    document_metadata = {
        "document_id": document_id,
        "file_path": str(local_pdf_path),
        "s3_key": f"documents/{document_id}/uploaded_file.pdf",
    }

    # Create a flag to check whether S3 was called.
    s3_called = {"value": False}

    # Fake S3 exists check.
    def fake_check_file_exists_in_s3(s3_key):
        # Mark S3 as called.
        s3_called["value"] = True

        # Return True.
        return True

    # Replace real S3 check function with fake function.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Call resolver.
    result_path = resolver.ensure_pdf_available_locally(document_metadata)

    # Check that resolver returned the local PDF path.
    assert result_path == str(local_pdf_path)

    # Check that S3 was not called because local file already existed.
    assert s3_called["value"] is False


# Test 2:
# If local PDF is missing, resolver should download PDF from fake S3.
def test_pdf_resolver_downloads_from_s3_when_local_file_missing(tmp_path, monkeypatch):
    # Set resolver upload root to temporary test folder.
    monkeypatch.setattr(resolver, "UPLOAD_ROOT", tmp_path)

    # Enable S3 fallback during this test.
    monkeypatch.setattr(resolver, "S3_UPLOAD_ENABLED", True)

    # Create fake document ID.
    document_id = "doc_test_002"

    # Create expected local PDF path.
    local_pdf_path = tmp_path / document_id / "uploaded_file.pdf"

    # Create fake metadata.
    document_metadata = {
        "document_id": document_id,
        "file_path": str(local_pdf_path),
        "s3_key": f"documents/{document_id}/uploaded_file.pdf",
    }

    # Fake S3 exists check.
    def fake_check_file_exists_in_s3(s3_key):
        # Pretend the file exists in S3.
        return True

    # Fake S3 download function.
    def fake_download_file_from_s3(s3_key, local_file_path):
        # Convert local path string into Path-like file.
        local_file = resolver.Path(local_file_path)

        # Create parent folder.
        local_file.parent.mkdir(parents=True, exist_ok=True)

        # Write fake PDF bytes to simulate S3 download.
        local_file.write_bytes(b"%PDF-1.4 restored from fake s3")

    # Replace real S3 check with fake.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Replace real S3 download with fake.
    monkeypatch.setattr(
        resolver.s3_service,
        "download_file_from_s3",
        fake_download_file_from_s3,
    )

    # Call resolver.
    result_path = resolver.ensure_pdf_available_locally(document_metadata)

    # Check returned path.
    assert result_path == str(local_pdf_path)

    # Check that file now exists locally after fake S3 download.
    assert local_pdf_path.exists()

    # Check fake downloaded content.
    assert local_pdf_path.read_bytes() == b"%PDF-1.4 restored from fake s3"


# Test 3:
# If local file is missing and S3 is disabled, resolver should return 404.
def test_download_artifact_fails_when_s3_disabled(tmp_path, monkeypatch):
    # Disable S3 fallback.
    monkeypatch.setattr(resolver, "S3_UPLOAD_ENABLED", False)

    # Create fake S3 key.
    s3_key = "documents/doc_test_003/chunks.json"

    # Create local path that does not exist.
    local_path = tmp_path / "doc_test_003" / "chunks.json"

    # Check that HTTPException is raised.
    with pytest.raises(HTTPException) as error:
        resolver.download_artifact_from_s3(
            s3_key=s3_key,
            local_path=local_path,
        )

    # Check status code.
    assert error.value.status_code == 404

    # Check error message.
    assert "S3 fallback is disabled" in error.value.detail


# Test 4:
# If local file is missing and S3 also does not have it, resolver should return 404.
def test_download_artifact_fails_when_file_not_found_in_s3(tmp_path, monkeypatch):
    # Enable S3 fallback.
    monkeypatch.setattr(resolver, "S3_UPLOAD_ENABLED", True)

    # Create fake S3 key.
    s3_key = "documents/doc_test_004/extracted_text.json"

    # Create local path that does not exist.
    local_path = tmp_path / "doc_test_004" / "extracted_text.json"

    # Fake S3 check says file does not exist.
    def fake_check_file_exists_in_s3(s3_key):
        # Pretend S3 does not have the file.
        return False

    # Replace real S3 check with fake.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Check that HTTPException is raised.
    with pytest.raises(HTTPException) as error:
        resolver.download_artifact_from_s3(
            s3_key=s3_key,
            local_path=local_path,
        )

    # Check status code.
    assert error.value.status_code == 404

    # Check error message.
    assert "not found in S3" in error.value.detail


# Test 5:
# If extracted_text.json is missing locally, resolver should restore it from fake S3.
def test_extracted_text_resolver_downloads_from_s3(tmp_path, monkeypatch):
    # Set resolver upload root to temporary folder.
    monkeypatch.setattr(resolver, "UPLOAD_ROOT", tmp_path)

    # Enable S3 fallback.
    monkeypatch.setattr(resolver, "S3_UPLOAD_ENABLED", True)

    # Create fake document ID.
    document_id = "doc_test_005"

    # Create expected extracted_text.json path.
    local_extracted_path = tmp_path / document_id / "extracted_text.json"

    # Create fake metadata.
    document_metadata = {
        "document_id": document_id,
        "extracted_text_path": str(local_extracted_path),
        "extracted_text_s3_key": f"documents/{document_id}/extracted_text.json",
    }

    # Fake S3 exists check.
    def fake_check_file_exists_in_s3(s3_key):
        # Pretend file exists in S3.
        return True

    # Fake S3 download.
    def fake_download_file_from_s3(s3_key, local_file_path):
        # Convert to Path.
        local_file = resolver.Path(local_file_path)

        # Create folder.
        local_file.parent.mkdir(parents=True, exist_ok=True)

        # Create fake extracted text data.
        fake_data = {
            "document_id": document_id,
            "page_count": 1,
            "pages": [
                {
                    "page_number": 1,
                    "text": "This is restored extracted text from fake S3.",
                }
            ],
        }

        # Write JSON file.
        local_file.write_text(json.dumps(fake_data), encoding="utf-8")

    # Replace S3 check.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Replace S3 download.
    monkeypatch.setattr(
        resolver.s3_service,
        "download_file_from_s3",
        fake_download_file_from_s3,
    )

    # Call resolver.
    result_path = resolver.ensure_extracted_text_available_locally(
        document_id=document_id,
        document_metadata=document_metadata,
    )

    # Check path.
    assert result_path == str(local_extracted_path)

    # Check file exists locally now.
    assert local_extracted_path.exists()

    # Read restored JSON.
    restored_data = json.loads(local_extracted_path.read_text(encoding="utf-8"))

    # Check restored content.
    assert restored_data["document_id"] == document_id

    # Check page text.
    assert "restored extracted text" in restored_data["pages"][0]["text"]


# Test 6:
# If chunks.json is missing locally, resolver should restore it from fake S3.
def test_chunks_resolver_downloads_from_s3(tmp_path, monkeypatch):
    # Set resolver upload root to temporary folder.
    monkeypatch.setattr(resolver, "UPLOAD_ROOT", tmp_path)

    # Enable S3 fallback.
    monkeypatch.setattr(resolver, "S3_UPLOAD_ENABLED", True)

    # Create fake document ID.
    document_id = "doc_test_006"

    # Create expected chunks path.
    local_chunks_path = tmp_path / document_id / "chunks.json"

    # Create fake metadata.
    document_metadata = {
        "document_id": document_id,
        "chunks_path": str(local_chunks_path),
        "chunks_s3_key": f"documents/{document_id}/chunks.json",
    }

    # Fake S3 exists check.
    def fake_check_file_exists_in_s3(s3_key):
        # Pretend file exists in S3.
        return True

    # Fake S3 download.
    def fake_download_file_from_s3(s3_key, local_file_path):
        # Convert path string to Path.
        local_file = resolver.Path(local_file_path)

        # Create parent folder.
        local_file.parent.mkdir(parents=True, exist_ok=True)

        # Create fake chunks data.
        fake_data = {
            "document_id": document_id,
            "chunk_count": 1,
            "chunks": [
                {
                    "chunk_id": "chunk_001",
                    "document_id": document_id,
                    "page_number": 1,
                    "text": "This is a restored chunk from fake S3.",
                    "word_count": 9,
                }
            ],
        }

        # Write JSON file.
        local_file.write_text(json.dumps(fake_data), encoding="utf-8")

    # Replace real S3 check.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Replace real S3 download.
    monkeypatch.setattr(
        resolver.s3_service,
        "download_file_from_s3",
        fake_download_file_from_s3,
    )

    # Call resolver.
    result_path = resolver.ensure_chunks_available_locally(
        document_id=document_id,
        document_metadata=document_metadata,
    )

    # Check path.
    assert result_path == str(local_chunks_path)

    # Check file exists locally now.
    assert local_chunks_path.exists()

    # Read restored JSON.
    restored_data = json.loads(local_chunks_path.read_text(encoding="utf-8"))

    # Check chunk count.
    assert restored_data["chunk_count"] == 1

    # Check restored chunk text.
    assert "restored chunk" in restored_data["chunks"][0]["text"]


# Test 7:
# If chunks.json already exists locally, resolver should not download from S3.
def test_chunks_resolver_uses_local_file_when_available(tmp_path, monkeypatch):
    # Set resolver upload root to temporary folder.
    monkeypatch.setattr(resolver, "UPLOAD_ROOT", tmp_path)

    # Create fake document ID.
    document_id = "doc_test_007"

    # Create local document folder.
    document_folder = tmp_path / document_id

    # Create folder.
    document_folder.mkdir(parents=True, exist_ok=True)

    # Create local chunks path.
    local_chunks_path = document_folder / "chunks.json"

    # Create local chunks data.
    fake_data = {
        "document_id": document_id,
        "chunk_count": 1,
        "chunks": [
            {
                "chunk_id": "chunk_local_001",
                "document_id": document_id,
                "page_number": 1,
                "text": "This local chunk should be used.",
                "word_count": 6,
            }
        ],
    }

    # Write local chunks file.
    local_chunks_path.write_text(json.dumps(fake_data), encoding="utf-8")

    # Create fake metadata.
    document_metadata = {
        "document_id": document_id,
        "chunks_path": str(local_chunks_path),
        "chunks_s3_key": f"documents/{document_id}/chunks.json",
    }

    # Create S3 call flag.
    s3_called = {"value": False}

    # Fake S3 exists check.
    def fake_check_file_exists_in_s3(s3_key):
        # Mark S3 as called.
        s3_called["value"] = True

        # Return True.
        return True

    # Replace S3 check.
    monkeypatch.setattr(
        resolver.s3_service,
        "check_file_exists_in_s3",
        fake_check_file_exists_in_s3,
    )

    # Call resolver.
    result_path = resolver.ensure_chunks_available_locally(
        document_id=document_id,
        document_metadata=document_metadata,
    )

    # Check resolver returned local path.
    assert result_path == str(local_chunks_path)

    # Check S3 was not called.
    assert s3_called["value"] is False