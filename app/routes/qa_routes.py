# Import APIRouter so we can create routes in a separate file.
from fastapi import APIRouter

# Import QARequest and QAResponse models.
from app.models.qa_models import QARequest, QAResponse

# Import the main QA service function.
from app.services.qa_service import answer_question


# Create a router for QA-related APIs.
router = APIRouter(
    # All routes in this file will start with /qa.
    prefix="/qa",

    # This groups the API under "QA" in Swagger UI.
    tags=["QA"]
)


# This endpoint answers questions using RAG.
@router.post("", response_model=QAResponse)
def ask_question(request: QARequest):
    # Send the request to the service layer and return the answer.
    return answer_question(request)