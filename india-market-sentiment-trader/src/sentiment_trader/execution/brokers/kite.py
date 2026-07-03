"""Kite Connect broker adapter — stub for future implementation."""

from __future__ import annotations

from sentiment_trader.execution.brokers.base import BrokerAdapter
from sentiment_trader.models import OrderRequest, OrderResult, Position, Quote


class KiteBroker(BrokerAdapter):
    def __init__(self) -> None:
        raise NotImplementedError(
            "KiteBroker is not implemented yet. Set broker.provider to mock or angel_one."
        )

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def get_quote(self, symbol: str) -> Quote | None:
        raise NotImplementedError

    async def place_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError

    async def get_cash_balance(self) -> float:
        raise NotImplementedError
