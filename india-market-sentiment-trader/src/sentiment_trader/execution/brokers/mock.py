from __future__ import annotations

import uuid

from sentiment_trader.execution.brokers.base import BrokerAdapter
from sentiment_trader.models import OrderRequest, OrderResult, Position, Quote, Side


class MockBroker(BrokerAdapter):
    """Paper trading broker that simulates fills at last known LTP."""

    def __init__(self, initial_cash: float = 1_000_000.0, slippage_bps: float = 5.0) -> None:
        self._cash = initial_cash
        self._slippage_bps = slippage_bps
        self._quotes: dict[str, Quote] = {}
        self._positions: dict[str, Position] = {}
        self._orders: list[OrderResult] = []

    def update_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote
        self._mark_positions(quote)

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def get_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    async def place_order(self, request: OrderRequest) -> OrderResult:
        quote = self._quotes.get(request.symbol)
        if quote is None:
            raise ValueError(f"No quote available for {request.symbol}")

        slip = quote.ltp * (self._slippage_bps / 10_000)
        fill_price = quote.ltp + slip if request.side == Side.BUY else quote.ltp - slip
        notional = fill_price * request.quantity

        if request.side == Side.BUY:
            if notional > self._cash:
                raise ValueError("Insufficient cash for mock order")
            self._cash -= notional
            self._add_position(request, fill_price)
        else:
            pos = self._positions.get(request.symbol)
            if pos is None or pos.quantity < request.quantity:
                raise ValueError(f"Insufficient position for {request.symbol}")
            self._cash += notional
            self._reduce_position(request.symbol, request.quantity)

        result = OrderResult(
            order_id=str(uuid.uuid4()),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            status="COMPLETE",
            fill_price=fill_price,
        )
        self._orders.append(result)
        return result

    async def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    async def get_cash_balance(self) -> float:
        return self._cash

    def _add_position(self, request: OrderRequest, fill_price: float) -> None:
        existing = self._positions.get(request.symbol)
        if existing is None:
            self._positions[request.symbol] = Position(
                symbol=request.symbol,
                quantity=request.quantity,
                avg_price=fill_price,
                product_type=request.product_type,
            )
            return

        total_qty = existing.quantity + request.quantity
        avg = ((existing.avg_price * existing.quantity) + (fill_price * request.quantity)) / total_qty
        existing.quantity = total_qty
        existing.avg_price = avg

    def _reduce_position(self, symbol: str, quantity: int) -> None:
        pos = self._positions[symbol]
        pos.quantity -= quantity
        if pos.quantity <= 0:
            del self._positions[symbol]

    def _mark_positions(self, quote: Quote) -> None:
        pos = self._positions.get(quote.symbol)
        if pos is None:
            return
        pos.unrealized_pnl = (quote.ltp - pos.avg_price) * pos.quantity
