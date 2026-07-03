from __future__ import annotations

from abc import ABC, abstractmethod

from sentiment_trader.models import OrderRequest, OrderResult, Position, Quote


class BrokerAdapter(ABC):
    """Broker-agnostic interface for order execution and market data."""

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote | None:
        ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    async def get_cash_balance(self) -> float:
        ...
