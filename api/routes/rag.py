"""RAG endpoint definitions."""

from fastapi import APIRouter

router = APIRouter(prefix="/rag")


@router.post("")
def run_rag(question: str) -> dict:
    """Placeholder RAG endpoint."""
    return {"question": question, "answer": None}
