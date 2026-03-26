# UNSW AI RAG System — Handover Document

**GitHub Repository**: https://github.com/even1207/unsw_rag
**Handover Date**: 2026-03-27
**Tech Stack**: Python · FastAPI · PostgreSQL + pgvector · OpenAI API

---

## 1. Project Overview

This project is a **research staff knowledge base Q&A system** for UNSW (University of New South Wales). Core capabilities:

- Crawls staff profiles from each Faculty (name, title, bio, publications, etc.)
- Fetches publication abstracts from multiple academic sources (OpenAlex / Semantic Scholar / Crossref / PubMed)
- Stores vectorised content in PostgreSQL + pgvector, supporting hybrid retrieval (BM25 + semantic vector search)
- Exposes a RAG Q&A API via FastAPI, backed by OpenAI GPT for answer generation

Example queries:
- "Who is researching digital twin?"
- "What papers have Wenjie Zhang and Zhengyi Yang co-authored?"
- "Which researchers in the Business School focus on finance?"

---

## 2. System Architecture

```
User query
    │
    ▼
FastAPI Server (api_server.py)
    │
    ├── Hybrid Search (search/)
    │     ├── BM25 full-text search  (bm25_search.py)
    │     ├── Vector search          (vector_search.py)
    │     ├── RRF fusion             (fusion.py)
    │     └── Reranker               (reranker.py)
    │
    └── RAG Generation (rag_generator.py)
          └── OpenAI GPT → answer + cited sources
```

Data pipeline flow:
```
Step 1: Crawl Staff Profiles     → data/processed/staff_{faculty}_profiles.json
Step 2: Parse publications + fetch abstracts → data/processed/rag_chunks.json
Step 3: Import into PostgreSQL   → staff / publications / chunks tables
Step 4: Generate embeddings      → embeddings table (pgvector)
```

---

## 3. Directory Structure

```
unsw_ai_rag/
├── api_server.py              # Main entry point: FastAPI server
├── api/
│   ├── server.py              # Alternative modular server entry
│   └── routes/
│       ├── rag.py             # /ask Q&A route
│       ├── search.py          # /search retrieval route
│       └── collaboration.py   # /collaboration route
├── pipeline/
│   ├── step1_fetch_staff.py             # Crawl staff profiles
│   ├── step2_parse_publications.py      # Parse publications + fetch abstracts
│   ├── step3_import_to_database.py      # Import into database
│   └── step4_generate_embeddings.py     # Generate vector embeddings
├── search/
│   ├── hybrid_search.py       # Hybrid search engine (main entry)
│   ├── bm25_search.py         # BM25 full-text search
│   ├── vector_search.py       # pgvector semantic search
│   ├── fusion.py              # RRF fusion algorithm
│   ├── reranker.py            # Reranker model
│   ├── rag_generator.py       # RAG answer generation
│   └── citation.py            # Citation formatting
├── database/
│   ├── schema.sql             # Base schema (staff / publications)
│   ├── rag_schema.py          # Full SQLAlchemy ORM (chunks / embeddings)
│   ├── models.py              # Simple data classes
│   └── db.py                  # Database connection
├── scripts/                   # One-off and maintenance scripts
├── config/
│   ├── settings.py            # Global config (reads from .env)
│   └── logging.conf           # Logging config
├── data/
│   ├── processed/             # Crawler output JSON files
│   └── cache/                 # Checkpoint files for resume support
├── tests/                     # Test files
├── .env.example               # Environment variable template
└── requirements.txt           # Python dependencies
```

---

## 4. Environment Setup

### 4.1 System Requirements

- Python 3.10+
- PostgreSQL 14+ with pgvector extension
- (Optional) Local Sentence Transformers model for the reranker

### 4.2 Installation

```bash
# 1. Clone the repository
git clone git@github.com:even1207/unsw_rag.git
cd unsw_rag

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in:
#   OPENAI_API_KEY=sk-...
```

### 4.3 Database Setup

```bash
# Install pgvector extension (macOS Homebrew example)
brew install postgresql@16
brew install pgvector

# Create the database
createdb unsw_rag

# Enable pgvector in psql
psql unsw_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Initialise the schema
python scripts/init_database.py
# Or manually:
psql unsw_rag < database/schema.sql
```

The default connection string in `config/settings.py` is:
```
postgresql://z5241339@localhost:5432/unsw_rag
```
**Update this to match your own username.** You can override it in `.env`:
```
POSTGRES_DSN=postgresql://your_user@localhost:5432/unsw_rag
```

---

## 5. Data Pipeline

Run the following four steps in order to go from crawling to a queryable knowledge base:

### Step 1: Crawl Staff Profiles

```bash
# List all supported faculties
python pipeline/step1_fetch_staff.py --list

# Crawl a specific faculty (resume supported by default)
python pipeline/step1_fetch_staff.py --faculty engineering
python pipeline/step1_fetch_staff.py --faculty arts
python pipeline/step1_fetch_staff.py --faculty business
python pipeline/step1_fetch_staff.py --faculty science
python pipeline/step1_fetch_staff.py --faculty medicine
python pipeline/step1_fetch_staff.py --faculty canberra

# Force restart from scratch (ignore checkpoint)
python pipeline/step1_fetch_staff.py --faculty engineering --fresh

# Save JSON only, skip database write
python pipeline/step1_fetch_staff.py --faculty engineering --no-db
```

Data source: UNSW Funnelback search API (internal service — requires campus network or VPN).

### Step 2: Parse Publications + Fetch Abstracts

```bash
python pipeline/step2_parse_publications.py
```

Tries sources in priority order: OpenAlex → Semantic Scholar → Crossref → PubMed.
Output: `data/processed/rag_chunks.json`

### Step 3: Import into Database

```bash
python pipeline/step3_import_to_database.py
```

### Step 4: Generate Vector Embeddings

```bash
python pipeline/step4_generate_embeddings.py
```

Uses OpenAI `text-embedding-3-small`. **This step incurs OpenAI API costs.**

---

## 6. Starting the API Server

```bash
# Start server on default port 8000
python api_server.py

# Custom port
python api_server.py --port 8080

# Development mode (auto-reload)
python api_server.py --reload
```

The server is ready when you see:
```
✓ SERVER READY - All models loaded successfully!
```

Interactive API docs: http://localhost:8000/docs

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ask` | RAG Q&A (primary endpoint) |
| GET  | `/ask` | RAG Q&A (curl-friendly) |
| GET  | `/search` | Retrieval only, no answer generation |
| GET  | `/collaboration` | Query collaboration relationships |
| GET  | `/health` | Health check |

Example request:
```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Who works on digital twin research?",
       "max_context": 10,
       "include_sources": true,
       "include_kg": true
     }'
```

---

## 7. Key Configuration

| Setting | File | Notes |
|---------|------|-------|
| `OPENAI_API_KEY` | `.env` | Required |
| `POSTGRES_DSN` | `.env` / `config/settings.py` | Database connection string |
| `funnelback_base_url` | `config/settings.py` | UNSW Funnelback API base URL |

`funnelback_base_url` in `config/settings.py` is currently a placeholder. Confirm the real URL from within the UNSW network before running Step 1.

---

## 8. Troubleshooting

**Q: Step 1 returns 0 results?**
Make sure you are connected to the UNSW campus network or VPN. Funnelback is an internal service not accessible from outside.

**Q: pgvector installation fails?**
See the [pgvector docs](https://github.com/pgvector/pgvector). Alternatively, use Docker:
```bash
docker run -d -e POSTGRES_DB=unsw_rag -e POSTGRES_PASSWORD=password \
  -p 5432:5432 ankane/pgvector
```

**Q: How do I control OpenAI API costs?**
Both Step 4 (embeddings) and the `/ask` endpoint call the OpenAI API.
- Start with a single small faculty (e.g. Business, ~384 staff) to test end-to-end.
- Use the `max_context` parameter on `/ask` to limit tokens per request (default: 10).

**Q: How do I refresh the data?**
Re-run Steps 1–4. Checkpoint/resume support means interrupted runs can be continued safely.

---

## 9. Data Status at Handover

Staff profile data already crawled (JSON files in `data/processed/`):

| Faculty | File |
|---------|------|
| Arts, Design & Architecture | `staff_arts_profiles.json` |
| Business School | `staff_business_profiles.json` |
| Canberra | `staff_canberra_profiles.json` |
| Medicine | `staff_medicine_profiles.json` |
| Science | `staff_science_profiles.json` |

Engineering data is being incrementally supplemented via the OpenAlex API (progress tracked in `scripts/.openalex_progress.json`).

---

## 10. Recommended Next Steps

- [ ] Complete Engineering Faculty crawl (currently partially sourced from OpenAlex)
- [ ] Onboard Law & Justice Faculty (may require a different entry point — investigate separately)
- [ ] Schedule the pipeline as a recurring job (e.g. cron) to keep data fresh
- [ ] Use `systemd` or Docker Compose to manage the server process in production
- [ ] Add an authentication layer to the API (currently open with no auth)
