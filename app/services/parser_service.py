# This file is the parser abstraction layer.
#
# Simple meaning:
# The worker should not directly decide:
# - Should I use Docling?
# - Should I use PyMuPDF?
# - Should I fallback?
#
# The worker should simply call:
# parse_document(pdf_path, document_id)
#
# This file decides which parser to use.

# Import parser settings from config.
from app.config import DOCLING_ENABLED
from app.config import PRIMARY_PARSER
from app.config import PARSER_FALLBACK_ENABLED

# Import PyMuPDF parser.
# This is our stable fallback parser.
from app.services.pdf_parser_service import extract_text_from_pdf

# Import logger.
from app.utils.logger import logger


def parse_document(pdf_path: str, document_id: str) -> dict:
    """
    Parse a PDF using configured parser.

    Flow:
    1. If Docling is enabled and primary parser is docling:
       try Docling.
    2. If Docling succeeds:
       return Docling result.
    3. If Docling fails and fallback is enabled:
       use PyMuPDF.
    4. If Docling is disabled:
       use PyMuPDF directly.

    Return format:
    {
        "document_id": "...",
        "parser_used": "docling" or "pymupdf",
        "page_count": 10,
        "extracted_text_path": "..."
    }
    """

    # Check whether we should try Docling first.
    should_try_docling = (
        DOCLING_ENABLED
        and PRIMARY_PARSER == "docling"
    )

    # If Docling is enabled, try it.
    if should_try_docling:
        try:
            # Import Docling parser inside the function.
            # Why?
            # If Docling is not installed and DOCLING_ENABLED=false,
            # the whole app should not crash during import.
            from app.services.docling_parser_service import extract_text_with_docling

            # Log that we are trying Docling.
            logger.info(
                "Trying Docling parser. document_id=%s pdf_path=%s",
                document_id,
                pdf_path,
            )

            # Run Docling parser.
            return extract_text_with_docling(
                pdf_path=pdf_path,
                document_id=document_id,
            )

        except Exception as error:
            # Log Docling error.
            logger.exception(
                "Docling parser failed. document_id=%s error=%s",
                document_id,
                str(error),
            )

            # If fallback is disabled, raise the error.
            if not PARSER_FALLBACK_ENABLED:
                raise

            # Log fallback.
            logger.info(
                "Falling back to PyMuPDF parser. document_id=%s",
                document_id,
            )

    # Use PyMuPDF parser.
    pymupdf_result = extract_text_from_pdf(
        pdf_path,
        document_id,
    )

    # Add parser_used field because old PyMuPDF result may not have it.
    pymupdf_result["parser_used"] = "pymupdf"

    # Return result.
    return pymupdf_result