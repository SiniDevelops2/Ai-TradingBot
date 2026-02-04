from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException

from app import db
from app.ingest import ingest_news, load_clean_news, parse_tickers_json
from app.llm_analyzer import StubLLMProvider, analyze_with_provider, build_prompt
from app.models import AnalyzeResponse, AnalyzeResult, NewsPayload
from app.rag import build_query, ensure_baseline_chunk, retrieve_top_k
from app.state_manager import apply_update

app = FastAPI(title="Company State RAG MVP")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.post("/ingest_news")
async def ingest_news_endpoint(payload: NewsPayload) -> dict[str, Any]:
    result = ingest_news(payload)
    return result.model_dump()


@app.post("/analyze_news/{news_id}")
async def analyze_news_endpoint(news_id: str) -> dict[str, Any]:
    article = load_clean_news(news_id)
    if not article:
        raise HTTPException(status_code=404, detail="News item not found")

    tickers = parse_tickers_json(article["tickers_json"])
    results: list[AnalyzeResult] = []
    provider = StubLLMProvider()

    for item in tickers:
        ticker = item["ticker"]
        ensure_baseline_chunk(ticker)
        query = build_query(article["title"], article["cleaned_text"], ticker)
        chunks = retrieve_top_k(ticker, query, top_k=6)
        prompt = build_prompt(ticker, article, chunks)
        llm_result = analyze_with_provider(prompt, chunks, provider)

        if llm_result.output is None:
            db.insert_analysis_run(
                news_id,
                ticker,
                [chunk.model_dump() for chunk in chunks],
                llm_result.raw,
                "failed",
                llm_result.error,
            )
            results.append(
                AnalyzeResult(
                    ticker=ticker,
                    status="failed",
                    error_message=llm_result.error,
                    analysis=None,
                )
            )
            continue

        db.insert_analysis_run(
            news_id,
            ticker,
            [chunk.model_dump() for chunk in chunks],
            llm_result.raw,
            "success",
            None,
        )
        apply_update(
            ticker,
            llm_result.output,
            {"id": article["id"], "published_at": article["published_at"]},
        )
        results.append(
            AnalyzeResult(
                ticker=ticker,
                status="success",
                error_message=None,
                analysis=llm_result.output,
            )
        )

    response = AnalyzeResponse(news_id=news_id, results=results)
    return response.model_dump()
