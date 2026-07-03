from __future__ import annotations

from sentiment_trader.execution.brokers.base import BrokerAdapter
from sentiment_trader.models import Position, Quote


class PortfolioTracker:
    def __init__(self, broker: BrokerAdapter, initial_capital: float) -> None:
        self._broker = broker
        self._initial_capital = initial_capital
        self._quotes: dict[str, Quote] = {}

    def update_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote
        if hasattr(self._broker, "update_quote"):
            self._broker.update_quote(quote)

    async def equity(self) -> float:
        cash = await self._broker.get_cash_balance()
        positions = await self._broker.get_positions()
        holdings = 0.0
        for pos in positions:
            quote = self._quotes.get(pos.symbol)
            ltp = quote.ltp if quote else pos.avg_price
            holdings += ltp * pos.quantity
        return cash + holdings

    async def cash(self) -> float:
        return await self._broker.get_cash_balance()

    async def positions(self) -> list[Position]:
        return await self._broker.get_positions()

    async def held_quantity(self, symbol: str) -> int:
        for pos in await self.positions():
            if pos.symbol == symbol:
                return pos.quantity
        return 0

    async def open_position_count(self) -> int:
        return len(await self.positions())
