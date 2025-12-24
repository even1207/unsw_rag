# UNSW AI RAG

Project scaffold for an ingestion + RAG pipeline that collects UNSW staff data and exposes it via an API.

## Structure

- `ingestor/`: Funnelback + scraping utilities for gathering staff data
- `database/`: schema and persistence helpers
- `rag/`: retrieval augmented generation pipeline
- `api/`: FastAPI server and routes
- `scripts/`: one-off scripts for data refresh tasks
- `config/`: environment and logging config
- `tests/`: starter test suite

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload
```
# unsw_rag
