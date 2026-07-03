from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

from sentiment_trader.config import SignalsConfig
from sentiment_trader.models import AggregatedSentiment, Quote, SignalAction, TradeSignal


class SignalEngine:
    def __init__(self, config: SignalsConfig) -> None:
        self._config = config
        self._price_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(deque)
        self._volume_history: dict[str, deque[int]] = defaultdict(lambda: deque(maxlen=config.volume_ma_periods))

    def record_quote(self, quote: Quote) -> None:
        window = timedelta(minutes=self._config.momentum_window_minutes)
        history = self._price_history[quote.symbol]
        history.append((quote.timestamp, quote.ltp))
        cutoff = quote.timestamp - window
        while history and history[0][0] < cutoff:
            history.popleft()
        self._volume_history[quote.symbol].append(quote.volume)

    def evaluate(self, sentiment: AggregatedSentiment, quote: Quote) -> TradeSignal:
        self.record_quote(quote)
        momentum = self._momentum(quote.symbol)
        volume_ok = self._volume_above_average(quote.symbol, quote.volume)

        if (
            sentiment.score >= self._config.buy_sentiment_threshold
            and momentum > 0
            and volume_ok
        ):
            return TradeSignal(
                symbol=quote.symbol,
                action=SignalAction.BUY,
                sentiment_score=sentiment.score,
                momentum=momentum,
                reason="positive_sentiment_with_momentum",
            )

        if sentiment.score <= self._config.sell_sentiment_threshold:
            return TradeSignal(
                symbol=quote.symbol,
                action=SignalAction.SELL,
                sentiment_score=sentiment.score,
                momentum=momentum,
                reason="negative_sentiment",
            )

        return TradeSignal(
            symbol=quote.symbol,
            action=SignalAction.HOLD,
            sentiment_score=sentiment.score,
            momentum=momentum,
            reason="no_signal",
        )

    def _momentum(self, symbol: str) -> float:
        history = self._price_history.get(symbol, deque())
        if len(history) < 2:
            return 0.0
        first = history[0][1]
        last = history[-1][1]
        if first == 0:
            return 0.0
        return (last - first) / first

    def _volume_above_average(self, symbol: str, current_volume: int) -> bool:
        volumes = self._volume_history.get(symbol)
        if not volumes or len(volumes) < 2:
            return True
        avg = sum(volumes) / len(volumes)
        return current_volume >= avg
