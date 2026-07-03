from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import structlog

from sentiment_trader.config import WatchlistConfig, WatchlistEntry

logger = structlog.get_logger(__name__)

SCRIP_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)
CACHE_TTL = timedelta(hours=12)


class InstrumentLookup:
    """Maps NSE tradingsymbols to Angel One symboltokens."""

    def __init__(self, watchlist: WatchlistConfig, cache_dir: Path | None = None) -> None:
        self._watchlist = watchlist
        self._cache_dir = cache_dir or Path(".scrip_master_cache")
        self._token_by_tradingsymbol: dict[str, str] = {}
        self._entry_by_symbol: dict[str, WatchlistEntry] = {
            e.symbol: e for e in watchlist.symbols
        }
        self._loaded_at: datetime | None = None

    def get_watchlist_entry(self, symbol: str) -> WatchlistEntry | None:
        return self._entry_by_symbol.get(symbol)

    def get_token(self, angel_tradingsymbol: str) -> str | None:
        return self._token_by_tradingsymbol.get(angel_tradingsymbol)

    async def refresh(self) -> None:
        if self._loaded_at and datetime.utcnow() - self._loaded_at < CACHE_TTL:
            return

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / "scrip_master.json"

        if cache_file.exists() and self._loaded_at is None:
            raw = cache_file.read_text(encoding="utf-8")
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRIP_MASTER_URL, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    resp.raise_for_status()
                    raw = await resp.text()
            cache_file.write_text(raw, encoding="utf-8")

        import json

        rows = json.loads(raw)
        wanted = {e.angel_tradingsymbol for e in self._watchlist.symbols}
        self._token_by_tradingsymbol.clear()

        for row in rows:
            ts = row.get("symbol") or row.get("tradingsymbol")
            if ts in wanted:
                self._token_by_tradingsymbol[ts] = str(row.get("token") or row.get("symboltoken"))

        self._loaded_at = datetime.utcnow()
        logger.info(
            "instruments.refreshed",
            resolved=len(self._token_by_tradingsymbol),
            wanted=len(wanted),
        )

    def load_from_csv_text(self, text: str) -> None:
        """Test helper to load token map from CSV."""
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            ts = row.get("tradingsymbol") or row.get("symbol")
            token = row.get("token") or row.get("symboltoken")
            if ts and token:
                self._token_by_tradingsymbol[ts] = str(token)
        self._loaded_at = datetime.utcnow()
