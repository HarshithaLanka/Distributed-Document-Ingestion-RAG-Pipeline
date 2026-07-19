"""
Evaluation metrics for the Document Intelligence RAG pipeline.

Week 15 metrics currently implemented:

1. Precision@k
2. Recall@k
3. Citation accuracy
4. Citation coverage
"""
import re

from collections.abc import Sequence
from collections.abc import Sequence


def remove_duplicates_preserve_order(
    values: Sequence[str],
) -> list[str]:
    """
    Remove duplicate string values while preserving their order.

    Example:
        ["chunk_001", "chunk_001", "chunk_002"]

    Returns:
        ["chunk_001", "chunk_002"]
    """

    seen: set[str] = set()
    unique_values: list[str] = []

    for value in values:
        cleaned_value = str(value).strip()

        # Ignore blank chunk IDs.
        if not cleaned_value:
            continue

        if cleaned_value not in seen:
            seen.add(cleaned_value)
            unique_values.append(cleaned_value)

    return unique_values


def normalize_page_numbers(
    pages: Sequence[int | str],
) -> list[int]:
    """
    Convert page values into unique integer page numbers.

    This supports page values such as:

        [1, 2, 2]
        ["1", "2"]
        [1, "2"]

    Invalid, blank, boolean, and negative values are ignored.

    Page zero is allowed because some systems may use
    zero-based page numbering.
    """

    seen: set[int] = set()
    normalized_pages: list[int] = []

    for page in pages:
        # Python treats True and False as integers.
        # We do not want them interpreted as page 1 or page 0.
        if isinstance(page, bool):
            continue

        try:
            cleaned_page = str(page).strip()

            if not cleaned_page:
                continue

            page_number = int(cleaned_page)

        except (TypeError, ValueError):
            continue

        # Negative page numbers are invalid.
        if page_number < 0:
            continue

        if page_number not in seen:
            seen.add(page_number)
            normalized_pages.append(page_number)

    return normalized_pages


def calculate_precision_at_k(
    expected_chunk_ids: Sequence[str],
    retrieved_chunk_ids: Sequence[str],
    k: int,
) -> float:
    """
    Calculate Precision@k.

    Precision@k answers:

        Of the chunks retrieved in the top-k results,
        how many were relevant?

    Formula:

        relevant retrieved chunks in top-k
        ----------------------------------
        number of retrieved chunks considered
    """

    if k <= 0:
        raise ValueError("k must be greater than 0.")

    expected_unique = set(
        remove_duplicates_preserve_order(expected_chunk_ids)
    )

    retrieved_unique = remove_duplicates_preserve_order(
        retrieved_chunk_ids
    )

    top_k_results = retrieved_unique[:k]

    if not top_k_results:
        return 0.0

    relevant_retrieved_count = sum(
        1
        for chunk_id in top_k_results
        if chunk_id in expected_unique
    )

    precision = (
        relevant_retrieved_count / len(top_k_results)
    )

    return round(precision, 4)


def calculate_recall_at_k(
    expected_chunk_ids: Sequence[str],
    retrieved_chunk_ids: Sequence[str],
    k: int,
) -> float | None:
    """
    Calculate Recall@k.

    Recall@k answers:

        Of all expected relevant chunks,
        how many appeared in the top-k results?

    Formula:

        expected chunks found in top-k
        ------------------------------
        total expected relevant chunks

    Returns:
        A score between 0.0 and 1.0.

        Returns None when no relevant chunks are expected,
        such as for an unanswerable question.
    """

    if k <= 0:
        raise ValueError("k must be greater than 0.")

    expected_unique = set(
        remove_duplicates_preserve_order(expected_chunk_ids)
    )

    if not expected_unique:
        return None

    retrieved_unique = remove_duplicates_preserve_order(
        retrieved_chunk_ids
    )

    top_k_results = retrieved_unique[:k]
    top_k_set = set(top_k_results)

    relevant_found_count = sum(
        1
        for expected_chunk_id in expected_unique
        if expected_chunk_id in top_k_set
    )

    recall = relevant_found_count / len(expected_unique)

    return round(recall, 4)


def calculate_citation_accuracy(
    expected_pages: Sequence[int | str],
    cited_pages: Sequence[int | str],
) -> float | None:
    """
    Calculate page-based citation accuracy.

    Citation accuracy answers:

        Of all pages cited by the QA system,
        how many were correct expected pages?

    Formula:

        correct cited pages
        -------------------
        total cited pages

    Returns:
        A score between 0.0 and 1.0.

        Returns None when both expected_pages and cited_pages
        are empty. In that situation, citation accuracy is not
        applicable.

    Examples:
        expected_pages = [1]
        cited_pages = [1]
        result = 1.0

        expected_pages = [1]
        cited_pages = [1, 2]
        result = 0.5

        expected_pages = [1]
        cited_pages = []
        result = 0.0
    """

    expected_unique = set(
        normalize_page_numbers(expected_pages)
    )

    cited_unique = normalize_page_numbers(cited_pages)

    # No citations were expected and none were generated.
    if not expected_unique and not cited_unique:
        return None

    # The answer should have citations but returned none.
    if not cited_unique:
        return 0.0

    correct_citation_count = sum(
        1
        for cited_page in cited_unique
        if cited_page in expected_unique
    )

    accuracy = correct_citation_count / len(cited_unique)

    return round(accuracy, 4)


def calculate_citation_coverage(
    expected_pages: Sequence[int | str],
    cited_pages: Sequence[int | str],
) -> float | None:
    """
    Calculate citation coverage.

    Citation coverage answers:

        Of all expected supporting pages,
        how many were successfully cited?

    Formula:

        expected pages found in citations
        ---------------------------------
        total expected pages

    Returns:
        A score between 0.0 and 1.0.

        Returns None when expected_pages is empty because
        there are no required citations to cover.
    """

    expected_unique = set(
        normalize_page_numbers(expected_pages)
    )

    if not expected_unique:
        return None

    cited_unique = set(
        normalize_page_numbers(cited_pages)
    )

    if not cited_unique:
        return 0.0

    covered_page_count = sum(
        1
        for expected_page in expected_unique
        if expected_page in cited_unique
    )

    coverage = covered_page_count / len(expected_unique)

    return round(coverage, 4)

def normalize_text(value: str | None) -> str:
    """
    Normalize text for basic keyword matching.

    The function:

    1. Converts text to lowercase.
    2. Replaces punctuation with spaces.
    3. Removes repeated whitespace.

    Example:
        "Real-Time Operating System!"

    Returns:
        "real time operating system"
    """

    if value is None:
        return ""

    text = str(value).lower()

    # Replace punctuation and special characters with spaces.
    text = re.sub(r"[^a-z0-9]+", " ", text)

    # Replace repeated whitespace with one space.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def keyword_exists_in_text(
    keyword: str,
    text: str,
) -> bool:
    """
    Check whether a keyword or phrase exists in normalized text.

    Matching is case-insensitive and punctuation-insensitive.

    Example:
        keyword = "real-time operating systems"
        text = "Real time operating systems are used..."

    Returns:
        True
    """

    normalized_keyword = normalize_text(keyword)
    normalized_text = normalize_text(text)

    if not normalized_keyword or not normalized_text:
        return False

    return normalized_keyword in normalized_text


def calculate_keyword_coverage(
    expected_keywords: Sequence[str],
    text: str,
) -> float | None:
    """
    Calculate expected-keyword coverage.

    Formula:

        expected keywords found in text
        -------------------------------
        total expected keywords

    This function can be used for either:

    1. Generated-answer keyword coverage.
    2. Retrieved-context keyword coverage.

    Returns:
        Score between 0.0 and 1.0.

        Returns None when expected_keywords is empty.
        This normally happens for unanswerable questions.
    """

    expected_unique = remove_duplicates_preserve_order(
        expected_keywords
    )

    if not expected_unique:
        return None

    matched_keyword_count = sum(
        1
        for keyword in expected_unique
        if keyword_exists_in_text(keyword, text)
    )

    coverage = matched_keyword_count / len(expected_unique)

    return round(coverage, 4)


def calculate_basic_faithfulness(
    expected_keywords: Sequence[str],
    answer_text: str,
    retrieved_contexts: Sequence[str],
) -> float | None:
    """
    Calculate a basic deterministic faithfulness score.

    A keyword is considered grounded when it appears in both:

    1. The generated answer.
    2. The retrieved context.

    Formula:

        answer keywords supported by context
        ------------------------------------
        expected keywords appearing in answer

    Returns:
        Score between 0.0 and 1.0.

        Returns None when expected_keywords is empty.

        Returns 0.0 when expected keywords exist but none
        appear in the generated answer.

    Important:
        This is a simple faithfulness proxy based on keywords.
        It is not a complete factual or semantic evaluation.
    """

    expected_unique = remove_duplicates_preserve_order(
        expected_keywords
    )

    if not expected_unique:
        return None

    combined_context = " ".join(
        str(context)
        for context in retrieved_contexts
        if str(context).strip()
    )

    keywords_in_answer = [
        keyword
        for keyword in expected_unique
        if keyword_exists_in_text(keyword, answer_text)
    ]

    if not keywords_in_answer:
        return 0.0

    grounded_keyword_count = sum(
        1
        for keyword in keywords_in_answer
        if keyword_exists_in_text(keyword, combined_context)
    )

    faithfulness = (
        grounded_keyword_count / len(keywords_in_answer)
    )

    return round(faithfulness, 4)


def normalize_answer_status(status: str | None) -> str:
    """
    Normalize answer-status values.

    Examples:
        "NOT FOUND"  -> "not_found"
        "not-found"  -> "not_found"
        "Found"      -> "found"
    """

    normalized = normalize_text(status)

    return normalized.replace(" ", "_")


def calculate_answer_status_accuracy(
    expected_status: str,
    actual_status: str,
) -> float:
    """
    Check whether one answer status is correct.

    Returns:
        1.0 when expected and actual statuses match.
        0.0 when they do not match.
    """

    expected_normalized = normalize_answer_status(
        expected_status
    )

    actual_normalized = normalize_answer_status(
        actual_status
    )

    if not expected_normalized:
        raise ValueError(
            "expected_status must not be empty."
        )

    if not actual_normalized:
        return 0.0

    return float(
        expected_normalized == actual_normalized
    )


def calculate_unsupported_answer_rate(
    expected_statuses: Sequence[str],
    actual_statuses: Sequence[str],
) -> float | None:
    """
    Calculate unsupported-answer rate.

    This metric only evaluates questions whose expected
    status is 'not_found'.

    An unsupported answer occurs when:

        expected status = not_found
        actual status   = anything other than not_found

    Formula:

        incorrectly answered unanswerable questions
        -------------------------------------------
        total unanswerable questions

    Returns:
        Score between 0.0 and 1.0.

        Returns None when the evaluation set contains no
        unanswerable questions.
    """

    if len(expected_statuses) != len(actual_statuses):
        raise ValueError(
            "expected_statuses and actual_statuses "
            "must have the same length."
        )

    unanswerable_case_count = 0
    unsupported_answer_count = 0

    for expected_status, actual_status in zip(
        expected_statuses,
        actual_statuses,
        strict=True,
    ):
        expected_normalized = normalize_answer_status(
            expected_status
        )

        actual_normalized = normalize_answer_status(
            actual_status
        )

        if expected_normalized != "not_found":
            continue

        unanswerable_case_count += 1

        if actual_normalized != "not_found":
            unsupported_answer_count += 1

    if unanswerable_case_count == 0:
        return None

    unsupported_rate = (
        unsupported_answer_count / unanswerable_case_count
    )

    return round(unsupported_rate, 4)