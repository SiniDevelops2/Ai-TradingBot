from __future__ import annotations

import re

ALIAS_MAP = {
    "apple": "AAPL",
    "apple inc": "AAPL",
    "tesla": "TSLA",
    "tesla motors": "TSLA",
    "microsoft": "MSFT",
}

TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")


def extract_tickers(cleaned_text: str, title: str) -> list[dict[str, float | str]]:
    combined = f"{title} {cleaned_text}"
    found = set()

    for match in TICKER_PATTERN.findall(combined):
        found.add(match.upper())

    lowered = combined.lower()
    for alias, ticker in ALIAS_MAP.items():
        if alias in lowered:
            found.add(ticker)

    results = []
    for ticker in sorted(found):
        results.append({"ticker": ticker, "confidence": 0.9})
    return results
