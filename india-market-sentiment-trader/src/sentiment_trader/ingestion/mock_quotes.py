from __future__ import annotations

import asyncio
import random
from datetime import datetime

import structlog

from sentiment_trader.config import WatchlistConfig
from sentiment_trader.models import Quote

logger = structlog.get_logger(__name__)

# Approximate NSE reference prices for mock mode
_SEED_PRICES = {
    "RELIANCE": 2850.0,
    "TCS": 4100.0,
    "HDFCBANK": 1680.0,
    "INFY": 1850.0,
    "SBIN": 820.0,
    "ITC": 465.0,
    "BHARTIARTL": 1580.0,
    "NIFTYBEES": 280.0,
}


class MockQuoteFeed:
    """Simulates live NSE quotes when Angel One stream is unavailable."""

    def __init__(self, watchlist: WatchlistConfig, on_quote) -> None:
        self._watchlist = watchlist
        self._on_quote = on_quote
        self._running = False
        self._prices = {
            e.symbol: _SEED_PRICES.get(e.symbol, 1000.0) for e in watchlist.symbols
        }
        self._volumes = {e.symbol: random.randint(100_000, 500_000) for e in watchlist.symbols}

    async def run(self, interval_seconds: float = 2.0) -> None:
        self._running = True
        logger.info("mock_quote_feed.started")
        while self._running:
            now = datetime.utcnow()
            for symbol, price in self._prices.items():
                drift = random.uniform(-0.003, 0.003)
                price = max(1.0, price * (1 + drift))
                self._prices[symbol] = price
                vol = self._volumes[symbol] + random.randint(100, 5000)
                self._volumes[symbol] = vol
                quote = Quote(
                    symbol=symbol,
                    ltp=round(price, 2),
                    volume=vol,
                    open=round(price * 0.998, 2),
                    high=round(price * 1.005, 2),
                    low=round(price * 0.995, 2),
                    close=round(price, 2),
                    timestamp=now,
                )
                self._on_quote(quote)
            await asyncio.sleep(interval_seconds)

    async def stop(self) -> None:
        self._running = False
