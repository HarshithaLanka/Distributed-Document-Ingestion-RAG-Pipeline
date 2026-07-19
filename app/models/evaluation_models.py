"""
Pydantic models for Week 15 RAG evaluation APIs.

These models define:

1. The request used to start an evaluation run.
2. The result for one golden-dataset question.
3. The overall evaluation summary.
4. The response returned by POST /evaluation/run.
5. The response returned by GET /evaluation/results.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    """
    Request body for POST /evaluation/run.

    The evaluation service will:

    1. Load the golden dataset.
    2. Run reranked retrieval for each question.
    3. Optionally run the QA pipeline.
    4. Calculate all Week 15 metrics.
    5. Save JSON and Markdown reports.
    """

    # Path to the manually verified golden dataset.
    dataset_path: str = "evaluation/golden_dataset.json"

    # Number of final retrieved chunks evaluated.
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    # Number of candidates collected before reranking.
    candidate_top_k: int = Field(
        default=10,
        ge=1,
        le=20,
    )

    # Retrieval weights.
    vector_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
    )

    keyword_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
    )

    graph_weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    # Keep false temporarily because your Neo4j connection
    # previously produced a DNS error.
    include_graph: bool = False

    # When true, evaluation also calls Ollama through QA.
    # When false, only retrieval metrics are calculated.
    run_qa: bool = True


class EvaluationCaseResult(BaseModel):
    """
    Evaluation result for one golden-dataset question.
    """

    # Golden-dataset identifiers.
    evaluation_id: str
    document_id: str
    question: str
    category: str

    # Retrieval configuration.
    top_k: int

    # Expected ground truth.
    expected_chunk_ids: List[str] = Field(
        default_factory=list
    )
    expected_pages: List[int] = Field(
        default_factory=list
    )
    expected_keywords: List[str] = Field(
        default_factory=list
    )
    expected_answer_status: str

    # Actual retrieval output.
    retrieved_chunk_ids: List[str] = Field(
        default_factory=list
    )
    retrieved_pages: List[int] = Field(
        default_factory=list
    )
    retrieved_contexts: List[str] = Field(
        default_factory=list
    )

    # Retrieval metrics.
    precision_at_k: float
    recall_at_k: Optional[float] = None

    # QA output.
    answer: Optional[str] = None
    actual_answer_status: Optional[str] = None
    cited_chunk_ids: List[str] = Field(
        default_factory=list
    )
    cited_pages: List[int] = Field(
        default_factory=list
    )

    # Citation and answer metrics.
    citation_accuracy: Optional[float] = None
    citation_coverage: Optional[float] = None
    answer_keyword_coverage: Optional[float] = None
    context_keyword_coverage: Optional[float] = None
    faithfulness_score: Optional[float] = None
    answer_status_accuracy: Optional[float] = None

    # Final case status.
    passed: bool

    # Store failures without stopping the complete run.
    error_message: Optional[str] = None


class EvaluationSummary(BaseModel):
    """
    Aggregate metrics across all evaluation questions.
    """

    total_questions: int
    successful_cases: int
    failed_cases: int

    # Number of questions whose final pass rule succeeded.
    passed_questions: int

    # Number of questions whose final pass rule failed.
    failed_questions: int

    # Retrieval averages.
    average_precision_at_k: float
    average_recall_at_k: Optional[float] = None

    # Citation averages.
    average_citation_accuracy: Optional[float] = None
    average_citation_coverage: Optional[float] = None

    # Answer and context quality averages.
    average_answer_keyword_coverage: Optional[float] = None
    average_context_keyword_coverage: Optional[float] = None
    average_faithfulness_score: Optional[float] = None
    answer_status_accuracy: Optional[float] = None

    # Lower is better.
    unsupported_answer_rate: Optional[float] = None


class EvaluationRunResponse(BaseModel):
    """
    Response returned by POST /evaluation/run.
    """

    evaluation_run_id: str
    status: str

    dataset_name: str
    dataset_version: str

    started_at: str
    completed_at: str

    top_k: int
    candidate_top_k: int
    run_qa: bool
    include_graph: bool

    summary: EvaluationSummary
    results: List[EvaluationCaseResult]

    json_report_path: str
    markdown_report_path: str


class EvaluationResultsResponse(BaseModel):
    """
    Response returned by GET /evaluation/results.

    This endpoint reads the most recently generated JSON report.
    """

    status: str
    report_found: bool
    report_path: Optional[str] = None
    evaluation: Optional[EvaluationRunResponse] = None