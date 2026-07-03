from __future__ import annotations

import structlog

from sentiment_trader.config import EnvSettings, WatchlistConfig
from sentiment_trader.execution.angel_auth import AngelAuthSession
from sentiment_trader.execution.brokers.base import BrokerAdapter
from sentiment_trader.ingestion.instrument_lookup import InstrumentLookup
from sentiment_trader.models import OrderRequest, OrderResult, Position, ProductType, Quote

logger = structlog.get_logger(__name__)

_ANGEL_PRODUCT = {
    ProductType.DELIVERY: "DELIVERY",
    ProductType.INTRADAY: "INTRADAY",
}


class AngelOneBroker(BrokerAdapter):
    """Angel One SmartAPI broker adapter."""

    def __init__(
        self,
        env: EnvSettings,
        watchlist: WatchlistConfig,
        instrument_lookup: InstrumentLookup,
    ) -> None:
        self._env = env
        self._watchlist = watchlist
        self._instruments = instrument_lookup
        self._session = AngelAuthSession(env)
        self._quotes: dict[str, Quote] = {}

    def update_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote

    async def connect(self) -> None:
        self._session.login()
        logger.info("angel_one.broker_connected")

    async def disconnect(self) -> None:
        return None

    async def get_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    async def place_order(self, request: OrderRequest) -> OrderResult:
        entry = self._instruments.get_watchlist_entry(symbol=request.symbol)
        if entry is None:
            raise ValueError(f"Symbol {request.symbol} not in watchlist")

        token = self._instruments.get_token(entry.angel_tradingsymbol)
        if token is None:
            raise ValueError(f"No symboltoken for {entry.angel_tradingsymbol}")

        quote = self._quotes.get(request.symbol)
        price = "0"
        if quote is not None and request.order_type == "LIMIT" and request.price:
            price = str(request.price)
        elif quote is not None:
            price = str(round(quote.ltp, 2))

        params = {
            "variety": "NORMAL",
            "tradingsymbol": entry.angel_tradingsymbol,
            "symboltoken": token,
            "transactiontype": request.side.value,
            "exchange": "NSE",
            "ordertype": request.order_type,
            "producttype": _ANGEL_PRODUCT[request.product_type],
            "duration": "DAY",
            "price": price,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(request.quantity),
            "scripconsent": "yes",
        }

        api = self._session.smart_api
        order_id = api.placeOrder(params)
        logger.info("angel_one.order_placed", order_id=order_id, symbol=request.symbol)

        return OrderResult(
            order_id=str(order_id),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            status="SUBMITTED",
            fill_price=float(price) if price != "0" else None,
            raw={"params": params},
        )

    async def get_positions(self) -> list[Position]:
        api = self._session.smart_api
        data = api.position()
        positions: list[Position] = []
        for row in data.get("data", []) or []:
            netqty = int(float(row.get("netqty", 0)))
            if netqty == 0:
                continue
            symbol = row.get("tradingsymbol", "").replace("-EQ", "")
            product = row.get("producttype", "DELIVERY")
            positions.append(
                Position(
                    symbol=symbol,
                    quantity=abs(netqty),
                    avg_price=float(row.get("avgnetprice", 0)),
                    product_type=ProductType.INTRADAY if product == "INTRADAY" else ProductType.DELIVERY,
                    unrealized_pnl=float(row.get("pnl", 0)),
                )
            )
        return positions

    async def get_cash_balance(self) -> float:
        api = self._session.smart_api
        data = api.rmsLimit()
        return float(data.get("data", {}).get("availablecash", 0))
