from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

import structlog

from sentiment_trader.config import EnvSettings, WatchlistConfig
from sentiment_trader.execution.angel_auth import AngelAuthSession
from sentiment_trader.ingestion.instrument_lookup import InstrumentLookup
from sentiment_trader.models import Quote

logger = structlog.get_logger(__name__)


class AngelMarketStream:
    """Wraps Angel One SmartWebSocketV2 for live NSE ticks."""

    def __init__(
        self,
        env: EnvSettings,
        watchlist: WatchlistConfig,
        instrument_lookup: InstrumentLookup,
        on_quote: Callable[[Quote], None],
    ) -> None:
        self._env = env
        self._watchlist = watchlist
        self._instruments = instrument_lookup
        self._on_quote = on_quote
        self._session = AngelAuthSession(env)
        self._ws = None
        self._thread = None
        self._running = False

    async def start(self) -> None:
        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
        except ImportError as exc:
            raise ImportError("Install angel extras: pip install '.[angel]'") from exc

        await self._instruments.refresh()
        jwt, feed = self._session.login()

        token_list = []
        for entry in self._watchlist.symbols:
            token = self._instruments.get_token(entry.angel_tradingsymbol)
            if token:
                token_list.append({"exchangeType": 1, "tokens": [token]})

        if not token_list:
            raise RuntimeError("No instrument tokens resolved for watchlist")

        self._ws = SmartWebSocketV2(jwt, self._env.angel_api_key, self._env.angel_client_code, feed)
        self._ws.on_data = self._handle_data
        self._ws.on_open = lambda ws: logger.info("angel_ws.connected")
        self._ws.on_close = lambda ws, code, msg: logger.warning("angel_ws.closed", code=code, msg=msg)
        self._ws.on_error = lambda ws, err: logger.error("angel_ws.error", error=str(err))

        self._running = True

        def _run():
            self._ws.connect()
            correlation_id = "sentiment-trader-1"
            mode = 2  # QUOTE
            self._ws.subscribe(correlation_id, mode, token_list)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run)

    def _handle_data(self, message) -> None:
        try:
            token = str(message.get("token") or message.get("symboltoken", ""))
            ltp = float(message.get("last_traded_price") or message.get("ltp", 0)) / 100
            volume = int(message.get("volume_trade_for_the_day") or message.get("volume", 0))
            symbol = self._token_to_symbol(token)
            if not symbol:
                return
            quote = Quote(
                symbol=symbol,
                ltp=ltp,
                volume=volume,
                open=float(message.get("open_price_of_the_day", 0)) / 100,
                high=float(message.get("high_price_of_the_day", 0)) / 100,
                low=float(message.get("low_price_of_the_day", 0)) / 100,
                close=float(message.get("closed_price", 0)) / 100,
                timestamp=datetime.utcnow(),
            )
            self._on_quote(quote)
        except Exception as exc:
            logger.exception("angel_ws.parse_error", error=str(exc))

    def _token_to_symbol(self, token: str) -> str | None:
        for entry in self._watchlist.symbols:
            if self._instruments.get_token(entry.angel_tradingsymbol) == token:
                return entry.symbol
        return None

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close_connection()
            except Exception:
                pass
