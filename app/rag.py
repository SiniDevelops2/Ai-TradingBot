from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from app import db
from app.models import RetrievedChunk
from app.utils import clean_text, simple_keywords


class EmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        cleaned = clean_text(text)
        total = sum(ord(char) for char in cleaned)
        return [((total + idx * 31) % 97) / 97.0 for idx in range(self.dim)]


@dataclass
class VectorChunk:
    chunk_key: str
    ticker: str
    layer: str
    source_id: str
    text: str
    embedding: list[float]


class VectorStore:
    def __init__(self, embedder: EmbeddingProvider) -> None:
        self.embedder = embedder

    def upsert(self, chunk_key: str, ticker: str, layer: str, source_id: str, text: str) -> None:
        embedding = self.embedder.embed(text)
        db.upsert_vector_chunk(chunk_key, ticker, layer, source_id, text, embedding)

    def query(self, ticker: str, query_text: str, top_k: int = 6) -> list[VectorChunk]:
        rows = db.fetch_all("SELECT * FROM vector_chunks WHERE ticker = ?", (ticker,))
        query_vec = self.embedder.embed(query_text)
        scored: list[tuple[float, VectorChunk]] = []
        for row in rows:
            embedding = json.loads(row["embedding_json"])
            score = cosine_similarity(query_vec, embedding)
            scored.append(
                (
                    score,
                    VectorChunk(
                        chunk_key=row["chunk_key"],
                        ticker=row["ticker"],
                        layer=row["layer"],
                        source_id=row["source_id"],
                        text=row["text"],
                        embedding=embedding,
                    ),
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


EMBEDDER = DeterministicEmbeddingProvider()
VECTOR_STORE = VectorStore(EMBEDDER)


def build_query(title: str, cleaned_text: str, ticker: str) -> str:
    keywords = simple_keywords(f"{title} {cleaned_text}")
    return " ".join([ticker, *keywords])


def retrieve_top_k(ticker: str, query_text: str, top_k: int = 6) -> list[RetrievedChunk]:
    chunks = VECTOR_STORE.query(ticker, query_text, top_k=top_k)
    return [
        RetrievedChunk(
            chunk_key=chunk.chunk_key,
            layer=chunk.layer,
            source_id=chunk.source_id,
            text=chunk.text,
        )
        for chunk in chunks
    ]


def upsert_chunk(chunk_key: str, ticker: str, layer: str, source_id: str, text: str) -> None:
    VECTOR_STORE.upsert(chunk_key, ticker, layer, source_id, text)


def ensure_baseline_chunk(ticker: str) -> None:
    existing = db.fetch_one("SELECT chunk_key FROM vector_chunks WHERE ticker = ?", (ticker,))
    if existing:
        return
    upsert_chunk("snapshot", ticker, "state", "snapshot", "{}")
