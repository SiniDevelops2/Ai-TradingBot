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
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS news_raw (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            published_at TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news_clean (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            published_at TEXT NOT NULL,
            title TEXT NOT NULL,
            cleaned_text TEXT NOT NULL,
            hash TEXT UNIQUE NOT NULL,
            tickers_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            retrieved_chunks_json TEXT NOT NULL,
            llm_output_json TEXT NOT NULL,
            llm_status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL
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
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            confidence REAL NOT NULL,
            evidence TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS state_snapshot (
            ticker TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vector_chunks (
            chunk_key TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            layer TEXT NOT NULL,
            source_id TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_state_event_guard
            ON state_events (ticker, source_id, event_type);
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


def utc_now() -> str:
    return datetime.utcnow().isoformat()


def insert_news_raw(payload: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO news_raw (id, source, published_at, title, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload["id"],
            payload["source"],
            payload["published_at"],
            payload["title"],
            payload["content"],
            utc_now(),
        ),
    )


def insert_news_clean(payload: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO news_clean (
            id, source, published_at, title, cleaned_text, hash, tickers_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["id"],
            payload["source"],
            payload["published_at"],
            payload["title"],
            payload["cleaned_text"],
            payload["hash"],
            json.dumps(payload["tickers"]),
            utc_now(),
        ),
    )


def insert_analysis_run(
    news_id: str,
    ticker: str,
    retrieved_chunks: list[dict[str, Any]],
    llm_output: str,
    status: str,
    error_message: str | None,
) -> None:
    execute(
        """
        INSERT INTO analysis_runs (
            news_id, ticker, retrieved_chunks_json, llm_output_json,
            llm_status, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            news_id,
            ticker,
            json.dumps(retrieved_chunks),
            llm_output,
            status,
            error_message,
            utc_now(),
        ),
    )


def upsert_snapshot(ticker: str, state_json: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO state_snapshot (ticker, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            state_json=excluded.state_json,
            updated_at=excluded.updated_at
        """,
        (ticker, json.dumps(state_json), utc_now()),
    )


def upsert_vector_chunk(
    chunk_key: str,
    ticker: str,
    layer: str,
    source_id: str,
    text: str,
    embedding: list[float],
) -> None:
    execute(
        """
        INSERT INTO vector_chunks (
            chunk_key, ticker, layer, source_id, text, embedding_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chunk_key) DO UPDATE SET
            text=excluded.text,
            embedding_json=excluded.embedding_json,
            created_at=excluded.created_at
        """,
        (
            chunk_key,
            ticker,
            layer,
            source_id,
            text,
            json.dumps(embedding),
            utc_now(),
        ),
    )
