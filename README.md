# Company State RAG MVP (Step 5)

This MVP implements news ingestion, ticker linking, RAG retrieval, LLM grounded impact analysis (strict JSON), and deterministic company state updates with conflict resolution.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic
```

Run the API:

```bash
uvicorn app.main:app --reload
```

## Sample CURL

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

## Expected JSON Output (example)

```json
{
  "ticker": "AAPL",
  "event_type": "earnings",
  "is_new_information": true,
  "impact_score": 0.2,
  "horizon": "swing",
  "severity": "med",
  "confidence": 0.6,
  "risk_flags": [],
  "contradiction_flags": ["none"],
  "summary": "Apple reported earnings and raised guidance for next quarter.",
  "evidence": "Apple reported earnings and raised guidance for next quarter.",
  "citations": [
    {"layer": "profile", "source_id": "AAPL", "why": "background"}
  ]
}
```

## Mock Dataset

See `data/mock_news.json` for 3 example news items (AAPL/TSLA) to drive the pipeline.

## Notes

- SQLite persistence lives at `data/app.db` by default (override with `APP_DB_PATH`).
- Vector store uses FAISS when available; otherwise it falls back to a deterministic in-memory store.
- The LLM adapter is stubbed for deterministic tests; a real provider adapter can be wired later.
