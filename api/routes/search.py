"""Search endpoint definitions."""

from fastapi import APIRouter

router = APIRouter(prefix="/search")


@router.get("")
def search_staff(q: str) -> dict:
    """Placeholder search endpoint."""
    return {"query": q, "results": []}
