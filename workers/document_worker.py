# Import sys so this worker can import app modules from the project root.
import sys

# Import Path to safely work with project folder paths.
from pathlib import Path

# Import load_dotenv so this worker can read values from .env.
from dotenv import load_dotenv


# Current file:
# workers/document_worker.py
#
# PROJECT_ROOT becomes:
# C:/Users/Harshitha/Documents/Document_Intelligence_RAG
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Add project root to Python path.
# This allows imports like:
# from app.services.sqs_service import ...
sys.path.append(str(PROJECT_ROOT))


# Load .env before importing app services.
# This is important because app.config reads environment variables during import.
load_dotenv(PROJECT_ROOT / ".env")


# Import config flag to check whether S3 upload is enabled.
from app.config import S3_UPLOAD_ENABLED  # noqa: E402

# Import SQS functions.
# receive_document_processing_messages reads jobs from SQS.
# delete_message removes the SQS message after the full job succeeds.
from app.services.sqs_service import receive_document_processing_messages  # noqa: E402
from app.services.sqs_service import delete_message  # noqa: E402

# Import metadata functions.
# get_document_by_id reads metadata from DynamoDB/local cache.
# update_document_metadata updates document status and artifact paths.
from app.services.metadata_service import get_document_by_id  # noqa: E402
from app.services.metadata_service import update_document_metadata  # noqa: E402

# Import artifact resolver functions.
# These make sure files exist locally.
# If local files are missing, they can recover/download from S3.
from app.services.artifact_resolver_service import ensure_pdf_available_locally  # noqa: E402
from app.services.artifact_resolver_service import ensure_extracted_text_available_locally  # noqa: E402
from app.services.artifact_resolver_service import ensure_chunks_available_locally  # noqa: E402

# Import PDF extraction service.
# This creates extracted_text.json from uploaded PDF.
from app.services.pdf_parser_service import extract_text_from_pdf  # noqa: E402

# Import chunking service.
# create_chunks_from_extracted_text creates chunks.json.
# load_chunks reads chunks.json before indexing.
from app.services.chunking_service import create_chunks_from_extracted_text  # noqa: E402
from app.services.chunking_service import load_chunks  # noqa: E402

# Import Pinecone indexing service.
# This creates embeddings and stores vectors in Pinecone.
from app.services.pinecone_service import index_document_chunks  # noqa: E402

# Import S3 upload functions for artifacts.
from app.services.s3_service import upload_extracted_text_to_s3  # noqa: E402
from app.services.s3_service import upload_chunks_to_s3  # noqa: E402
from app.services.s3_service import S3ServiceError  # noqa: E402


def extract_document_in_worker(document_id: str, document: dict) -> dict:
    """
    Run extraction inside the worker.

    Simple meaning:
    This function takes document_id, finds the PDF, extracts text,
    saves extracted_text.json, uploads it to S3, and updates metadata.

    Returns:
    Latest document metadata after extraction.
    """

    print("\n========== EXTRACTION STEP STARTED ==========")

    # Update status to extracting.
    update_document_metadata(
        document_id,
        {
            "status": "extracting",
            "error_message": None,
        }
    )

    # Make sure PDF exists locally.
    # If local PDF is missing, this can recover it from S3.
    pdf_path = ensure_pdf_available_locally(document)

    print("PDF available locally at:", pdf_path)

    # Extract page-wise text from PDF.
    extraction_result = extract_text_from_pdf(
        pdf_path,
        document_id,
    )

    print("Extraction completed.")
    print("Page count:", extraction_result["page_count"])
    print("Extracted text path:", extraction_result["extracted_text_path"])

    # Default S3 values for extracted_text.json.
    extracted_text_s3_bucket = None
    extracted_text_s3_key = None
    extracted_text_s3_uri = None
    extracted_text_s3_upload_status = "disabled"
    extracted_text_s3_error_message = None

    # Upload extracted_text.json to S3 if enabled.
    if S3_UPLOAD_ENABLED:
        try:
            print("Uploading extracted_text.json to S3...")

            extracted_s3_result = upload_extracted_text_to_s3(
                local_file_path=extraction_result["extracted_text_path"],
                document_id=document_id,
            )

            extracted_text_s3_bucket = extracted_s3_result["bucket"]
            extracted_text_s3_key = extracted_s3_result["s3_key"]
            extracted_text_s3_uri = extracted_s3_result["s3_uri"]
            extracted_text_s3_upload_status = "success"

            print("Extracted text uploaded to S3.")
            print("Extracted text S3 key:", extracted_text_s3_key)

        except S3ServiceError as error:
            # Extraction succeeded locally, but S3 artifact upload failed.
            extracted_text_s3_upload_status = "failed"
            extracted_text_s3_error_message = str(error)

            print("WARNING: extracted_text.json S3 upload failed.")
            print("Error:", str(error))

    # Update metadata after extraction.
    update_document_metadata(
        document_id,
        {
            "status": "extracted",
            "page_count": extraction_result["page_count"],
            "extracted_text_path": extraction_result["extracted_text_path"],
            "extracted_text_s3_bucket": extracted_text_s3_bucket,
            "extracted_text_s3_key": extracted_text_s3_key,
            "extracted_text_s3_uri": extracted_text_s3_uri,
            "extracted_text_s3_upload_status": extracted_text_s3_upload_status,
            "extracted_text_s3_error_message": extracted_text_s3_error_message,
            "error_message": None,
        }
    )

    print("========== EXTRACTION STEP COMPLETED ==========")

    # Return latest metadata.
    return get_document_by_id(document_id)


def chunk_document_in_worker(document_id: str, document: dict) -> dict:
    """
    Run chunking inside the worker.

    Simple meaning:
    This function uses extracted_text.json, creates chunks.json,
    uploads chunks.json to S3, and updates metadata.

    Returns:
    Latest document metadata after chunking.
    """

    print("\n========== CHUNKING STEP STARTED ==========")

    # Chunking cannot happen without extracted text.
    if document.get("extracted_text_path") is None:
        raise RuntimeError(
            "Cannot chunk document because extracted_text_path is missing."
        )

    # Update status to chunking.
    update_document_metadata(
        document_id,
        {
            "status": "chunking",
            "error_message": None,
        }
    )

    # IMPORTANT:
    # Your resolver expects document_id, not the full document dictionary.
    extracted_text_path = ensure_extracted_text_available_locally(document_id)

    print("Extracted text available locally at:", extracted_text_path)

    # Create chunks from extracted_text.json.
    chunking_result = create_chunks_from_extracted_text(
        extracted_text_path=str(extracted_text_path),
        document_id=document_id,
        chunk_size=150,
        overlap=30,
    )

    print("Chunking completed.")
    print("Chunk count:", chunking_result["chunk_count"])
    print("Chunks path:", chunking_result["chunks_path"])

    # Default S3 values for chunks.json.
    chunks_s3_bucket = None
    chunks_s3_key = None
    chunks_s3_uri = None
    chunks_s3_upload_status = "disabled"
    chunks_s3_error_message = None

    # Upload chunks.json to S3 if enabled.
    if S3_UPLOAD_ENABLED:
        try:
            print("Uploading chunks.json to S3...")

            chunks_s3_result = upload_chunks_to_s3(
                local_file_path=chunking_result["chunks_path"],
                document_id=document_id,
            )

            chunks_s3_bucket = chunks_s3_result["bucket"]
            chunks_s3_key = chunks_s3_result["s3_key"]
            chunks_s3_uri = chunks_s3_result["s3_uri"]
            chunks_s3_upload_status = "success"

            print("Chunks uploaded to S3.")
            print("Chunks S3 key:", chunks_s3_key)

        except S3ServiceError as error:
            # Chunking succeeded locally, but S3 artifact upload failed.
            chunks_s3_upload_status = "failed"
            chunks_s3_error_message = str(error)

            print("WARNING: chunks.json S3 upload failed.")
            print("Error:", str(error))

    # Update metadata after chunking.
    update_document_metadata(
        document_id,
        {
            "status": "chunked",
            "chunk_count": chunking_result["chunk_count"],
            "chunks_path": chunking_result["chunks_path"],
            "chunks_s3_bucket": chunks_s3_bucket,
            "chunks_s3_key": chunks_s3_key,
            "chunks_s3_uri": chunks_s3_uri,
            "chunks_s3_upload_status": chunks_s3_upload_status,
            "chunks_s3_error_message": chunks_s3_error_message,
            "error_message": None,
        }
    )

    print("========== CHUNKING STEP COMPLETED ==========")

    # Return latest metadata.
    return get_document_by_id(document_id)


def index_document_in_worker(document_id: str, document: dict) -> dict:
    """
    Run Pinecone indexing inside the worker.

    Simple meaning:
    This function loads chunks.json, creates embeddings,
    stores vectors in Pinecone, and updates metadata.

    Returns:
    Latest document metadata after indexing.
    """

    print("\n========== INDEXING STEP STARTED ==========")

    # Indexing cannot happen without chunks.
    if document.get("chunks_path") is None:
        raise RuntimeError(
            "Cannot index document because chunks_path is missing."
        )

    # Update status to indexing.
    update_document_metadata(
        document_id,
        {
            "status": "indexing",
            "error_message": None,
        }
    )

    # Make sure chunks.json exists locally.
    # If local chunks.json is missing, this can recover it from S3.
    chunks_path = ensure_chunks_available_locally(document_id)

    print("Chunks available locally at:", chunks_path)

    # Load chunks from chunks.json.
    chunks_data = load_chunks(str(chunks_path))

    print("Loaded chunks.")
    print("Chunk count:", chunks_data.get("chunk_count"))

    # Create embeddings and store vectors in Pinecone.
    indexing_result = index_document_chunks(chunks_data)

    print("Indexing completed.")
    print("Vector count:", indexing_result["vector_count"])

    # Update metadata after indexing.
    update_document_metadata(
        document_id,
        {
            "status": "indexed",
            "vector_count": indexing_result["vector_count"],
            "error_message": None,
        }
    )

    print("========== INDEXING STEP COMPLETED ==========")

    # Return latest metadata.
    return get_document_by_id(document_id)


def process_one_sqs_message():
    """
    Process one SQS message.

    Current full worker behavior:
    - If status is queued/uploaded: extract -> chunk -> index.
    - If status is extracted: chunk -> index.
    - If status is chunked: index.
    - If status is indexed: delete SQS message.

    Important:
    SQS message is deleted ONLY after indexing succeeds.
    """

    print("Starting Document Worker")
    print("Reading one message from SQS...")

    # Receive one message from SQS.
    messages = receive_document_processing_messages(max_messages=1)

    # If no message exists, stop cleanly.
    if not messages:
        print("No messages found in SQS queue.")
        print("Upload a PDF in Swagger or wait for visibility timeout.")
        return

    # Get first SQS message.
    message = messages[0]

    # Get receipt handle.
    # This is required to delete the message after successful processing.
    receipt_handle = message.get("receipt_handle")

    # Get message body.
    body = message.get("body", {})

    # Extract job details from SQS message.
    document_id = body.get("document_id")
    job_type = body.get("job_type")
    pipeline_steps = body.get("pipeline_steps")

    print("\nSQS message received.")
    print("SQS Message ID:", message.get("message_id"))
    print("Job Type:", job_type)
    print("Document ID:", document_id)
    print("Pipeline Steps:", pipeline_steps)

    # Validate document_id.
    if not document_id:
        print("ERROR: document_id missing in SQS message.")
        return

    # Fetch metadata from DynamoDB/local cache.
    document = get_document_by_id(document_id)

    # Stop if metadata does not exist.
    if document is None:
        print("ERROR: Document metadata not found.")
        print("document_id:", document_id)
        return

    # Read current status.
    current_status = document.get("status")

    print("\nDocument metadata found.")
    print("Filename:", document.get("filename"))
    print("Current Status:", current_status)

    try:
        # If document is newly queued/uploaded, run extraction first.
        if current_status in ["queued", "uploaded"]:
            print("\nStatus is queued/uploaded.")
            print("Worker will run extraction first.")

            document = extract_document_in_worker(document_id, document)
            current_status = document.get("status")

        # If document is extracted, run chunking.
        if current_status == "extracted":
            print("\nStatus is extracted.")
            print("Worker will run chunking now.")

            document = chunk_document_in_worker(document_id, document)
            current_status = document.get("status")

        # If document is chunked, run indexing.
        if current_status == "chunked":
            print("\nStatus is chunked.")
            print("Worker will run indexing now.")

            document = index_document_in_worker(document_id, document)
            current_status = document.get("status")

        # If document is indexed, full job is complete.
        if current_status == "indexed":
            print("\nDocument indexed successfully.")
            print("Now deleting SQS message because full job is complete.")

            delete_result = delete_message(receipt_handle)

            print(delete_result.get("message"))
            print("SQS message deleted successfully.")

        else:
            print("\nWorker stopped with status:", current_status)
            print("SQS message was NOT deleted because job is not fully complete.")

        print("\nWorker finished successfully.")

    except Exception as error:
        # If any worker step fails, mark document failed.
        update_document_metadata(
            document_id,
            {
                "status": "failed",
                "error_message": str(error),
            }
        )

        print("\nERROR: Worker failed.")
        print("Document ID:", document_id)
        print("Error:", str(error))

        print("\nSQS message was NOT deleted.")
        print("After visibility timeout, SQS can retry this job.")


# Run this only when executing the file directly.
if __name__ == "__main__":
    process_one_sqs_message()