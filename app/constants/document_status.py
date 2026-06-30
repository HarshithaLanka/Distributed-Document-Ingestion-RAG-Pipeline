# app/constants/document_status.py

"""
This file keeps all document statuses and event names in one place.

Why this file is useful:
- We avoid typing random strings like "indexed", "Indexing", "completed" in many files.
- If status names are centralized, the worker, routes, tests, and metadata all stay consistent.
"""


# These are the main document statuses used in the pipeline.
class DocumentStatus:
    # PDF was uploaded but may not be queued yet.
    UPLOADED = "uploaded"

    # PDF upload completed and message was sent to SQS.
    QUEUED = "queued"

    # Worker picked the document from SQS.
    PROCESSING = "processing"

    # Worker is extracting text from the PDF.
    EXTRACTING = "extracting"

    # Text extraction finished.
    EXTRACTED = "extracted"

    # Worker is splitting extracted text into chunks.
    CHUNKING = "chunking"

    # Chunking finished.
    CHUNKED = "chunked"

    # Worker is creating embeddings and saving vectors to Pinecone.
    INDEXING = "indexing"

    # Pinecone indexing finished.
    INDEXED = "indexed"

    # Full document pipeline finished successfully.
    COMPLETED = "completed"

    # Something failed during processing.
    FAILED = "failed"

    # Upload worked, but queue sending failed.
    QUEUE_FAILED = "queue_failed"

    # Worker skipped this document because it was already completed/indexed.
    SKIPPED = "skipped"


# These statuses mean we should not process the same document again.
TERMINAL_SUCCESS_STATUSES = {
    DocumentStatus.INDEXED,
    DocumentStatus.COMPLETED,
}


# These statuses mean the document processing ended in some way.
TERMINAL_STATUSES = {
    DocumentStatus.INDEXED,
    DocumentStatus.COMPLETED,
    DocumentStatus.FAILED,
    DocumentStatus.QUEUE_FAILED,
    DocumentStatus.SKIPPED,
}


# These are human-readable processing steps.
class ProcessingStep:
    UPLOADED = "PDF uploaded"
    QUEUED = "Document queued for background processing"
    PROCESSING = "Worker picked the document"
    EXTRACTING = "Extracting text from PDF"
    EXTRACTED = "Text extraction completed"
    CHUNKING = "Creating page-aware chunks"
    CHUNKED = "Chunking completed"
    INDEXING = "Indexing chunks into Pinecone"
    INDEXED = "Vector indexing completed"
    COMPLETED = "Document processing completed"
    FAILED = "Document processing failed"
    SKIPPED = "Document already processed, skipping duplicate message"


# These are event names stored in the event table.
class DocumentEventType:
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_QUEUED = "DOCUMENT_QUEUED"

    PROCESSING_STARTED = "PROCESSING_STARTED"

    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"

    CHUNKING_STARTED = "CHUNKING_STARTED"
    CHUNKING_COMPLETED = "CHUNKING_COMPLETED"

    INDEXING_STARTED = "INDEXING_STARTED"
    INDEXING_COMPLETED = "INDEXING_COMPLETED"

    DOCUMENT_COMPLETED = "DOCUMENT_COMPLETED"
    DOCUMENT_FAILED = "DOCUMENT_FAILED"

    DOCUMENT_SKIPPED = "DOCUMENT_SKIPPED"


# This maps status to progress percentage.
# The frontend or Swagger can show this like a progress bar later.
STATUS_PROGRESS = {
    DocumentStatus.UPLOADED: 5,
    DocumentStatus.QUEUED: 10,
    DocumentStatus.PROCESSING: 20,
    DocumentStatus.EXTRACTING: 35,
    DocumentStatus.EXTRACTED: 50,
    DocumentStatus.CHUNKING: 60,
    DocumentStatus.CHUNKED: 70,
    DocumentStatus.INDEXING: 85,
    DocumentStatus.INDEXED: 95,
    DocumentStatus.COMPLETED: 100,
    DocumentStatus.FAILED: 100,
    DocumentStatus.QUEUE_FAILED: 100,
    DocumentStatus.SKIPPED: 100,
}


def get_progress_for_status(status: str) -> int:
    """
    Return progress percentage for a given status.

    Example:
    status = "indexing"
    returns 85
    """

    return STATUS_PROGRESS.get(status, 0)