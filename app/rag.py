from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import math

from app import db
from app.models import RAGChunk
from app.utils import clean_text

try:
    import faiss  # type: ignore

    FAISS_AVAILABLE = True
except Exception:
    faiss = None
    FAISS_AVAILABLE = False


@dataclass
class VectorRecord:
    vector: list[float]
    metadata: dict[str, Any]


class EmbeddingProvider:
    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        cleaned = clean_text(text)
        total = sum(ord(ch) for ch in cleaned)
        return [((total + i * 31) % 97) / 97.0 for i in range(self.dim)]


class VectorStore:
    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self.records: list[VectorRecord] = []

    def add(self, vector: list[float], metadata: dict[str, Any]) -> None:
        self.records.append(VectorRecord(vector=vector, metadata=metadata))

    def search(self, vector: list[float], top_k: int = 6) -> list[VectorRecord]:
        scored = []
        for record in self.records:
            score = cosine_similarity(vector, record.vector)
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:top_k]]


class FaissVectorStore(VectorStore):
    def __init__(self, dim: int = 16) -> None:
        super().__init__(dim=dim)
        self.index = faiss.IndexFlatIP(dim)

    def add(self, vector: list[float], metadata: dict[str, Any]) -> None:
        import numpy as np

        self.records.append(VectorRecord(vector=vector, metadata=metadata))
        self.index.add(np.array([vector], dtype="float32"))

    def search(self, vector: list[float], top_k: int = 6) -> list[VectorRecord]:
        import numpy as np

        if not self.records:
            return []
        distances, indices = self.index.search(np.array([vector], dtype="float32"), top_k)
        results = []
        for idx in indices[0]:
            if idx == -1:
                continue
            results.append(self.records[idx])
        return results


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


EMBEDDER = EmbeddingProvider()
STORE = FaissVectorStore(dim=EMBEDDER.dim) if FAISS_AVAILABLE else VectorStore(dim=EMBEDDER.dim)


def refresh_store() -> None:
    STORE.records.clear()
    if FAISS_AVAILABLE:
        STORE.index.reset()

    profile_rows = db.fetch_all("SELECT * FROM profile")
    for row in profile_rows:
        vector = EMBEDDER.embed(row["profile_text"])
        STORE.add(
            vector,
            {
                "ticker": row["ticker"],
                "layer": "profile",
                "source_id": row["ticker"],
                "timestamp": row["updated_at"],
                "text": row["profile_text"],
            },
        )

    event_rows = db.fetch_all(
        "SELECT id, ticker, summary, evidence, created_at FROM state_events"
    )
    for row in event_rows:
        text = f"{row['summary']} {row['evidence']}"
        vector = EMBEDDER.embed(text)
        STORE.add(
            vector,
            {
                "ticker": row["ticker"],
                "layer": "event",
                "source_id": str(row["id"]),
                "timestamp": row["created_at"],
                "text": text,
            },
        )

    snapshot_rows = db.fetch_all("SELECT * FROM state_snapshot")
    for row in snapshot_rows:
        vector = EMBEDDER.embed(row["state_json"])
        STORE.add(
            vector,
            {
                "ticker": row["ticker"],
                "layer": "state",
                "source_id": row["ticker"],
                "timestamp": row["updated_at"],
                "text": row["state_json"],
            },
        )


def retrieve_context(ticker: str, query: str, top_k: int = 6) -> list[RAGChunk]:
    refresh_store()
    query_vector = EMBEDDER.embed(query)
    results = STORE.search(query_vector, top_k=top_k)
    chunks: list[RAGChunk] = []
    for record in results:
        if record.metadata.get("ticker") != ticker:
            continue
        text = record.metadata.get("text", "")
        snippet = clean_text(text)[:280]
        timestamp = record.metadata.get("timestamp")
        timestamp_dt = datetime.fromisoformat(timestamp) if timestamp else None
        chunks.append(
            RAGChunk(
                layer=record.metadata["layer"],
                source_id=record.metadata["source_id"],
                snippet=snippet,
                timestamp=timestamp_dt,
            )
        )
    return chunks


def seed_profiles_if_missing() -> None:
    rows = db.fetch_all("SELECT ticker FROM profile")
    if rows:
        return
    profiles = {
        "AAPL": "Apple designs consumer electronics and services with a focus on iPhone, Mac, wearables, and recurring services revenue. Key risks include supply chain disruption and regulatory scrutiny.",
        "TSLA": "Tesla develops electric vehicles, energy storage, and software-led vehicle platforms. Key risks include demand volatility, regulatory changes, and manufacturing ramp constraints.",
    }
    for ticker, text in profiles.items():
        db.upsert_profile(ticker, text)
