from __future__ import annotations

from datetime import datetime

from app import db
from app.models import LLMImpact
from app.rag import upsert_chunk


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _summary_similarity(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _should_close(summary: str, contradiction_flags: list[str], confidence: float) -> bool:
    lowered = summary.lower()
    resolved_terms = {"resolved", "settled", "closed", "withdrawn"}
    if any(term in lowered for term in resolved_terms):
        return True
    return "conflicts_with_state" in contradiction_flags and confidence >= 0.75


def apply_update(ticker: str, analysis: LLMImpact, news_meta: dict[str, str]) -> dict[str, str]:
    if not analysis.is_new_information:
        return {"status": "ignored"}

    guard = db.fetch_one(
        """
        SELECT id FROM state_events
        WHERE ticker = ? AND source_id = ? AND event_type = ?
        """,
        (ticker, news_meta["id"], analysis.event_type),
    )
    if guard:
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
        if _summary_similarity(row["summary"], analysis.summary) > 0.4:
            matched_event = row
            break

    if _should_close(analysis.summary, analysis.contradiction_flags, analysis.confidence):
        if matched_event:
            db.execute(
                "UPDATE state_events SET status = 'closed', end_ts = ? WHERE id = ?",
                (news_meta["published_at"], matched_event["id"]),
            )
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
                news_meta["id"],
                news_meta["published_at"],
                news_meta["published_at"],
                analysis.confidence,
                analysis.evidence,
                db.utc_now(),
            ),
        )
        rebuild_snapshot(ticker)
        return {"status": "closed"}

    if matched_event:
        should_update = (
            analysis.confidence > matched_event["confidence"]
            or news_meta["published_at"] > matched_event["start_ts"]
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
                    news_meta["published_at"],
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
            news_meta["id"],
            news_meta["published_at"],
            analysis.confidence,
            analysis.evidence,
            db.utc_now(),
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
        "last_updated": db.utc_now(),
    }
    db.upsert_snapshot(ticker, snapshot)

    for row in rows:
        chunk_key = f"event:{row['id']}"
        text = f"{row['summary']} {row['evidence']}"
        upsert_chunk(chunk_key, ticker, "event", f"event_{row['id']}", text)

    upsert_chunk("snapshot", ticker, "state", "snapshot", json_dump(snapshot))


def json_dump(payload: dict[str, str | float | list[dict[str, str | float]]]) -> str:
    import json

    return json.dumps(payload)
