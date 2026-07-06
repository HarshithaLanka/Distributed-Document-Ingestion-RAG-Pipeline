# app/services/qa_service.py

# Import re so we can detect question patterns safely using regular expressions.
import re

# Import json so we can read chunks.json or redacted_chunks.json from local storage.
import json

# Import Path so we can safely build file paths on Windows, Mac, or Linux.
from pathlib import Path

# Import List so we can type hint lists of chunks and citations.
from typing import List

# Import Dict so we can type hint dictionaries.
from typing import Dict

# Import Any because Pinecone search results may contain different fields.
from typing import Any

# Import QARequest and QAResponse models.
from app.models.qa_models import QARequest, QAResponse

# Import Citation model.
from app.models.qa_models import Citation

# Import embedding function so we can convert text into a vector.
from app.services.embedding_service import generate_embedding

# Import Pinecone search function.
from app.services.pinecone_service import search_vectors

# Import Ollama answer generation function.
from app.services.llm_service import generate_answer_from_ollama

# Import JSON parser for LLM response.
from app.services.llm_service import parse_llm_json_response

# Import PII redaction so QA never returns raw emails/phones/SSNs.
from app.services.pii_redaction_service import redact_text


# This finds the root folder of your project.
# Example:
# app/services/qa_service.py -> project root is two levels above app/services.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# This is the exact fallback answer for not-found cases.
NOT_FOUND_ANSWER = "I could not find this information in the document."


# These are the only answer statuses we allow in the final API response.
ALLOWED_ANSWER_STATUSES = ["found", "partial", "not_found"]


# This helper safely redacts any text before sending it to the LLM or user.
def get_redacted_text(text: str) -> str:
    """
    Redact sensitive values from text.

    Actual meaning:
    Even if raw text accidentally comes from Pinecone or chunks.json,
    this function hides emails, phone numbers, and SSN-like values.
    """

    # Redact the text using Week 11 redaction service.
    result = redact_text(text or "")

    # Return only the safe redacted text.
    return result["redacted_text"]


# These patterns usually mean the user wants a summary.
SUMMARY_PATTERNS = [
    r"\bsummarize\b",
    r"\bsummary\b",
    r"\bwhat is this document about\b",
    r"\bwhat is the document about\b",
    r"\bwhat is .* about\b",
    r"\bwhat does this document say\b",
    r"\bkey points\b",
    r"\bmain points\b",
    r"\boverview\b",
    r"\bbrief\b",
]


# These patterns usually mean the user wants judgment, evaluation, or opinion from evidence.
JUDGMENT_PATTERNS = [
    r"\bis .* good\b",
    r"\bis .* strong\b",
    r"\bis .* weak\b",
    r"\bgood profile\b",
    r"\bstrong profile\b",
    r"\bweak profile\b",
    r"\bsuitable\b",
    r"\bfit for\b",
    r"\beligible\b",
    r"\bevaluate\b",
    r"\bassess\b",
    r"\bchances\b",
    r"\bstrengths?\b",
    r"\bweaknesses?\b",
    r"\bbetter\b",
    r"\bbest\b",
    r"\brisk\b",
    r"\bconcern\b",
    r"\bquality\b",
]


# These words usually appear in important document-level summary sections.
# This is generic and not specific to one document type.
SUMMARY_ANCHOR_KEYWORDS = [
    "abstract",
    "introduction",
    "overview",
    "purpose",
    "objective",
    "problem statement",
    "proposed system",
    "scope",
    "executive summary",
    "summary",
    "conclusion",
    "future scope",
    "background",
]


# These words usually mean the user is asking about people, names, authors,
# students, guides, professors, team members, or document creators.
IDENTITY_KEYWORDS = [
    "who",
    "name",
    "author",
    "writer",
    "professor",
    "teacher",
    "guide",
    "mentor",
    "submitted by",
    "prepared by",
    "written by",
    "created by",
    "student",
    "students",
    "team",
    "team mate",
    "team mates",
    "teammate",
    "teammates",
    "member",
    "members",
    "group member",
    "group members",
    "project member",
    "project members",
]


# These words usually mean the user is asking about skills, tools,
# programming languages, technologies, frameworks, or databases.
SKILL_TECH_KEYWORDS = [
    "skill",
    "skills",
    "technical skill",
    "technical skills",
    "technology",
    "technologies",
    "programming language",
    "programming languages",
    "language",
    "languages",
    "tool",
    "tools",
    "framework",
    "frameworks",
    "library",
    "libraries",
    "database",
    "databases",
    "frontend",
    "backend",
    "web technology",
    "web technologies",
    "version control",
    "core subjects",
    "technical stack",
    "tech stack",
]


# These are common words that do not help exact keyword matching.
# Example:
# "Explain about FixMyMill Project she mentioned"
# Useful word is "FixMyMill", not "explain", "about", "project", "she", "mentioned".
STOPWORDS = {
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "the",
    "a",
    "an",
    "about",
    "explain",
    "tell",
    "me",
    "mentioned",
    "mention",
    "from",
    "in",
    "this",
    "that",
    "these",
    "those",
    "document",
    "pdf",
    "project",
    "she",
    "he",
    "they",
    "it",
    "her",
    "his",
    "their",
    "of",
    "for",
    "to",
    "and",
    "or",
    "with",
    "did",
    "does",
    "do",
    "know",
    "give",
    "briefly",
    "list",
    "show",
    "details",
    "detail",
}


# This function decides what type of question the user asked.
def detect_question_type(question: str) -> str:
    """
    Detect whether the question is:
    - direct_factual
    - summary
    - evidence_based_judgment
    """

    # Convert the question to lowercase so pattern matching is easier.
    lower_question = question.lower().strip()

    # First check if the user is asking for a summary.
    for pattern in SUMMARY_PATTERNS:
        # If the question matches a summary pattern, return summary.
        if re.search(pattern, lower_question):
            return "summary"

    # Then check if the user is asking for judgment or evaluation.
    for pattern in JUDGMENT_PATTERNS:
        # If the question matches a judgment pattern, return evidence-based judgment.
        if re.search(pattern, lower_question):
            return "evidence_based_judgment"

    # Otherwise, treat it as a direct factual question.
    return "direct_factual"


# This function checks whether the user is asking for names, people, authors,
# team members, students, guides, or other identity information.
def is_identity_or_people_question(question: str) -> bool:
    # Convert question to lowercase for easier matching.
    lower_question = question.lower()

    # Return True if any people-related keyword appears in the question.
    return any(keyword in lower_question for keyword in IDENTITY_KEYWORDS)


# This function checks whether the user is asking about skills,
# programming languages, tools, technologies, frameworks, or databases.
def is_skill_or_technology_question(question: str) -> bool:
    # Convert question to lowercase for easier matching.
    lower_question = question.lower()

    # Return True if any skill/technology keyword appears in the question.
    return any(keyword in lower_question for keyword in SKILL_TECH_KEYWORDS)


# This function extracts important words from the user's question.
# This is used for lexical fallback.
# Example:
# "Explain about FixMyMill Project she mentioned"
# becomes:
# ["fixmymill"]
def extract_important_keywords(question: str) -> List[str]:
    # Find words that may contain letters, numbers, dot, hash, plus, colon, underscore, or hyphen.
    words = re.findall(r"[A-Za-z0-9.#:+_-]+", question)

    # Create an empty list to store useful keywords.
    keywords = []

    # Loop through every extracted word.
    for word in words:
        # Convert the word to lowercase.
        cleaned_word = word.lower().strip()

        # Skip very short words because they are usually not helpful.
        if len(cleaned_word) < 3:
            continue

        # Skip common words that do not help retrieval.
        if cleaned_word in STOPWORDS:
            continue

        # Add useful keyword.
        keywords.append(cleaned_word)

    # Remove duplicates while preserving order.
    unique_keywords = list(dict.fromkeys(keywords))

    # Return final keyword list.
    return unique_keywords


# This function extracts exact reference phrases from the question.
# This is important for questions like:
# "What is Week 6 plan?"
# "What is Chapter 3 about?"
# "Explain Section 2.1"
# We want to match "week 6" exactly, not loose words like "week" and "6".
def extract_exact_reference_phrases(question: str) -> List[str]:
    # Convert question to lowercase.
    lower_question = question.lower()

    # These patterns capture common structured references inside documents.
    reference_patterns = [
        r"\bweek\s+\d+\b",
        r"\bday\s+\d+\b",
        r"\bchapter\s+\d+\b",
        r"\bsection\s+\d+(?:\.\d+)*\b",
        r"\bclause\s+\d+(?:\.\d+)*\b",
        r"\bpage\s+\d+\b",
        r"\bpart\s+\d+\b",
        r"\bmodule\s+\d+\b",
        r"\bunit\s+\d+\b",
    ]

    # Create an empty list for extracted phrases.
    phrases = []

    # Loop through each regex pattern.
    for pattern in reference_patterns:
        # Find all matching exact phrases.
        matches = re.findall(pattern, lower_question)

        # Add every match to the phrases list.
        for match in matches:
            phrases.append(match.strip())

    # Remove duplicates while preserving order.
    unique_phrases = list(dict.fromkeys(phrases))

    # Return exact reference phrases.
    return unique_phrases


# This function builds a better search query for Pinecone.
# The original user question is still used for final answering.
# This rewritten query is only used for retrieval/search.
def build_retrieval_query(question: str, question_type: str) -> str:
    # For direct factual questions, usually use the original question.
    if question_type == "direct_factual":
        # If the question asks about identity/name/team info, add helpful retrieval words.
        if is_identity_or_people_question(question):
            # These words help retrieve title pages, submitted-by sections, and headers.
            return (
                question
                + " name title author writer professor teacher guide mentor "
                + "submitted by prepared by written by created by "
                + "student students team members project members group members "
                + "cover page title page header"
            )

        # If the question asks about skills/technologies/languages,
        # add retrieval words commonly used in resumes and technical documents.
        if is_skill_or_technology_question(question):
            return (
                question
                + " skills technical skills technologies programming languages "
                + "web technologies frontend backend tools frameworks libraries "
                + "database databases version control implementation technology "
                + "core subjects tech stack"
            )

        # If it is not a special direct factual question, return the original question.
        return question

    # For summary questions, add general document-level terms.
    if question_type == "summary":
        # These terms help Pinecone retrieve chunks about document purpose and key points.
        summary_terms = (
            " main topic purpose overview key points important details "
            "document summary introduction abstract conclusion proposed system"
        )

        # Return original question plus summary-related terms.
        return question + summary_terms

    # For judgment questions, add evidence-related terms.
    if question_type == "evidence_based_judgment":
        # These terms help Pinecone retrieve evidence for evaluation questions.
        judgment_terms = (
            " evidence strengths weaknesses performance quality suitability "
            "skills achievements risks concerns results outcomes recommendation"
        )

        # Return original question plus judgment-related terms.
        return question + judgment_terms

    # Fallback to original question.
    return question


# This function creates a short preview for citations.
def create_source_preview(text: str, max_chars: int = 220) -> str:
    # First redact sensitive information.
    safe_text = get_redacted_text(text)

    # Replace line breaks and extra spaces with single spaces.
    cleaned_text = " ".join(safe_text.split())

    # If the text is already short, return it fully.
    if len(cleaned_text) <= max_chars:
        return cleaned_text

    # Otherwise, return only the first max_chars characters.
    return cleaned_text[:max_chars] + "..."


# This function converts Pinecone matches into clean chunk dictionaries.
def normalize_pinecone_matches(matches: List[Any]) -> List[Dict[str, Any]]:
    # Create an empty list to store cleaned chunks.
    cleaned_chunks = []

    # Loop through each match returned by Pinecone.
    for match in matches:
        # If match is a dictionary, get metadata using dictionary access.
        if isinstance(match, dict):
            metadata = match.get("metadata", {})
            score = match.get("score", 0.0)

        # If match is an object, get metadata using object access.
        else:
            metadata = getattr(match, "metadata", {})
            score = getattr(match, "score", 0.0)

        # Get source text from metadata.
        source_text = metadata.get("source_text", "")

        # Some older search functions may return text as "text" instead of "source_text".
        if not source_text and isinstance(match, dict):
            source_text = match.get("text", "")

        # Skip empty chunks because empty text cannot help answer the question.
        if not source_text.strip():
            continue

        # Redact source text before it enters QA flow.
        safe_source_text = get_redacted_text(source_text)

        # Create one cleaned chunk dictionary.
        cleaned_chunk = {
            # Store chunk ID.
            "chunk_id": metadata.get("chunk_id", ""),

            # Store page number.
            "page_number": int(metadata.get("page_number", 0)),

            # Store word count.
            "word_count": int(metadata.get("word_count", 0)),

            # Store safe redacted source text.
            "source_text": safe_source_text,

            # Store Pinecone similarity score.
            "score": float(score),
        }

        # Add the cleaned chunk to the final list.
        cleaned_chunks.append(cleaned_chunk)

    # Return all cleaned chunks.
    return cleaned_chunks


# This function filters chunks using a minimum score.
def filter_chunks_by_score(
    chunks: List[Dict[str, Any]],
    min_score: float,
) -> List[Dict[str, Any]]:
    # Keep only chunks whose score is greater than or equal to min_score.
    return [chunk for chunk in chunks if chunk["score"] >= min_score]


# This function loads chunks from local storage.
# Week 11 important change:
# Prefer redacted_chunks.json first.
# If only chunks.json exists, redact text in memory before using it.
def load_local_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Load local chunks safely.

    Actual meaning:
    QA fallback should not read raw chunks.json directly if redacted_chunks.json exists.

    Priority:
    1. uploads/{document_id}/redacted_chunks.json
    2. uploads/{document_id}/chunks.json with in-memory redaction
    """

    # Build document upload folder path.
    document_folder = PROJECT_ROOT / "uploads" / document_id

    # Build path to redacted chunks.
    redacted_chunks_path = document_folder / "redacted_chunks.json"

    # Build path to original chunks.
    chunks_path = document_folder / "chunks.json"

    # Prefer redacted_chunks.json.
    if redacted_chunks_path.exists():
        selected_path = redacted_chunks_path

    # If redacted file does not exist, use chunks.json.
    elif chunks_path.exists():
        selected_path = chunks_path

    # If neither file exists, return empty list.
    else:
        return []

    # Open selected chunks file.
    with open(selected_path, "r", encoding="utf-8") as file:
        chunks_data = json.load(file)

    # Some projects save chunks.json as a list.
    # Some projects save chunks.json as {"chunks": [...]}.
    if isinstance(chunks_data, dict):
        chunks_data = chunks_data.get("chunks", [])

    # If the loaded data is not a list, return safely.
    if not isinstance(chunks_data, list):
        return []

    # Create an empty list to store normalized chunks.
    normalized_chunks = []

    # Loop through every chunk.
    for chunk in chunks_data:
        # Skip invalid chunk objects.
        if not isinstance(chunk, dict):
            continue

        # Get chunk text safely.
        source_text = chunk.get("text", "")

        # Some formats may store the text as source_text.
        if not source_text:
            source_text = chunk.get("source_text", "")

        # Skip empty chunks.
        if not source_text.strip():
            continue

        # Always redact again as final safety.
        safe_source_text = get_redacted_text(source_text)

        # Convert local chunk format into Pinecone-like format.
        normalized_chunk = {
            # Store chunk ID.
            "chunk_id": chunk.get("chunk_id", ""),

            # Store page number.
            "page_number": int(chunk.get("page_number", 0)),

            # Store word count.
            "word_count": int(chunk.get("word_count", 0)),

            # Store safe chunk text.
            "source_text": safe_source_text,

            # Use 1.0 because local anchor chunks are intentionally selected.
            # This is not a Pinecone similarity score.
            "score": 1.0,
        }

        # Add this chunk.
        normalized_chunks.append(normalized_chunk)

    # Return all safe local chunks.
    return normalized_chunks


# This function checks whether a chunk looks like a table of contents.
# Table of contents chunks list headings/page numbers but do not explain the real content.
def is_table_of_contents_chunk(text: str) -> bool:
    # Convert text to lowercase for easier checking.
    lower_text = text.lower()

    # These words usually appear in table of contents pages.
    toc_signals = [
        "chapter no",
        "title page no",
        "page no",
        "table of contents",
        "contents",
    ]

    # Count how many table-of-contents signals appear in the text.
    signal_count = sum(1 for signal in toc_signals if signal in lower_text)

    # If multiple TOC signals appear, treat this as table of contents.
    if signal_count >= 2:
        return True

    # If the text contains many numbered section headings, it may be TOC.
    section_heading_count = len(re.findall(r"\b\d+\.\d+\b", lower_text))

    # If many section numbers appear, it is probably a contents/index chunk.
    if section_heading_count >= 5:
        return True

    # Otherwise, it is not a table of contents chunk.
    return False


# This function gives priority points to chunks that are useful for document summaries.
def calculate_summary_anchor_score(
    chunk: Dict[str, Any],
    max_page_number: int,
) -> int:
    # Start with zero points.
    score = 0

    # Get page number from the chunk.
    page_number = chunk.get("page_number", 0)

    # Get source text from the chunk.
    source_text = chunk.get("source_text", "")

    # Convert text to lowercase for keyword matching.
    lower_text = source_text.lower()

    # If this chunk looks like table of contents, do not use it as a summary anchor.
    if is_table_of_contents_chunk(source_text):
        return 0

    # Page 1 usually contains title and document identity.
    if page_number == 1:
        score += 8

    # Pages 2 and 3 usually contain certificate/declaration/author/guide/institution details.
    if 2 <= page_number <= 3:
        score += 4

    # Early pages usually contain abstract/introduction/problem/proposed system.
    if 4 <= page_number <= 12:
        score += 3

    # Last few pages usually contain conclusion/future scope.
    if max_page_number > 0 and page_number >= max_page_number - 3:
        score += 3

    # Strongly prioritize abstract because it usually summarizes the whole document.
    if "abstract" in lower_text:
        score += 8

    # Strongly prioritize introduction and overview.
    if "introduction" in lower_text or "overview" in lower_text:
        score += 6

    # Prioritize problem statement and proposed system.
    if "problem statement" in lower_text or "proposed system" in lower_text:
        score += 6

    # Prioritize conclusion and future scope.
    if "conclusion" in lower_text or "future scope" in lower_text:
        score += 5

    # Add smaller points for other generic summary-related words.
    for keyword in SUMMARY_ANCHOR_KEYWORDS:
        if keyword in lower_text:
            score += 2

    # Return final anchor score.
    return score


# This function selects important chunks for summary questions.
def get_summary_anchor_chunks(
    document_id: str,
    max_anchor_chunks: int = 3,
) -> List[Dict[str, Any]]:
    # Load all safe local chunks.
    local_chunks = load_local_chunks(document_id)

    # If no local chunks are available, return empty list.
    if not local_chunks:
        return []

    # Find the highest page number in this document.
    max_page_number = max(chunk.get("page_number", 0) for chunk in local_chunks)

    # Create a list to store chunks with their anchor scores.
    scored_chunks = []

    # Loop through each local chunk.
    for chunk in local_chunks:
        # Calculate how useful this chunk is for a document-level summary.
        anchor_score = calculate_summary_anchor_score(
            chunk=chunk,
            max_page_number=max_page_number,
        )

        # Keep only chunks that received some score.
        if anchor_score > 0:
            scored_chunks.append((anchor_score, chunk))

    # Sort chunks by anchor score descending.
    # If scores are same, earlier pages come first.
    scored_chunks.sort(
        key=lambda item: (-item[0], item[1].get("page_number", 0))
    )

    # Take only the best few anchor chunks.
    selected_chunks = [item[1] for item in scored_chunks[:max_anchor_chunks]]

    # Return selected anchor chunks.
    return selected_chunks


# This function selects first-page/header chunks for identity questions.
# Names and team members are usually present in title page, cover page, or certificate page.
def get_identity_anchor_chunks(
    document_id: str,
    max_anchor_chunks: int = 3,
) -> List[Dict[str, Any]]:
    # Load all safe local chunks.
    local_chunks = load_local_chunks(document_id)

    # If no local chunks are available, return empty list.
    if not local_chunks:
        return []

    # Create empty list for selected identity chunks.
    selected_chunks = []

    # Loop through chunks in page order.
    for chunk in local_chunks:
        # Get page number safely.
        page_number = chunk.get("page_number", 0)

        # Get source text safely.
        source_text = chunk.get("source_text", "")

        # Avoid table of contents chunks.
        if is_table_of_contents_chunk(source_text):
            continue

        # First 3 pages usually contain submitted by, authors, guide, institution, certificate.
        if page_number <= 3:
            selected_chunks.append(chunk)

        # Stop after enough anchor chunks.
        if len(selected_chunks) >= max_anchor_chunks:
            break

    # Return selected identity anchor chunks.
    return selected_chunks


# This function selects chunks that are likely to contain skills, technologies,
# programming languages, tools, frameworks, or databases.
def get_skill_technology_anchor_chunks(
    document_id: str,
    max_anchor_chunks: int = 3,
) -> List[Dict[str, Any]]:
    # Load all safe local chunks.
    local_chunks = load_local_chunks(document_id)

    # If no local chunks are available, return empty list.
    if not local_chunks:
        return []

    # Create an empty list to store scored chunks.
    scored_chunks = []

    # Loop through local chunks.
    for chunk in local_chunks:
        # Get source text safely.
        source_text = chunk.get("source_text", "")

        # Convert text to lowercase.
        lower_text = source_text.lower()

        # Skip table of contents chunks.
        if is_table_of_contents_chunk(source_text):
            continue

        # Start score from zero.
        score = 0

        # First two pages are important for resumes because skills are often near the top.
        if chunk.get("page_number", 0) <= 2:
            score += 3

        # Give points for skill/technology keywords.
        for keyword in SKILL_TECH_KEYWORDS:
            if keyword in lower_text:
                score += 4

        # Extra section words that commonly appear in resumes and technical reports.
        section_words = [
            "skills",
            "web technologies",
            "database",
            "version control",
            "languages",
            "implementation",
            "technology",
            "software requirements",
            "dependencies",
            "core subjects",
            "tools",
            "frameworks",
            "libraries",
        ]

        # Give extra points for section headings.
        for word in section_words:
            if word in lower_text:
                score += 5

        # Keep only useful chunks.
        if score > 0:
            scored_chunks.append((score, chunk))

    # Sort by score descending, then earlier pages first.
    scored_chunks.sort(
        key=lambda item: (-item[0], item[1].get("page_number", 0))
    )

    # Return top selected chunks.
    return [item[1] for item in scored_chunks[:max_anchor_chunks]]


# This function searches local chunks using exact keyword overlap.
# This is the lexical fallback.
# It helps find exact names, company names, project names, IDs, tools, and technical terms
# that vector search may miss.
def get_keyword_overlap_chunks(
    document_id: str,
    question: str,
    max_keyword_chunks: int = 3,
) -> List[Dict[str, Any]]:
    # Load safe chunks from local storage.
    local_chunks = load_local_chunks(document_id)

    # If no local chunks exist, return empty list.
    if not local_chunks:
        return []

    # Extract important keywords from the question.
    keywords = extract_important_keywords(question)

    # Extract exact structured phrases like "week 6", "chapter 3", "section 2.1".
    exact_phrases = extract_exact_reference_phrases(question)

    # If no useful keywords and no exact phrases exist, return empty list.
    if not keywords and not exact_phrases:
        return []

    # First pass: strongly prefer exact phrase matches.
    exact_scored_chunks = []

    # Second pass: normal keyword overlap fallback.
    keyword_scored_chunks = []

    # Loop through every local chunk.
    for chunk in local_chunks:
        # Get source text.
        source_text = chunk.get("source_text", "")

        # Skip table of contents chunks.
        if is_table_of_contents_chunk(source_text):
            continue

        # Convert chunk text to lowercase.
        lower_text = source_text.lower()

        # Count exact phrase matches like "week 6".
        exact_phrase_matches = sum(
            1 for phrase in exact_phrases if phrase in lower_text
        )

        # Count normal keyword matches like "fixmymill".
        overlap_count = sum(
            1 for keyword in keywords if keyword in lower_text
        )

        # Give small boost to early pages because resumes/reports often put important info early.
        early_page_boost = 1 if chunk.get("page_number", 0) <= 3 else 0

        # If exact phrase matched, store in exact phrase list with strong score.
        if exact_phrase_matches > 0:
            score = (exact_phrase_matches * 20) + overlap_count + early_page_boost
            exact_scored_chunks.append((score, chunk))
            continue

        # If no exact phrase matched but keyword matched, store as normal fallback.
        if overlap_count > 0:
            score = overlap_count + early_page_boost
            keyword_scored_chunks.append((score, chunk))

    # If exact phrase matches exist, use only them first.
    # This prevents "Week 6" questions from accidentally using "Day 6" chunks.
    if exact_scored_chunks:
        exact_scored_chunks.sort(
            key=lambda item: (-item[0], item[1].get("page_number", 0))
        )
        return [item[1] for item in exact_scored_chunks[:max_keyword_chunks]]

    # Otherwise, use normal keyword overlap chunks.
    keyword_scored_chunks.sort(
        key=lambda item: (-item[0], item[1].get("page_number", 0))
    )

    # Return top keyword-matched chunks.
    return [item[1] for item in keyword_scored_chunks[:max_keyword_chunks]]


# This function merges anchor chunks and Pinecone chunks without duplicates.
def merge_and_deduplicate_chunks(
    first_chunks: List[Dict[str, Any]],
    second_chunks: List[Dict[str, Any]],
    max_total_chunks: int = 5,
) -> List[Dict[str, Any]]:
    # Create empty list for final chunks.
    merged_chunks = []

    # Create set to remember chunk IDs already added.
    seen_chunk_ids = set()

    # Loop through anchor chunks first, then Pinecone chunks.
    for chunk in first_chunks + second_chunks:
        # Get chunk id.
        chunk_id = chunk.get("chunk_id", "")

        # Skip chunks without chunk id.
        if not chunk_id:
            continue

        # Skip duplicate chunk ids.
        if chunk_id in seen_chunk_ids:
            continue

        # Add chunk to final list.
        merged_chunks.append(chunk)

        # Mark this chunk id as already added.
        seen_chunk_ids.add(chunk_id)

        # Stop if we reached maximum allowed chunks.
        if len(merged_chunks) >= max_total_chunks:
            break

    # Return merged chunks.
    return merged_chunks


# This function shortens long chunk text before sending it to Ollama.
# This prevents local Ollama models from timing out on very large prompts.
def limit_chunk_text(text: str, max_chars: int = 1200) -> str:
    # Clean extra spaces and line breaks.
    cleaned_text = " ".join(text.split())

    # If text is already short, return it as it is.
    if len(cleaned_text) <= max_chars:
        return cleaned_text

    # Otherwise, return only the first part.
    return cleaned_text[:max_chars] + "..."


# This function builds the context text that goes into the RAG prompt.
def build_context_text(chunks: List[Dict[str, Any]]) -> str:
    # Create an empty list to store formatted context blocks.
    context_blocks = []

    # Loop through each retrieved chunk.
    for chunk in chunks:
        # Redact again before sending context to Ollama.
        safe_source_text = get_redacted_text(chunk["source_text"])

        # Shorten the chunk text before sending it to Ollama.
        limited_source_text = limit_chunk_text(
            text=safe_source_text,
            max_chars=1200,
        )

        # Format the chunk with chunk ID, page number, score, and shortened source text.
        block = (
            f"[chunk_id: {chunk['chunk_id']} | "
            f"page: {chunk['page_number']} | "
            f"score: {chunk['score']:.4f}]\n"
            f"{limited_source_text}"
        )

        # Add this formatted block to the context list.
        context_blocks.append(block)

    # Join all context blocks with a visible separator.
    return "\n\n---\n\n".join(context_blocks)


# This function builds a document-agnostic RAG prompt for Ollama.
def build_rag_prompt(question: str, context_text: str, question_type: str) -> str:
    # This prompt works for any normal readable PDF, not only LOR documents.
    return f"""
You are a document-grounded question answering assistant.

Your job:
Answer the user's question using ONLY the provided document context.

Very important rules:
1. Do NOT use outside knowledge.
2. Do NOT guess missing facts.
3. Do NOT invent names, dates, numbers, scores, subjects, organizations, locations, laws, products, or achievements.
4. Do not infer relationships such as "on behalf of", "employed by", "approved by", "admitted to", or "affiliated with" unless the document clearly states them.
5. Preserve exact wording for important facts such as names, titles, dates, numbers, laws, policies, products, organizations, and technical terms.
6. Do not shorten or rewrite technical terms unless the document itself uses the shorter form.
7. Use complete sentences.
8. If the question asks "Who is X?", explain who X is based only on the document.
9. If the question asks who the team members, students, authors, or submitted-by people are, use the names exactly as shown in the document context.
10. If the question asks about skills, programming languages, technologies, tools, frameworks, databases, frontend, backend, or version control, answer only from the provided context.
11. If the question asks about a specific week, day, chapter, section, clause, page, part, module, or unit, answer from that exact referenced section if present in the context.
12. If the question asks what the document is about, summarize the main purpose of the document.
13. For summary questions, prioritize title, abstract, introduction, overview, problem statement, proposed system, conclusion, and future scope if these are present in the context.
14. Use the smallest number of chunks needed to support the answer.
15. Use only chunk IDs that directly support the answer.
16. If the answer is not clearly supported by the context, return answer_status as "not_found".
17. Return valid JSON only. Do not return markdown.
18. If the context contains placeholders such as [EMAIL_REDACTED], [PHONE_REDACTED], or [SSN_REDACTED], use the placeholder exactly. Do not try to reconstruct the original sensitive value.

Question type:
{question_type}

How to answer direct factual questions:
- Answer only if the fact is clearly present in the context.
- Give a complete answer, not just one word or one name.
- Use exact details from the document.
- If the exact fact is not present, return answer_status as "not_found".

How to answer summary questions:
- Summarize the document or section using only the provided context.
- Do not add outside assumptions.
- Mention the main topic, purpose, and key points if available.
- Prefer high-level document sections such as title, abstract, introduction, overview, proposed system, and conclusion.
- Use only directly relevant chunk IDs.
- If the provided context is not enough to summarize, return answer_status as "partial".

How to answer evidence-based judgment questions:
- You may make a cautious judgment using evidence from the context.
- Start the answer with "Based on the document,"
- Mention the evidence used.
- Mention limitations if the document does not provide enough information.
- Do not claim anything beyond the document.

Required JSON format:
{{
  "answer": "final answer here",
  "used_chunk_ids": ["chunk_id_1"],
  "answer_status": "found"
}}

Allowed answer_status values:
- "found" means the document directly supports the answer.
- "partial" means the document gives some evidence but not enough for a complete answer.
- "not_found" means the information is not available in the document.

Document context:
{context_text}

User question:
{question}
""".strip()


# This function checks whether the LLM answer is basically saying "not found".
def is_not_found_answer(answer: str) -> bool:
    # Convert answer to lowercase so checking is easier.
    lower_answer = answer.lower()

    # These phrases usually mean the model could not find the answer.
    not_found_phrases = [
        "could not find",
        "not found",
        "not available",
        "does not mention",
        "not mentioned",
        "no information",
        "cannot determine",
        "not enough information",
    ]

    # Return True if any not-found phrase appears in the answer.
    return any(phrase in lower_answer for phrase in not_found_phrases)


# This function creates citations only for the chunks used by the LLM.
def build_citations(
    chunks: List[Dict[str, Any]],
    used_chunk_ids: List[str],
    question_type: str,
) -> List[Citation]:
    # Create a dictionary so we can quickly find chunks by chunk_id.
    chunk_map = {chunk["chunk_id"]: chunk for chunk in chunks}

    # Create an empty list for final citations.
    citations = []

    # Create a set so duplicate chunk IDs do not create duplicate citations.
    seen_chunk_ids = set()

    # For direct factual questions, keep only first 2 used chunks.
    if question_type == "direct_factual":
        used_chunk_ids = used_chunk_ids[:2]

    # For summary questions, allow more citations because summary may need multiple chunks.
    if question_type == "summary":
        used_chunk_ids = used_chunk_ids[:4]

    # For judgment questions, allow a few citations because judgment may need multiple evidence points.
    if question_type == "evidence_based_judgment":
        used_chunk_ids = used_chunk_ids[:4]

    # Loop through each chunk ID used by the model.
    for chunk_id in used_chunk_ids:
        # Skip duplicate chunk IDs.
        if chunk_id in seen_chunk_ids:
            continue

        # Skip chunk IDs that are not present in retrieved chunks.
        if chunk_id not in chunk_map:
            continue

        # Get the matching chunk.
        chunk = chunk_map[chunk_id]

        # Create one citation object.
        citation = Citation(
            chunk_id=chunk["chunk_id"],
            page_number=chunk["page_number"],
            score=chunk["score"],
            source_preview=create_source_preview(chunk["source_text"]),
        )

        # Add citation to final list.
        citations.append(citation)

        # Mark this chunk ID as already used.
        seen_chunk_ids.add(chunk_id)

    # Return clean citations.
    return citations


# This function creates a not-found response.
def create_not_found_response(question_type: str) -> QAResponse:
    # Return a standard not-found response with no citations.
    return QAResponse(
        answer=NOT_FOUND_ANSWER,
        citations=[],
        answer_status="not_found",
        question_type=question_type,
    )


# This function chooses the min_score based on question type and question wording.
def get_effective_min_score(
    question_type: str,
    requested_min_score: float,
    question: str,
) -> float:
    # If direct factual question asks identity/name/team-related info,
    # allow lower threshold because names often appear in headers or first pages.
    if question_type == "direct_factual" and is_identity_or_people_question(question):
        return min(requested_min_score, 0.25)

    # If direct factual question asks skill/technology-related info,
    # allow lower threshold because skills may appear as short bullet points.
    if question_type == "direct_factual" and is_skill_or_technology_question(question):
        return min(requested_min_score, 0.25)

    # If question has exact references like Week 6 or Chapter 3,
    # allow lower vector threshold because lexical fallback will handle exact matching.
    if extract_exact_reference_phrases(question):
        return min(requested_min_score, 0.25)

    # Other direct factual questions stay stricter.
    if question_type == "direct_factual":
        return requested_min_score

    # Summary questions are broad, so allow lower similarity.
    if question_type == "summary":
        return min(requested_min_score, 0.25)

    # Judgment questions are broad, so allow lower similarity.
    if question_type == "evidence_based_judgment":
        return min(requested_min_score, 0.25)

    # Fallback to requested min_score.
    return requested_min_score


# This function safely validates answer_status from the LLM.
def normalize_answer_status(answer_status: str) -> str:
    # If LLM returns a valid status, keep it.
    if answer_status in ALLOWED_ANSWER_STATUSES:
        return answer_status

    # Otherwise, treat it as not_found for safety.
    return "not_found"


# This is the main service function used by the /qa route.
def answer_question(request: QARequest) -> QAResponse:
    # Detect the type of user question.
    question_type = detect_question_type(request.question)

    # Build a better retrieval query.
    retrieval_query = build_retrieval_query(
        question=request.question,
        question_type=question_type,
    )

    # Convert the retrieval query into an embedding vector.
    question_embedding = generate_embedding(retrieval_query)

    # Search Pinecone for similar chunks inside this document.
    pinecone_matches = search_vectors(
        query_embedding=question_embedding,
        document_id=request.document_id,
        top_k=request.top_k,
    )

    # Convert Pinecone matches into clean safe dictionaries.
    chunks = normalize_pinecone_matches(pinecone_matches)

    # Choose min_score based on question type.
    effective_min_score = get_effective_min_score(
        question_type=question_type,
        requested_min_score=request.min_score,
        question=request.question,
    )

    # Filter Pinecone chunks using the effective min_score.
    filtered_chunks = filter_chunks_by_score(
        chunks=chunks,
        min_score=effective_min_score,
    )

    # For summary questions, add important document-level chunks from local storage.
    if question_type == "summary":
        # Get important summary anchor chunks from local storage.
        summary_anchor_chunks = get_summary_anchor_chunks(
            document_id=request.document_id,
            max_anchor_chunks=3,
        )

        # Merge summary anchor chunks first, then Pinecone chunks.
        filtered_chunks = merge_and_deduplicate_chunks(
            first_chunks=summary_anchor_chunks,
            second_chunks=filtered_chunks,
            max_total_chunks=5,
        )

    # For direct factual people/name/team questions, add first-page/header chunks.
    if question_type == "direct_factual" and is_identity_or_people_question(request.question):
        # Get cover/header chunks from local storage.
        identity_anchor_chunks = get_identity_anchor_chunks(
            document_id=request.document_id,
            max_anchor_chunks=3,
        )

        # Merge identity anchor chunks first, then Pinecone chunks.
        filtered_chunks = merge_and_deduplicate_chunks(
            first_chunks=identity_anchor_chunks,
            second_chunks=filtered_chunks,
            max_total_chunks=5,
        )

    # For direct factual skill/technology questions, add skills/technology chunks.
    if question_type == "direct_factual" and is_skill_or_technology_question(request.question):
        # Get skills/technology chunks from local storage.
        skill_technology_anchor_chunks = get_skill_technology_anchor_chunks(
            document_id=request.document_id,
            max_anchor_chunks=3,
        )

        # Merge skill/technology chunks first, then Pinecone chunks.
        filtered_chunks = merge_and_deduplicate_chunks(
            first_chunks=skill_technology_anchor_chunks,
            second_chunks=filtered_chunks,
            max_total_chunks=5,
        )

    # Generic lexical fallback.
    # This helps exact names and references like:
    # FixMyMill, YOLOv8, TastyThreads, Week 6, Chapter 3, Section 2.1, invoice numbers, policy names.
    keyword_overlap_chunks = get_keyword_overlap_chunks(
        document_id=request.document_id,
        question=request.question,
        max_keyword_chunks=3,
    )

    # Merge keyword chunks first, then existing filtered chunks.
    filtered_chunks = merge_and_deduplicate_chunks(
        first_chunks=keyword_overlap_chunks,
        second_chunks=filtered_chunks,
        max_total_chunks=5,
    )

    # If no chunks are available after filtering/anchor/keyword merge, return not found.
    if not filtered_chunks:
        return create_not_found_response(question_type)

    # Build context text from filtered chunks.
    # This context is redacted before going to Ollama.
    context_text = build_context_text(filtered_chunks)

    # Build the final RAG prompt.
    prompt = build_rag_prompt(
        question=request.question,
        context_text=context_text,
        question_type=question_type,
    )

    # Send the prompt to Ollama.
    raw_llm_response = generate_answer_from_ollama(prompt)

    # Parse the LLM response as JSON.
    llm_data = parse_llm_json_response(raw_llm_response)

    # Get the answer from the parsed LLM JSON.
    answer = llm_data.get("answer", NOT_FOUND_ANSWER).strip()

    # Redact final answer immediately.
    safe_answer = get_redacted_text(answer)

    # Get chunk IDs that the LLM says it used.
    used_chunk_ids = llm_data.get("used_chunk_ids", [])

    # Get answer status from the LLM and normalize it.
    answer_status = normalize_answer_status(
        llm_data.get("answer_status", "not_found")
    )

    # If the model says not found, return clean not-found response.
    if answer_status == "not_found":
        return create_not_found_response(question_type)

    # If the answer text itself looks like not-found, return clean not-found response.
    if is_not_found_answer(safe_answer):
        return create_not_found_response(question_type)

    # If the model did not provide used chunk IDs, do not trust the answer.
    if not used_chunk_ids:
        return create_not_found_response(question_type)

    # For direct factual questions, do not allow partial answers.
    if question_type == "direct_factual" and answer_status == "partial":
        return create_not_found_response(question_type)

    # Build clean citations only from chunks used by the model.
    # Citation previews are redacted inside create_source_preview().
    citations = build_citations(
        chunks=filtered_chunks,
        used_chunk_ids=used_chunk_ids,
        question_type=question_type,
    )

    # If no valid citations remain, return not found because answer has no evidence.
    if not citations:
        return create_not_found_response(question_type)

    # Return final safe answer with citations.
    return QAResponse(
        answer=safe_answer,
        citations=citations,
        answer_status=answer_status,
        question_type=question_type,
    )
