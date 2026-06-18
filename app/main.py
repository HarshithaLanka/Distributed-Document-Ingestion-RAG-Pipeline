# Import FastAPI to create the backend app.
from fastapi import FastAPI

# Import document router.
from app.routes.document_routes import router as document_router


# Create FastAPI application object.
app = FastAPI(
    # Title shown in Swagger UI.
    title="Production-Grade Document Intelligence and RAG Pipeline",

    # Description shown in Swagger UI.
    description="Week 1 backend for PDF upload, local storage, and metadata tracking.",

    # Version of the API.
    version="1.0.0"
)


# Create a simple health check API.
@app.get("/health")
def health_check():
    # Return simple status response.
    return {
        "status": "ok",
        "message": "Document Intelligence API is running."
    }


# Connect document routes to the main FastAPI app.
app.include_router(document_router)