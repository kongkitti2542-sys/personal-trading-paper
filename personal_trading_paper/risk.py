from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import SessionState


@dataclass(frozen=True)
class RiskConfig:
    risk_fraction: Decimal
    max_position_fraction: Decimal
    stop_loss_fraction: Decimal
    allow_position_overlap: bool = False

    def __post_init__(self) -> None:
        for name, value in (("risk_fraction", self.risk_fraction), ("max_position_fraction", self.max_position_fraction), ("stop_loss_fraction", self.stop_loss_fraction)):
            if not value.is_finite() or not 0 < value < 1:
                raise ValueError(f"{name} must be greater than 0 and less than 1")


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def approve_entry(self, state: SessionState, price: Decimal) -> tuple[Decimal, Decimal] | None:
        if not price.is_finite() or price <= 0 or state.capital <= 0:
            return None
        if state.position is not None and not self.config.allow_position_overlap:
            return None
        stop = price * (Decimal("1") - self.config.stop_loss_fraction)
        risk_amount = state.capital * self.config.risk_fraction
        size_by_risk = risk_amount / (price - stop)
        max_size = state.capital * self.config.max_position_fraction / price
        size = min(size_by_risk, max_size)
        if size <= 0 or size * price > state.capital:
            return None
        return size, stop
