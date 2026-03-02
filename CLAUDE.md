# Trading Bot — Claude Code Context

This file is read automatically by Claude Code on every session.
It provides the architectural context needed to work autonomously.

## Document Reading Order (LLM Session Start)

1. **`SESSION_LOG.md`** (last 2–3 entries) — What happened recently; handoff notes from previous sessions
2. **`SESSION_TOPOLOGY.md`** §5 — Identify your session type using the decision tree
3. **`PROJECT_DESIGN.md`** — Read for design or structural work. Contains all ADRs (why things are built this way), active RFCs (proposed changes), technical debt register, and evolution log.
4. **This file (`CLAUDE.md`)** — Session context, invariants, quick-reference conventions (you are here)
5. **`IMPLEMENTATION_BACKLOG.md`** — What to build next and in what order
6. **`.python-style-guide.md`** — How to write the code (read before writing any non-trivial code)

## Project purpose
**Enterprise-grade algorithmic trading platform** for UK-first multi-asset markets (FTSE 100/250 equities, BTC/GBP crypto, planned forex) with:
1. Historical data collection & analysis — EODHD as primary data source, yfinance as fallback
2. Systematic strategy development (rule-based + ML/neural net) including fundamental and correlational analysis
3. Real-time paper trading (sandbox first, PROD path available)

No real money is used unless the user explicitly enables production mode with funded account.

## Three Core Pillars

### Pillar 1: Historical Data Collection & Analysis
- Fetch OHLCV data from multiple providers — **EODHD (primary)**, yfinance (fallback), Massive/Polygon.io, Alpha Vantage, Alpaca
- Normalize across providers, store in SQLite + Parquet with time-series indexes
- Fundamental data pipeline (earnings, financials, ratios) via EODHD Fundamentals API
- Cross-dataset correlational analysis: OHLCV × fundamentals × sentiment × macro
- Exploratory data analysis: trends, seasonality, anomalies, regime detection
- Corporate action adjustments (splits, dividends) via EODHD Corporate Actions API

### Pillar 2: Strategy Development & Evaluation
**Implemented:**
- ✓ MA Crossover (golden/death cross)
- ✓ RSI Momentum (overbought/oversold)
- ✓ Bollinger Bands (mean reversion)
- ✓ MACD Crossover (momentum)

**In Development:**
- ATR-based stops (volatility scaling)
- ADX trend filter (avoid choppy markets)
- Walk-forward backtesting (overfitting detection)
- Neural networks (LSTM/XGBoost on indicator features)

### Pillar 3: Real-Time Trading & Learning
- Paper trading via Alpaca (free, no real money)
- Risk controls: position limits, max daily loss, correlation limits
- Audit trail: every signal, order, fill logged immutably
- Automated retraining loop: retrain models weekly on fresh data
- Daily reporting: P&L, Sharpe ratio, drawdown metrics

## Tech stack
- Python 3.10+
- **EODHD API** (primary market data: OHLCV, fundamentals, corporate actions, forex — API key required)
- yfinance (fallback market data, no API key needed)
- pandas, numpy (data manipulation)
- ta (technical indicators)
- PyTorch (neural networks — MLP implemented, LSTM planned)
- XGBoost (gradient boosting — implemented)
- scikit-learn (calibration/metrics)
- skorch (PyTorch wrapper for sklearn-compatible training)
- alpaca-py (broker, paper trading is free at alpaca.markets)
- coinbase-advanced-py (crypto broker — Coinbase Advanced Trade)
- python-binance (crypto fallback broker — Binance)
- pytest (testing — 657 tests passing)
- SQLite (operational data: audit log, registry, kill switch)
- Parquet (research data: historical OHLCV snapshots)

## Code Style & Standards

**Full style guide:** [.python-style-guide.md](.python-style-guide.md) — read this before writing any non-trivial code.

**MANDATORY for any LLM starting a coding task:** Read `.python-style-guide.md` in full before writing new modules or making structural changes. The summary below covers the most critical rules; the file has complete examples, gotchas, and checklists.

**Enforcement (automatic on commit):**
- `black` — Code formatting (line length: 100)
- `pylint` — Linting & metrics
- `pycodestyle` — PEP 8 violations
- `isort` — Import ordering
- Pre-commit hooks enforce on every `git commit` (bypass: `git commit --no-verify`)

**Key Conventions — must follow without exception:**

*Signatures & types:*
- Type hints on all public functions
- NumPy-style docstrings (Args, Returns, Raises)
- Explicit > implicit — clear signatures, no bare `*args`/`**kwargs`
- All timestamps UTC-aware (`pd.to_datetime(..., utc=True)`)
- Private methods/attributes prefixed with `_`

*Architecture invariants:*
- `RiskManager.approve_signal()` is the **ONLY** path from Signal to Order
- `BacktestEngine` uses `PaperBroker` — never `AlpacaBroker` or `IBKRBroker`
- Strategy inheritance: `class MyStrategy(BaseStrategy)`
- Provider inheritance: `class MyProvider(BaseProvider)`
- Never import from `main.py` in tests — import from the source module directly

*Common Python gotchas — enforce on every PR:*
- **No mutable default arguments** — use `None` sentinel, create inside function
  ```python
  # BAD:  def fn(items=[])
  # GOOD: def fn(items=None) → if items is None: items = []
  ```
- **No late-binding closures over mutable state** — capture values via default args or class attributes, never rely on shared outer-scope variables
- **No circular imports** — if two modules depend on each other, extract the shared contract to `src/data/models.py`
- **No module-level mutable state** — pass objects through constructors, not globals
- **Keep `__init__.py` minimal** — empty or single docstring; no logic

*Design:*
- **Prefer pure functions** (data in → data out, no side effects) for transformations, indicators, and reporting. Reserve classes for objects with long-lived state (brokers, risk manager, strategies).
- **Do not reuse variable names for different types** within a function
- **Boolean tests:** use `if x:` / `if x is None:` — never `if x == True:` / `if x == None:`
- **String building:** use `''.join(parts)` — never `+=` in a loop
- **Throwaway variables:** use `_` for unused loop/unpack values

*Architecture anti-patterns to avoid (by name):*
- **Spaghetti code** — deeply nested closures/conditionals (see `main.py:on_bar` — target of Step 37)
- **Hidden coupling** — test files importing from `main.py` (target of Steps 37–43)
- **Global state abuse** — module-level mutable objects shared across calls

**Setup (first time only):**
```bash
pip install pre-commit black pylint pycodestyle isort
pre-commit install  # Hooks active; will check on every commit
```

**Manual style check:**
```bash
black --check src/ tests/  # See violations
black src/ tests/          # Auto-fix all formatting
pylint src/ --rcfile=.pylintrc
```

## Architecture — where things live

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| Config | `config/settings.py` | All parameters — edit here first |
| Data | `src/data/feeds.py` | Fetch OHLCV via provider layer (EODHD primary, yfinance fallback) |
| Providers | `src/data/providers.py` | EODHDProvider, YFinanceProvider, PolygonProvider, AlphaVantageProvider |
| Symbol utils | `src/data/symbol_utils.py` | Provider-specific symbol normalisation |
| Models | `src/data/models.py` | Bar, Signal, Order, Position, AssetClass dataclasses |
| Strategies | `src/strategies/` | One file per strategy (10 total); all inherit BaseStrategy |
| Risk | `src/risk/manager.py` | Gate between signals and orders; crypto overlay via `CryptoRiskConfig` |
| Broker — Equities paper | `src/execution/broker.py` → `AlpacaBroker` | Alpaca paper trading (equities) |
| Broker — Equities live | `src/execution/ibkr_broker.py` → `IBKRBroker` | Interactive Brokers live |
| Broker — Crypto primary | `src/execution/broker.py` → `CoinbaseBroker` | Coinbase Advanced Trade |
| Broker — Crypto fallback | `src/execution/broker.py` → `BinanceBroker` | Binance fallback (testnet) |
| Broker — Backtest | `src/execution/broker.py` → `PaperBroker` | In-memory simulation; BacktestEngine only |
| Portfolio | `src/portfolio/tracker.py` | P&L and metrics (GBP base) |
| Backtest | `backtest/engine.py` | Bar replay, zero lookahead |
| Trading loop | `src/trading/loop.py` | `TradingLoopHandler`; broker factory with crypto fallback |
| CLI | `src/cli/arguments.py`, `src/cli/runtime.py` | Argument parsing and mode dispatch |
| Entry | `main.py` | 62-line wiring only — do NOT add logic here |

## How to add a new strategy (standard pattern)

1. Create `src/strategies/<name>.py` subclassing `BaseStrategy`
2. Implement `generate_signal(symbol) -> Optional[Signal]`
3. Set `min_bars_required()` to the longest lookback period (use ≥ 3× for ATR-dependent strategies)
4. Register in `src/cli/runtime.py` strategy map (not `main.py`)
5. Add tests in `tests/test_strategies.py`

The MA crossover (`src/strategies/ma_crossover.py`) is the canonical example.

## How to run

```bash
# Backtest
python main.py backtest --start 2022-01-01 --end 2024-01-01

# Specific strategy / symbols
python main.py backtest --strategy rsi_momentum --symbols AAPL NVDA MSFT

# Paper trade (requires .env with Alpaca keys)
python main.py paper

# Research: run XGBoost pipeline from config
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json

# Research: inspect resolved config or list presets
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json --dry-run
python main.py research_train_xgboost --print-presets
```

Research outputs land in `research/experiments/<experiment_id>/` (results, artifacts, training_report).
See `research/README.md` for pipeline details and troubleshooting.

Research artifacts checklist:
- `results/aggregate_summary.json`
- `results/promotion_check.json`
- `results/fold_F1.json`
- `artifacts/<model_id>/model.bin`
- `artifacts/<model_id>/metadata.json`
- `training_report.json`

## How to test

```bash
python -m pytest tests/ -v
```

All tests must pass before considering any task complete.
Never skip a failing test — fix the underlying code.

## Key invariants — never break these

- `RiskManager.approve_signal()` is the ONLY path from Signal to Order.
  Do not submit orders directly from strategies.
- `BacktestEngine` uses `PaperBroker`, not `AlpacaBroker`. Never mix them.
- `generate_signal()` must return `None` if `len(df) < min_bars_required()`.
  This prevents lookahead bias.
- Signal `strength` must be in [0.0, 1.0]. It scales position size.
- Never hardcode ticker symbols or dates outside `config/settings.py`.

## Pre-Commit Hygiene Gate (ADR-021)

Before every non-trivial `git commit`, run the 10-point checklist in `SESSION_TOPOLOGY.md §11`.
For quick commits (≤3 files), checks 1–3 and 9 are sufficient. See ADR-021 in `PROJECT_DESIGN.md §3` for rationale.

## Current Status & Completion Tracker

### ✅ Completed (Foundation + UK Operational)
- [x] 10 strategies (MA, RSI, MACD, Bollinger, ADX, OBV, Stochastic, ATR Stops, Pairs, MLStrategyWrapper)
- [x] Backtesting engine with event-driven replay + walk-forward harness
- [x] Risk manager with VaR gate, circuit breakers, kill switch, correlation limits
- [x] EODHD primary data provider + yfinance fallback
- [x] Multi-provider stack: EODHD, yfinance, Polygon/Massive, Alpha Vantage (scaffold)
- [x] Alpaca paper trading + IBKR live trading
- [x] CoinbaseBroker (crypto primary) + BinanceBroker (crypto fallback)
- [x] Audit logger (async queue → SQLite) + daily report generator
- [x] UK profile: FX-normalised GBP portfolio, UK tax export, session guardrails
- [x] XGBoost ML pipeline (walk-forward, SHAP, promotion check)
- [x] MLP baseline (skorch, pre-LSTM gate)
- [x] Research track governance (4-stage promotion R1→R4)
- [x] 657 passing tests

### 🚧 In Progress
- [ ] MO-2: 3 consecutive in-window paper sessions with fills
- [ ] Step 36: QuantConnect free-tier cross-validation (awaiting operator)
- [ ] EODHD fundamental data pipeline (new — see ticket plan below)
- [ ] Cross-dataset correlational analysis framework (new)

### 🎯 Future (Planned)
- [ ] LSTM/deep-sequence model (gated behind MLP performance)
- [ ] Forex data integration via EODHD
- [ ] Fundamental-driven strategies (earnings, valuation factors)
- [ ] Multi-strategy ensemble voting
- [ ] WebSocket real-time feeds
- [ ] REST API dashboard (FastAPI scaffold exists)

## Next Immediate Steps

**For current outstanding tasks, prompts, and next steps (consolidated in one place), see:**
**[IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)**

**Key priorities:**
1. EODHD fundamental data pipeline (earnings, financials, ratios)
2. Cross-dataset correlational analysis framework
3. Forex integration via EODHD
4. MO-2 in-window paper session sign-off (operator)
5. LSTM baseline (gated behind MLP gate)

Refer to IMPLEMENTATION_BACKLOG for the full Copilot Task Queue and operational milestones.

## Enterprise Checklist (before going to production)

- [ ] **Data integrity:** Automated validation + alerting on gaps
- [ ] **Risk controls:** VaR, CVaR, correlation limits, daily loss circuit breaker
- [ ] **Audit trail:** Immutable log of all decisions + timestamps
- [ ] **Backtesting validation:** Walk-forward + out-of-sample tests
- [ ] **Documentation:** All strategies, parameters, assumptions documented
- [ ] **Testing:** Unit + integration + scenario tests with 90%+ coverage
- [ ] **Monitoring:** Real-time alerts on data quality, execution errors, P&L anomalies
- [ ] **Performance SLA:** Backtest in < 5s, order fill in < 1s, alert in < 10s

## Key invariants — never break these

- `RiskManager.approve_signal()` is the ONLY path from Signal to Order.
  Do not submit orders directly from strategies.
- `BacktestEngine` uses `PaperBroker`, not `AlpacaBroker`. Never mix them.
- `generate_signal()` must return `None` if `len(df) < min_bars_required()`.
  This prevents lookahead bias.
- Signal `strength` must be in [0.0, 1.0]. It scales position size.
- Never hardcode ticker symbols or dates outside `config/settings.py`.
- All timestamps must be timezone-aware (UTC).
- Neural network models must be version-controlled with metadata (training date, parameters, performance metrics).
- Before every non-trivial commit, run the Pre-Commit Hygiene Gate (`SESSION_TOPOLOGY.md §11`, ADR-021).

