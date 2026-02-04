from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NewsPayload(BaseModel):
    id: str
    source: str
    published_at: str
    title: str
    content: str


class IngestResult(BaseModel):
    id: str
    status: Literal["inserted", "duplicate"]
    tickers: list[dict[str, float | str]]


class RetrievedChunk(BaseModel):
    chunk_key: str
    layer: str
    source_id: str
    text: str


class Citation(BaseModel):
    layer: str
    source_id: str
    why: str


class LLMImpact(BaseModel):
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
    status: str
    error_message: str | None
    analysis: LLMImpact | None


class AnalyzeResponse(BaseModel):
    news_id: str
    results: list[AnalyzeResult]


class StateSnapshot(BaseModel):
    ticker: str
    open_events: list[dict[str, str | float]]
    recent_catalysts: list[dict[str, str | float]]
    key_risks: list[dict[str, str | float]]
    last_updated: datetime
