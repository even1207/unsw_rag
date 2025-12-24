"""
RAG Q&A API Server

A persistent FastAPI server that loads models once and handles multiple requests efficiently.

Usage:
    # Start server
    python3 api_server.py

    # Or with custom port
    python3 api_server.py --port 8000

    # Test with curl
    curl -X POST "http://localhost:8000/ask" \
         -H "Content-Type: application/json" \
         -d '{"query": "What is digital twin?", "max_context": 5}'
"""
import sys
from pathlib import Path
import logging
from typing import Optional
import argparse
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Add project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from search.hybrid_search import HybridSearchEngine
from search.rag_generator import RAGAnswerGenerator
from pipeline.step4_generate_embeddings import EmbeddingGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for API
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for asking questions"""
    query: str = Field(..., description="User question", min_length=1)
    max_context: int = Field(10, description="Maximum context chunks to use", ge=1, le=20)
    include_sources: bool = Field(True, description="Whether to include source citations")
    model: Optional[str] = Field(None, description="Override default LLM model")


class QueryResponse(BaseModel):
    """Response model for answers"""
    query: str
    answer: str
    sources: list
    model: str
    tokens_used: int
    search_results_count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    models_loaded: bool
    database_connected: bool


# ============================================================================
# Global State - Models loaded once at startup
# ============================================================================

class AppState:
    """Application state holding loaded models"""
    def __init__(self):
        self.db_engine = None
        self.SessionLocal = None
        self.search_engine = None
        self.rag_generator = None
        self.embedding_generator = None
        self.initialized = False


app_state = AppState()


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="UNSW RAG Q&A API",
    description="RAG-based question answering system for UNSW research",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """
    Initialize models and database connections on startup.
    This runs once when the server starts.
    """
    logger.info("=" * 80)
    logger.info("STARTING RAG Q&A API SERVER")
    logger.info("=" * 80)

    try:
        # 1. Connect to database
        logger.info(f"Connecting to database: {settings.postgres_dsn}")
        app_state.db_engine = create_engine(settings.postgres_dsn, echo=False)
        app_state.SessionLocal = sessionmaker(bind=app_state.db_engine)
        logger.info("✓ Database connected")

        # 2. Initialize embedding generator
        logger.info("Initializing embedding generator...")
        app_state.embedding_generator = EmbeddingGenerator(model_type="openai")
        logger.info("✓ Embedding generator initialized")

        # 3. Initialize search engine (this loads the reranker model)
        logger.info("Initializing search engine with reranker...")
        logger.info("  (This will take ~7 seconds for model loading...)")
        session = app_state.SessionLocal()
        try:
            app_state.search_engine = HybridSearchEngine(
                session=session,
                embedding_generator=app_state.embedding_generator,
                use_reranker=True,
                reranker_model="local"
            )
        finally:
            session.close()
        logger.info("✓ Search engine initialized")

        # 4. Initialize RAG answer generator
        logger.info("Initializing RAG answer generator...")
        app_state.rag_generator = RAGAnswerGenerator(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=1000
        )
        logger.info("✓ RAG generator initialized")

        app_state.initialized = True

        logger.info("=" * 80)
        logger.info("✓ SERVER READY - All models loaded successfully!")
        logger.info("=" * 80)
        logger.info("API endpoints available at:")
        logger.info("  - POST /ask       - Ask a question")
        logger.info("  - GET  /health    - Health check")
        logger.info("  - GET  /docs      - API documentation")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down server...")
    if app_state.db_engine:
        app_state.db_engine.dispose()
    logger.info("✓ Server shutdown complete")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "UNSW RAG Q&A API",
        "version": "1.0.0",
        "status": "running" if app_state.initialized else "initializing",
        "endpoints": {
            "ask": "POST /ask - Ask a question",
            "health": "GET /health - Health check",
            "docs": "GET /docs - API documentation"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health_check():
    """
    Health check endpoint

    Returns the status of the server and whether models are loaded.
    """
    database_ok = False
    if app_state.db_engine:
        try:
            # Test database connection
            with app_state.db_engine.connect() as conn:
                conn.execute("SELECT 1")
            database_ok = True
        except:
            pass

    return {
        "status": "healthy" if app_state.initialized and database_ok else "unhealthy",
        "models_loaded": app_state.initialized,
        "database_connected": database_ok
    }


@app.post("/ask", response_model=QueryResponse, tags=["Q&A"])
async def ask_question(request: QueryRequest):
    """
    Ask a question and get an answer based on UNSW research documents.

    The system will:
    1. Search for relevant documents using hybrid search (BM25 + Vector + Reranker)
    2. Generate a natural language answer using LLM based on retrieved documents
    3. Return the answer with citations

    Args:
        request: QueryRequest with query and optional parameters

    Returns:
        QueryResponse with answer and sources
    """
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="Server not fully initialized")

    try:
        logger.info(f"Processing query: {request.query}")

        # Create database session for this request
        db_session = app_state.SessionLocal()

        try:
            # 1. Search for relevant documents
            logger.info("Searching for relevant documents...")
            search_response = app_state.search_engine.search(
                query=request.query,
                top_k=request.max_context,
                include_scores=True
            )

            logger.info(f"Found {search_response['total_results']} relevant documents")

            # 2. Generate answer with LLM
            logger.info("Generating answer with LLM...")

            # Use custom model if specified
            if request.model:
                # Create a temporary generator with the specified model
                temp_generator = RAGAnswerGenerator(
                    model=request.model,
                    temperature=0.7,
                    max_tokens=1000
                )
                answer_data = temp_generator.generate_answer(
                    query=request.query,
                    search_results=search_response['citations'],
                    max_context_chunks=request.max_context
                )
            else:
                # Use default generator
                answer_data = app_state.rag_generator.generate_answer(
                    query=request.query,
                    search_results=search_response['citations'],
                    max_context_chunks=request.max_context
                )

            logger.info(f"✓ Answer generated ({answer_data['tokens_used']} tokens)")

            # 3. Prepare response
            response = QueryResponse(
                query=request.query,
                answer=answer_data["answer"],
                sources=answer_data["sources"] if request.include_sources else [],
                model=answer_data["model"],
                tokens_used=answer_data["tokens_used"],
                search_results_count=search_response["total_results"]
            )

            return response

        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main - Run Server
# ============================================================================

def main():
    """Main function to run the server"""
    parser = argparse.ArgumentParser(description="Run RAG Q&A API Server")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    # Run server
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
