from __future__ import annotations

import re
from typing import Iterable

ALIAS_MAP = {
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "AAPL": "AAPL",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
}

TICKER_RE = re.compile(r"\$([A-Z]{1,5})")


def extract_tickers(texts: Iterable[str]) -> list[str]:
    joined = " ".join(texts).upper()
    tickers = set()
    for match in TICKER_RE.findall(joined):
        tickers.add(match)
    for alias, ticker in ALIAS_MAP.items():
        if alias in joined:
            tickers.add(ticker)
    return sorted(tickers)
