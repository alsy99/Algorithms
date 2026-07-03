from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatchlistEntry(BaseModel):
    symbol: str
    angel_tradingsymbol: str
    aliases: list[str] = Field(default_factory=list)


class WatchlistConfig(BaseModel):
    symbols: list[WatchlistEntry]


class BrokerConfig(BaseModel):
    provider: Literal["mock", "angel_one", "kite"] = "mock"


class MarketConfig(BaseModel):
    exchange: str = "NSE"
    timezone: str = "Asia/Kolkata"
    session_open: str = "09:15"
    session_close: str = "15:30"
    pre_open: str = "09:00"
    intraday_squareoff: str = "15:15"


class SentimentConfig(BaseModel):
    model: Literal["vader", "finbert"] = "vader"
    aggregation_window_minutes: int = 15
    decay_lambda: float = 0.05
    poll_rss_seconds: int = 120
    poll_reddit_seconds: int = 60


class SignalsConfig(BaseModel):
    buy_sentiment_threshold: float = 0.35
    sell_sentiment_threshold: float = -0.25
    momentum_window_minutes: int = 5
    volume_ma_periods: int = 20


class RiskConfig(BaseModel):
    max_position_pct: float = 5.0
    max_open_positions: int = 3
    daily_loss_limit_pct: float = 2.0
    cooldown_minutes: int = 30
    default_product: Literal["DELIVERY", "INTRADAY"] = "DELIVERY"


class PortfolioConfig(BaseModel):
    initial_capital_inr: float = 1_000_000


class MonitoringConfig(BaseModel):
    health_port: int = 8080
    metrics_port: int = 9090


class AppConfig(BaseModel):
    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    angel_api_key: str = ""
    angel_client_code: str = ""
    angel_pin: str = ""
    angel_totp_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "india-market-sentiment-trader/0.1"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://trader:trader@localhost:5432/sentiment_trader"
    log_level: str = "INFO"
    config_dir: str = "config"


def load_config(config_dir: str | Path | None = None) -> tuple[AppConfig, WatchlistConfig]:
    base = Path(config_dir or os.getenv("CONFIG_DIR", "config"))
    settings_path = base / "settings.yaml"
    watchlist_path = base / "watchlist.yaml"

    with settings_path.open(encoding="utf-8") as f:
        settings_data = yaml.safe_load(f) or {}
    with watchlist_path.open(encoding="utf-8") as f:
        watchlist_data = yaml.safe_load(f) or {}

    return AppConfig.model_validate(settings_data), WatchlistConfig.model_validate(watchlist_data)
