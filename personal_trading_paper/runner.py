from __future__ import annotations

import argparse
import time
from decimal import Decimal

from .market_data import INTERVAL_MS, MarketDataError, fetch_latest_closed, validate_candle
from .models import SessionState, utc_iso
from .paper_execution import process_candle
from .persistence import StateStore
from .reporting import render_summary
from .risk import RiskConfig, RiskManager
from .strategy import DemoUpCandleStrategy


def run_once(store: StateStore, state: SessionState, risk: RiskManager, previous=None, fetcher=None) -> tuple[SessionState, object | None]:
    fetcher = fetcher or fetch_latest_closed
    candle = fetcher()
    now_ms = int(time.time() * 1000)
    if not validate_candle(candle, now_ms, state.last_candle_time):
        print(f"DUPLICATE candle {utc_iso(candle.close_time)} ignored")
        return state, previous
    outcome = process_candle(state, previous, candle, DemoUpCandleStrategy(), risk)
    state.last_candle_time = candle.open_time
    store.save(state)
    position = state.position
    print(f"{utc_iso(candle.close_time)} price={candle.close} signal={outcome} risk={'approved' if outcome.startswith('ENTRY') else 'not-approved'} position={'FLAT' if position is None else 'LONG'}")
    if state.trades and state.trades[-1].exit_time == candle.close_time:
        trade = state.trades[-1]
        print(f"  entry={trade.entry_price} exit={trade.exit_price} reason={trade.exit_reason} P/L net={trade.net_pnl}")
    return state, candle


def main() -> None:
    parser = argparse.ArgumentParser(description="Public-data paper trading only; no live order capability.")
    parser.add_argument("--capital", required=True, type=Decimal)
    parser.add_argument("--risk-fraction", required=True, type=Decimal, help="e.g. 0.01; explicit user-selected risk")
    parser.add_argument("--max-position-fraction", required=True, type=Decimal)
    parser.add_argument("--stop-loss-fraction", required=True, type=Decimal)
    parser.add_argument("--state", default="paper-state.sqlite3")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    if not args.capital.is_finite() or args.capital <= 0 or args.poll_seconds <= 0:
        parser.error("capital and poll interval must be positive")
    try:
        risk = RiskManager(RiskConfig(args.risk_fraction, args.max_position_fraction, args.stop_loss_fraction))
        store = StateStore(args.state)
        state = store.load(args.capital)
        previous = None
        print(f"Paper only | BTCUSDT 5m | strategy={DemoUpCandleStrategy.name} | fees=0 placeholder | slippage=0 placeholder")
        while True:
            try:
                state, previous = run_once(store, state, risk, previous)
                print(render_summary(state))
            except MarketDataError as exc:
                print(f"SAFE: market data rejected: {exc}")
            except Exception as exc:
                raise SystemExit(f"STOP / SAFE: unexpected error; no further candles will be processed: {exc}") from exc
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped safely. Session state was saved after each processed candle.")
    except ValueError as exc:
        raise SystemExit(f"STOP / SAFE: {exc}") from exc


if __name__ == "__main__":
    main()
