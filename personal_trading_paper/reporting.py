from __future__ import annotations

from decimal import Decimal

from .models import SessionState, utc_iso


def performance_summary(state: SessionState) -> dict[str, object]:
    trades = state.trades or []
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl < 0]
    gross_wins = sum((t.net_pnl for t in wins), Decimal(0))
    gross_losses = -sum((t.net_pnl for t in losses), Decimal(0))
    peak = state.starting_capital
    max_drawdown = Decimal(0)
    running = state.starting_capital
    for trade in trades:
        running += trade.net_pnl
        peak = max(peak, running)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - running) / peak)
    return {
        "Starting Capital": state.starting_capital,
        "Current Capital": state.capital,
        "Realized P/L": state.capital - state.starting_capital,
        "Win Rate": Decimal(len(wins)) / len(trades) if trades else Decimal(0),
        "Profit Factor": gross_wins / gross_losses if gross_losses else (Decimal("Infinity") if gross_wins else Decimal(0)),
        "Number of Trades": len(trades), "Wins": len(wins), "Losses": len(losses),
        "Average Trade": sum((t.net_pnl for t in trades), Decimal(0)) / len(trades) if trades else Decimal(0),
        "Max Drawdown": max_drawdown,
        "Current Position": "FLAT" if state.position is None else f"LONG {state.position.size} @ {state.position.entry_price}",
        "Last Candle Time": "—" if state.last_candle_time is None else utc_iso(state.last_candle_time),
    }


def render_summary(state: SessionState) -> str:
    return "\n".join(f"{key}: {value}" for key, value in performance_summary(state).items())
