from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from sentiment_trader.monitoring.dashboard import DASHBOARD_HTML

NEWS_PROCESSED = Counter("news_items_processed_total", "News items processed")
SENTIMENT_UPDATES = Counter("sentiment_updates_total", "Sentiment updates", ["symbol"])
TRADES_EXECUTED = Counter("trades_executed_total", "Trades executed", ["side"])
OPEN_POSITIONS = Gauge("open_positions", "Open positions")
EQUITY_INR = Gauge("equity_inr", "Portfolio equity in INR")

StatusProvider = Callable[[], Awaitable[dict[str, Any]]]


class HealthServer:
    def __init__(self, port: int) -> None:
        self._port = port
        self._healthy = True
        self._runner: web.AppRunner | None = None
        self._status_provider: StatusProvider | None = None

    def set_status_provider(self, provider: StatusProvider) -> None:
        self._status_provider = provider

    def set_healthy(self, value: bool) -> None:
        self._healthy = value

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._dashboard)
        app.router.add_get("/health", self._health)
        app.router.add_get("/api/status", self._status)
        app.router.add_get("/metrics", self._metrics)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()

    async def _dashboard(self, _request: web.Request) -> web.Response:
        return web.Response(text=DASHBOARD_HTML, content_type="text/html")

    async def _health(self, _request: web.Request) -> web.Response:
        status = 200 if self._healthy else 503
        return web.json_response({"status": "ok" if self._healthy else "degraded"}, status=status)

    async def _status(self, _request: web.Request) -> web.Response:
        if self._status_provider is None:
            return web.json_response({"status": "starting"}, status=503)
        data = await self._status_provider()
        response = web.json_response(data)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    async def _metrics(self, _request: web.Request) -> web.Response:
        return web.Response(body=generate_latest(), content_type=CONTENT_TYPE_LATEST)
