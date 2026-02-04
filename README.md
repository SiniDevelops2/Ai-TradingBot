# Company State RAG MVP (Step 5)

This project implements a news-driven company state system up through Step 5:
ingest news → clean/dedupe → ticker linking → RAG retrieval → prompt builder →
LLM JSON validation → audit logging → Option B state updates → snapshot rebuild →
vector index updates. No trading logic or broker execution is included.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload
```

## Sample curl

```bash
curl -X POST http://localhost:8000/ingest_news \
  -H 'Content-Type: application/json' \
  -d '{
    "id":"news-apple-1",
    "source":"mock",
    "published_at":"2025-01-01T10:00:00Z",
    "title":"Apple earnings beat expectations",
    "content":"Apple reported earnings and raised guidance for next quarter."
  }'
```

```bash
curl -X POST http://localhost:8000/analyze_news/news-apple-1
```

## Notes

- SQLite persistence defaults to `data/app.db` (override with `APP_DB_PATH`).
- Embeddings and LLM calls are stubbed for deterministic, offline runs.
- Vector chunks are stored in SQLite and queried via cosine similarity.
