from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from sentiment_trader.models import AggregatedSentiment, SentimentScore


@dataclass
class _Sample:
    score: float
    timestamp: datetime


class SentimentAggregator:
    def __init__(self, window_minutes: int = 15, decay_lambda: float = 0.05) -> None:
        self._window = timedelta(minutes=window_minutes)
        self._decay_lambda = decay_lambda
        self._samples: dict[str, deque[_Sample]] = defaultdict(deque)

    def add(self, score: SentimentScore) -> AggregatedSentiment:
        bucket = self._samples[score.symbol]
        bucket.append(_Sample(score=score.score, timestamp=score.timestamp))
        self._evict(score.symbol, score.timestamp)
        agg = self._aggregate(score.symbol, score.timestamp)
        return agg

    def get(self, symbol: str, now: datetime | None = None) -> AggregatedSentiment | None:
        ts = now or datetime.utcnow()
        self._evict(symbol, ts)
        if not self._samples[symbol]:
            return None
        return self._aggregate(symbol, ts)

    def _evict(self, symbol: str, now: datetime) -> None:
        bucket = self._samples[symbol]
        cutoff = now - self._window
        while bucket and bucket[0].timestamp < cutoff:
            bucket.popleft()

    def _aggregate(self, symbol: str, now: datetime) -> AggregatedSentiment:
        bucket = self._samples[symbol]
        weighted_sum = 0.0
        weight_total = 0.0
        for sample in bucket:
            age_min = max(0.0, (now - sample.timestamp).total_seconds() / 60.0)
            weight = math.exp(-self._decay_lambda * age_min)
            weighted_sum += sample.score * weight
            weight_total += weight
        score = weighted_sum / weight_total if weight_total else 0.0
        return AggregatedSentiment(
            symbol=symbol,
            score=score,
            sample_count=len(bucket),
            timestamp=now,
        )
