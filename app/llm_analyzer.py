from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.models import LLMImpactResult, RAGChunk

PROMPT_TEMPLATE = """
You are a market impact analyst. Return STRICT JSON only with the schema below.
If uncertain or insufficient evidence, set is_new_information=false and confidence low.
Never output BUY/SELL recommendations.

Schema:
{
  "ticker": "AAPL",
  "event_type": "lawsuit|earnings|guidance|product_launch|regulatory|macro|other",
  "is_new_information": true/false,
  "impact_score": -1.0..1.0,
  "horizon": "intraday|swing|long",
  "severity": "low|med|high",
  "confidence": 0..1,
  "risk_flags": ["rumor","low_quality_source","ambiguous","already_priced_in"],
  "contradiction_flags": ["conflicts_with_guidance","conflicts_with_state","none"],
  "summary": "1-2 sentence",
  "evidence": "1 short excerpt from the article",
  "citations": [{"layer":"profile|state|event","source_id":"...","why":"..."}]
}

Context chunks (cite by layer + source_id):
{context}

Article:
{article}
"""

# Example JSON (for stub testing only; real LLM must not rely on this):
# {
#   "ticker": "AAPL",
#   "event_type": "earnings",
#   "is_new_information": true,
#   "impact_score": 0.3,
#   "horizon": "swing",
#   "severity": "med",
#   "confidence": 0.7,
#   "risk_flags": [],
#   "contradiction_flags": ["none"],
#   "summary": "Apple reported a quarterly beat and raised guidance.",
#   "evidence": "Apple reported earnings above expectations.",
#   "citations": [{"layer": "profile", "source_id": "AAPL", "why": "baseline profile"}]
# }


@dataclass
class LLMResponse:
    raw_json: dict[str, Any] | None
    error: str | None = None


class LLMClient:
    def analyze(self, ticker: str, article: str, context: list[RAGChunk]) -> LLMResponse:
        lowered = article.lower()
        event_type = "other"
        if "earnings" in lowered:
            event_type = "earnings"
        elif "guidance" in lowered or "forecast" in lowered:
            event_type = "guidance"
        elif "lawsuit" in lowered or "sued" in lowered:
            event_type = "lawsuit"
        elif "launch" in lowered or "product" in lowered:
            event_type = "product_launch"
        elif "regulator" in lowered or "regulatory" in lowered:
            event_type = "regulatory"
        elif "macro" in lowered or "inflation" in lowered:
            event_type = "macro"

        confidence = 0.6 if event_type != "other" else 0.3
        impact_score = 0.2 if event_type in {"product_launch", "earnings"} else -0.2

        citations = []
        for chunk in context[:2]:
            citations.append(
                {"layer": chunk.layer, "source_id": chunk.source_id, "why": "background"}
            )

        payload = {
            "ticker": ticker,
            "event_type": event_type,
            "is_new_information": True,
            "impact_score": impact_score,
            "horizon": "swing",
            "severity": "med" if abs(impact_score) > 0.15 else "low",
            "confidence": confidence,
            "risk_flags": [],
            "contradiction_flags": ["none"],
            "summary": article[:140].strip(),
            "evidence": article[:120].strip(),
            "citations": citations,
        }
        return LLMResponse(raw_json=payload)


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def analyze(self, ticker: str, article: str, context: list[RAGChunk]) -> LLMResponse:
        raise NotImplementedError("Connect to OpenAI API here; keep optional for MVP.")


def analyze_article(
    ticker: str,
    article: str,
    context: list[RAGChunk],
    client: LLMClient | None = None,
) -> LLMImpactResult | None:
    client = client or LLMClient()
    response = client.analyze(ticker=ticker, article=article, context=context)
    if response.error:
        return None
    if response.raw_json is None:
        return None
    try:
        return LLMImpactResult.model_validate(response.raw_json)
    except ValidationError:
        return None
