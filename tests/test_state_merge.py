from __future__ import annotations

import importlib
from datetime import datetime

import pytest

pytest.importorskip("pydantic")


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    import app.db as db

    importlib.reload(db)
    db.init_db()
    return db


def build_analysis(**overrides):
    from app.models import LLMImpact

    payload = {
        "ticker": "AAPL",
        "event_type": "guidance",
        "is_new_information": True,
        "impact_score": 0.2,
        "horizon": "swing",
        "severity": "med",
        "confidence": 0.6,
        "risk_flags": [],
        "contradiction_flags": ["none"],
        "summary": "Company issued guidance update.",
        "evidence": "Guidance update evidence.",
        "citations": [],
    }
    payload.update(overrides)
    return LLMImpact.model_validate(payload)


def test_state_merge_flow(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    from app.state_manager import apply_update
    import app.db as db

    analysis = build_analysis()
    apply_update("AAPL", analysis, {"id": "news-1", "published_at": "2025-01-01T10:00:00Z"})

    updated = build_analysis(summary="Company issued guidance update with details.", confidence=0.8)
    apply_update("AAPL", updated, {"id": "news-2", "published_at": "2025-01-02T10:00:00Z"})

    closing = build_analysis(
        summary="Guidance issue resolved after settlement.",
        contradiction_flags=["conflicts_with_state"],
        confidence=0.8,
    )
    apply_update("AAPL", closing, {"id": "news-3", "published_at": "2025-01-03T10:00:00Z"})

    idempotent = apply_update(
        "AAPL", closing, {"id": "news-3", "published_at": "2025-01-03T10:00:00Z"}
    )
    assert idempotent["status"] == "idempotent"

    rows = db.fetch_all("SELECT * FROM state_events")
    statuses = {row["status"] for row in rows}
    assert "closed" in statuses
