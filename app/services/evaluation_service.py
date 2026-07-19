"""
Week 15 RAG Evaluation Service.

This service:

1. Loads evaluation/golden_dataset.json.
2. Runs the real hybrid retrieval pipeline.
3. Reranks retrieved candidates.
4. Calculates retrieval metrics.
5. Optionally runs the QA pipeline.
6. Calculates citation and answer-quality metrics.
7. Generates JSON and Markdown reports.

The evaluation continues even if one question fails.
One failed case should not stop the remaining evaluation cases.
"""

# Import json to read the golden dataset and write JSON reports.
import json

# Import datetime so every run has start and completion timestamps.
from datetime import datetime, timezone

# Import Path for Windows-safe and platform-safe paths.
from pathlib import Path

# Import Any because golden dataset values are loaded from JSON.
from typing import Any

# Import uuid4 to create a unique evaluation run ID.
from uuid import uuid4


# Import QA request model.
from app.models.qa_models import QARequest

# Import Week 15 evaluation response models.
from app.models.evaluation_models import (
    EvaluationCaseResult,
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationSummary,
)

# Import Week 14 hybrid retrieval.
from app.services.hybrid_retrieval_service import (
    hybrid_search_document,
)

# Import Week 14 reranking.
from app.services.reranking_service import rerank_candidates

# Import the existing QA service.
from app.services.qa_service import answer_question

# Import all metrics implemented during Week 15.
from evaluation.metrics import (
    calculate_answer_status_accuracy,
    calculate_basic_faithfulness,
    calculate_citation_accuracy,
    calculate_citation_coverage,
    calculate_keyword_coverage,
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_unsupported_answer_rate,
)


# Resolve the project root.
#
# Current file:
# app/services/evaluation_service.py
#
# parents[0] = app/services
# parents[1] = app
# parents[2] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Folder where generated evaluation reports are stored.
REPORTS_DIRECTORY = (
    PROJECT_ROOT
    / "evaluation"
    / "reports"
)


def utc_now_string() -> str:
    """
    Return the current UTC time as an ISO-formatted string.

    Example:
        2026-07-14T10:30:00.123456+00:00
    """

    return datetime.now(timezone.utc).isoformat()


def resolve_project_path(path_value: str) -> Path:
    """
    Convert a relative project path into an absolute path.

    Example:
        evaluation/golden_dataset.json

    Becomes:
        C:/Users/.../Document_Intelligence_RAG/
        evaluation/golden_dataset.json

    Absolute paths are kept unchanged.
    """

    path = Path(path_value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def path_relative_to_project(path: Path) -> str:
    """
    Return a portable project-relative path when possible.

    Example:
        evaluation/reports/evaluation_run_123.json
    """

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_golden_dataset(
    dataset_path: str,
) -> dict[str, Any]:
    """
    Load and validate the golden dataset.

    Required root fields:
        dataset_name
        version
        evaluation_cases

    Required fields for every evaluation case:
        evaluation_id
        document_id
        question
        category
        expected_answer_status
        expected_pages
        expected_chunk_ids
        expected_keywords
        notes
    """

    resolved_path = resolve_project_path(dataset_path)

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Golden dataset not found: {resolved_path}"
        )

    with open(
        resolved_path,
        "r",
        encoding="utf-8",
    ) as dataset_file:
        dataset = json.load(dataset_file)

    if not isinstance(dataset, dict):
        raise ValueError(
            "Golden dataset root must be a JSON object."
        )

    required_root_fields = {
        "dataset_name",
        "version",
        "evaluation_cases",
    }

    missing_root_fields = (
        required_root_fields - set(dataset)
    )

    if missing_root_fields:
        raise ValueError(
            "Golden dataset is missing root fields: "
            + ", ".join(sorted(missing_root_fields))
        )

    evaluation_cases = dataset.get(
        "evaluation_cases",
        [],
    )

    if not isinstance(evaluation_cases, list):
        raise ValueError(
            "evaluation_cases must be a JSON list."
        )

    if not evaluation_cases:
        raise ValueError(
            "Golden dataset contains no evaluation cases."
        )

    required_case_fields = {
        "evaluation_id",
        "document_id",
        "question",
        "category",
        "expected_answer_status",
        "expected_pages",
        "expected_chunk_ids",
        "expected_keywords",
        "notes",
    }

    seen_evaluation_ids: set[str] = set()

    for position, case in enumerate(
        evaluation_cases,
        start=1,
    ):
        if not isinstance(case, dict):
            raise ValueError(
                f"Evaluation case {position} "
                "must be a JSON object."
            )

        missing_case_fields = (
            required_case_fields - set(case)
        )

        if missing_case_fields:
            raise ValueError(
                f"Evaluation case {position} is missing: "
                + ", ".join(
                    sorted(missing_case_fields)
                )
            )

        evaluation_id = str(
            case.get("evaluation_id", "")
        ).strip()

        if not evaluation_id:
            raise ValueError(
                f"Evaluation case {position} "
                "has an empty evaluation_id."
            )

        if evaluation_id in seen_evaluation_ids:
            raise ValueError(
                "Duplicate evaluation_id found: "
                f"{evaluation_id}"
            )

        seen_evaluation_ids.add(evaluation_id)

        if not str(
            case.get("document_id", "")
        ).strip():
            raise ValueError(
                f"{evaluation_id} has an empty document_id."
            )

        if not str(
            case.get("question", "")
        ).strip():
            raise ValueError(
                f"{evaluation_id} has an empty question."
            )

        for list_field in [
            "expected_pages",
            "expected_chunk_ids",
            "expected_keywords",
        ]:
            if not isinstance(
                case.get(list_field),
                list,
            ):
                raise ValueError(
                    f"{evaluation_id}.{list_field} "
                    "must be a list."
                )

    return dataset


def normalize_weights(
    request: EvaluationRunRequest,
) -> tuple[float, float, float]:
    """
    Normalize active retrieval weights so they add up to 1.

    When graph retrieval is disabled, graph weight becomes zero.

    Example:
        vector = 0.6
        keyword = 0.4
        graph = 0.0

    Result:
        0.6, 0.4, 0.0
    """

    active_graph_weight = (
        request.graph_weight
        if request.include_graph
        else 0.0
    )

    total_weight = (
        request.vector_weight
        + request.keyword_weight
        + active_graph_weight
    )

    if total_weight <= 0:
        raise ValueError(
            "At least one active retrieval weight "
            "must be greater than 0."
        )

    return (
        request.vector_weight / total_weight,
        request.keyword_weight / total_weight,
        active_graph_weight / total_weight,
    )


def safe_page_number(
    value: Any,
) -> int | None:
    """
    Convert one page value into an integer safely.

    Invalid values return None.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        page_number = int(value)
    except (TypeError, ValueError):
        return None

    if page_number < 0:
        return None

    return page_number


def unique_page_numbers(
    results: list[dict[str, Any]],
) -> list[int]:
    """
    Extract unique page numbers from retrieved results
    while preserving their retrieval order.
    """

    pages: list[int] = []
    seen: set[int] = set()

    for result in results:
        page_number = safe_page_number(
            result.get("page_number")
        )

        if page_number is None:
            continue

        if page_number not in seen:
            seen.add(page_number)
            pages.append(page_number)

    return pages


def unique_strings(
    values: list[Any],
) -> list[str]:
    """
    Convert values into unique non-empty strings
    while preserving order.
    """

    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned_value = str(value or "").strip()

        if not cleaned_value:
            continue

        if cleaned_value not in seen:
            seen.add(cleaned_value)
            output.append(cleaned_value)

    return output


def extract_citation_values(
    citations: list[Any],
) -> tuple[list[str], list[int]]:
    """
    Extract chunk IDs and page numbers from QA citations.

    Citation items may be:

    - Pydantic Citation objects
    - Dictionaries
    """

    chunk_ids: list[str] = []
    pages: list[int] = []

    for citation in citations:
        if isinstance(citation, dict):
            chunk_id = citation.get("chunk_id")
            page_value = citation.get("page_number")
        else:
            chunk_id = getattr(
                citation,
                "chunk_id",
                None,
            )
            page_value = getattr(
                citation,
                "page_number",
                None,
            )

        if chunk_id:
            chunk_ids.append(str(chunk_id))

        page_number = safe_page_number(page_value)

        if page_number is not None:
            pages.append(page_number)

    return (
        unique_strings(chunk_ids),
        list(dict.fromkeys(pages)),
    )


def average_optional(
    values: list[float | None],
) -> float | None:
    """
    Calculate the average while ignoring None values.

    None means that the metric was not applicable.

    Example:
        Recall is None for an unanswerable question.
    """

    usable_values = [
        float(value)
        for value in values
        if value is not None
    ]

    if not usable_values:
        return None

    return round(
        sum(usable_values) / len(usable_values),
        4,
    )


def create_qa_request(
    document_id: str,
    question: str,
    top_k: int,
) -> QARequest:
    """
    Create a QARequest compatible with the existing QA model.

    The project QA model uses:
        document_id
        question
        top_k
        min_score

    min_score is added only when that field exists.
    """

    request_data: dict[str, Any] = {
        "document_id": document_id,
        "question": question,
        "top_k": top_k,
    }

    # Support the current QARequest model while remaining
    # compatible if min_score is later removed.
    model_fields = getattr(
        QARequest,
        "model_fields",
        {},
    )

    if "min_score" in model_fields:
        request_data["min_score"] = 0.25

    return QARequest(**request_data)


def determine_case_passed(
    expected_status: str,
    recall_at_k: float | None,
    citation_accuracy: float | None,
    answer_status_accuracy: float | None,
    run_qa: bool,
) -> bool:
    """
    Apply a simple and explainable per-case pass rule.

    Answerable question:
        - At least one expected chunk must be retrieved.
        - When QA runs, answer status must be correct.
        - When QA runs, at least one citation must be correct.

    Unanswerable question:
        - When QA runs, the system must return not_found.
        - During retrieval-only evaluation, it is treated as
          not applicable and does not fail.
    """

    normalized_expected_status = (
        str(expected_status)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if normalized_expected_status == "not_found":
        if not run_qa:
            return True

        return answer_status_accuracy == 1.0

    retrieval_passed = (
        recall_at_k is not None
        and recall_at_k > 0.0
    )

    if not run_qa:
        return retrieval_passed

    qa_status_passed = (
        answer_status_accuracy == 1.0
    )

    citation_passed = (
        citation_accuracy is not None
        and citation_accuracy > 0.0
    )

    return (
        retrieval_passed
        and qa_status_passed
        and citation_passed
    )


def evaluate_one_case(
    case: dict[str, Any],
    request: EvaluationRunRequest,
    vector_weight: float,
    keyword_weight: float,
    graph_weight: float,
) -> EvaluationCaseResult:
    """
    Run retrieval, reranking, optional QA, and metrics
    for one golden-dataset question.
    """

    evaluation_id = str(case["evaluation_id"])
    document_id = str(case["document_id"])
    question = str(case["question"])
    category = str(case["category"])

    expected_status = str(
        case["expected_answer_status"]
    )

    expected_pages = [
        int(page)
        for page in case.get(
            "expected_pages",
            [],
        )
        if str(page).strip().isdigit()
    ]

    expected_chunk_ids = unique_strings(
        case.get("expected_chunk_ids", [])
    )

    expected_keywords = unique_strings(
        case.get("expected_keywords", [])
    )

    # -----------------------------------------------------
    # Retrieval and reranking
    # -----------------------------------------------------

    try:
        # Run the same retrieval configuration requested
        # for this evaluation run.
        hybrid_candidates = hybrid_search_document(
            document_id=document_id,
            query=question,
            top_k=request.candidate_top_k,
            vector_top_k=min(
                request.candidate_top_k,
                20,
            ),
            keyword_top_k=min(
                request.candidate_top_k,
                20,
            ),
            graph_top_k=min(
                request.candidate_top_k,
                10,
            ),
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            graph_weight=graph_weight,
            include_graph=request.include_graph,
        )

        # Rerank the candidate pool and keep only top-k results.
        reranked_results = rerank_candidates(
            question=question,
            candidates=hybrid_candidates,
            final_top_k=request.top_k,
        )

    except Exception as error:
        # Retrieval failure for one question should not stop
        # the complete evaluation run.
        return EvaluationCaseResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            question=question,
            category=category,
            top_k=request.top_k,
            expected_chunk_ids=expected_chunk_ids,
            expected_pages=expected_pages,
            expected_keywords=expected_keywords,
            expected_answer_status=expected_status,
            retrieved_chunk_ids=[],
            retrieved_pages=[],
            retrieved_contexts=[],
            precision_at_k=0.0,
            recall_at_k=(
                None
                if not expected_chunk_ids
                else 0.0
            ),
            passed=False,
            error_message=(
                "Retrieval failed: "
                f"{type(error).__name__}: {error}"
            ),
        )

    retrieved_chunk_ids = unique_strings(
        [
            result.get("chunk_id")
            for result in reranked_results
        ]
    )

    retrieved_pages = unique_page_numbers(
        reranked_results
    )

    retrieved_contexts = [
        str(
            result.get("text")
            or result.get("source_text")
            or ""
        )
        for result in reranked_results
        if str(
            result.get("text")
            or result.get("source_text")
            or ""
        ).strip()
    ]

    precision_at_k = calculate_precision_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=request.top_k,
    )

    recall_at_k = calculate_recall_at_k(
        expected_chunk_ids=expected_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=request.top_k,
    )

    context_keyword_coverage = (
        calculate_keyword_coverage(
            expected_keywords=expected_keywords,
            text=" ".join(retrieved_contexts),
        )
    )

    # Default QA values when run_qa is false.
    answer: str | None = None
    actual_answer_status: str | None = None
    cited_chunk_ids: list[str] = []
    cited_pages: list[int] = []

    citation_accuracy: float | None = None
    citation_coverage: float | None = None
    answer_keyword_coverage: float | None = None
    faithfulness_score: float | None = None
    answer_status_accuracy: float | None = None

    error_message: str | None = None

    # -----------------------------------------------------
    # Optional QA and citation evaluation
    # -----------------------------------------------------

    if request.run_qa:
        try:
            qa_request = create_qa_request(
                document_id=document_id,
                question=question,
                top_k=request.top_k,
            )

            # Pass the evaluation retrieval configuration
            # into QA so include_graph=False is respected.
            qa_response = answer_question(
                request=qa_request,
                include_graph=request.include_graph,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                graph_weight=graph_weight,
            )

            answer = str(
                getattr(
                    qa_response,
                    "answer",
                    "",
                )
                or ""
            )

            actual_answer_status = str(
                getattr(
                    qa_response,
                    "answer_status",
                    "",
                )
                or ""
            )

            citations = list(
                getattr(
                    qa_response,
                    "citations",
                    [],
                )
                or []
            )

            (
                cited_chunk_ids,
                cited_pages,
            ) = extract_citation_values(citations)

            citation_accuracy = (
                calculate_citation_accuracy(
                    expected_pages=expected_pages,
                    cited_pages=cited_pages,
                )
            )

            citation_coverage = (
                calculate_citation_coverage(
                    expected_pages=expected_pages,
                    cited_pages=cited_pages,
                )
            )

            answer_keyword_coverage = (
                calculate_keyword_coverage(
                    expected_keywords=expected_keywords,
                    text=answer,
                )
            )

            faithfulness_score = (
                calculate_basic_faithfulness(
                    expected_keywords=expected_keywords,
                    answer_text=answer,
                    retrieved_contexts=retrieved_contexts,
                )
            )

            answer_status_accuracy = (
                calculate_answer_status_accuracy(
                    expected_status=expected_status,
                    actual_status=actual_answer_status,
                )
            )

        except Exception as error:
            error_message = (
                "QA failed: "
                f"{type(error).__name__}: {error}"
            )

    passed = determine_case_passed(
        expected_status=expected_status,
        recall_at_k=recall_at_k,
        citation_accuracy=citation_accuracy,
        answer_status_accuracy=answer_status_accuracy,
        run_qa=request.run_qa,
    )

    # A QA error means the complete case did not pass.
    if error_message:
        passed = False

    return EvaluationCaseResult(
        evaluation_id=evaluation_id,
        document_id=document_id,
        question=question,
        category=category,
        top_k=request.top_k,
        expected_chunk_ids=expected_chunk_ids,
        expected_pages=expected_pages,
        expected_keywords=expected_keywords,
        expected_answer_status=expected_status,
        retrieved_chunk_ids=retrieved_chunk_ids,
        retrieved_pages=retrieved_pages,
        retrieved_contexts=retrieved_contexts,
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
        answer=answer,
        actual_answer_status=actual_answer_status,
        cited_chunk_ids=cited_chunk_ids,
        cited_pages=cited_pages,
        citation_accuracy=citation_accuracy,
        citation_coverage=citation_coverage,
        answer_keyword_coverage=(
            answer_keyword_coverage
        ),
        context_keyword_coverage=(
            context_keyword_coverage
        ),
        faithfulness_score=faithfulness_score,
        answer_status_accuracy=(
            answer_status_accuracy
        ),
        passed=passed,
        error_message=error_message,
    )


def build_evaluation_summary(
    results: list[EvaluationCaseResult],
) -> EvaluationSummary:
    """
    Aggregate all per-question results into one summary.
    """

    total_questions = len(results)

    successful_cases = sum(
        1
        for result in results
        if result.error_message is None
    )

    failed_cases = (
        total_questions - successful_cases
    )

    passed_questions = sum(
        1
        for result in results
        if result.passed
    )

    failed_questions = (
        total_questions - passed_questions
    )

    # Unsupported-answer rate uses only cases where QA
    # produced an actual status.
    status_pairs = [
        (
            result.expected_answer_status,
            result.actual_answer_status,
        )
        for result in results
        if result.actual_answer_status is not None
    ]

    if status_pairs:
        unsupported_answer_rate = (
            calculate_unsupported_answer_rate(
                expected_statuses=[
                    expected
                    for expected, _ in status_pairs
                ],
                actual_statuses=[
                    actual
                    for _, actual in status_pairs
                ],
            )
        )
    else:
        unsupported_answer_rate = None

    return EvaluationSummary(
        total_questions=total_questions,
        successful_cases=successful_cases,
        failed_cases=failed_cases,
        passed_questions=passed_questions,
        failed_questions=failed_questions,
        average_precision_at_k=(
            average_optional(
                [
                    result.precision_at_k
                    for result in results
                ]
            )
            or 0.0
        ),
        average_recall_at_k=average_optional(
            [
                result.recall_at_k
                for result in results
            ]
        ),
        average_citation_accuracy=average_optional(
            [
                result.citation_accuracy
                for result in results
            ]
        ),
        average_citation_coverage=average_optional(
            [
                result.citation_coverage
                for result in results
            ]
        ),
        average_answer_keyword_coverage=(
            average_optional(
                [
                    result.answer_keyword_coverage
                    for result in results
                ]
            )
        ),
        average_context_keyword_coverage=(
            average_optional(
                [
                    result.context_keyword_coverage
                    for result in results
                ]
            )
        ),
        average_faithfulness_score=average_optional(
            [
                result.faithfulness_score
                for result in results
            ]
        ),
        answer_status_accuracy=average_optional(
            [
                result.answer_status_accuracy
                for result in results
            ]
        ),
        unsupported_answer_rate=(
            unsupported_answer_rate
        ),
    )


def metric_text(
    value: float | None,
) -> str:
    """
    Format one metric for the Markdown report.
    """

    if value is None:
        return "N/A"

    return f"{value:.4f}"


def create_markdown_report(
    response: EvaluationRunResponse,
) -> str:
    """
    Convert one evaluation response into a readable
    Markdown quality report.
    """

    summary = response.summary

    lines = [
        "# RAG Evaluation Report",
        "",
        "## Evaluation Configuration",
        "",
        f"- Run ID: `{response.evaluation_run_id}`",
        f"- Dataset: `{response.dataset_name}`",
        f"- Dataset version: `{response.dataset_version}`",
        f"- Started: `{response.started_at}`",
        f"- Completed: `{response.completed_at}`",
        f"- Top K: `{response.top_k}`",
        f"- Candidate Top K: `{response.candidate_top_k}`",
        f"- QA enabled: `{response.run_qa}`",
        f"- Graph retrieval enabled: `{response.include_graph}`",
        "",
        "## Overall Metrics",
        "",
        f"- Total questions: {summary.total_questions}",
        f"- Successful cases: {summary.successful_cases}",
        f"- Cases with errors: {summary.failed_cases}",
        f"- Passed questions: {summary.passed_questions}",
        f"- Failed questions: {summary.failed_questions}",
        (
            "- Average Precision@k: "
            f"{metric_text(summary.average_precision_at_k)}"
        ),
        (
            "- Average Recall@k: "
            f"{metric_text(summary.average_recall_at_k)}"
        ),
        (
            "- Average citation accuracy: "
            f"{metric_text(summary.average_citation_accuracy)}"
        ),
        (
            "- Average citation coverage: "
            f"{metric_text(summary.average_citation_coverage)}"
        ),
        (
            "- Average answer keyword coverage: "
            f"{metric_text(summary.average_answer_keyword_coverage)}"
        ),
        (
            "- Average context keyword coverage: "
            f"{metric_text(summary.average_context_keyword_coverage)}"
        ),
        (
            "- Average faithfulness score: "
            f"{metric_text(summary.average_faithfulness_score)}"
        ),
        (
            "- Answer-status accuracy: "
            f"{metric_text(summary.answer_status_accuracy)}"
        ),
        (
            "- Unsupported-answer rate: "
            f"{metric_text(summary.unsupported_answer_rate)}"
        ),
        "",
        "## Per-Question Results",
        "",
    ]

    for result in response.results:
        lines.extend(
            [
                (
                    f"### {result.evaluation_id} — "
                    f"{'PASS' if result.passed else 'FAIL'}"
                ),
                "",
                f"**Document:** `{result.document_id}`",
                "",
                f"**Category:** `{result.category}`",
                "",
                f"**Question:** {result.question}",
                "",
                (
                    "**Expected chunks:** "
                    + (
                        ", ".join(
                            f"`{chunk_id}`"
                            for chunk_id
                            in result.expected_chunk_ids
                        )
                        or "None"
                    )
                ),
                "",
                (
                    "**Retrieved chunks:** "
                    + (
                        ", ".join(
                            f"`{chunk_id}`"
                            for chunk_id
                            in result.retrieved_chunk_ids
                        )
                        or "None"
                    )
                ),
                "",
                (
                    f"**Precision@{result.top_k}:** "
                    f"{metric_text(result.precision_at_k)}"
                ),
                "",
                (
                    f"**Recall@{result.top_k}:** "
                    f"{metric_text(result.recall_at_k)}"
                ),
                "",
                (
                    "**Expected answer status:** "
                    f"`{result.expected_answer_status}`"
                ),
                "",
                (
                    "**Actual answer status:** "
                    f"`{result.actual_answer_status or 'N/A'}`"
                ),
                "",
                (
                    "**Citation accuracy:** "
                    f"{metric_text(result.citation_accuracy)}"
                ),
                "",
                (
                    "**Faithfulness:** "
                    f"{metric_text(result.faithfulness_score)}"
                ),
                "",
            ]
        )

        if result.answer:
            lines.extend(
                [
                    "**Answer:**",
                    "",
                    result.answer,
                    "",
                ]
            )

        if result.error_message:
            lines.extend(
                [
                    "**Error:**",
                    "",
                    f"`{result.error_message}`",
                    "",
                ]
            )

    lines.extend(
        [
            "## Limitations",
            "",
            (
                "- Faithfulness is a deterministic "
                "keyword-based proxy, not a complete "
                "semantic fact-check."
            ),
            (
                "- OCR and layout parsing errors can affect "
                "chunk text, expected keyword matching, "
                "and retrieval quality."
            ),
            (
                "- Chunk IDs may change if documents are "
                "reprocessed with a different chunking strategy."
            ),
            (
                "- Failure cases are intentionally retained "
                "to show honest system limitations."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_evaluation_reports(
    response: EvaluationRunResponse,
) -> tuple[Path, Path]:
    """
    Write run-specific and latest report files.

    Files created:

        evaluation/reports/evaluation_<run_id>.json
        evaluation/reports/evaluation_<run_id>.md
        evaluation/reports/latest_evaluation.json
        evaluation/reports/latest_evaluation.md
    """

    REPORTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_id = response.evaluation_run_id

    json_report_path = (
        REPORTS_DIRECTORY
        / f"evaluation_{run_id}.json"
    )

    markdown_report_path = (
        REPORTS_DIRECTORY
        / f"evaluation_{run_id}.md"
    )

    latest_json_path = (
        REPORTS_DIRECTORY
        / "latest_evaluation.json"
    )

    latest_markdown_path = (
        REPORTS_DIRECTORY
        / "latest_evaluation.md"
    )

    response_data = response.model_dump(
        mode="json"
    )

    markdown_content = create_markdown_report(
        response
    )

    for output_path in [
        json_report_path,
        latest_json_path,
    ]:
        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as report_file:
            json.dump(
                response_data,
                report_file,
                indent=2,
                ensure_ascii=False,
            )

    for output_path in [
        markdown_report_path,
        latest_markdown_path,
    ]:
        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as report_file:
            report_file.write(markdown_content)

    return (
        json_report_path,
        markdown_report_path,
    )


def run_evaluation(
    request: EvaluationRunRequest,
) -> EvaluationRunResponse:
    """
    Run the complete Week 15 evaluation workflow.
    """

    started_at = utc_now_string()

    evaluation_run_id = (
        datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        + "_"
        + uuid4().hex[:8]
    )

    dataset = load_golden_dataset(
        request.dataset_path
    )

    (
        vector_weight,
        keyword_weight,
        graph_weight,
    ) = normalize_weights(request)

    results: list[EvaluationCaseResult] = []

    for case in dataset["evaluation_cases"]:
        result = evaluate_one_case(
            case=case,
            request=request,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            graph_weight=graph_weight,
        )

        results.append(result)

    summary = build_evaluation_summary(results)

    completed_at = utc_now_string()

    json_report_path = (
        REPORTS_DIRECTORY
        / f"evaluation_{evaluation_run_id}.json"
    )

    markdown_report_path = (
        REPORTS_DIRECTORY
        / f"evaluation_{evaluation_run_id}.md"
    )

    response = EvaluationRunResponse(
        evaluation_run_id=evaluation_run_id,
        status="completed",
        dataset_name=str(
            dataset.get(
                "dataset_name",
                "unknown_dataset",
            )
        ),
        dataset_version=str(
            dataset.get(
                "version",
                "unknown",
            )
        ),
        started_at=started_at,
        completed_at=completed_at,
        top_k=request.top_k,
        candidate_top_k=request.candidate_top_k,
        run_qa=request.run_qa,
        include_graph=request.include_graph,
        summary=summary,
        results=results,
        json_report_path=path_relative_to_project(
            json_report_path
        ),
        markdown_report_path=path_relative_to_project(
            markdown_report_path
        ),
    )

    write_evaluation_reports(response)

    return response


def get_latest_evaluation_report() -> EvaluationRunResponse | None:
    """
    Read the latest generated evaluation JSON report.

    Returns:
        EvaluationRunResponse when a report exists.

        None when evaluation has not been run yet.
    """

    latest_report_path = (
        REPORTS_DIRECTORY
        / "latest_evaluation.json"
    )

    if not latest_report_path.exists():
        return None

    with open(
        latest_report_path,
        "r",
        encoding="utf-8",
    ) as report_file:
        report_data = json.load(report_file)

    return EvaluationRunResponse.model_validate(
        report_data
    )