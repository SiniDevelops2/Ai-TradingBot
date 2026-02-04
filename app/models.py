from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NewsIn(BaseModel):
    id: str
    source: str
    published_at: datetime
    title: str
    content: str


class NewsClean(BaseModel):
    id: str
    cleaned_text: str
    hash: str
    tickers: list[str]


class RAGChunk(BaseModel):
    layer: Literal["profile", "state", "event"]
    source_id: str
    snippet: str
    timestamp: datetime | None = None


class Citation(BaseModel):
    layer: Literal["profile", "state", "event"]
    source_id: str
    why: str


class LLMImpactResult(BaseModel):
    ticker: str
    event_type: Literal[
        "lawsuit",
        "earnings",
        "guidance",
        "product_launch",
        "regulatory",
        "macro",
        "other",
    ]
    is_new_information: bool
    impact_score: float = Field(..., ge=-1.0, le=1.0)
    horizon: Literal["intraday", "swing", "long"]
    severity: Literal["low", "med", "high"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_flags: list[str]
    contradiction_flags: list[str]
    summary: str
    evidence: str
    citations: list[Citation]


class AnalyzeResult(BaseModel):
    ticker: str
    analysis: LLMImpactResult | None
    retrieved_chunks: list[RAGChunk]
    error: str | None = None


class AnalyzeResponse(BaseModel):
    news_id: str
    results: list[AnalyzeResult]


class StateEvent(BaseModel):
    event_type: str
    status: str
    severity: str
    impact_score: float
    horizon: str
    summary: str
    source_id: str
    start_ts: datetime
    end_ts: datetime | None
    confidence: float
    evidence: str


class StateSnapshot(BaseModel):
    ticker: str
    open_events: list[dict[str, Any]]
    recent_catalysts: list[dict[str, Any]]
    key_risks: list[dict[str, Any]]
    last_updated: datetime


class IngestResponse(BaseModel):
    id: str
    deduped: bool
    tickers: list[str]
