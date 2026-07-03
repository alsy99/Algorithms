from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ProductType(str, Enum):
    DELIVERY = "DELIVERY"
    INTRADAY = "INTRADAY"


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Quote:
    symbol: str
    ltp: float
    volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NewsItem:
    id: str
    source: str
    text: str
    published_at: datetime
    url: str = ""


@dataclass
class SentimentScore:
    symbol: str
    score: float
    source_id: str
    timestamp: datetime
    raw_text: str = ""


@dataclass
class AggregatedSentiment:
    symbol: str
    score: float
    sample_count: int
    timestamp: datetime


@dataclass
class OrderRequest:
    symbol: str
    side: Side
    quantity: int
    product_type: ProductType
    order_type: str = "MARKET"
    price: float | None = None


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: Side
    quantity: int
    status: str
    fill_price: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    product_type: ProductType
    unrealized_pnl: float = 0.0


@dataclass
class TradeSignal:
    symbol: str
    action: SignalAction
    sentiment_score: float
    momentum: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
