# personal-trading-paper

Standalone BTCUSDT 5-minute paper-trading MVP. It does not import or depend on `personal-trading-bot`. The only network access is public Binance market data (`/api/v3/klines`); there is no API-key, account, or order code.

## Safety and behavior

- Only completed, valid, fresh, sequential candles are processed. Duplicate candles are ignored. A data error skips the cycle.
- The included `DemoUpCandleStrategy` enters long on a green candle. **This is a demonstration strategy, not a production strategy.** Replace it through the `Strategy` protocol only after supplying a separately validated strategy.
- Risk sizing and a fixed stop are required inputs. The runner refuses overlapping entries. There is no leverage or position addition.
- Stops are simulated at the configured stop price if a candle low touches them. Time exit occurs after 288 following bars (24 hours).
- Fees and slippage are currently zero placeholders, so reported P/L is gross of real transaction costs.
- SQLite persists capital, open position, journal, and last processed candle. Corrupt state stops the program. Ctrl+C stops the loop; each accepted candle is saved.

## Run

Use Python 3.12+ and only the standard library. Select the capital and risk values explicitly; these are examples of CLI shape, not recommended settings:

```powershell
python -m personal_trading_paper.runner --capital 1000 --risk-fraction 0.01 --max-position-fraction 0.5 --stop-loss-fraction 0.02
```

Run tests from this directory:

```powershell
python -m unittest discover -s tests -v
```
