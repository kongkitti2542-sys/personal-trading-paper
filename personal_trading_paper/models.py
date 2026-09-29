from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def utc_iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: int


@dataclass
class Position:
    side: str
    entry_time: int
    entry_price: Decimal
    size: Decimal
    stop_loss: Decimal
    bars_held: int = 0


@dataclass(frozen=True)
class Trade:
    entry_time: int
    exit_time: int
    side: str
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    stop_loss: Decimal
    bars_held: int
    exit_reason: str
    gross_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    net_pnl: Decimal


@dataclass
class SessionState:
    starting_capital: Decimal
    capital: Decimal
    last_candle_time: int | None = None
    position: Position | None = None
    trades: list[Trade] | None = None

    def __post_init__(self) -> None:
        if self.trades is None:
            self.trades = []


def decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"invalid decimal value: {value!r}") from exc
    if not result.is_finite():
        raise ValueError("state contains a non-finite number")
    return result


def position_to_dict(position: Position | None) -> dict[str, Any] | None:
    if position is None:
        return None
    return {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(position).items()}


def trade_to_dict(trade: Trade) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(trade).items()}


def state_to_dict(state: SessionState) -> dict[str, Any]:
    return {
        "starting_capital": str(state.starting_capital),
        "capital": str(state.capital),
        "last_candle_time": state.last_candle_time,
        "position": position_to_dict(state.position),
        "trades": [trade_to_dict(trade) for trade in state.trades or []],
    }


def state_from_dict(raw: dict[str, Any]) -> SessionState:
    try:
        pos_raw = raw["position"]
        position = None if pos_raw is None else Position(
            side=str(pos_raw["side"]), entry_time=int(pos_raw["entry_time"]),
            entry_price=decimal(pos_raw["entry_price"]), size=decimal(pos_raw["size"]),
            stop_loss=decimal(pos_raw["stop_loss"]), bars_held=int(pos_raw["bars_held"]),
        )
        trades = [Trade(
            entry_time=int(t["entry_time"]), exit_time=int(t["exit_time"]), side=str(t["side"]),
            entry_price=decimal(t["entry_price"]), exit_price=decimal(t["exit_price"]),
            size=decimal(t["size"]), stop_loss=decimal(t["stop_loss"]), bars_held=int(t["bars_held"]),
            exit_reason=str(t["exit_reason"]), gross_pnl=decimal(t["gross_pnl"]),
            fees=decimal(t["fees"]), slippage=decimal(t["slippage"]), net_pnl=decimal(t["net_pnl"]),
        ) for t in raw["trades"]]
        state = SessionState(decimal(raw["starting_capital"]), decimal(raw["capital"]), raw["last_candle_time"], position, trades)
        if state.starting_capital <= 0 or state.capital < 0:
            raise ValueError("invalid capital in state")
        if state.last_candle_time is not None and (not isinstance(state.last_candle_time, int) or state.last_candle_time < 0):
            raise ValueError("invalid last candle timestamp")
        if position and (position.side != "LONG" or position.entry_price <= 0 or position.size <= 0 or position.stop_loss <= 0 or position.bars_held < 0):
            raise ValueError("invalid position in state")
        return state
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("corrupt session state") from exc
