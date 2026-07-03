from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sentiment_trader.config import RiskConfig
from sentiment_trader.models import OrderRequest, ProductType, Side, TradeSignal


@dataclass
class RiskState:
    session_start_equity: float = 0.0
    halted: bool = False
    last_close_by_symbol: dict[str, datetime] = field(default_factory=dict)


class RiskManager:
    def __init__(self, config: RiskConfig, initial_capital: float) -> None:
        self._config = config
        self._state = RiskState(session_start_equity=initial_capital)

    def reset_session(self, equity: float) -> None:
        self._state = RiskState(session_start_equity=equity)

    def check_order(
        self,
        signal: TradeSignal,
        cash: float,
        equity: float,
        open_positions: int,
        ltp: float,
        held_qty: int = 0,
    ) -> tuple[bool, str]:
        if self._state.halted:
            return False, "daily_loss_limit_hit"

        if signal.action.value == "HOLD":
            return False, "hold_signal"

        if signal.action.value == "BUY":
            if open_positions >= self._config.max_open_positions:
                return False, "max_open_positions"
            last_close = self._state.last_close_by_symbol.get(signal.symbol)
            if last_close:
                cooldown = timedelta(minutes=self._config.cooldown_minutes)
                if datetime.utcnow() - last_close < cooldown:
                    return False, "cooldown_active"

            max_notional = equity * (self._config.max_position_pct / 100.0)
            if max_notional <= 0 or ltp <= 0:
                return False, "invalid_price"
            qty = int(max_notional // ltp)
            if qty < 1:
                return False, "position_too_small"
            if qty * ltp > cash:
                return False, "insufficient_cash"
            return True, "ok"

        if signal.action.value == "SELL":
            if held_qty < 1:
                return False, "no_position"
            return True, "ok"

        return False, "unknown"

    def build_order(
        self,
        signal: TradeSignal,
        cash: float,
        equity: float,
        ltp: float,
        held_qty: int = 0,
        open_positions: int = 0,
    ) -> OrderRequest | None:
        allowed, _ = self.check_order(
            signal, cash, equity, open_positions=open_positions, ltp=ltp, held_qty=held_qty
        )
        if not allowed and signal.action.value == "BUY":
            return None

        product = ProductType.DELIVERY
        if self._config.default_product == "INTRADAY":
            product = ProductType.INTRADAY

        if signal.action.value == "BUY":
            max_notional = equity * (self._config.max_position_pct / 100.0)
            qty = max(1, int(max_notional // ltp))
            return OrderRequest(
                symbol=signal.symbol,
                side=Side.BUY,
                quantity=qty,
                product_type=product,
            )

        if signal.action.value == "SELL" and held_qty > 0:
            return OrderRequest(
                symbol=signal.symbol,
                side=Side.SELL,
                quantity=held_qty,
                product_type=product,
            )
        return None

    def update_after_close(self, symbol: str, equity: float) -> None:
        self._state.last_close_by_symbol[symbol] = datetime.utcnow()
        loss_pct = ((equity - self._state.session_start_equity) / self._state.session_start_equity) * 100
        if loss_pct <= -self._config.daily_loss_limit_pct:
            self._state.halted = True
