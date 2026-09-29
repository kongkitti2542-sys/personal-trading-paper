from __future__ import annotations

import json
import time
from decimal import Decimal
from urllib.error import URLError
from urllib.request import urlopen

from .models import Candle

INTERVAL_MS = 5 * 60 * 1000
BASE_URL = "https://data-api.binance.vision"


class MarketDataError(Exception):
    """Public market data is unavailable or invalid; runner must remain safe."""


def validate_candle(candle: Candle, now_ms: int, last_open_time: int | None = None) -> bool:
    values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
    if any(not value.is_finite() for value in values):
        raise MarketDataError("candle has non-finite values")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0 or candle.volume < 0:
        raise MarketDataError("candle has invalid price or volume")
    if candle.open_time < 0 or candle.open_time % INTERVAL_MS != 0:
        raise MarketDataError("candle timestamp is not aligned to 5-minute interval")
    if candle.close_time != candle.open_time + INTERVAL_MS - 1:
        raise MarketDataError("candle interval is invalid")
    if candle.high < max(candle.open, candle.close, candle.low) or candle.low > min(candle.open, candle.close, candle.high):
        raise MarketDataError("candle OHLC values are inconsistent")
    if candle.close_time >= now_ms:
        raise MarketDataError("unfinished candle ignored")
    if now_ms - candle.close_time > INTERVAL_MS:
        raise MarketDataError("market data is stale")
    if last_open_time is not None:
        if candle.open_time == last_open_time:
            return False
        if candle.open_time < last_open_time:
            raise MarketDataError("candle is older than the last processed candle")
        if candle.open_time != last_open_time + INTERVAL_MS:
            raise MarketDataError("candle sequence has a gap")
    return True


def fetch_latest_closed(symbol: str = "BTCUSDT", now_ms: int | None = None) -> Candle:
    """Fetch public klines only; this module has no account or order methods."""
    try:
        with urlopen(f"{BASE_URL}/api/v3/klines?symbol={symbol}&interval=5m&limit=2", timeout=10) as response:
            rows = json.loads(response.read())
        if not isinstance(rows, list):
            raise MarketDataError("unexpected Binance kline response")
        now = int(time.time() * 1000) if now_ms is None else now_ms
        closed = [row for row in rows if int(row[6]) < now]
        if not closed:
            raise MarketDataError("no closed candle returned")
        row = closed[-1]
        return Candle(int(row[0]), Decimal(row[1]), Decimal(row[2]), Decimal(row[3]), Decimal(row[4]), Decimal(row[5]), int(row[6]))
    except (URLError, TimeoutError, OSError, ValueError, IndexError, TypeError, json.JSONDecodeError) as exc:
        if isinstance(exc, MarketDataError):
            raise
        raise MarketDataError(f"public market data fetch failed: {exc}") from exc
