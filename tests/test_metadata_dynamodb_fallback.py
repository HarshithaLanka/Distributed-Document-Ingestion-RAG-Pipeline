# Import json so we can create fake documents.json files.
import json

# Import metadata service so we can test metadata behavior directly.
from app.services import metadata_service


# Helper function to point metadata_service to a temporary documents.json file.
def setup_temp_metadata_file(tmp_path, monkeypatch, initial_documents):
    """
    Simple meaning:
    During tests, we should not use the real app/data/documents.json.

    So we create a temporary fake documents.json file inside pytest temp folder.
    """

    # Create fake data folder.
    data_dir = tmp_path / "data"

    # Create the folder.
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create fake documents.json path.
    documents_file = data_dir / "documents.json"

    # Write initial documents into fake documents.json.
    documents_file.write_text(
        json.dumps(initial_documents),
        encoding="utf-8",
    )

    # Tell metadata_service to use this fake data folder.
    monkeypatch.setattr(metadata_service, "DATA_DIR", data_dir)

    # Tell metadata_service to use this fake documents.json file.
    monkeypatch.setattr(metadata_service, "DOCUMENTS_FILE", documents_file)

    # Return fake documents file path.
    return documents_file


# Test 1:
# If DynamoDB has documents, load_documents should use DynamoDB first.
def test_load_documents_uses_dynamodb_first_when_available(tmp_path, monkeypatch):
    # Setup local documents.json with a local record.
    setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[
            {
                "document_id": "doc_local_001",
                "filename": "local.pdf",
                "status": "uploaded",
            }
        ],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Fake DynamoDB list function.
    def fake_list_documents_from_dynamodb_if_enabled(limit=50):
        # Return DynamoDB records.
        return [
            {
                "document_id": "doc_dynamo_001",
                "filename": "from_dynamodb.pdf",
                "status": "indexed",
            }
        ]

    # Replace real DynamoDB list with fake.
    monkeypatch.setattr(
        metadata_service,
        "list_documents_from_dynamodb_if_enabled",
        fake_list_documents_from_dynamodb_if_enabled,
    )

    # Call load_documents.
    result = metadata_service.load_documents()

    # Confirm DynamoDB record was returned.
    assert len(result) == 1
    assert result[0]["document_id"] == "doc_dynamo_001"
    assert result[0]["filename"] == "from_dynamodb.pdf"


# Test 2:
# If DynamoDB is empty, load_documents should fallback to local JSON.
def test_load_documents_falls_back_to_local_when_dynamodb_empty(tmp_path, monkeypatch):
    # Setup local documents.json with local record.
    setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[
            {
                "document_id": "doc_local_001",
                "filename": "local.pdf",
                "status": "uploaded",
            }
        ],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Fake DynamoDB returns empty list.
    def fake_list_documents_from_dynamodb_if_enabled(limit=50):
        return []

    # Replace real DynamoDB list with fake.
    monkeypatch.setattr(
        metadata_service,
        "list_documents_from_dynamodb_if_enabled",
        fake_list_documents_from_dynamodb_if_enabled,
    )

    # Call load_documents.
    result = metadata_service.load_documents()

    # Confirm local record was returned.
    assert len(result) == 1
    assert result[0]["document_id"] == "doc_local_001"
    assert result[0]["filename"] == "local.pdf"


# Test 3:
# If DynamoDB has one document, get_document_by_id should use DynamoDB first.
def test_get_document_by_id_uses_dynamodb_first(tmp_path, monkeypatch):
    # Setup local documents.json with same document ID but different filename.
    setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[
            {
                "document_id": "doc_001",
                "filename": "local_version.pdf",
                "status": "uploaded",
            }
        ],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Fake DynamoDB get function.
    def fake_get_document_from_dynamodb_if_enabled(document_id):
        return {
            "document_id": document_id,
            "filename": "dynamodb_version.pdf",
            "status": "indexed",
        }

    # Replace real DynamoDB get with fake.
    monkeypatch.setattr(
        metadata_service,
        "get_document_from_dynamodb_if_enabled",
        fake_get_document_from_dynamodb_if_enabled,
    )

    # Call get_document_by_id.
    result = metadata_service.get_document_by_id("doc_001")

    # Confirm DynamoDB version was returned, not local version.
    assert result["filename"] == "dynamodb_version.pdf"
    assert result["status"] == "indexed"


# Test 4:
# If DynamoDB does not have document, get_document_by_id should fallback to local JSON.
def test_get_document_by_id_falls_back_to_local_when_dynamodb_missing(tmp_path, monkeypatch):
    # Setup local documents.json with one document.
    setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[
            {
                "document_id": "doc_local_001",
                "filename": "local.pdf",
                "status": "uploaded",
            }
        ],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Fake DynamoDB returns None.
    def fake_get_document_from_dynamodb_if_enabled(document_id):
        return None

    # Replace real DynamoDB get with fake.
    monkeypatch.setattr(
        metadata_service,
        "get_document_from_dynamodb_if_enabled",
        fake_get_document_from_dynamodb_if_enabled,
    )

    # Call get_document_by_id.
    result = metadata_service.get_document_by_id("doc_local_001")

    # Confirm local document was returned.
    assert result is not None
    assert result["filename"] == "local.pdf"


# Test 5:
# add_document_metadata should write to DynamoDB and local backup.
def test_add_document_metadata_writes_to_dynamodb_and_local_backup(tmp_path, monkeypatch):
    # Setup empty local documents.json.
    documents_file = setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Track DynamoDB put call.
    dynamodb_put_called = {"value": False}

    # Fake DynamoDB save wrapper.
    def fake_save_document_to_dynamodb_if_enabled(document_metadata):
        # Mark DynamoDB as called.
        dynamodb_put_called["value"] = True

        # Confirm document_id is present.
        assert document_metadata["document_id"] == "doc_add_001"

        # Return fake success.
        return {
            "dynamodb_write_status": "success",
            "dynamodb_error_message": None,
        }

    # Replace real DynamoDB save wrapper.
    monkeypatch.setattr(
        metadata_service,
        "save_document_to_dynamodb_if_enabled",
        fake_save_document_to_dynamodb_if_enabled,
    )

    # Add document.
    result = metadata_service.add_document_metadata(
        {
            "document_id": "doc_add_001",
            "filename": "add_test.pdf",
            "status": "uploaded",
        }
    )

    # Confirm DynamoDB was called.
    assert dynamodb_put_called["value"] is True

    # Confirm result status.
    assert result["dynamodb_write_status"] == "success"

    # Confirm local backup was written.
    saved_documents = json.loads(documents_file.read_text(encoding="utf-8"))

    # Check one local record exists.
    assert len(saved_documents) == 1

    # Check local backup document ID.
    assert saved_documents[0]["document_id"] == "doc_add_001"


# Test 6:
# update_document_metadata should update DynamoDB and local backup.
def test_update_document_metadata_updates_dynamodb_and_local_backup(tmp_path, monkeypatch):
    # Setup local backup with existing document.
    documents_file = setup_temp_metadata_file(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        initial_documents=[
            {
                "document_id": "doc_update_001",
                "filename": "update_test.pdf",
                "status": "uploaded",
            }
        ],
    )

    # Enable DynamoDB.
    monkeypatch.setattr(metadata_service, "DYNAMODB_ENABLED", True)

    # Fake get_document_by_id dependency through DynamoDB.
    def fake_get_document_from_dynamodb_if_enabled(document_id):
        return {
            "document_id": document_id,
            "filename": "update_test.pdf",
            "status": "uploaded",
        }

    # Track update call.
    dynamodb_update_called = {"value": False}

    # Fake DynamoDB update wrapper.
    def fake_update_document_in_dynamodb_if_enabled(document_id, updates):
        # Mark update called.
        dynamodb_update_called["value"] = True

        # Confirm correct update.
        assert updates["status"] == "indexed"

        # Return fake success.
        return {
            "dynamodb_write_status": "success",
            "dynamodb_error_message": None,
        }

    # Replace DynamoDB get.
    monkeypatch.setattr(
        metadata_service,
        "get_document_from_dynamodb_if_enabled",
        fake_get_document_from_dynamodb_if_enabled,
    )

    # Replace DynamoDB update.
    monkeypatch.setattr(
        metadata_service,
        "update_document_in_dynamodb_if_enabled",
        fake_update_document_in_dynamodb_if_enabled,
    )

    # Update metadata.
    result = metadata_service.update_document_metadata(
        document_id="doc_update_001",
        updates={
            "status": "indexed",
            "vector_count": 10,
        },
    )

    # Confirm update result.
    assert result is not None
    assert result["status"] == "indexed"
    assert result["vector_count"] == 10

    # Confirm DynamoDB update was called.
    assert dynamodb_update_called["value"] is True

    # Confirm local backup was updated.
    saved_documents = json.loads(documents_file.read_text(encoding="utf-8"))

    # Check local backup status.
    assert saved_documents[0]["status"] == "indexed"

    # Check local backup vector count.
    assert saved_documents[0]["vector_count"] == 10