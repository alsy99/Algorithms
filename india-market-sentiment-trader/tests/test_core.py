from __future__ import annotations

from pathlib import Path

import pytest

from sentiment_trader.config import load_config
from sentiment_trader.execution.brokers.mock import MockBroker
from sentiment_trader.models import OrderRequest, ProductType, Quote, Side, SignalAction, TradeSignal
from sentiment_trader.execution.risk import RiskManager
from sentiment_trader.sentiment.aggregator import SentimentAggregator
from sentiment_trader.sentiment.preprocessor import content_hash, normalize_text
from sentiment_trader.sentiment.scorer import SentimentScorer
from sentiment_trader.sentiment.ticker_linker import TickerLinker
from sentiment_trader.signals.engine import SignalEngine
from datetime import datetime
from sentiment_trader.models import AggregatedSentiment, SentimentScore


@pytest.fixture
def configs():
    root = Path(__file__).resolve().parents[1]
    return load_config(root / "config")


def test_normalize_and_hash():
    text = "<p>Reliance reports strong earnings</p>"
    cleaned = normalize_text(text)
    assert "Reliance" in cleaned
    assert content_hash(cleaned) == content_hash(cleaned)


def test_ticker_linker(configs):
    _, watchlist = configs
    linker = TickerLinker(watchlist)
    symbols = linker.link("Reliance Industries beats estimates; TCS also rises")
    assert "RELIANCE" in symbols
    assert "TCS" in symbols


def test_vader_scorer(configs):
    app_config, _ = configs
    scorer = SentimentScorer(app_config.sentiment)
    positive = scorer.score("Reliance reports record profit growth and strong outlook")
    negative = scorer.score("Company faces major fraud investigation and steep losses")
    assert positive > negative


def test_aggregator_decay():
    agg = SentimentAggregator(window_minutes=15, decay_lambda=0.05)
    now = datetime.utcnow()
    result = agg.add(SentimentScore(symbol="RELIANCE", score=0.8, source_id="1", timestamp=now))
    assert result.symbol == "RELIANCE"
    assert result.sample_count == 1


def test_mock_broker_buy_sell():
    import asyncio

    broker = MockBroker(initial_cash=100_000)
    quote = Quote(symbol="RELIANCE", ltp=1000.0, volume=1000, timestamp=datetime.utcnow())
    broker.update_quote(quote)

    async def _run():
        order = OrderRequest(
            symbol="RELIANCE",
            side=Side.BUY,
            quantity=10,
            product_type=ProductType.DELIVERY,
        )
        result = await broker.place_order(order)
        assert result.status == "COMPLETE"
        assert result.fill_price is not None
        positions = await broker.get_positions()
        assert len(positions) == 1

    asyncio.run(_run())


def test_risk_blocks_oversized_position(configs):
    app_config, _ = configs
    risk = RiskManager(app_config.risk, initial_capital=100_000)
    signal = TradeSignal(
        symbol="RELIANCE",
        action=SignalAction.BUY,
        sentiment_score=0.9,
        momentum=0.01,
        reason="test",
    )
    allowed, reason = risk.check_order(
        signal, cash=1000, equity=100_000, open_positions=0, ltp=5000, held_qty=0
    )
    assert not allowed
    assert reason == "insufficient_cash"


def test_signal_engine_buy(configs):
    app_config, _ = configs
    engine = SignalEngine(app_config.signals)
    now = datetime.utcnow()
    quote = Quote(symbol="RELIANCE", ltp=100.0, volume=1_000_000, timestamp=now)
    for i in range(5):
        engine.record_quote(
            Quote(symbol="RELIANCE", ltp=100.0 + i, volume=1_000_000 + i * 1000, timestamp=now)
        )
    sentiment = AggregatedSentiment(symbol="RELIANCE", score=0.9, sample_count=3, timestamp=now)
    signal = engine.evaluate(sentiment, quote)
    assert signal.action in {SignalAction.BUY, SignalAction.HOLD}
