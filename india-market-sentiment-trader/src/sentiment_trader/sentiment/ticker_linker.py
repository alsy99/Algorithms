from __future__ import annotations

import re

from sentiment_trader.config import WatchlistConfig


class TickerLinker:
    def __init__(self, watchlist: WatchlistConfig) -> None:
        self._patterns: list[tuple[str, re.Pattern[str]]] = []
        for entry in watchlist.symbols:
            terms = [entry.symbol] + entry.aliases
            escaped = [re.escape(t) for t in terms if t]
            if not escaped:
                continue
            pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)
            self._patterns.append((entry.symbol, pattern))

    def link(self, text: str) -> list[str]:
        found: list[str] = []
        for symbol, pattern in self._patterns:
            if pattern.search(text):
                found.append(symbol)
        return found
