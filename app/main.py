# Import FastAPI to create backend app.
from fastapi import FastAPI

# Import Request so exception handlers can know which API path caused the error.
from fastapi import Request

# Import HTTPException so we can handle normal FastAPI errors cleanly.
from fastapi import HTTPException

# Import RequestValidationError so we can handle missing/wrong request fields cleanly.
from fastapi.exceptions import RequestValidationError

# Import JSONResponse so we can return our own clean JSON error format.
from fastapi.responses import JSONResponse

# Import status so we can use readable HTTP status names like HTTP_500_INTERNAL_SERVER_ERROR.
from fastapi import status

# Import jsonable_encoder to safely convert validation errors into JSON.
from fastapi.encoders import jsonable_encoder

# Import document router.
from app.routes.document_routes import router as document_router

# Import search router.
from app.routes.search_routes import router as search_router

# Import QA router.
from app.routes.qa_routes import router as qa_router

# Import our custom application exception class.
from app.utils.exceptions import AppException

# Import logger helper.
from app.utils.logger import get_logger


# Create a logger for this file.
# __name__ means this logger will show the file/module name in logs.
logger = get_logger(__name__)


# Create FastAPI app.
app = FastAPI(
    title="Production-Grade Document Intelligence and RAG Pipeline",
    description="Backend for PDF upload, extraction, chunking, indexing, vector search, and RAG Q&A.",
    version="1.0.0"
)


# Health check API.
@app.get("/health")
def health_check():
    # Log whenever health check is called.
    logger.info("Health check endpoint called")

    # Return simple success response.
    return {
        "status": "ok",
        "message": "Document Intelligence API is running."
    }


# Handle our custom app errors.
# Example: raise NotFoundException("Document not found")
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    # Log custom application errors.
    logger.warning(
        f"Application error | path={request.url.path} | "
        f"code={exc.error_code} | message={exc.message}"
    )

    # Return clean JSON response.
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "path": request.url.path
            }
        }
    )


# Handle normal FastAPI HTTP errors.
# Example: raise HTTPException(status_code=404, detail="Document not found")
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Log HTTP errors.
    logger.warning(
        f"HTTP error | path={request.url.path} | "
        f"status_code={exc.status_code} | detail={exc.detail}"
    )

    # Return clean JSON response.
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "path": request.url.path
            }
        }
    )


# Handle request validation errors.
# Example: user calls /qa without document_id.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log validation errors.
    logger.warning(
        f"Validation error | path={request.url.path} | errors={exc.errors()}"
    )

    # Return clean validation error response.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "path": request.url.path,
                "details": jsonable_encoder(exc.errors())
            }
        }
    )


# Handle unexpected server errors.
# This is the final safety net.
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log full unexpected error.
    # exc_info=True shows the full traceback in terminal.
    logger.error(
        f"Unexpected server error | path={request.url.path} | error={str(exc)}",
        exc_info=True
    )

    # Return safe 500 response.
    # We do not expose full internal error details to the user.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Something went wrong inside the server",
                "path": request.url.path
            }
        }
    )


# Connect document APIs.
app.include_router(document_router)


# Connect search APIs.
app.include_router(search_router)


# Connect Q&A APIs.
app.include_router(qa_router)