from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.models import LLMImpact, RetrievedChunk

PROMPT_TEMPLATE = """
[PASTE THE PROMPT TEMPLATE HERE EXACTLY]
"""


def build_prompt(ticker: str, article: dict[str, Any], retrieved_chunks: list[RetrievedChunk]) -> str:
    formatted_chunks = []
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        formatted_chunks.append(
            f"[{idx}] layer={chunk.layer} source_id={chunk.source_id} text={chunk.text}"
        )
    joined_chunks = "\n".join(formatted_chunks)
    return PROMPT_TEMPLATE.format(
        TICKER=ticker,
        SOURCE=article["source"],
        PUBLISHED_AT=article["published_at"],
        TITLE=article["title"],
        ARTICLE_TEXT=article["cleaned_text"],
        RETRIEVED_CHUNKS=joined_chunks,
    )


class LLMProvider:
    def analyze(self, prompt: str) -> str:
        raise NotImplementedError


class StubLLMProvider(LLMProvider):
    def analyze(self, prompt: str) -> str:
        layer = "state"
        source_id = "snapshot"
        for line in prompt.splitlines():
            if line.strip().startswith("[1]") and "layer=" in line and "source_id=" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("layer="):
                        layer = part.split("=", 1)[1]
                    if part.startswith("source_id="):
                        source_id = part.split("=", 1)[1]
                break
        payload = {
            "ticker": "AAPL",
            "event_type": "earnings",
            "is_new_information": True,
            "impact_score": 0.2,
            "horizon": "swing",
            "severity": "med",
            "confidence": 0.72,
            "risk_flags": [],
            "contradiction_flags": ["none"],
            "summary": "Earnings update driven by recent results.",
            "evidence": "Reported earnings and guidance details.",
            "citations": [
                {"layer": layer, "source_id": source_id, "why": "context"},
            ],
        }
        return json.dumps(payload)


class FailingLLMProvider(LLMProvider):
    def analyze(self, prompt: str) -> str:
        return "{invalid-json"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def analyze(self, prompt: str) -> str:
        raise NotImplementedError("Wire up a real LLM provider here.")


@dataclass
class LLMResult:
    output: LLMImpact | None
    raw: str
    error: str | None


def parse_output(raw_json: str) -> LLMImpact:
    parsed = json.loads(raw_json)
    return LLMImpact.model_validate(parsed)


def validate_output(parsed: LLMImpact, retrieved_chunks: list[RetrievedChunk]) -> None:
    if not parsed.citations:
        raise ValueError("Citations must be non-empty.")
    valid_pairs = {(chunk.layer, chunk.source_id) for chunk in retrieved_chunks}
    for citation in parsed.citations:
        if (citation.layer, citation.source_id) not in valid_pairs:
            raise ValueError("Citation references missing chunk.")
    allowed = {"conflicts_with_guidance", "conflicts_with_state", "none"}
    if not any(flag in allowed for flag in parsed.contradiction_flags):
        raise ValueError("Invalid contradiction flags.")


def analyze_with_provider(
    prompt: str,
    retrieved_chunks: list[RetrievedChunk],
    provider: LLMProvider,
) -> LLMResult:
    raw = provider.analyze(prompt)
    try:
        parsed = parse_output(raw)
        validate_output(parsed, retrieved_chunks)
        return LLMResult(output=parsed, raw=raw, error=None)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return LLMResult(output=None, raw=raw, error=str(exc))
