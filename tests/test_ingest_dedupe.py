from __future__ import annotations

import importlib

import pytest

pytest.importorskip("pydantic")


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    import app.db as db

    importlib.reload(db)
    db.init_db()
    return db


def test_ingest_dedupe(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    from app.ingest import ingest_news
    from app.models import NewsPayload

    payload = NewsPayload(
        id="news-1",
        source="mock",
        published_at="2025-01-01T10:00:00Z",
        title="Apple earnings",
        content="Apple reported earnings.",
    )
    first = ingest_news(payload)
    second = ingest_news(payload)

    assert first.status == "inserted"
    assert second.status == "duplicate"

    import app.db as db

    rows = db.fetch_all("SELECT * FROM news_clean")
    assert len(rows) == 1
