from __future__ import annotations

import importlib
from datetime import datetime, timedelta

import pytest

pydantic = pytest.importorskip("pydantic")


def setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    import app.db as db

    importlib.reload(db)
    db.init_db()
    import app.state_manager as state_manager

    importlib.reload(state_manager)
    return db, state_manager


def build_analysis(**overrides):
    from app.models import LLMImpactResult

    base = {
        "ticker": "AAPL",
        "event_type": "guidance",
        "is_new_information": True,
        "impact_score": 0.2,
        "horizon": "swing",
        "severity": "med",
        "confidence": 0.6,
        "risk_flags": [],
        "contradiction_flags": ["none"],
        "summary": "Company issues new guidance update.",
        "evidence": "Guidance raised for Q4.",
        "citations": [],
    }
    base.update(overrides)
    return LLMImpactResult.model_validate(base)


def test_new_open_event_creates_state(tmp_path, monkeypatch):
    db, state_manager = setup_db(tmp_path, monkeypatch)
    analysis = build_analysis()
    result = state_manager.apply_event_update(
        ticker="AAPL",
        news_id="news-1",
        published_at=datetime.utcnow(),
        analysis=analysis,
    )
    assert result["status"] == "inserted"
    rows = db.fetch_all("SELECT * FROM state_events")
    assert len(rows) == 1
    assert rows[0]["status"] == "open"


def test_same_type_newer_updates_open_event(tmp_path, monkeypatch):
    db, state_manager = setup_db(tmp_path, monkeypatch)
    analysis = build_analysis()
    state_manager.apply_event_update("AAPL", "news-1", datetime.utcnow(), analysis)

    newer_analysis = build_analysis(
        summary="Company raises guidance more than expected.",
        confidence=0.8,
    )
    result = state_manager.apply_event_update(
        "AAPL",
        "news-2",
        datetime.utcnow() + timedelta(minutes=5),
        newer_analysis,
    )
    assert result["status"] == "updated"
    rows = db.fetch_all("SELECT * FROM state_events")
    assert len(rows) == 1
    assert "raises guidance" in rows[0]["summary"]


def test_resolution_news_closes_open_event(tmp_path, monkeypatch):
    db, state_manager = setup_db(tmp_path, monkeypatch)
    analysis = build_analysis()
    state_manager.apply_event_update("AAPL", "news-1", datetime.utcnow(), analysis)

    closing_analysis = build_analysis(
        summary="Guidance issue resolved after settlement.",
        contradiction_flags=["conflicts_with_state"],
    )
    result = state_manager.apply_event_update(
        "AAPL",
        "news-3",
        datetime.utcnow() + timedelta(hours=1),
        closing_analysis,
    )
    assert result["status"] == "closed"
    rows = db.fetch_all("SELECT * FROM state_events")
    statuses = {row["status"] for row in rows}
    assert "open" not in statuses
    assert "closed" in statuses


def test_idempotency_on_rerun(tmp_path, monkeypatch):
    db, state_manager = setup_db(tmp_path, monkeypatch)
    analysis = build_analysis()
    state_manager.apply_event_update("AAPL", "news-1", datetime.utcnow(), analysis)
    result = state_manager.apply_event_update("AAPL", "news-1", datetime.utcnow(), analysis)
    assert result["status"] == "idempotent"
    rows = db.fetch_all("SELECT * FROM state_events")
    assert len(rows) == 1
