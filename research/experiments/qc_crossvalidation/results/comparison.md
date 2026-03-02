# QuantConnect Cross-Validation: Results Comparison

**Step**: 36  
**Date range**: 2025-01-01 to 2026-01-01  
**Symbols**: HSBA.L, LLOY.L, BP.L, RIO.L, GLEN.L  
**Capital**: £100,000 (matching Step 1)

---

## Status

**PENDING OPERATOR ACTION** — The QCAlgorithm files have been created but must
be uploaded to QuantConnect Cloud and backtested manually (**free tier only**).

### Steps to complete

1. Log in to [quantconnect.com](https://www.quantconnect.com/)
2. Create a new algorithm → paste contents of `ma_crossover_qc.py` → Backtest
3. Create a new algorithm → paste contents of `rsi_momentum_qc.py` → Backtest
4. Record results below and compare against Step 1 baseline

---

## MA Crossover — Side-by-Side Results

| Metric              | Trading Bot (Step 1) | QuantConnect | Delta | Notes |
|---------------------|---------------------|--------------|-------|-------|
| Sharpe Ratio        | _TBD_               | _TBD_        |       |       |
| Max Drawdown        | _TBD_               | _TBD_        |       |       |
| Total Trades        | _TBD_               | _TBD_        |       |       |
| Win Rate            | _TBD_               | _TBD_        |       |       |
| Total Return (%)    | _TBD_               | _TBD_        |       |       |

---

## RSI Momentum — Side-by-Side Results

| Metric              | Trading Bot (Step 1) | QuantConnect | Delta | Notes |
|---------------------|---------------------|--------------|-------|-------|
| Sharpe Ratio        | _TBD_               | _TBD_        |       |       |
| Max Drawdown        | _TBD_               | _TBD_        |       |       |
| Total Trades        | _TBD_               | _TBD_        |       |       |
| Win Rate            | _TBD_               | _TBD_        |       |       |
| Total Return (%)    | _TBD_               | _TBD_        |       |       |

---

## Expected Divergence Sources

1. **Slippage model**: LEAN uses IB-style half-spread slippage for market
   orders; our PaperBroker uses zero slippage. Expect QC returns to be
   slightly lower.

2. **Commission model**: LEAN uses IB-style per-share commissions for US
   equities (and stamp duty for UK); our PaperBroker uses zero commissions.
   UK trades incur 0.5 % SDRT on buys — QC may apply this.

3. **Data source**: LEAN uses its own equity data feed (QuantQuote / Morningstar
   base); our bot baseline uses EODHD adjusted daily bars. Minor
   differences in adjusted close values after corporate actions are possible.

4. **Fill timing**: LEAN fills market orders at the next bar's open by default;
   our PaperBroker fills at the signal bar's close. This one-bar offset can
   cause trade-by-trade divergence even if aggregate metrics are close.

5. **RSI warm-up**: LEAN's Wilder RSI converges after ~3× period bars; our
   ewm-based RSI converges similarly. Any early-period trade differences
   are warm-up artefacts and should be ignored.

---

## Conclusion

_To be written after backtest results are recorded._

Material discrepancies (>10 % Sharpe deviation or >5 pp drawdown difference)
should be investigated and documented here with root-cause analysis.
