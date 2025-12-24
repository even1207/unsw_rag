# RAG Q&A API Server

A high-performance, persistent API server for UNSW research question answering.

## Features

- ✅ **Persistent Model Loading**: Models load once at startup (saves ~7 seconds per query)
- ✅ **Fast Response**: ~7-8 seconds per query (vs ~14 seconds with script)
- ✅ **RESTful API**: Easy integration with any application
- ✅ **Auto Documentation**: Interactive API docs at `/docs`
- ✅ **Health Monitoring**: Health check endpoint
- ✅ **Concurrent Requests**: Handle multiple queries simultaneously

## Installation

Install required dependencies:

```bash
pip install fastapi uvicorn requests
```

## Quick Start

### 1. Start the Server

```bash
# Default (port 8000)
python3 api_server.py

# Custom port
python3 api_server.py --port 8080

# Development mode (auto-reload)
python3 api_server.py --reload
```

Server will be ready when you see:
```
✓ SERVER READY - All models loaded successfully!
```

### 2. Test with Client

```bash
# Ask a question
python3 test_api_client.py --query "What is digital twin?"

# With custom context size
python3 test_api_client.py --query "Industry 4.0" --max-context 5

# Check server health
python3 test_api_client.py --health

# Run benchmark
python3 test_api_client.py --benchmark
```

### 3. Use with curl

```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What are the applications of digital twin?",
       "max_context": 10,
       "include_sources": true
     }'
```

## API Endpoints

### `POST /ask`

Ask a question and get an answer.

**Request Body:**
```json
{
  "query": "Your question here",
  "max_context": 10,
  "include_sources": true,
  "model": "gpt-4o-mini"  // optional
}
```

**Response:**
```json
{
  "query": "Your question",
  "answer": "Generated answer based on documents...",
  "sources": [
    {
      "type": "publication",
      "title": "Paper Title",
      "year": 2023,
      "url": "https://doi.org/..."
    }
  ],
  "model": "gpt-4o-mini",
  "tokens_used": 1234,
  "search_results_count": 42
}
```

### `GET /health`

Check server health.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": true,
  "database_connected": true
}
```

### `GET /docs`

Interactive API documentation (Swagger UI).

## Performance Comparison

| Method | First Request | Subsequent Requests |
|--------|--------------|---------------------|
| **Script** (`test_rag_qa.py`) | ~14.6s | ~14.6s (reload every time) |
| **API Server** (`api_server.py`) | ~14.6s (startup) | **~7-8s** ⚡ |

**Speed improvement: ~50% faster for subsequent requests**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Server                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Startup (once):                                     │  │
│  │  1. Load Reranker Model (~7s)                        │  │
│  │  2. Initialize Search Engine                         │  │
│  │  3. Initialize RAG Generator                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Per Request (~7-8s):                                │  │
│  │  1. BM25 + Vector Search     (~0.7s)                 │  │
│  │  2. Reranking                (~1.0s)                 │  │
│  │  3. LLM Generation           (~6.0s)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Advanced Usage

### Python Client

```python
import requests

response = requests.post(
    "http://localhost:8000/ask",
    json={
        "query": "What is Industry 4.0?",
        "max_context": 5,
        "include_sources": True
    }
)

data = response.json()
print(data["answer"])
```

### JavaScript/Node.js Client

```javascript
const response = await fetch('http://localhost:8000/ask', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What is Industry 4.0?',
    max_context: 5,
    include_sources: true
  })
});

const data = await response.json();
console.log(data.answer);
```

### Custom Model

```bash
# Use GPT-4 instead of default gpt-4o-mini
python3 test_api_client.py \
  --query "Complex research question" \
  --model gpt-4o
```

## Production Deployment

### Using gunicorn (recommended for production)

```bash
pip install gunicorn

gunicorn api_server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Using Docker

```dockerfile
FROM python:3.9

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["python3", "api_server.py", "--host", "0.0.0.0", "--port", "8000"]
```

## Troubleshooting

### Server won't start

1. Check database connection:
   ```bash
   psql -U z5241339 -d unsw_rag -c "SELECT 1"
   ```

2. Check OpenAI API key:
   ```python
   from config.settings import settings
   print(settings.openai_api_key)
   ```

### Slow responses

- First request after startup is slower (model loading)
- Subsequent requests should be ~7-8 seconds
- Check network latency to OpenAI API
- Consider using `--no-reranker` flag (saves 1 second, slight accuracy loss)

### Connection refused

- Make sure server is running: `python3 api_server.py`
- Check port is not in use: `lsof -i :8000`
- Try different port: `python3 api_server.py --port 8080`

## Monitoring

Server logs show:
- Request processing time
- Number of search results
- Tokens consumed
- Errors and warnings

Example log:
```
2025-12-22 15:00:00 - INFO - Processing query: What is digital twin?
2025-12-22 15:00:01 - INFO - Found 42 relevant documents
2025-12-22 15:00:07 - INFO - ✓ Answer generated (1046 tokens)
```

## API Rate Limiting

The server uses OpenAI API, which has rate limits:
- gpt-4o-mini: 500 RPM (requests per minute)
- gpt-4o: 10,000 RPM

For high-traffic scenarios, consider:
1. Implementing request queuing
2. Caching frequent queries
3. Using multiple API keys with load balancing
