import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal as D
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from personal_trading_paper.market_data import INTERVAL_MS, MarketDataError, validate_candle
from personal_trading_paper.models import Candle, Position, SessionState
from personal_trading_paper.paper_execution import TIME_EXIT_BARS, process_candle
from personal_trading_paper.persistence import StateStore
from personal_trading_paper.reporting import performance_summary
from personal_trading_paper.risk import RiskConfig, RiskManager


def candle(index, open_=100, high=101, low=99, close=100):
    start = index * INTERVAL_MS
    return Candle(start, D(open_), D(high), D(low), D(close), D(1), start + INTERVAL_MS - 1)


class AlwaysEnter:
    name = "test"
    def should_enter(self, previous, current):
        return True


class NeverEnter:
    name = "test"
    def should_enter(self, previous, current):
        return False


def risk():
    return RiskManager(RiskConfig(D("0.01"), D("0.5"), D("0.02")))


class PaperSystemTests(unittest.TestCase):
    def test_closed_candle_validation(self):
        c = candle(1)
        self.assertTrue(validate_candle(c, c.close_time + 1))
        with self.assertRaisesRegex(MarketDataError, "unfinished"):
            validate_candle(c, c.close_time)

    def test_duplicate_and_old_candles(self):
        c = candle(3)
        self.assertFalse(validate_candle(c, c.close_time + 1, c.open_time))
        with self.assertRaises(MarketDataError):
            validate_candle(candle(2), c.close_time + 1, c.open_time)

    def test_stale_data_and_sequence_gap(self):
        c = candle(1)
        with self.assertRaisesRegex(MarketDataError, "stale"):
            validate_candle(c, c.close_time + INTERVAL_MS + 1)
        with self.assertRaisesRegex(MarketDataError, "gap"):
            validate_candle(candle(3), candle(3).close_time + 1, candle(1).open_time)

    def test_invalid_candle(self):
        c = candle(1)
        bad = Candle(c.open_time, c.open, D("90"), c.low, c.close, c.volume, c.close_time)
        with self.assertRaises(MarketDataError):
            validate_candle(bad, bad.close_time + 1)

    def test_entry_and_no_overlapping_position(self):
        state = SessionState(D(1000), D(1000))
        self.assertEqual(process_candle(state, None, candle(1), AlwaysEnter(), risk()), "ENTRY LONG")
        self.assertEqual(process_candle(state, None, candle(2), AlwaysEnter(), risk()), "HOLD")
        self.assertEqual(state.position.side, "LONG")

    def test_stop_loss_and_pnl(self):
        state = SessionState(D(1000), D(1000))
        process_candle(state, None, candle(1), AlwaysEnter(), risk())
        stop = state.position.stop_loss
        exit_candle = candle(2, open_=stop, high=stop, low=stop - 1, close=stop)
        self.assertEqual(process_candle(state, candle(1), exit_candle, NeverEnter(), risk()), "EXIT STOP_LOSS")
        trade = state.trades[0]
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees - trade.slippage)
        self.assertEqual(state.capital, D(1000) + trade.net_pnl)

    def test_time_exit_after_288_bars(self):
        state = SessionState(D(1000), D(1000))
        process_candle(state, None, candle(0), AlwaysEnter(), risk())
        for i in range(1, TIME_EXIT_BARS):
            result = process_candle(state, candle(i - 1), candle(i), NeverEnter(), risk())
            self.assertEqual(result, "HOLD")
        result = process_candle(state, candle(TIME_EXIT_BARS - 1), candle(TIME_EXIT_BARS), NeverEnter(), risk())
        self.assertEqual(result, "EXIT TIME_EXIT")
        self.assertEqual(state.trades[0].bars_held, TIME_EXIT_BARS)

    def test_duplicate_processing(self):
        state = SessionState(D(1000), D(1000))
        c = candle(1)
        self.assertTrue(validate_candle(c, c.close_time + 1, state.last_candle_time))
        process_candle(state, None, c, AlwaysEnter(), risk())
        state.last_candle_time = c.open_time
        self.assertFalse(validate_candle(c, c.close_time + 1, state.last_candle_time))
        self.assertEqual(len(state.trades), 0)

    def test_restart_persistence_and_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.sqlite")
            state = SessionState(D(1000), D(1000), candle(1).open_time, Position("LONG", 123, D(100), D(1), D(98), 4))
            store.save(state)
            restored = store.load(D(999))
            self.assertEqual(restored.capital, D(1000))
            self.assertEqual(restored.position.bars_held, 4)
            self.assertEqual(restored.last_candle_time, state.last_candle_time)

    def test_corrupt_state_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            path.write_text("not sqlite")
            with self.assertRaises(ValueError):
                StateStore(path).load(D(1000))

    def test_graceful_stop(self):
        from personal_trading_paper import runner
        output = StringIO()
        with patch("sys.argv", ["runner", "--capital", "1000", "--risk-fraction", ".01", "--max-position-fraction", ".5", "--stop-loss-fraction", ".02"]), \
             patch.object(runner, "fetch_latest_closed", side_effect=KeyboardInterrupt), \
             redirect_stdout(output):
            runner.main()
        self.assertIn("Stopped safely", output.getvalue())

    def test_no_live_order_path(self):
        package = Path(__file__).parents[1] / "personal_trading_paper"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
        self.assertNotIn("/api/v3/order", source)
        self.assertNotIn("create_order", source)

    def test_performance_summary(self):
        state = SessionState(D(1000), D(1000))
        summary = performance_summary(state)
        self.assertEqual(summary["Number of Trades"], 0)


if __name__ == "__main__":
    unittest.main()
