from __future__ import annotations

import importlib
from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def setup_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    import app.db as db

    importlib.reload(db)
    db.init_db()

    import app.rag as rag

    importlib.reload(rag)
    rag.seed_profiles_if_missing()

    import app.main as main

    importlib.reload(main)
    return main.app, db


def test_ingest_analyze_pipeline(tmp_path, monkeypatch):
    app, db = setup_app(tmp_path, monkeypatch)
    client = TestClient(app)
    news_payload = {
        "id": "news-1",
        "source": "mock",
        "published_at": datetime.utcnow().isoformat(),
        "title": "Apple earnings beat expectations",
        "content": "Apple reported earnings and raised guidance for next quarter.",
    }
    ingest_resp = client.post("/ingest_news", json=news_payload)
    assert ingest_resp.status_code == 200
    assert "AAPL" in ingest_resp.json()["tickers"]

    analyze_resp = client.post("/analyze_news/news-1")
    assert analyze_resp.status_code == 200
    payload = analyze_resp.json()
    assert payload["results"]

    snapshot = db.fetch_one("SELECT * FROM state_snapshot WHERE ticker = ?", ("AAPL",))
    assert snapshot is not None

    audit = db.fetch_one("SELECT * FROM analysis_runs WHERE news_id = ?", ("news-1",))
    assert audit is not None
