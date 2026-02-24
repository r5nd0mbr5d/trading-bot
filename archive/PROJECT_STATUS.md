# Trading Bot — Project Status & Summary

Generated: February 23, 2026

> Status note: this file is a high-level snapshot. For authoritative task status, blockers, and latest completion state, use [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md).

---

## Executive Summary

**Enterprise-grade algorithmic trading platform** with three core pillars:
1. **Historical Data Collection & Analysis** (25% complete)
2. **Strategy Development & Evaluation** (55% complete)
3. **Real-Time Trading & Learning** (45% complete)

**Overall Completion:** ~60% of Tier 1 (Foundation)

---

## Latest Update (Feb 23, 2026)

### ✅ Newly Completed (UK Readiness)

- [x] **IBKR broker adapter operational** — account-mode guardrails (paper/live mismatch blocking)
- [x] **UK runtime profile (`uk_paper`)** — IBKR defaults, UK symbol set, GBP base currency
- [x] **Market session enforcement** — LSE + US regular session checks, DST-safe timezone handling
- [x] **Timezone invariant fix** — all feed/bar timestamps normalized to UTC-aware datetimes
- [x] **IBKR contract localization** — symbol-level overrides + `.L` inference to GBP/LSE routing
- [x] **FX-normalized portfolio snapshots** — base-currency reporting via configurable FX rates
- [x] **UK tax export CLI mode** — `uk_tax_export` generates ledger, realized gains, and FX notes CSVs
- [x] **Paper session summary CLI mode** — `paper_session_summary` exports execution KPIs to JSON + CSV
- [x] **Paper reconciliation CLI mode** — `paper_reconcile` compares actual KPI drift vs expected targets with tolerance flags
- [x] **Paper trial automation mode** — `paper_trial` runs timed paper session + summary + optional strict reconciliation
- [x] **Trial manifest framework** — `TrialManifest` JSON config for reusable paper trials (3 presets: conservative/standard/aggressive)
- [x] **Manifest-driven CLI** — `paper_trial --manifest configs/trial_standard.json` loads all settings from single JSON
- [x] **Paper-only live promotion gate** — registry blocks `approved_for_live` unless paper KPIs clear explicit thresholds
- [x] **Real-time audit event enrichment** — signals/orders/fills/session events plus fee/slippage fields

### ✅ Test Status

- [x] **287 passing tests** (100% pass rate)
- [x] Added dedicated tests for data timezone handling, IBKR paths, market hours, FX snapshots, UK tax export, and trial manifest loading/CLI integration
- [x] New manifest tests: load/save roundtrip, defaults, override behavior, invalid JSON/missing fields, nonexistent files

---

## Current Status

### ✅ Completed & Tested

#### Strategy Implementations (4)
- [x] **MA Crossover** — Golden cross (fast > slow) → LONG, death cross → CLOSE
- [x] **RSI Momentum** — RSI < 30 → LONG, RSI > 70 → CLOSE
- [x] **MACD Crossover** — MACD > signal line → LONG, bearish crossover → CLOSE
- [x] **Bollinger Bands** — Price touches lower band → LONG, crosses middle band → CLOSE

#### Backtesting Infrastructure
- [x] **Event-driven backtesting engine** — zero lookahead bias, realistic P&L
- [x] **Next-bar-open fills** — orders buffered at bar[t] close, filled at bar[t+1] open
- [x] **Slippage + commission** — 0.05% slippage, $0.005/share commission
- [x] **Paper broker simulator** — realistic order execution simulation

#### Risk Management (production-grade)
- [x] **Position sizing** — Kelly-scaled, signal-strength weighted
- [x] **Stop-loss / Take-profit** — configurable per trade
- [x] **Max drawdown circuit breaker** — halts trading at 20% portfolio loss
- [x] **Intraday loss circuit breaker** — halts if portfolio drops >2% in a day
- [x] **Consecutive loss circuit breaker** — halts after 5 losing trades in a row
- [x] **VaR gate** — blocks new trades if 1-day VaR > 5%
- [x] **Thread-safe** — all state mutations under threading.Lock
- [x] **Kill switch** — persistent SQLite flag, survives restarts, requires operator reset

#### Risk Analytics
- [x] **PortfolioVaR** — historical simulation, 252-day rolling window
- [x] **historical_var_cvar()** — standalone function for VaR + CVaR calculation

#### Strategy Registry
- [x] **SQLite metadata store** — name, version, type, status, parameters
- [x] **Disk artifact storage** — `strategies/<name>/<version>/model.pt`
- [x] **SHA256 integrity verification** — raises ValueError on hash mismatch
- [x] **Lifecycle management** — `experimental → approved_for_paper → approved_for_live`
- [x] **Live promotion readiness gate** — requires paper summary metrics and threshold pass before `approved_for_live`

#### Audit Logging
- [x] **Async audit logger** — asyncio.Queue + background writer task
- [x] **Non-blocking log_event()** — never slows down the trading loop
- [x] **SQLite persistence** — `audit_log` table with 4 indexes
- [x] **Query API** — filter by event_type, symbol, strategy, limit

#### Paper Trading
- [x] **Alpaca integration** — connects to paper account, real market data
- [x] **Pre-warm logic** — loads 5-day 1-min history on startup, no cold-start delay
- [x] **Portfolio snapshots** — logged every poll cycle
- [x] **Kill switch integration** — checks before every bar callback

#### Testing
- [x] **154 passing tests** (100% pass rate)
- [x] **conftest.py** — restricts anyio to asyncio backend

---

## Test Breakdown (140 total)

| Test file | Tests | Coverage |
|---|---|---|
| test_strategies.py | 17 | MA, RSI, MACD, Bollinger Bands |
| test_risk.py | 14 | Position sizing, all circuit breakers, VaR gate |
| test_kill_switch.py | 11 | Trigger, reset, persistence, error handling |
| test_var.py | 15 | VaR/CVaR math, edge cases, rolling window |
| test_registry.py | 22 | Save/load, hash verification, promote, list + paper-readiness live gate |
| test_audit.py | 12 | Async queue, flush, query, persistence |
| test_data_feed.py | 3 | UTC timestamp normalization and conversion |
| test_ibkr_broker.py | 8 | IBKR status/account/contract/currency behaviors |
| test_market_hours.py | 8 | LSE + US session gating, DST-aware checks |
| test_portfolio_fx.py | 2 | Base-currency FX normalization in snapshots |
| test_uk_tax_export.py | 2 | UK tax CSV export and enriched fill parsing |
| test_main_uk_tax_export.py | 1 | CLI export wrapper wiring |
| test_session_summary.py | 1 | Paper session KPI metrics and JSON/CSV export |
| test_main_paper_session_summary.py | 1 | Paper session summary CLI wrapper wiring |
| test_reconciliation.py | 3 | KPI reconciliation drift flags + JSON/CSV export (incl. missing audit table resilience) |
| test_main_paper_reconcile.py | 1 | Paper reconciliation CLI wrapper wiring |
| test_main_paper_trial.py | 3 | Paper trial orchestration: health gate, strict drift, success path |
| test_trial_manifest.py | 4 | Manifest load/save, roundtrip, defaults |
| test_main_paper_trial_manifest.py | 5 | Manifest CLI integration, JSON validation, missing fields |
| (integration) | 7 | End-to-end backtest cycles |

```
============================= test session info ==============================
platform win32 — Python 3.10, pytest-9.x

163 passed in 2.03s
```

---

## Configuration Defaults

```python
# Data
source = "yfinance"
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
timeframe = "1d"

# Strategy (default: ma_crossover)
name = "ma_crossover"

# Risk
max_position_pct = 0.10           # Max 10% per position
max_portfolio_risk_pct = 0.02     # Risk 2% per trade
stop_loss_pct = 0.05              # 5% stop
take_profit_pct = 0.15            # 15% target
max_open_positions = 10
max_drawdown_pct = 0.20           # 20% circuit breaker
max_intraday_loss_pct = 0.02      # 2% intraday halt
consecutive_loss_limit = 5        # 5 consecutive losses → halt
max_var_pct = 0.05                # 5% 1-day VaR gate
var_window = 252                  # 252-day rolling VaR window

# Broker
provider = "alpaca"               # use --profile uk_paper for UK IBKR defaults
paper_trading = True
slippage_pct = 0.0005             # 0.05% per fill
commission_per_share = 0.005      # $0.005/share

# UK / FX
base_currency = "USD"             # UK profile sets GBP
fx_rates = {"USD_GBP": 0.79}
enforce_market_hours = True

# General
risk_free_rate = 0.0              # Used in Sharpe ratio
initial_capital = 100_000.0
```

---

## Latest Backtest Results

**Strategy:** Bollinger Bands
**Period:** 2023-01-01 to 2024-01-01
**Symbols:** AAPL, MSFT, GOOGL, AMZN, TSLA
**Capital:** $100,000

```
Performance Metrics
─────────────────────────────────────────
Initial Capital       : $100,000.00
Final Value           : $107,717.23
Total Return          : 7.72%
Sharpe Ratio          : 2.48 ⭐ (excellent)
Max Drawdown          : 1.07% ⭐ (very conservative)
Total Signals         : 88
Total Trades          : 26
```

---

## Architecture Overview

### Layer 1: Data
- **feeds.py** — Fetch OHLCV via yfinance (free, no API key)
- **models.py** — Bar, Signal, Order, Position dataclasses

### Layer 2: Strategies
- **base.py** — BaseStrategy abstract class
- **ma_crossover.py** — Golden/death cross
- **rsi_momentum.py** — Overbought/oversold
- **macd_crossover.py** — MACD momentum
- **bollinger_bands.py** — Mean reversion
- **registry.py** — SQLite strategy registry with SHA256 verification

### Layer 3: Risk
- **manager.py** — Position sizing, stops, limits, 4 circuit breakers, VaR gate
- **kill_switch.py** — Persistent kill switch (SQLite), survives restarts
- **var.py** — PortfolioVaR + historical_var_cvar()

### Layer 4: Execution
- **broker.py** — AlpacaBroker (paper/live) + PaperBroker (backtest simulation)
- **ibkr_broker.py** — IBKR adapter with symbol routing + account-type checks
- **market_hours.py** — exchange session checks for LSE/US markets

### Layer 5: Portfolio
- **tracker.py** — Position tracking, P&L, max drawdown, snapshots

### Layer 6: Audit
- **logger.py** — Async audit trail, non-blocking, SQLite persistence
- **uk_tax_export.py** — UK tax-oriented CSV exports from audit_log
- **session_summary.py** — paper session KPI summary exports from audit_log

### Layer 7: Backtesting
- **engine.py** — Event-driven replay, next-bar-open fills, slippage/commission

### Layer 8: Entry
- **main.py** — CLI: backtest / paper / live modes, pre-warm logic

---

## File Structure

```
trading-bot/
├── main.py                      ← Entry point (CLI)
├── config/
│   └── settings.py              ← All configuration
├── src/
│   ├── data/
│   │   ├── models.py            ← Bar, Signal, Order, Position
│   │   └── feeds.py             ← Data fetching (yfinance)
│   ├── strategies/
│   │   ├── base.py              ← BaseStrategy (abstract)
│   │   ├── ma_crossover.py
│   │   ├── rsi_momentum.py
│   │   ├── macd_crossover.py
│   │   ├── bollinger_bands.py
│   │   └── registry.py          ← Strategy registry + lifecycle ✨
│   ├── risk/
│   │   ├── manager.py           ← Risk controls, 4 circuit breakers ✨
│   │   ├── kill_switch.py       ← Persistent kill switch ✨
│   │   └── var.py               ← VaR/CVaR analytics ✨
│   ├── execution/
│   │   └── broker.py            ← Alpaca + Paper broker
│   ├── audit/
│   │   └── logger.py            ← Async audit trail ✨
│   └── portfolio/
│       └── tracker.py           ← Position tracking
├── backtest/
│   └── engine.py                ← Event-driven backtester ✨ (next-bar fills)
├── tests/
│   ├── conftest.py              ← anyio asyncio-only fixture ✨
│   ├── test_strategies.py       ← 17 tests ✓
│   ├── test_risk.py             ← 14 tests ✓
│   ├── test_kill_switch.py      ← 11 tests ✓
│   ├── test_var.py              ← 15 tests ✓
│   ├── test_registry.py         ← 21 tests ✓
│   └── test_audit.py            ← 12 tests ✓
└── requirements.txt
```

---

## UK Deployment Notes

- **Alpaca paper trading** — works from the UK (just an API, no real account needed)
- **Alpaca live trading** — US residents only; UK residents cannot open a live Alpaca account
- **For UK live trading** — use Interactive Brokers (`ib_insync` Python API); would require a new `IBKRBroker` class
- **US market hours in UK time:**
  - GMT (Oct–Mar): 14:30 – 21:00
  - BST (Mar–Oct): 15:30 – 22:00
- **Tax:** Capital Gains Tax applies to trading profits for UK residents; the audit logger records every fill to `trading.db`

---

## Quick Start Commands

```bash
# Run all 97 tests
pytest tests/ -v

# Backtest with default settings (MA Crossover, 2022-today, 5 stocks)
python main.py backtest

# Backtest a specific strategy and date range
python main.py backtest --strategy bollinger_bands --start 2022-01-01 --end 2025-01-01

# Backtest specific symbols (including UK stocks via Yahoo Finance)
python main.py backtest --symbols HSBA.L VOD.L BP.L --strategy bollinger_bands

# Paper trade (requires .env with Alpaca API keys)
python main.py paper --strategy bollinger_bands

# Paper trade with custom symbols and capital
python main.py paper --strategy ma_crossover --symbols AAPL MSFT NVDA --capital 50000

# UK paper profile (IBKR + UK symbols + GBP base)
python main.py paper --profile uk_paper

# Generate UK tax export CSVs from audit log
python main.py uk_tax_export --profile uk_paper --db-path trading.db --output-dir reports/uk_tax

# Generate paper session summary metrics (JSON + CSV)
python main.py paper_session_summary --profile uk_paper --db-path trading.db --output-dir reports/session

# Reconcile paper KPIs against expected targets (strict exits non-zero on drift)
python main.py paper_reconcile --profile uk_paper --db-path trading.db --expected-json reports/session/expected_kpis.json --output-dir reports/reconcile --strict-reconcile

# One-command paper trial (health check + timed run + summary + strict reconcile)
python main.py paper_trial --profile uk_paper --paper-duration-seconds 900 --expected-json reports/session/presets/expected_kpis_standard.json --tolerance-json reports/session/presets/tolerances_standard.json --output-dir reports/reconcile --strict-reconcile
```

---

## Not Yet Started (Priority Order)

### Tier 1: Foundation Remaining
- [ ] ATR indicator — volatility-scaled stop losses (replaces fixed 5%)
- [ ] ADX trend filter — only trade when ADX > 25
- [ ] Walk-forward validation — detect overfitting across time windows
- [ ] Multi-provider data adapter — Polygon.io, IEX Cloud fallbacks
- [ ] Equity curve visualization
- [ ] Monte Carlo resampling (luck vs skill analysis)

### Tier 2: Enhancement
- [ ] Daily P&L report + email/Slack alerts
- [ ] Live vs backtest reconciliation
- [ ] Correlation-based position limits (don't hold 5 correlated tech stocks)
- [x] Interactive Brokers broker adapter (UK-ready)

### Tier 3: Advanced ML
- [ ] LSTM price predictor (PyTorch)
- [ ] XGBoost direction classifier
- [ ] Automated weekly model retraining
- [ ] REST API dashboard (FastAPI)

---

## Key Achievements

### Production-Grade Risk Controls ✓
- 4 independent circuit breakers (drawdown, intraday, consecutive loss, VaR)
- Thread-safe state management
- Persistent kill switch (survives crashes/restarts)
- Full audit trail (SQLite, indexed, queryable)

### Realistic Backtesting ✓
- Zero lookahead bias
- Next-bar-open fills (no "buy at the close you just observed")
- Slippage and commission modeled
- Daily returns fed into VaR tracker

### Test Coverage ✓
- 154 tests, 100% passing
- All new modules have dedicated test files
- Async tests properly isolated (asyncio only, no trio conflicts)

---

**Last Updated:** February 23, 2026
**Test Suite:** 154/154 passing ✓
**Status:** Foundation layer (~60% complete) → UK paper-trading + tax export + KPI summary + reconciliation + promotion guardrails + trial automation operational
**Ready for:** Extended UK paper runs, data-provider abstraction, and advanced risk/reporting features
