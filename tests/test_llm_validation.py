from __future__ import annotations

import pytest

pytest.importorskip("pydantic")


def test_llm_validation_rejects_bad_citation():
    from app.llm_analyzer import validate_output
    from app.models import Citation, LLMImpact, RetrievedChunk

    retrieved = [
        RetrievedChunk(chunk_key="snapshot", layer="state", source_id="snapshot", text="state")
    ]
    impact = LLMImpact(
        ticker="AAPL",
        event_type="earnings",
        is_new_information=True,
        impact_score=0.2,
        horizon="swing",
        severity="med",
        confidence=0.7,
        risk_flags=[],
        contradiction_flags=["none"],
        summary="summary",
        evidence="evidence",
        citations=[Citation(layer="state", source_id="missing", why="bad")],
    )

    with pytest.raises(ValueError):
        validate_output(impact, retrieved)
