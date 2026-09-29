from __future__ import annotations

from decimal import Decimal

from .models import Candle, Position, SessionState, Trade
from .risk import RiskManager
from .strategy import Strategy

TIME_EXIT_BARS = 288


def process_candle(state: SessionState, previous: Candle | None, candle: Candle, strategy: Strategy, risk: RiskManager,
                   fee_rate: Decimal = Decimal("0"), slippage_rate: Decimal = Decimal("0")) -> str:
    """Process one validated candle. Only simulated long entries/exits are possible."""
    if fee_rate < 0 or slippage_rate < 0:
        raise ValueError("fees and slippage cannot be negative")
    if state.position:
        position = state.position
        position.bars_held += 1
        if candle.low <= position.stop_loss:
            _close(state, candle, position.stop_loss, "STOP_LOSS", fee_rate, slippage_rate)
            return "EXIT STOP_LOSS"
        if position.bars_held >= TIME_EXIT_BARS:
            _close(state, candle, candle.close, "TIME_EXIT", fee_rate, slippage_rate)
            return "EXIT TIME_EXIT"
        return "HOLD"
    if strategy.should_enter(previous, candle):
        approved = risk.approve_entry(state, candle.close)
        if approved:
            size, stop = approved
            state.position = Position("LONG", candle.close_time, candle.close, size, stop)
            return "ENTRY LONG"
    return "NO_ENTRY"


def _close(state: SessionState, candle: Candle, exit_price: Decimal, reason: str, fee_rate: Decimal, slippage_rate: Decimal) -> None:
    position = state.position
    assert position is not None
    gross = (exit_price - position.entry_price) * position.size
    fees = (position.entry_price + exit_price) * position.size * fee_rate
    slippage = (position.entry_price + exit_price) * position.size * slippage_rate
    net = gross - fees - slippage
    state.capital += net
    state.trades.append(Trade(position.entry_time, candle.close_time, position.side, position.entry_price, exit_price,
                              position.size, position.stop_loss, position.bars_held, reason, gross, fees, slippage, net))
    state.position = None
