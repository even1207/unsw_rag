"""FastAPI server bootstrap for the UNSW AI RAG service."""

from fastapi import FastAPI

app = FastAPI(title="UNSW AI RAG")


@app.get("/health")
def healthcheck() -> dict:
    """Return a static health payload."""
    return {"status": "ok"}
