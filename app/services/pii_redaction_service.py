# This file handles PII redaction.
#
# PII means Personally Identifiable Information.
# Examples:
# - email address
# - phone number
# - SSN-like number
#
# Redaction means:
# Replace sensitive values with safe placeholders.
#
# Example:
# john@example.com -> [EMAIL_REDACTED]
#
# Week 11 goal:
# Before sending chunks to Pinecone, create redacted_chunks.json.
# Pinecone should store redacted text, not raw sensitive text.

# Import json to read chunks.json and write redacted_chunks.json.
import json

# Import re for regex pattern matching.
# Regex is used to find emails, phone numbers, and SSN-like values.
import re

# Import Path to safely work with file paths.
from pathlib import Path


# ---------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------

# Email pattern.
# Finds examples like:
# john@example.com
# john.doe@company.co.in
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


# Phone number pattern.
# This is intentionally simple and practical.
# Finds examples like:
# +91 9876543210
# 9876543210
# 214-555-1234
# (214) 555-1234
PHONE_PATTERN = re.compile(
    r"(\+?\d{1,3}[\s-]?)?(\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}|\d{10})"
)


# SSN-like pattern.
# Finds examples like:
# 123-45-6789
#
# This is mainly useful for US-style fake test data.
SSN_PATTERN = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"
)


# ---------------------------------------------------------
# Text redaction helpers
# ---------------------------------------------------------

def redact_pattern(
    text: str,
    pattern: re.Pattern,
    placeholder: str,
    pii_type: str,
) -> tuple[str, int, list[str]]:
    """
    Redact one regex pattern from text.

    Parameters:
    text:
        Original text.

    pattern:
        Regex pattern used to find sensitive values.

    placeholder:
        Replacement text.
        Example: [EMAIL_REDACTED]

    pii_type:
        Type of sensitive value.
        Example: email, phone, ssn

    Returns:
        redacted_text:
            Text after replacement.

        count:
            Number of replacements made.

        types:
            List containing pii_type if redaction happened.
    """

    # Find all matches before replacing.
    matches = pattern.findall(text)

    # Count matches.
    match_count = len(matches)

    # Replace matching values with placeholder.
    redacted_text = pattern.sub(placeholder, text)

    # If at least one match happened, return this PII type.
    redaction_types = [pii_type] if match_count > 0 else []

    # Return redacted text, count, and type list.
    return redacted_text, match_count, redaction_types


def redact_text(text: str) -> dict:
    """
    Redact PII from one text string.

    Input:
        "Email me at john@example.com"

    Output:
        {
            "redacted_text": "Email me at [EMAIL_REDACTED]",
            "redaction_applied": True,
            "redaction_count": 1,
            "redaction_types": ["email"]
        }
    """

    # If text is empty or None, return safe empty result.
    if not text:
        return {
            "redacted_text": "",
            "redaction_applied": False,
            "redaction_count": 0,
            "redaction_types": [],
        }

    # Start with original text.
    redacted_text = text

    # Track total redactions.
    total_redaction_count = 0

    # Track which PII types were redacted.
    all_redaction_types = []

    # Redact emails.
    redacted_text, count, types = redact_pattern(
        text=redacted_text,
        pattern=EMAIL_PATTERN,
        placeholder="[EMAIL_REDACTED]",
        pii_type="email",
    )

    # Update total count.
    total_redaction_count += count

    # Add types.
    all_redaction_types.extend(types)

    # Redact SSN-like values before phone.
    # Why before phone?
    # SSN has digits too, so we handle the more specific pattern first.
    redacted_text, count, types = redact_pattern(
        text=redacted_text,
        pattern=SSN_PATTERN,
        placeholder="[SSN_REDACTED]",
        pii_type="ssn",
    )

    # Update total count.
    total_redaction_count += count

    # Add types.
    all_redaction_types.extend(types)

    # Redact phone numbers.
    redacted_text, count, types = redact_pattern(
        text=redacted_text,
        pattern=PHONE_PATTERN,
        placeholder="[PHONE_REDACTED]",
        pii_type="phone",
    )

    # Update total count.
    total_redaction_count += count

    # Add types.
    all_redaction_types.extend(types)

    # Remove duplicate types while keeping simple order.
    unique_redaction_types = []

    # Loop through all types found.
    for pii_type in all_redaction_types:
        # Add only if not already present.
        if pii_type not in unique_redaction_types:
            unique_redaction_types.append(pii_type)

    # Return redaction result.
    return {
        "redacted_text": redacted_text,
        "redaction_applied": total_redaction_count > 0,
        "redaction_count": total_redaction_count,
        "redaction_types": unique_redaction_types,
    }


# ---------------------------------------------------------
# Chunk redaction helpers
# ---------------------------------------------------------

def redact_chunk(chunk: dict) -> dict:
    """
    Redact PII from one chunk.

    Input chunk has:
    {
        "chunk_id": "chunk_001",
        "text": "Email: john@example.com"
    }

    Output chunk keeps same metadata but replaces text:
    {
        "chunk_id": "chunk_001",
        "text": "Email: [EMAIL_REDACTED]",
        "redaction_applied": true,
        "redaction_count": 1,
        "redaction_types": ["email"]
    }
    """

    # Copy original chunk so we do not modify the original dictionary directly.
    redacted_chunk = chunk.copy()

    # Get original chunk text.
    original_text = chunk.get("text", "")

    # Redact text.
    redaction_result = redact_text(original_text)

    # Replace chunk text with redacted text.
    # This is important because this text will later go to Pinecone.
    redacted_chunk["text"] = redaction_result["redacted_text"]

    # Add redaction metadata.
    redacted_chunk["redaction_applied"] = redaction_result["redaction_applied"]
    redacted_chunk["redaction_count"] = redaction_result["redaction_count"]
    redacted_chunk["redaction_types"] = redaction_result["redaction_types"]

    # Keep a boolean marker that this chunk has passed privacy processing.
    redacted_chunk["privacy_processed"] = True

    # Return redacted chunk.
    return redacted_chunk


def redact_chunks_data(chunks_data: dict) -> dict:
    """
    Redact PII from loaded chunks.json data.

    Input:
        chunks_data from chunks.json

    Output:
        same structure, but chunks contain redacted text.
    """

    # Get original chunks.
    chunks = chunks_data.get("chunks", [])

    # Create list for redacted chunks.
    redacted_chunks = []

    # Track total redactions across document.
    total_redaction_count = 0

    # Track all PII types found across document.
    document_redaction_types = []

    # Loop through chunks.
    for chunk in chunks:
        # Redact one chunk.
        redacted_chunk = redact_chunk(chunk)

        # Add redacted chunk to list.
        redacted_chunks.append(redacted_chunk)

        # Add chunk redaction count to document total.
        total_redaction_count += redacted_chunk.get("redaction_count", 0)

        # Add chunk redaction types.
        for pii_type in redacted_chunk.get("redaction_types", []):
            if pii_type not in document_redaction_types:
                document_redaction_types.append(pii_type)

    # Copy original chunks_data so we keep document_id, parser_used, etc.
    redacted_chunks_data = chunks_data.copy()

    # Replace chunks with redacted chunks.
    redacted_chunks_data["chunks"] = redacted_chunks

    # Add redaction summary.
    redacted_chunks_data["privacy_processed"] = True
    redacted_chunks_data["redaction_applied"] = total_redaction_count > 0
    redacted_chunks_data["redaction_count"] = total_redaction_count
    redacted_chunks_data["redaction_types"] = document_redaction_types

    # Keep chunk_count accurate.
    redacted_chunks_data["chunk_count"] = len(redacted_chunks)

    # Return redacted chunks data.
    return redacted_chunks_data


def create_redacted_chunks_file(chunks_path: str) -> dict:
    """
    Read chunks.json, redact PII, and write redacted_chunks.json.

    Input:
        uploads/{document_id}/chunks.json

    Output:
        uploads/{document_id}/redacted_chunks.json

    Return:
        {
            "redacted_chunks_path": "...",
            "redaction_count": 3,
            "redaction_types": ["email", "phone"]
        }
    """

    # Convert chunks path to Path object.
    path = Path(chunks_path)

    # Check if chunks.json exists.
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    # Read chunks.json.
    with open(path, "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    # Redact loaded chunks data.
    redacted_chunks_data = redact_chunks_data(chunks_data)

    # Create output path in same folder.
    redacted_chunks_path = path.parent / "redacted_chunks.json"

    # Write redacted_chunks.json.
    with open(redacted_chunks_path, "w", encoding="utf-8") as file:
        json.dump(redacted_chunks_data, file, indent=4, ensure_ascii=False)

    # Return useful summary.
    return {
        "redacted_chunks_path": str(redacted_chunks_path),
        "chunk_count": redacted_chunks_data.get("chunk_count", 0),
        "redaction_applied": redacted_chunks_data.get("redaction_applied", False),
        "redaction_count": redacted_chunks_data.get("redaction_count", 0),
        "redaction_types": redacted_chunks_data.get("redaction_types", []),
    }


def load_redacted_chunks(redacted_chunks_path: str) -> dict:
    """
    Load redacted_chunks.json.

    This will be used later by the worker before sending data to Pinecone.
    """

    # Convert path string to Path object.
    path = Path(redacted_chunks_path)

    # Check if file exists.
    if not path.exists():
        raise FileNotFoundError(f"Redacted chunks file not found: {redacted_chunks_path}")

    # Read redacted_chunks.json.
    with open(path, "r", encoding="utf-8") as file:
        redacted_chunks_data = json.load(file)

    # Return data.
    return redacted_chunks_data