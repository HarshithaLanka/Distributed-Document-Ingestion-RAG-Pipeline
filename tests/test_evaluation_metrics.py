"""
Tests for Week 15 RAG evaluation metrics.
"""

import pytest

from evaluation.metrics import (
    calculate_precision_at_k,
    remove_duplicates_preserve_order,
)
from evaluation.metrics import (
    calculate_precision_at_k,
    calculate_recall_at_k,
    remove_duplicates_preserve_order,
)

from evaluation.metrics import (
    calculate_answer_status_accuracy,
    calculate_basic_faithfulness,
    calculate_citation_accuracy,
    calculate_citation_coverage,
    calculate_keyword_coverage,
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_unsupported_answer_rate,
    keyword_exists_in_text,
    normalize_answer_status,
    normalize_page_numbers,
    normalize_text,
    remove_duplicates_preserve_order,
)
def test_remove_duplicates_preserves_order():
    values = [
        "chunk_001",
        "chunk_002",
        "chunk_001",
        "chunk_003",
    ]

    result = remove_duplicates_preserve_order(values)

    assert result == [
        "chunk_001",
        "chunk_002",
        "chunk_003",
    ]


def test_precision_at_k_when_two_of_five_are_relevant():
    expected_chunk_ids = [
        "chunk_022",
        "chunk_023",
    ]

    retrieved_chunk_ids = [
        "chunk_007",
        "chunk_023",
        "chunk_022",
        "chunk_005",
        "chunk_003",
    ]

    result = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=5,
    )

    assert result == 0.4


def test_precision_at_k_when_all_results_are_relevant():
    expected_chunk_ids = [
        "chunk_001",
        "chunk_002",
        "chunk_003",
    ]

    retrieved_chunk_ids = [
        "chunk_001",
        "chunk_002",
        "chunk_003",
    ]

    result = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    assert result == 1.0


def test_precision_at_k_when_no_results_are_relevant():
    expected_chunk_ids = [
        "chunk_001",
        "chunk_002",
    ]

    retrieved_chunk_ids = [
        "chunk_010",
        "chunk_011",
        "chunk_012",
    ]

    result = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    assert result == 0.0


def test_precision_at_k_with_empty_retrieval_results():
    result = calculate_precision_at_k(
        expected_chunk_ids=["chunk_001"],
        retrieved_chunk_ids=[],
        k=5,
    )

    assert result == 0.0


def test_precision_at_k_uses_only_first_k_results():
    expected_chunk_ids = [
        "chunk_004",
    ]

    retrieved_chunk_ids = [
        "chunk_001",
        "chunk_002",
        "chunk_003",
        "chunk_004",
    ]

    result = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    # chunk_004 is outside the top three.
    assert result == 0.0


def test_precision_at_k_removes_duplicate_retrieval_results():
    expected_chunk_ids = [
        "chunk_001",
    ]

    retrieved_chunk_ids = [
        "chunk_001",
        "chunk_001",
        "chunk_002",
    ]

    result = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    # After duplicate removal:
    # ["chunk_001", "chunk_002"]
    # One of two results is relevant.
    assert result == 0.5


def test_precision_at_k_rejects_zero_k():
    with pytest.raises(ValueError, match="k must be greater than 0"):
        calculate_precision_at_k(
            expected_chunk_ids=["chunk_001"],
            retrieved_chunk_ids=["chunk_001"],
            k=0,
        )


def test_precision_at_k_rejects_negative_k():
    with pytest.raises(ValueError, match="k must be greater than 0"):
        calculate_precision_at_k(
            expected_chunk_ids=["chunk_001"],
            retrieved_chunk_ids=["chunk_001"],
            k=-1,
        )
        
        
        
def test_recall_at_k_when_two_of_four_expected_chunks_are_found():
    expected_chunk_ids = [
        "chunk_026",
        "chunk_027",
        "chunk_038",
        "chunk_039",
    ]

    retrieved_chunk_ids = [
        "chunk_038",
        "chunk_036",
        "chunk_034",
        "chunk_026",
        "chunk_007",
    ]

    result = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=5,
    )

    # Two of four expected chunks were retrieved.
    assert result == 0.5


def test_recall_at_k_when_all_expected_chunks_are_found():
    expected_chunk_ids = [
        "chunk_001",
        "chunk_002",
        "chunk_003",
    ]

    retrieved_chunk_ids = [
        "chunk_003",
        "chunk_001",
        "chunk_002",
        "chunk_020",
    ]

    result = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=4,
    )

    assert result == 1.0


def test_recall_at_k_when_no_expected_chunks_are_found():
    expected_chunk_ids = [
        "chunk_001",
        "chunk_002",
    ]

    retrieved_chunk_ids = [
        "chunk_010",
        "chunk_011",
        "chunk_012",
    ]

    result = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    assert result == 0.0


def test_recall_at_k_uses_only_first_k_results():
    expected_chunk_ids = [
        "chunk_004",
    ]

    retrieved_chunk_ids = [
        "chunk_001",
        "chunk_002",
        "chunk_003",
        "chunk_004",
    ]

    result = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    # chunk_004 exists, but it is outside the top three.
    assert result == 0.0


def test_recall_at_k_removes_duplicate_chunk_ids():
    expected_chunk_ids = [
        "chunk_001",
        "chunk_001",
        "chunk_002",
    ]

    retrieved_chunk_ids = [
        "chunk_001",
        "chunk_001",
        "chunk_002",
    ]

    result = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=3,
    )

    # After duplicate removal, both expected chunks were found.
    assert result == 1.0


def test_recall_at_k_returns_none_when_expected_chunks_are_empty():
    result = calculate_recall_at_k(
        expected_chunk_ids=[],
        retrieved_chunk_ids=[
            "chunk_001",
            "chunk_002",
        ],
        k=5,
    )

    # Recall is not meaningful for an unanswerable question.
    assert result is None


def test_recall_at_k_rejects_zero_k():
    with pytest.raises(
        ValueError,
        match="k must be greater than 0",
    ):
        calculate_recall_at_k(
            expected_chunk_ids=["chunk_001"],
            retrieved_chunk_ids=["chunk_001"],
            k=0,
        )


def test_recall_at_k_rejects_negative_k():
    with pytest.raises(
        ValueError,
        match="k must be greater than 0",
    ):
        calculate_recall_at_k(
            expected_chunk_ids=["chunk_001"],
            retrieved_chunk_ids=["chunk_001"],
            k=-1,
        )
def test_normalize_page_numbers():
    pages = [
        1,
        "2",
        2,
        "3",
        "",
        "invalid",
        -1,
        True,
    ]

    result = normalize_page_numbers(pages)

    assert result == [1, 2, 3]


def test_citation_accuracy_when_all_citations_are_correct():
    result = calculate_citation_accuracy(
        expected_pages=[1, 2],
        cited_pages=[1, 2],
    )

    assert result == 1.0


def test_citation_accuracy_when_one_of_two_citations_is_correct():
    result = calculate_citation_accuracy(
        expected_pages=[1],
        cited_pages=[1, 2],
    )

    assert result == 0.5


def test_citation_accuracy_when_expected_pages_exist_but_no_citations():
    result = calculate_citation_accuracy(
        expected_pages=[1],
        cited_pages=[],
    )

    assert result == 0.0


def test_citation_accuracy_returns_none_when_both_lists_are_empty():
    result = calculate_citation_accuracy(
        expected_pages=[],
        cited_pages=[],
    )

    assert result is None


def test_citation_accuracy_is_zero_for_unexpected_citation():
    result = calculate_citation_accuracy(
        expected_pages=[],
        cited_pages=[5],
    )

    # An unanswerable question should not produce a citation.
    assert result == 0.0


def test_citation_accuracy_removes_duplicate_cited_pages():
    result = calculate_citation_accuracy(
        expected_pages=[1],
        cited_pages=[1, 1, 2],
    )

    # Duplicate page 1 is counted only once.
    # Unique cited pages are [1, 2].
    assert result == 0.5


def test_citation_accuracy_supports_string_page_numbers():
    result = calculate_citation_accuracy(
        expected_pages=["1", "2"],
        cited_pages=[1, "2"],
    )

    assert result == 1.0


def test_citation_coverage_when_one_of_two_expected_pages_is_cited():
    result = calculate_citation_coverage(
        expected_pages=[1, 2],
        cited_pages=[2, 5],
    )

    assert result == 0.5


def test_citation_coverage_when_all_expected_pages_are_cited():
    result = calculate_citation_coverage(
        expected_pages=[1, 2],
        cited_pages=[1, 2, 5],
    )

    # Page 5 is unnecessary, but both required pages were cited.
    assert result == 1.0


def test_citation_coverage_when_no_citations_are_returned():
    result = calculate_citation_coverage(
        expected_pages=[1, 2],
        cited_pages=[],
    )

    assert result == 0.0


def test_citation_coverage_returns_none_without_expected_pages():
    result = calculate_citation_coverage(
        expected_pages=[],
        cited_pages=[],
    )

    assert result is None
    
def test_normalize_text_handles_case_and_punctuation():
    result = normalize_text(
        "Real-Time Operating Systems!"
    )

    assert result == "real time operating systems"


def test_keyword_exists_in_text_ignores_case_and_punctuation():
    result = keyword_exists_in_text(
        keyword="real-time operating systems",
        text=(
            "Real time operating systems are used "
            "for deadline-sensitive applications."
        ),
    )

    assert result is True


def test_keyword_coverage_when_three_of_four_keywords_are_found():
    expected_keywords = [
        "RTOS",
        "deadlines",
        "industrial control",
        "flight control",
    ]

    answer_text = (
        "An RTOS processes events within deadlines. "
        "It is used in flight control."
    )

    result = calculate_keyword_coverage(
        expected_keywords=expected_keywords,
        text=answer_text,
    )

    assert result == 0.75


def test_keyword_coverage_when_no_keywords_are_found():
    result = calculate_keyword_coverage(
        expected_keywords=[
            "RTOS",
            "deadlines",
        ],
        text="This text discusses databases.",
    )

    assert result == 0.0


def test_keyword_coverage_returns_none_without_expected_keywords():
    result = calculate_keyword_coverage(
        expected_keywords=[],
        text="Any answer",
    )

    assert result is None

def test_basic_faithfulness_when_all_answer_keywords_are_grounded():
    expected_keywords = [
        "RTOS",
        "deadlines",
        "industrial control",
    ]

    answer_text = (
        "An RTOS handles deadlines and is used "
        "in industrial control."
    )

    retrieved_contexts = [
        (
            "A real-time operating system, also called an RTOS, "
            "processes events within deadlines."
        ),
        (
            "RTOS applications include industrial control "
            "and flight control."
        ),
    ]

    result = calculate_basic_faithfulness(
        expected_keywords=expected_keywords,
        answer_text=answer_text,
        retrieved_contexts=retrieved_contexts,
    )

    assert result == 1.0


def test_basic_faithfulness_detects_unsupported_answer_keyword():
    expected_keywords = [
        "RTOS",
        "deadlines",
        "annual salary",
    ]

    answer_text = (
        "An RTOS handles deadlines and provides "
        "a high annual salary."
    )

    retrieved_contexts = [
        (
            "An RTOS processes events within "
            "specified deadlines."
        )
    ]

    result = calculate_basic_faithfulness(
        expected_keywords=expected_keywords,
        answer_text=answer_text,
        retrieved_contexts=retrieved_contexts,
    )

    # RTOS and deadlines are grounded.
    # Annual salary is mentioned in the answer but is not
    # supported by the retrieved context.
    assert result == 0.6667


def test_basic_faithfulness_returns_zero_when_answer_has_no_keywords():
    result = calculate_basic_faithfulness(
        expected_keywords=[
            "RTOS",
            "deadlines",
        ],
        answer_text="The document does not explain this.",
        retrieved_contexts=[
            "An RTOS processes events within deadlines."
        ],
    )

    assert result == 0.0


def test_basic_faithfulness_returns_none_without_expected_keywords():
    result = calculate_basic_faithfulness(
        expected_keywords=[],
        answer_text="Answer not found.",
        retrieved_contexts=[],
    )

    assert result is None


def test_normalize_answer_status():
    assert normalize_answer_status("NOT FOUND") == "not_found"
    assert normalize_answer_status("not-found") == "not_found"
    assert normalize_answer_status("Found") == "found"


def test_answer_status_accuracy_when_status_matches():
    result = calculate_answer_status_accuracy(
        expected_status="not_found",
        actual_status="NOT FOUND",
    )

    assert result == 1.0


def test_answer_status_accuracy_when_status_does_not_match():
    result = calculate_answer_status_accuracy(
        expected_status="not_found",
        actual_status="found",
    )

    assert result == 0.0


def test_unsupported_answer_rate():
    expected_statuses = [
        "found",
        "not_found",
        "found",
        "not_found",
    ]

    actual_statuses = [
        "found",
        "found",
        "found",
        "not_found",
    ]

    result = calculate_unsupported_answer_rate(
        expected_statuses=expected_statuses,
        actual_statuses=actual_statuses,
    )

    # Two questions were expected to be not_found.
    # One was incorrectly answered.
    assert result == 0.5


def test_unsupported_answer_rate_is_zero_when_all_are_handled_safely():
    result = calculate_unsupported_answer_rate(
        expected_statuses=[
            "not_found",
            "not_found",
        ],
        actual_statuses=[
            "not_found",
            "NOT FOUND",
        ],
    )

    assert result == 0.0


def test_unsupported_answer_rate_returns_none_without_unanswerable_cases():
    result = calculate_unsupported_answer_rate(
        expected_statuses=[
            "found",
            "found",
        ],
        actual_statuses=[
            "found",
            "not_found",
        ],
    )

    assert result is None


def test_unsupported_answer_rate_rejects_different_list_lengths():
    with pytest.raises(
        ValueError,
        match="must have the same length",
    ):
        calculate_unsupported_answer_rate(
            expected_statuses=[
                "not_found",
                "found",
            ],
            actual_statuses=[
                "found",
            ],
        )