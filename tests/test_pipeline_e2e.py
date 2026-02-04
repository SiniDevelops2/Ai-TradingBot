from __future__ import annotations

import importlib

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("pydantic")
from fastapi.testclient import TestClient


def setup_app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    import app.db as db

    importlib.reload(db)
    db.init_db()

    import app.main as main

    importlib.reload(main)
    return main.app, db


def test_pipeline_e2e(tmp_path, monkeypatch):
    app, db = setup_app(tmp_path, monkeypatch)
    client = TestClient(app)
    payload = {
        "id": "news-1",
        "source": "mock",
        "published_at": "2025-01-01T10:00:00Z",
        "title": "Apple earnings beat",
        "content": "Apple reported earnings and guidance.",
    }
    ingest_resp = client.post("/ingest_news", json=payload)
    assert ingest_resp.status_code == 200

    analyze_resp = client.post("/analyze_news/news-1")
    assert analyze_resp.status_code == 200
    result = analyze_resp.json()
    assert result["results"]

    audit = db.fetch_one("SELECT * FROM analysis_runs WHERE news_id = ?", ("news-1",))
    assert audit is not None

    snapshot = db.fetch_one("SELECT * FROM state_snapshot WHERE ticker = ?", ("AAPL",))
    assert snapshot is not None
