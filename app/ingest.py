from __future__ import annotations

import json
from typing import Any

from app import db
from app.models import IngestResult, NewsPayload
from app.ticker_linker import extract_tickers
from app.utils import clean_text, compute_hash


def ingest_news(payload: NewsPayload) -> IngestResult:
    db.init_db()
    cleaned_text = clean_text(payload.content)
    content_hash = compute_hash(cleaned_text)
    tickers = extract_tickers(cleaned_text, payload.title)

    existing = db.fetch_one("SELECT id FROM news_clean WHERE hash = ?", (content_hash,))
    status = "inserted"
    if existing:
        status = "duplicate"
    else:
        db.insert_news_clean(
            {
                "id": payload.id,
                "source": payload.source,
                "published_at": payload.published_at,
                "title": payload.title,
                "cleaned_text": cleaned_text,
                "hash": content_hash,
                "tickers": tickers,
            }
        )

    raw_existing = db.fetch_one("SELECT id FROM news_raw WHERE id = ?", (payload.id,))
    if not raw_existing:
        db.insert_news_raw(
            {
                "id": payload.id,
                "source": payload.source,
                "published_at": payload.published_at,
                "title": payload.title,
                "content": payload.content,
            }
        )

    return IngestResult(id=payload.id, status=status, tickers=tickers)


def load_clean_news(news_id: str) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM news_clean WHERE id = ?", (news_id,))
    if not row:
        return None
    return dict(row)


def parse_tickers_json(raw: str) -> list[dict[str, float | str]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []
