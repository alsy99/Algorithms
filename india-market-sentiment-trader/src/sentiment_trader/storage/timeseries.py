from __future__ import annotations

from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


class TimeseriesStore:
    """Persistence layer — logs to structured logs when DB unavailable."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool = None

    async def connect(self) -> None:
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=3)
            await self._ensure_schema()
            logger.info("timeseries.connected")
        except Exception as exc:
            logger.warning("timeseries.unavailable", error=str(exc))
            self._pool = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def _ensure_schema(self) -> None:
        if self._pool is None:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentiment_scores (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL,
                    sample_count INT,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INT NOT NULL,
                    fill_price DOUBLE PRECISION,
                    sentiment_score DOUBLE PRECISION,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

    async def save_sentiment(self, symbol: str, score: float, sample_count: int) -> None:
        if self._pool is None:
            logger.info("sentiment.persist_skipped", symbol=symbol, score=score)
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sentiment_scores (symbol, score, sample_count, recorded_at) VALUES ($1, $2, $3, $4)",
                symbol,
                score,
                sample_count,
                datetime.utcnow(),
            )

    async def save_trade(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        fill_price: float | None,
        sentiment_score: float,
    ) -> None:
        if self._pool is None:
            logger.info(
                "trade.persist_skipped",
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
            )
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trades (order_id, symbol, side, quantity, fill_price, sentiment_score, recorded_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                order_id,
                symbol,
                side,
                quantity,
                fill_price,
                sentiment_score,
                datetime.utcnow(),
            )
