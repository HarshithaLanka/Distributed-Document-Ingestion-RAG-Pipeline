# Import FastAPI to create backend app.
from fastapi import FastAPI

# Import document router.
from app.routes.document_routes import router as document_router

# Import search router.
from app.routes.search_routes import router as search_router

# Import QA router.
from app.routes.qa_routes import router as qa_router


# Create FastAPI app.
app = FastAPI(
    title="Production-Grade Document Intelligence and RAG Pipeline",
    description="Backend for PDF upload, extraction, chunking, indexing, vector search, and RAG Q&A.",
    version="1.0.0"
)


# Health check API.
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Document Intelligence API is running."
    }


# Connect document APIs.
app.include_router(document_router)


# Connect search APIs.
app.include_router(search_router)


# Connect Q&A APIs.
app.include_router(qa_router)