from __future__ import annotations

import json
from datetime import datetime

from app import db
from app.models import LLMImpactResult


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _summary_similarity(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _is_closure(summary: str, contradiction_flags: list[str]) -> bool:
    lowered = summary.lower()
    closure_terms = ["resolved", "settled", "closed", "withdrawn", "ended"]
    if any(term in lowered for term in closure_terms):
        return True
    return "conflicts_with_state" in contradiction_flags


def apply_event_update(
    ticker: str,
    news_id: str,
    published_at: str | datetime,
    analysis: LLMImpactResult,
) -> dict[str, str]:
    published_dt = _parse_ts(published_at)
    existing = db.fetch_one(
        "SELECT id FROM state_events WHERE ticker = ? AND event_type = ? AND source_id = ?",
        (ticker, analysis.event_type, news_id),
    )
    if existing:
        return {"status": "idempotent"}

    open_events = db.fetch_all(
        "SELECT * FROM state_events WHERE ticker = ? AND status = 'open'",
        (ticker,),
    )
    matched_event = None
    for row in open_events:
        if row["event_type"] == analysis.event_type:
            matched_event = row
            break
        similarity = _summary_similarity(row["summary"], analysis.summary)
        if similarity > 0.4:
            matched_event = row
            break

    closing = _is_closure(analysis.summary, analysis.contradiction_flags)
    if closing and matched_event:
        db.execute(
            """
            UPDATE state_events
            SET status = 'closed', end_ts = ?
            WHERE id = ?
            """,
            (published_dt.isoformat(), matched_event["id"]),
        )

    if closing:
        db.execute(
            """
            INSERT INTO state_events (
                ticker, event_type, status, severity, impact_score, horizon, summary,
                source_id, start_ts, end_ts, confidence, evidence, created_at
            ) VALUES (?, ?, 'closed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                analysis.event_type,
                analysis.severity,
                analysis.impact_score,
                analysis.horizon,
                analysis.summary,
                news_id,
                published_dt.isoformat(),
                published_dt.isoformat(),
                analysis.confidence,
                analysis.evidence,
                datetime.utcnow().isoformat(),
            ),
        )
        rebuild_snapshot(ticker)
        return {"status": "closed"}

    if matched_event:
        should_update = (
            analysis.confidence > matched_event["confidence"]
            or published_dt.isoformat() > matched_event["start_ts"]
        )
        if should_update:
            db.execute(
                """
                UPDATE state_events
                SET severity = ?, impact_score = ?, horizon = ?, summary = ?,
                    confidence = ?, evidence = ?, start_ts = ?
                WHERE id = ?
                """,
                (
                    analysis.severity,
                    analysis.impact_score,
                    analysis.horizon,
                    analysis.summary,
                    analysis.confidence,
                    analysis.evidence,
                    published_dt.isoformat(),
                    matched_event["id"],
                ),
            )
            rebuild_snapshot(ticker)
            return {"status": "updated"}

    db.execute(
        """
        INSERT INTO state_events (
            ticker, event_type, status, severity, impact_score, horizon, summary,
            source_id, start_ts, end_ts, confidence, evidence, created_at
        ) VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            ticker,
            analysis.event_type,
            analysis.severity,
            analysis.impact_score,
            analysis.horizon,
            analysis.summary,
            news_id,
            published_dt.isoformat(),
            analysis.confidence,
            analysis.evidence,
            datetime.utcnow().isoformat(),
        ),
    )
    rebuild_snapshot(ticker)
    return {"status": "inserted"}


def rebuild_snapshot(ticker: str) -> None:
    rows = db.fetch_all(
        """
        SELECT * FROM state_events
        WHERE ticker = ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (ticker,),
    )
    open_events = [row for row in rows if row["status"] == "open"]
    recent_catalysts = []
    key_risks = []

    for row in rows:
        entry = {
            "event_type": row["event_type"],
            "summary": row["summary"],
            "status": row["status"],
            "impact_score": row["impact_score"],
            "start_ts": row["start_ts"],
            "source_id": row["source_id"],
        }
        if len(recent_catalysts) < 10:
            recent_catalysts.append(entry)

    for row in open_events:
        if row["severity"] == "high" or row["impact_score"] < 0:
            key_risks.append(
                {
                    "event_type": row["event_type"],
                    "summary": row["summary"],
                    "severity": row["severity"],
                    "impact_score": row["impact_score"],
                    "source_id": row["source_id"],
                }
            )

    snapshot = {
        "ticker": ticker,
        "open_events": [
            {
                "event_type": row["event_type"],
                "summary": row["summary"],
                "start_ts": row["start_ts"],
                "severity": row["severity"],
                "impact_score": row["impact_score"],
                "horizon": row["horizon"],
                "confidence": row["confidence"],
                "source_id": row["source_id"],
            }
            for row in open_events
        ],
        "recent_catalysts": recent_catalysts,
        "key_risks": key_risks,
        "last_updated": datetime.utcnow().isoformat(),
    }
    db.store_snapshot(ticker, snapshot)
