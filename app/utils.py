from __future__ import annotations

import hashlib
import html
import re


def clean_text(text: str) -> str:
    no_html = re.sub(r"<[^>]+>", " ", text)
    normalized = html.unescape(no_html)
    lowered = normalized.lower()
    collapsed = re.sub(r"\s+", " ", lowered).strip()
    return collapsed


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def simple_keywords(text: str, limit: int = 8) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "over",
        "after",
        "about",
        "they",
        "their",
        "has",
        "have",
        "had",
        "were",
        "was",
        "are",
        "but",
        "not",
    }
    tokens = [token.strip(".,:;!?()[]") for token in text.split()]
    keywords = [token for token in tokens if token and token not in stopwords]
    return keywords[:limit]
