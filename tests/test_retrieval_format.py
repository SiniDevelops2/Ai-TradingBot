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


def test_retrieval_format(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    from app.rag import build_query, retrieve_top_k, upsert_chunk
    from app.llm_analyzer import build_prompt

    upsert_chunk("snapshot", "AAPL", "state", "snapshot", "state text")

    query = build_query("Apple earnings", "Apple reported earnings", "AAPL")
    chunks = retrieve_top_k("AAPL", query, top_k=1)
    assert chunks
    chunk = chunks[0]
    assert chunk.layer
    assert chunk.source_id
    assert chunk.text

    article = {
        "source": "mock",
        "published_at": "2025-01-01T10:00:00Z",
        "title": "Apple earnings",
        "cleaned_text": "apple reported earnings",
    }
    prompt = build_prompt("AAPL", article, chunks)
    assert "layer=" in prompt
    assert "source_id=" in prompt
