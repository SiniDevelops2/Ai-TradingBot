from __future__ import annotations

import json
from datetime import datetime

from app import db
from app.models import IngestResponse, NewsIn
from app.ticker_linker import extract_tickers
from app.utils import clean_text, hash_text


def ingest_news(item: NewsIn) -> IngestResponse:
    db.init_db()
    cleaned_text = clean_text(f"{item.title} {item.content}")
    content_hash = hash_text(cleaned_text)
    deduped = False

    existing = db.fetch_one("SELECT id FROM news_clean WHERE hash = ?", (content_hash,))
    if existing:
        deduped = True
    else:
        db.execute(
            """
            INSERT INTO news_raw (id, source, published_at, title, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.source,
                item.published_at.isoformat(),
                item.title,
                item.content,
            ),
        )

    tickers = extract_tickers([item.title, item.content])
    if not deduped:
        db.execute(
            """
            INSERT INTO news_clean (id, cleaned_text, hash, tickers_json)
            VALUES (?, ?, ?, ?)
            """,
            (item.id, cleaned_text, content_hash, json.dumps(tickers)),
        )
    return IngestResponse(id=item.id, deduped=deduped, tickers=tickers)


def load_clean_news(news_id: str) -> dict[str, str] | None:
    row = db.fetch_one("SELECT * FROM news_clean WHERE id = ?", (news_id,))
    if not row:
        return None
    return {
        "id": row["id"],
        "cleaned_text": row["cleaned_text"],
        "hash": row["hash"],
        "tickers_json": row["tickers_json"],
    }


def load_raw_news(news_id: str) -> dict[str, str] | None:
    row = db.fetch_one("SELECT * FROM news_raw WHERE id = ?", (news_id,))
    if not row:
        return None
    return {
        "id": row["id"],
        "source": row["source"],
        "published_at": row["published_at"],
        "title": row["title"],
        "content": row["content"],
    }
