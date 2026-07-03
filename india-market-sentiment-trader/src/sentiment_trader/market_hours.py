from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sentiment_trader.config import MarketConfig


def market_is_open(config: MarketConfig, now: datetime | None = None) -> bool:
    tz = ZoneInfo(config.timezone)
    local = (now or datetime.utcnow()).astimezone(tz)
    if local.weekday() >= 5:
        return False
    open_h, open_m = map(int, config.session_open.split(":"))
    close_h, close_m = map(int, config.session_close.split(":"))
    start = local.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    end = local.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    return start <= local <= end
