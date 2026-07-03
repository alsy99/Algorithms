from __future__ import annotations

import asyncio
import signal
from datetime import datetime

import structlog

from sentiment_trader.config import EnvSettings, load_config
from sentiment_trader.execution.brokers.mock import MockBroker
from sentiment_trader.execution.factory import create_broker
from sentiment_trader.execution.portfolio import PortfolioTracker
from sentiment_trader.execution.risk import RiskManager
from sentiment_trader.ingestion.instrument_lookup import InstrumentLookup
from sentiment_trader.ingestion.mock_quotes import MockQuoteFeed
from sentiment_trader.ingestion.news_rss import NewsRssPoller
from sentiment_trader.ingestion.reddit_stream import RedditPoller
from sentiment_trader.market_hours import market_is_open
from sentiment_trader.models import Quote, SignalAction
from sentiment_trader.monitoring.dashboard import DashboardState
from sentiment_trader.monitoring.health import (
    EQUITY_INR,
    NEWS_PROCESSED,
    OPEN_POSITIONS,
    SENTIMENT_UPDATES,
    TRADES_EXECUTED,
    HealthServer,
)
from sentiment_trader.sentiment.aggregator import SentimentAggregator
from sentiment_trader.sentiment.preprocessor import content_hash, normalize_text
from sentiment_trader.sentiment.scorer import SentimentScorer
from sentiment_trader.sentiment.ticker_linker import TickerLinker
from sentiment_trader.signals.engine import SignalEngine
from sentiment_trader.storage.redis_client import InMemoryStore
from sentiment_trader.storage.timeseries import TimeseriesStore

logger = structlog.get_logger(__name__)


class TradingBot:
    def __init__(self) -> None:
        self._config, self._watchlist = load_config()
        self._env = EnvSettings()
        self._store = InMemoryStore()
        self._timeseries = TimeseriesStore(self._env.database_url)
        self._instruments = InstrumentLookup(self._watchlist)
        self._broker = create_broker(self._config, self._env, self._watchlist, self._instruments)
        self._portfolio = PortfolioTracker(self._broker, self._config.portfolio.initial_capital_inr)
        self._risk = RiskManager(self._config.risk, self._config.portfolio.initial_capital_inr)
        self._scorer = SentimentScorer(self._config.sentiment)
        self._linker = TickerLinker(self._watchlist)
        self._aggregator = SentimentAggregator(
            window_minutes=self._config.sentiment.aggregation_window_minutes,
            decay_lambda=self._config.sentiment.decay_lambda,
        )
        self._signals = SignalEngine(self._config.signals)
        self._health = HealthServer(self._config.monitoring.health_port)
        self._dashboard_state = DashboardState()
        self._health.set_status_provider(self._build_status)
        self._news = NewsRssPoller(self._config.sentiment.poll_rss_seconds)
        self._reddit = RedditPoller(
            self._env, self._watchlist, self._config.sentiment.poll_reddit_seconds
        )
        self._quote_feed: MockQuoteFeed | None = None
        self._tasks: list[asyncio.Task] = []
        self._latest_quotes: dict[str, Quote] = {}
        self._shutdown = asyncio.Event()
        self._news_count = 0

    async def start(self) -> None:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ]
        )
        await self._store.connect()
        await self._timeseries.connect()
        await self._broker.connect()
        await self._health.start()

        if isinstance(self._broker, MockBroker):
            await self._broker.connect()
            self._quote_feed = MockQuoteFeed(self._watchlist, self._on_quote)
            self._tasks.append(asyncio.create_task(self._quote_feed.run()))

        self._tasks.extend(
            [
                asyncio.create_task(self._news.run()),
                asyncio.create_task(self._reddit.run()),
                asyncio.create_task(self._sentiment_loop()),
                asyncio.create_task(self._trading_loop()),
            ]
        )
        logger.info(
            "bot.started",
            broker=self._config.broker.provider,
            symbols=[s.symbol for s in self._watchlist.symbols],
        )
        self._dashboard_state.log("Bot started in mock/paper mode")

    async def _build_status(self) -> dict:
        equity = await self._portfolio.equity()
        positions = await self._portfolio.positions()
        watchlist_rows = []
        for entry in self._watchlist.symbols:
            symbol = entry.symbol
            quote = self._latest_quotes.get(symbol)
            agg = self._aggregator.get(symbol)
            ltp = quote.ltp if quote else 0.0
            sentiment = agg.score if agg else 0.0
            momentum = 0.0
            signal = "HOLD"
            if quote and agg:
                sig = self._signals.evaluate(agg, quote)
                momentum = sig.momentum
                signal = sig.action.value
            watchlist_rows.append(
                {
                    "symbol": symbol,
                    "ltp": ltp,
                    "sentiment": sentiment,
                    "momentum": momentum,
                    "signal": signal,
                }
            )
        return {
            "status": "ok",
            "broker": self._config.broker.provider,
            "equity_inr": equity,
            "news_processed": self._news_count,
            "open_positions": len(positions),
            "market_open": market_is_open(self._config.market),
            "watchlist": watchlist_rows,
            "recent_activity": list(self._dashboard_state.recent_activity),
        }

    async def stop(self) -> None:
        self._shutdown.set()
        if self._quote_feed is not None:
            await self._quote_feed.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._health.stop()
        await self._timeseries.close()
        await self._broker.disconnect()
        logger.info("bot.stopped")

    def _on_quote(self, quote: Quote) -> None:
        self._latest_quotes[quote.symbol] = quote
        self._portfolio.update_quote(quote)
        self._signals.record_quote(quote)

    async def _sentiment_loop(self) -> None:
        queues = [self._news.queue, self._reddit.queue]
        while not self._shutdown.is_set():
            for queue in queues:
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                await self._process_news(item)
            await asyncio.sleep(0.5)

    async def _process_news(self, item) -> None:
        text = normalize_text(item.text)
        digest = content_hash(text)
        if not await self._store.sadd("seen_news", digest):
            return

        NEWS_PROCESSED.inc()
        self._news_count += 1
        score_value = self._scorer.score(text)
        symbols = self._linker.link(text)
        if not symbols:
            return

        now = datetime.utcnow()
        for symbol in symbols:
            from sentiment_trader.models import SentimentScore

            scored = SentimentScore(
                symbol=symbol,
                score=score_value,
                source_id=item.id,
                timestamp=now,
                raw_text=text[:500],
            )
            agg = self._aggregator.add(scored)
            SENTIMENT_UPDATES.labels(symbol=symbol).inc()
            await self._store.set_json(f"sentiment:{symbol}", agg.__dict__)
            await self._timeseries.save_sentiment(symbol, agg.score, agg.sample_count)
            logger.info(
                "sentiment.updated",
                symbol=symbol,
                score=round(agg.score, 4),
                source=item.source,
            )
            self._dashboard_state.log(f"Sentiment {symbol}: {agg.score:.3f} ({item.source})")

    async def _trading_loop(self) -> None:
        while not self._shutdown.is_set():
            if not market_is_open(self._config.market):
                await asyncio.sleep(5)
                continue

            equity = await self._portfolio.equity()
            cash = await self._portfolio.cash()
            positions = await self._portfolio.positions()
            OPEN_POSITIONS.set(len(positions))
            EQUITY_INR.set(equity)

            for symbol, quote in list(self._latest_quotes.items()):
                agg = self._aggregator.get(symbol)
                if agg is None:
                    continue
                signal = self._signals.evaluate(agg, quote)
                if signal.action == SignalAction.HOLD:
                    continue

                held = await self._portfolio.held_quantity(symbol)
                allowed, reason = self._risk.check_order(
                    signal,
                    cash=cash,
                    equity=equity,
                    open_positions=len(positions),
                    ltp=quote.ltp,
                    held_qty=held,
                )
                if not allowed:
                    logger.debug("trade.blocked", symbol=symbol, reason=reason)
                    continue

                order = self._risk.build_order(
                    signal, cash, equity, quote.ltp, held_qty=held, open_positions=len(positions)
                )
                if order is None:
                    continue

                try:
                    result = await self._broker.place_order(order)
                    TRADES_EXECUTED.labels(side=order.side.value).inc()
                    await self._timeseries.save_trade(
                        result.order_id,
                        result.symbol,
                        result.side.value,
                        result.quantity,
                        result.fill_price,
                        signal.sentiment_score,
                    )
                    logger.info(
                        "trade.executed",
                        order_id=result.order_id,
                        symbol=result.symbol,
                        side=result.side.value,
                        qty=result.quantity,
                        price=result.fill_price,
                    )
                    self._dashboard_state.log(
                        f"Trade {result.side.value} {result.quantity} {result.symbol} @ ₹{result.fill_price}"
                    )
                    if order.side.value == "SELL":
                        self._risk.update_after_close(symbol, await self._portfolio.equity())
                except Exception as exc:
                    logger.exception("trade.failed", symbol=symbol, error=str(exc))

            await asyncio.sleep(10)


async def _run() -> None:
    bot = TradingBot()
    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        bot._shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    await bot.start()
    try:
        await bot._shutdown.wait()
    finally:
        await bot.stop()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
