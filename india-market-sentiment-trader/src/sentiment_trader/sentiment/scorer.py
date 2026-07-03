from __future__ import annotations

import structlog

from sentiment_trader.config import SentimentConfig

logger = structlog.get_logger(__name__)


class SentimentScorer:
    def __init__(self, config: SentimentConfig) -> None:
        self._config = config
        self._vader = None
        self._finbert = None

    def score(self, text: str) -> float:
        if self._config.model == "finbert":
            return self._score_finbert(text)
        return self._score_vader(text)

    def _score_vader(self, text: str) -> float:
        if self._vader is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self._vader = SentimentIntensityAnalyzer()
        compound = self._vader.polarity_scores(text)["compound"]
        return max(-1.0, min(1.0, compound))

    def _score_finbert(self, text: str) -> float:
        if self._finbert is None:
            try:
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                import torch
            except ImportError:
                logger.warning("finbert.unavailable", fallback="vader")
                return self._score_vader(text)

            model_name = "ProsusAI/finbert"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self._finbert = (tokenizer, model, torch)

        tokenizer, model, torch = self._finbert
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]
        positive = float(probs[0])
        negative = float(probs[1])
        return positive - negative
