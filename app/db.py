from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("APP_DB_PATH", "data/app.db"))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS profile (
            ticker TEXT PRIMARY KEY,
            profile_text TEXT NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE IF NOT EXISTS state_snapshot (
            ticker TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE IF NOT EXISTS state_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            impact_score REAL NOT NULL,
            horizon TEXT NOT NULL,
            summary TEXT NOT NULL,
            source_id TEXT NOT NULL,
            start_ts DATETIME NOT NULL,
            end_ts DATETIME,
            confidence REAL NOT NULL,
            evidence TEXT NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news_raw (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            published_at DATETIME NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news_clean (
            id TEXT PRIMARY KEY,
            cleaned_text TEXT NOT NULL,
            hash TEXT NOT NULL,
            tickers_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id TEXT NOT NULL,
            tickers_json TEXT NOT NULL,
            retrieved_chunks_json TEXT NOT NULL,
            llm_output_json TEXT NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_state_events_guard
            ON state_events (ticker, event_type, source_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_news_clean_hash
            ON news_clean (hash);
        """
    )
    conn.commit()
    conn.close()


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    conn = get_connection()
    conn.execute(query, params)
    conn.commit()
    conn.close()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = get_connection()
    cur = conn.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def upsert_profile(ticker: str, profile_text: str) -> None:
    now = datetime.utcnow().isoformat()
    execute(
        """
        INSERT INTO profile (ticker, profile_text, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            profile_text=excluded.profile_text,
            updated_at=excluded.updated_at
        """,
        (ticker, profile_text, now),
    )


def store_snapshot(ticker: str, state_json: dict[str, Any]) -> None:
    now = datetime.utcnow().isoformat()
    execute(
        """
        INSERT INTO state_snapshot (ticker, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            state_json=excluded.state_json,
            updated_at=excluded.updated_at
        """,
        (ticker, json.dumps(state_json), now),
    )
