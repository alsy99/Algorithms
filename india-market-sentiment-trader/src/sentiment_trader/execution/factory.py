from __future__ import annotations

from sentiment_trader.config import AppConfig, EnvSettings, WatchlistConfig
from sentiment_trader.execution.brokers.angel_one import AngelOneBroker
from sentiment_trader.execution.brokers.base import BrokerAdapter
from sentiment_trader.execution.brokers.mock import MockBroker
from sentiment_trader.ingestion.instrument_lookup import InstrumentLookup


def create_broker(
    config: AppConfig,
    env: EnvSettings,
    watchlist: WatchlistConfig,
    instrument_lookup: InstrumentLookup | None = None,
) -> BrokerAdapter:
    provider = config.broker.provider
    if provider == "mock":
        return MockBroker(initial_cash=config.portfolio.initial_capital_inr)
    if provider == "angel_one":
        lookup = instrument_lookup or InstrumentLookup(watchlist)
        return AngelOneBroker(env, watchlist, lookup)
    if provider == "kite":
        from sentiment_trader.execution.brokers.kite import KiteBroker

        return KiteBroker()
    raise ValueError(f"Unknown broker provider: {provider}")
