from __future__ import annotations

from typing import Protocol

from .models import Candle


class Strategy(Protocol):
    name: str

    def should_enter(self, previous: Candle | None, current: Candle) -> bool: ...


class DemoUpCandleStrategy:
    """Non-production example: enter long when a candle closes above its open."""

    name = "demo-up-candle (not a production strategy)"

    def should_enter(self, previous: Candle | None, current: Candle) -> bool:
        return current.close > current.open
