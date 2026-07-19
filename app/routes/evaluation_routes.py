"""
Week 15 RAG evaluation API routes.

Endpoints:

POST /evaluation/run
    Runs the golden-dataset evaluation and generates reports.

GET /evaluation/results
    Returns the latest generated evaluation report.
"""

# Import APIRouter to group evaluation endpoints.
from fastapi import APIRouter

# Import HTTPException for clean API errors.
from fastapi import HTTPException

# Import status for readable HTTP status constants.
from fastapi import status


# Import evaluation request and response models.
from app.models.evaluation_models import (
    EvaluationResultsResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
)

# Import evaluation service functions.
from app.services.evaluation_service import (
    get_latest_evaluation_report,
    run_evaluation,
)


# Create the evaluation router.
router = APIRouter(
    prefix="/evaluation",
    tags=["Evaluation"],
)


@router.post(
    "/run",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_200_OK,
)
def run_rag_evaluation(
    request: EvaluationRunRequest,
) -> EvaluationRunResponse:
    """
    Run the complete Week 15 RAG evaluation.

    Flow:

    Golden dataset
        ↓
    Hybrid retrieval
        ↓
    Reranking
        ↓
    Optional QA
        ↓
    Precision@k and Recall@k
        ↓
    Citation metrics
        ↓
    Faithfulness and answer-status metrics
        ↓
    JSON and Markdown reports
    """

    try:
        return run_evaluation(request)

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Evaluation failed: "
                f"{type(error).__name__}: {error}"
            ),
        ) from error


@router.get(
    "/results",
    response_model=EvaluationResultsResponse,
    status_code=status.HTTP_200_OK,
)
def get_evaluation_results() -> EvaluationResultsResponse:
    """
    Return the latest generated evaluation report.

    This endpoint does not rerun evaluation.
    It only reads:

        evaluation/reports/latest_evaluation.json
    """

    try:
        evaluation = get_latest_evaluation_report()

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Could not read evaluation report: "
                f"{type(error).__name__}: {error}"
            ),
        ) from error

    if evaluation is None:
        return EvaluationResultsResponse(
            status="not_found",
            report_found=False,
            report_path=None,
            evaluation=None,
        )

    return EvaluationResultsResponse(
        status="completed",
        report_found=True,
        report_path=(
            "evaluation/reports/latest_evaluation.json"
        ),
        evaluation=evaluation,
    )