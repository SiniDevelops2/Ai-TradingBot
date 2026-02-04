from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from app import db
from app.ingest import ingest_news, load_clean_news, load_raw_news
from app.llm_analyzer import analyze_article
from app.models import AnalyzeResponse, NewsIn
from app.rag import retrieve_context, seed_profiles_if_missing
from app.state_manager import apply_event_update

app = FastAPI(title="Company State RAG MVP")


db.init_db()
seed_profiles_if_missing()


@app.post("/ingest_news")
async def ingest_news_endpoint(item: NewsIn):
    response = ingest_news(item)
    return response.model_dump()


@app.post("/analyze_news/{news_id}")
async def analyze_news_endpoint(news_id: str):
    cleaned = load_clean_news(news_id)
    raw = load_raw_news(news_id)
    if not cleaned or not raw:
        raise HTTPException(status_code=404, detail="News item not found")

    tickers = json.loads(cleaned["tickers_json"])
    results = []
    retrieved_payload: dict[str, Any] = {}
    llm_payload: dict[str, Any] = {}

    for ticker in tickers:
        query = f"{raw['title']} {raw['content']} {ticker}"
        chunks = retrieve_context(ticker=ticker, query=query, top_k=6)
        retrieved_payload[ticker] = [chunk.model_dump() for chunk in chunks]
        analysis = analyze_article(ticker=ticker, article=cleaned["cleaned_text"], context=chunks)
        if analysis is None:
            llm_payload[ticker] = {"error": "invalid_json"}
            results.append({"ticker": ticker, "analysis": None, "retrieved_chunks": chunks, "error": "invalid_json"})
            continue
        llm_payload[ticker] = analysis.model_dump()
        apply_event_update(
            ticker=ticker,
            news_id=news_id,
            published_at=raw["published_at"],
            analysis=analysis,
        )
        results.append({"ticker": ticker, "analysis": analysis, "retrieved_chunks": chunks, "error": None})

    db.execute(
        """
        INSERT INTO analysis_runs (news_id, tickers_json, retrieved_chunks_json, llm_output_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            news_id,
            json.dumps(tickers),
            json.dumps(retrieved_payload),
            json.dumps(llm_payload),
            datetime.utcnow().isoformat(),
        ),
    )

    return AnalyzeResponse(news_id=news_id, results=results).model_dump()
