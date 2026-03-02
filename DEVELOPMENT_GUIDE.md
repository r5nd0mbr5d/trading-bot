# Trading Bot — AI-Assisted Development Guide

How to use each tool in your environment to research, build, and extend this bot.

---

## Table of Contents

0. [Phase 0: Pre-Build Research](#phase-0--pre-build-research-required-before-implementation) — Answer 11 key questions in LibreChat before any code is written
0b. [UK Profit Research Track](#uk-profit-research-track-offline-strategy-rd) — UK-first strategy R&D structure and workflow
1. [Tool Selection Matrix](#tool-selection-matrix) — Choose the right AI tool for your task
2. [Phase 1: Research](#phase-1--research-before-writing-code) — Research concepts & requirements
3. [Phase 2: Architecture Review](#phase-2--architecture-review-before-implementation) — Validate design
4. [Phase 3: Implementation](#phase-3--implementation-adding-new-features) — Build features
5. [Phase 4: Code Review](#phase-4--code-review-after-implementation) — Quality gate
6. [Phase 5: Backtesting](#phase-5--backtesting) — Validate strategy performance
7. [Phase 6: Paper Trading](#phase-6--paper-trading) — Live testing in sandbox
8. [Enterprise Roadmap](#enterprise-project-roadmap) — 8-week implementation plan
9. [Testing Standards](#testing--documentation-standards-enterprise-grade) — Quality requirements
10. [Feature Priority](#suggested-feature-priority-tier-system) — Tier 1/2/3 system
11. [Troubleshooting](#troubleshooting--common-issues) — Fix common problems
12. [CI/CD Pipeline](#cicd-pipeline-setup) — Automated testing & deployment
13. [Resources](#resources) — Books, papers, tools, and references
14. [Quick Prompt Reference](#quick-prompt-reference) — Ready-to-use prompts
15. [FAQ](#faq) — Frequently asked questions

---

## Phase 0 — Pre-Build Research (required before implementation)

The enterprise CLAUDE.md contains significant architectural choices that must be
decided **before Claude Code writes a single line of infrastructure code**.
Answering these questions in LibreChat first saves days of rework.

All question text, answer slots, and status tracking live in:
**`RESEARCH_QUESTIONS.md`** (same directory as this file)

### Quick reference — what to ask where

| # | Question | Best model | Status |
|---|----------|------------|--------|
| Q1 | Time-series storage: TimescaleDB vs DuckDB+Parquet vs SQLite | LibreChat: **qwen2.5-coder 32B** | [x] |
| Q2 | Event-driven vs vectorised backtesting engine design | LibreChat: **qwen2.5-coder 32B** | [x] |
| Q3 | Strategy registry: file-based vs DB-backed, artifact versioning | LibreChat: **qwen2.5-coder 32B** | [x] |
| Q4 | Free data provider limits: Polygon, Tiingo, Alpha Vantage, yfinance, Alpaca | LibreChat: **gemini-2.5-flash** | [x] |
| Q5 | Alpaca Paper WebSocket streaming — capabilities and reconnection patterns | LibreChat: **gemini-2.5-flash** | [x] |
| Q6 | NN feature engineering: OHLCV features, window sizes, normalisation | **Copilot Chat** `@workspace` | [x] |
| Q7 | NN architecture baseline: MLP vs LSTM vs 1D-CNN for price direction | **Copilot Chat** `@workspace` | [x] |
| Q8 | VaR and CVaR implementation for a retail trading bot | **Copilot Chat** | [x] |
| Q9 | Kill-switch design: persistence, position liquidation, safe resume | **Copilot Chat** | [x] |
| Q10 | Code review: `src/risk/manager.py` — formula correctness and edge cases | **Copilot Chat** `@workspace` | [x] |
| Q11 | Code review: `backtest/engine.py` — lookahead bias and PnL correctness | **Copilot Chat** `@workspace` | [x] |

### Answered decisions (non-Claude-Opus agents)

**Date completed:** 2026-02-23

- **Q1 (storage):** Use DuckDB + Parquet for research/history; keep SQLite for registry/audit/kill-switch metadata.
- **Q2 (engine style):** Keep event-driven architecture for parity with live trading; use queue/callback flow to avoid code duplication.
- **Q3 (registry):** Use hybrid registry: metadata in SQLite + artifacts on disk with SHA256 hash validation.
- **Q4 (data providers):** EODHD is the primary data source (OHLCV + fundamentals + corporate actions + forex). yfinance serves as a free fallback. Massive/Polygon.io for tick data. Alpha Vantage as additional fallback. See ADR-022.
- **Q5 (streaming):** Use WebSocket streaming for paper/runtime where available; implement heartbeat, reconnect with backoff, and idempotent resubscribe.
- **Q6 (features):** Prioritize return/volatility/momentum/volume regime features with leakage-safe rolling normalization and strict timestamp alignment.
- **Q7 (NN baseline):** Start with XGBoost/MLP baseline first, then LSTM only if sequence signal justifies complexity; use time-based train/val/test splits.
- **Q8 (VaR/CVaR):** Use historical simulation VaR/CVaR as gate (not just reporting), with ATR-based sizing retained as complementary control.
- **Q9 (kill-switch):** Persist halt state in SQLite; enforce pre-order checks, deterministic liquidation path, and explicit operator reset workflow.
- **Q10 (risk manager review):** Keep fixed-fractional sizing with strict input guards, add missing halt conditions, and preserve thread-safe/shared-state protections.
- **Q11 (backtest audit):** Keep zero-lookahead semantics, model realistic fills/costs (slippage + commission), and ensure risk-free assumptions are configurable.

### How to use

1. Open LibreChat at http://localhost:3080
2. Select the model shown above for each question
3. Copy the full prompt from `RESEARCH_QUESTIONS.md`
4. Paste the response back into `RESEARCH_QUESTIONS.md` under the matching answer slot
5. Update the status column above from `[ ]` to `[x]`
6. When a block is complete, start a Claude Code session:
   ```
   Read RESEARCH_QUESTIONS.md — Block 1 is fully answered.
   Use those decisions to implement the storage layer.
   ```

### What can start immediately (no research needed)

The Bollinger Bands strategy (CLAUDE.md Section 8) can go to Claude Code right now:
```
Add src/strategies/bollinger_bands.py:
- BUY when close <= lower band (20-day MA - 2 std)
- SELL when close >= middle band (20-day MA)
- Follow ma_crossover.py pattern exactly
- Register in main.py
- Add tests, run pytest, confirm all pass
```

---

## UK Profit Research Track (offline strategy R&D)

For your target outcome (profitability as a UK-based operator), keep runtime trading and
strategy research in the **same project**, but isolate experimental work in a dedicated
research layer so only validated candidates are promoted into runtime.

### Scope alignment (UK-first, not US-only)

- Primary market focus: UK-listed equities/ETFs and GBP base-currency reporting
- Optional expansion: US/EU/global symbols only when portfolio-level profitability improves
- Promotion standard: all research candidates must pass paper-trial and risk gates before runtime enablement

### Suggested structure

Use this project layout for research work:

```text
research/
  README.md
  prompts/
    UK_STRATEGY_PROMPTS.md
  tickets/
    UK_RESEARCH_TICKETS.md
  data/
    snapshots/
    features/
  experiments/
    notebooks/
    runs/
  models/
    artifacts/
    metadata/
```

### Execution assets

- Prompt and agent breakdown: [research/prompts/UK_STRATEGY_PROMPTS.md](research/prompts/UK_STRATEGY_PROMPTS.md)
- Initial implementation tickets: [research/tickets/UK_RESEARCH_TICKETS.md](research/tickets/UK_RESEARCH_TICKETS.md)

### Research pipeline quickstart

```bash
# Run XGBoost pipeline from a config file
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json

# Inspect resolved config or list presets
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json --dry-run
python main.py research_train_xgboost --print-presets
```

Expected outputs (per experiment):

- `research/experiments/<experiment_id>/results/aggregate_summary.json`
- `research/experiments/<experiment_id>/results/promotion_check.json`
- `research/experiments/<experiment_id>/results/fold_F1.json`
- `research/experiments/<experiment_id>/artifacts/<model_id>/model.bin`
- `research/experiments/<experiment_id>/artifacts/<model_id>/metadata.json`
- `research/experiments/<experiment_id>/training_report.json`

Common research commands:

| Purpose | Command |
|---|---|
| Run config-driven XGBoost | `python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json` |
| Print resolved config | `python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json --dry-run` |
| List XGBoost presets | `python main.py research_train_xgboost --print-presets` |

---

## Tool Selection Matrix

| Task | Best tool | Why |
|------|-----------|-----|
| Research indicators / strategies | LibreChat + **qwen2.5:14b** | Explains concepts without hallucinating code |
| Research enterprise requirements | LibreChat + **Gemini 2.0 Flash** | Web-aware, broad knowledge |
| Architecture review | LibreChat + **qwen2.5-coder:32b** | Reads long files, reasons over structure |
| Run research pipeline (CLI) | VS Code terminal | Produces reproducible artifacts and logs |
| Implement a new strategy file | **Aider + Gemini** (cloud) | Structured diff, auto-commits |
| Quick edits / single function | **Aider + qwen2.5-coder** (local) | Fast, free, offline |
| Cross-file refactor | **Claude Code** (Pro OAuth) | Multi-file context, runs tests |
| Code review / bug hunt | LibreChat + **deepseek-coder:33b** | Strong analytical coder |
| Inline explanation while coding | VS Code + **ChatGPT/Copilot** | Fastest for in-editor questions |

---

## Phase 1 — Research (before writing code)

### Prompt: enterprise strategy requirements
Use **LibreChat → qwen2.5:14b or Gemini** before starting any new feature.

```
You are a quantitative analyst at a hedge fund.
I'm building a Python algorithmic trading bot for a UK-based operator trading UK-first but not US-only equities.
List the 10 most important signals/indicators used in professional
systematic strategies, with a one-sentence explanation of each,
and note which are already in pandas-ta.
```

Expected output includes: RSI, MACD, Bollinger Bands, ATR, ADX, OBV,
VWAP, Ichimoku, momentum factors, mean-reversion setups.

### Prompt: risk management requirements
```
What risk controls do institutional quant funds implement beyond
simple stop-losses? Include: VaR, CVaR, Kelly criterion, position
correlation limits, sector exposure, and intraday loss limits.
Suggest which are practical to add to a retail bot first.
```

### Prompt: backtesting pitfalls
```
List the most common mistakes that cause backtests to look better
than live performance: lookahead bias, survivorship bias, overfitting,
transaction cost assumptions, slippage. How do I detect each?
```

---

## Phase 2 — Architecture Review (before implementation)

### Use Claude Code to review the scaffold

```powershell
cd C:\Users\rando\Projects\trading-bot
claude
```

Prompt:
```
Review the architecture of this trading bot codebase.
Identify: missing components for production use, any design flaws,
and the 3 highest-priority features to add next.
Be specific about which files to change.
```

### Use qwen2.5-coder:32b in LibreChat for deep code review

Paste the contents of `src/risk/manager.py` and ask:
```
Review this risk management module for:
1. Mathematical correctness of the position sizing formula
2. Edge cases that could cause division by zero or negative qty
3. Missing risk controls an institution would expect
4. Thread safety issues if running multiple symbols concurrently
```

---

## Phase 3 — Implementation (adding new features)

### Pattern: add a new strategy with Aider (cloud)

```powershell
cd C:\Users\rando\Projects

$env:GEMINI_API_KEY = "AIza..."
aider --config aider/aider-cloud.yml `
      trading-bot/src/strategies/base.py `
      trading-bot/src/strategies/ma_crossover.py
```

Prompt inside Aider:
```
Create trading-bot/src/strategies/bollinger_bands.py implementing a
Bollinger Bands mean-reversion strategy.
- BUY when price touches the lower band (2 std below 20-day MA)
- SELL when price returns to the middle band
- Follow the exact same pattern as ma_crossover.py
- Add it to the STRATEGIES dict in main.py
```

Aider will: create the file, update main.py, and make two git commits.

### Pattern: add a technical indicator with Aider (local, offline)

```powershell
$env:OPENAI_API_BASE = "http://localhost:11434/v1"
$env:OPENAI_API_KEY  = "ollama"

aider --config aider/aider-local.yml `
      --model ollama/qwen2.5-coder:32b `
      trading-bot/src/strategies/rsi_momentum.py
```

Prompt:
```
Add a 200-day simple moving average trend filter to RSIMomentumStrategy.
Only emit a LONG signal if RSI is oversold AND close > 200-day SMA.
This avoids buying in a downtrend.
```

### Pattern: multi-file feature with Claude Code

```powershell
cd C:\Users\rando\Projects\trading-bot
claude
```

Prompt:
```
Add VWAP (Volume-Weighted Average Price) support:
1. Add a compute_vwap() helper to src/data/feeds.py
2. Create src/strategies/vwap_reversion.py using VWAP as the mean
3. Add it to STRATEGIES in main.py
4. Add tests in tests/test_strategies.py
5. Run the tests — make sure all pass
```

Claude Code reads all relevant files, implements across 4 files, runs pytest.

---

## Phase 4 — Code Review (after implementation)

### Use deepseek-coder:33b for thorough code review

In LibreChat → **deepseek-coder 33B**, paste your new strategy file:
```
Review this trading strategy implementation for:
1. Look-ahead bias — is it accidentally reading future prices?
2. Correct use of .iloc[-1] vs .loc[date] in pandas
3. Off-by-one errors in rolling windows
4. Memory leaks from unbounded bar history growth
5. Correctness of the signal_strength normalisation (must stay 0-1)
```

### Run the tests

```powershell
cd trading-bot
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Phase 5 — Backtesting

```powershell
cd trading-bot
pip install -r requirements.txt

# Backtest MA crossover on default symbols (2022-2024)
python main.py backtest --start 2022-01-01 --end 2024-01-01

# Test RSI on specific symbols
python main.py backtest --strategy rsi_momentum --symbols AAPL NVDA MSFT

# Vary parameters (edit config/settings.py or pass a custom Settings object)
```

Interpret results with Claude Code:
```
Here are my backtest results: [paste output]
The Sharpe is 0.4 and max drawdown is 35%. What are the likely causes
and what parameter changes or additional filters would improve it?
```

---

## Phase 6 — Paper Trading

```powershell
# 1. Create free Alpaca account at https://alpaca.markets
# 2. Copy paper trading API keys to trading-bot/.env
# 3. Run
cd trading-bot
python main.py paper --strategy ma_crossover
```

Monitor in a second terminal:
```powershell
# Alpaca paper dashboard: https://app.alpaca.markets/paper/dashboard
# Or check logs:
Get-Content trading-bot\app.log -Wait
```

---

## Enterprise Project Roadmap

The trading bot is built on three core pillars. Use this roadmap to guide development within each phase.

### Pillar 1: Historical Data Collection & Analysis

**Objective:** Build a robust data foundation for strategy research and backtesting.

#### Phase 1.1 — Data Pipeline Setup
- [x] **Multiple provider support** — EODHD primary (ADR-022), yfinance fallback, Massive/Polygon tick data, Alpha Vantage scaffolded
  - File: `src/data/providers.py` (all providers in single module)
  - Pattern: `HistoricalDataProvider` protocol + concrete implementations + factory
- [ ] **OHLCV data persistence** — extend to store in SQLite with proper indexes
  - File: `src/data/store.py` (new)
  - Include: instruments, bars, trades, corporate actions schemas
- [ ] **Incremental backfill** — download history once, append daily
  - File: `src/data/ingestion.py` (new)
  - Resume interrupted downloads, validate data integrity
- [ ] **Macro/economic data** — add unemployment, CPI, Fed rate feeds
  - File: `src/data/macros.py` (new)
  - Join with price data for correlation analysis

#### Phase 1.2 — Exploratory Data Analysis (EDA)
- [ ] **Statistical profiling notebook** — `notebooks/01_data_exploration.ipynb`
  - Autocorrelation, stationarity tests (ADF), distribution analysis
  - Identify trends, seasonality, structural breaks
- [ ] **Factor analysis** — correlation matrix, R² decomposition
  - Which sectors/symbols move together?
  - Identify uncorrelated diversifiers
- [ ] **Anomaly detection** — identify gaps, outliers, data quality issues
  - Daily change distributions, volume anomalies
- [ ] **Regime identification** — bull/bear cycles, volatility regimes
  - Hidden Markov Model or regime-switching analysis

#### Phase 1.3 — Data Quality & Validation
- [ ] **Integrity checks** — OHLC ordering (L ≤ C ≤ H), volume > 0, no future dates
- [ ] **Survivorship bias handling** — track delisted symbols separately
- [ ] **Corporate action adjustments** — splits and dividends corrections
- [ ] **Automated monitoring** — flag data gaps, stale feeds, provider outages

### Pillar 2: Strategy Development & Evaluation

**Objective:** Systematically develop, test, and validate trading strategies with enterprise rigor.

#### Phase 2.1 — Core Technical Indicators (Signals/Indicators)
Implement these in order of priority. Create `src/indicators/` module with utilities.

**Priority A (Momentum & Trend):**
- [ ] **Moving Averages** — SMA, EMA, WMA (already used, enhance with DEMA/TEMA)
- [x] **Relative Strength Index (RSI)** — overbought/oversold detection (DONE: rsi_momentum.py)
- [x] **MACD** — momentum + signal line crossover (DONE: macd_crossover.py)
- [ ] **ADX (Average Directional Index)** — trend strength filter
  - File: `src/indicators/adx.py`
  - Use as: only trade if ADX > 25 (strong trend)
- [ ] **Stochastic Oscillator** — %K, %D for overbought/oversold, momentum divergence

**Priority B (Volatility & Reversion):**
- [x] **Bollinger Bands** — mean reversion bands (DONE: bollinger_bands.py)
- [x] **ATR (Average True Range)** — volatility-scaled stops and position sizing
  - File: `src/indicators/atr.py`
  - Replace fixed 5% stop with 2× ATR
- [ ] **Keltner Channels** — volatility bands (alternative to BB)
- [ ] **Historical Volatility** — 20/60-day windows, volatility clustering

**Priority C (Volume & Flow):**
- [ ] **On-Balance Volume (OBV)** — accumulation/distribution signal
  - File: `src/indicators/obv.py`
- [ ] **Chaikin Money Flow (CMF)** — money flow intensity
- [ ] **Volume-Weighted Average Price (VWAP)** — mean reversion target

**Priority D (Advanced):**
- [ ] **Fibonacci Retracement Levels** — support/resistance identification
- [ ] **Commodity Channel Index (CCI)** — cyclical tops/bottoms
- [ ] **Ichimoku Cloud** — all-in-one indicator for momentum + support/resistance

#### Phase 2.2 — Strategy Architecture
- [ ] **Strategy registry enhancement** — version control, approval workflow
  - Status: experimental → approved_for_paper → approved_for_live
  - File: `src/strategies/registry.py` (enhance existing)
- [ ] **Multi-timeframe strategies** — 1h MA + 1d RSI confluence
  - File: `src/strategies/multi_timeframe.py` (new)
- [ ] **Strategy combinations** — voting/ensemble logic
  - File: `src/strategies/ensemble.py` (new)
  - Example: LONG if (RSI oversold AND price > BB lower) OR (MACD bullish cross)

#### Phase 2.3 — Rule-Based Strategies (Non-ML)
- [ ] **Mean Reversion** — buy dips, sell rallies (extend Bollinger Bands)
- [ ] **Trend Following** — MA crossover, ADX confirmation, ATR stops
- [ ] **Momentum** — RSI/Stochastic bounces, MACD divergences
- [ ] **Sector Rotation** — outperformance relative to benchmark
- [ ] **Pairs Trading** — mean-reverting spread between correlated symbols

#### Phase 2.4 — Backtesting Infrastructure
- [ ] **Walk-forward optimization** — rolling 6mo train / 1mo test
  - File: `backtest/walk_forward.py` (new)
  - Detect parameter overfitting
- [ ] **Scenario testing** — 2008 crisis, COVID crash, high-vol regimes
  - Ensure strategy is robust, not lucky
- [ ] **Monte Carlo resampling** — test sensitivity to trade sequence
- [ ] **Out-of-sample validation** — hold-out test set with no optimization

#### Phase 2.5 — ML/Neural Network Integration (Priority: Tier 3)
- [ ] **Feature engineering pipeline** — indicators → normalized features
  - File: `src/ml/features.py` (new)
  - Lookback windows, normalization, lagging for no lookahead
- [ ] **Time-aware data splits** — train_start:train_end, val_start:val_end, test_start:test_end
  - File: `src/ml/data_splitter.py` (new)
  - No future data leakage
- [ ] **PyTorch-based models** — LSTM for price prediction
  - File: `src/ml/models/lstm.py` (new)
  - Multi-step ahead forecast (1d, 5d)
- [ ] **XGBoost classifier** — binary classification (up/down direction)
  - File: `src/ml/models/xgboost_classifier.py` (new)
- [ ] **NN strategy wrapper** — integrate trained models as strategies
  - File: `src/strategies/neural_net_strategy.py` (new)
  - Serialize model weights + metadata for reproducibility
- [ ] **Experiment tracking** — log all NN runs (hyperparams, metrics, model artifacts)
  - File: `src/ml/experiment_tracker.py` (new)
  - Use MLflow or Weights & Biases

### Pillar 3: Real-Time Trading & Continuous Learning

**Objective:** Execute tested strategies live in sandbox, with automated feedback loops.

#### Phase 3.1 — Live Market Data Integration
- [ ] **Real-time WebSocket streams** — Alpaca, Binance live feeds
  - File: `src/execution/market_feed.py` (enhance)
  - Reconnection + heartbeat handling
- [ ] **Tick data handling** — timestamp ordering, microsecond precision
- [ ] **Data validation in flight** — detect stale/gap data

#### Phase 3.2 — Execution & Order Management
- [ ] **Order execution adapters** — already have AlpacaBroker, add others
  - Support: market, limit (with time-in-force), conditional orders
- [ ] **Slippage modeling** — estimate fill price vs theoretical
  - File: `src/execution/slippage.py` (new)
- [ ] **Commission tracking** — account for broker fees in P&L
- [ ] **Multi-order state machine** — handle partial fills, rejections, cancellations

#### Phase 3.3 — Risk Management (Enterprise-Grade)
- [ ] **Position sizing refinement** — Kelly criterion, fixed fractional, portfolio heat
  - File: `src/risk/position_sizing.py` (enhance)
- [ ] **Correlation-based limits** — don't over-concentrate in correlated assets
  - File: `src/risk/correlation_limiter.py` (new)
- [ ] **Value at Risk (VaR)** — historical or parametric 95% confidence loss
  - File: `src/risk/var.py` (new)
- [ ] **Intraday loss circuit breaker** — auto-halt at -2% daily loss
  - File: `src/risk/circuit_breaker.py` (enhance)
- [ ] **Sector/factor exposure limits** — bounds on concentration
- [ ] **Liquidity checks** — verify enough volume before entering

#### Phase 3.4 — Paper Trading Pipeline
- [ ] **Continuous paper trading bot** — daemon that runs 24/5
  - File: `src/trading/paper_trader.py` (enhance)
  - Graceful restart, health checks
- [ ] **Trade logging & audit trail** — every signal, order, fill recorded
  - File: `src/trading/audit_log.py` (new)
  - Immutable append-only with timestamps + strategy ID + version
- [ ] **Daily reporting** — P&L, Sharpe, max DD, win rate emails
  - File: `src/reporting/daily_report.py` (new)
- [ ] **Alert system** — Slack/email on large losses, execution errors, data gaps

#### Phase 3.5 — Automated Learning Loop
- [ ] **Performance analysis** — capture live vs backtest discrepancies
  - File: `src/analysis/live_backtest_comparison.py` (new)
  - Diagnose sources: slippage, commission, execution timing
- [ ] **Strategy retraining trigger** — retrain NN weekly/monthly
  - File: `src/ml/retraining_scheduler.py` (new)
  - Only if validation performance degrades
- [ ] **Parameter adaptation** — seasonal adjustment, volatility regime switching
  - File: `src/strategies/adaptive_params.py` (new)

---

## Testing & Documentation Standards (Enterprise-Grade)

### Testing Protocol

**Unit Tests (src/tests/):**
- [ ] Indicator computation correctness (test against known values)
- [ ] Risk calculations (position sizing, VaR, limits)
- [ ] Data validation (OHLC ordering, gaps)
- [ ] Signal generation (no lookahead bias, proper timestamps)

**Integration Tests (tests/integration/):**
- [ ] Backtest engine with sample data → verify P&L, Sharpe
- [ ] Strategy + risk manager → trades respect limits
- [ ] Data pipeline → fetch, validate, store cycles

**Scenario Tests (tests/scenarios/):**
- [ ] Live feed with mocked bars → verify decision loop
- [ ] Order rejection → confirm proper fallback
- [ ] Circuit breaker trigger → confirm trading halts
- [ ] Data gap → confirm alert fires, trades pause

**Performance Tests:**
- [ ] Backtest 10y of data in < 5 seconds
- [ ] Real-time indicator update in < 10ms
- [ ] Portfolio retrieval in < 100ms

Run all tests before each deployment:
```powershell
pytest tests/ -v --tb=short --cov=src
```

### Documentation Standards

**Code Documentation:**
- [ ] Docstrings on all public functions (type hints + example usage)
- [ ] Inline comments explaining non-obvious logic
- [ ] Links to research papers / trading books in strategy docstrings

**Architecture Documentation:**
- [ ] System design diagram (components + data flow)
- [ ] Database schema diagram (tables + relationships)
- [ ] State machine diagrams (order lifecycle, trading modes)

**Strategy Documentation (per strategy file):**
- [ ] Trading logic (entry/exit rules in plain English)
- [ ] Hyperparameters (defaults, recommended ranges, sensitivity)
- [ ] Backtest results (Sharpe, DD, win rate on multiple date ranges)
- [ ] Known limitations (regime-specific, correlation assumptions)
- [ ] References (papers, books, blog posts)

**Deployment Documentation:**
- [ ] Config file guide (all knobs explained)
- [ ] Secrets management (API keys, environment variables)
- [ ] Monitoring checklist (what to watch in production)

---

## Suggested Feature Priority (Tier System)

**For current task tracking, see:** [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)

The Tier system below is a reference framework for feature classification. All active tasks (with deadlines, blockers, and success criteria) are tracked in the centralized backlog.

**Task Selection Process:**
1. Check [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) for current week's items
2. Use the Tier reference below to understand priority/complexity
3. Update status in backlog after completion

### Tier 1 — High Priority (Foundation)
- [x] **Bollinger Bands strategy** ✓ (DONE)
- [x] **Paper trial automation + manifest framework** ✓ (DONE)
- [x] **Paper session summary + reconciliation** ✓ (DONE)
- [x] **Paper-only guardrails** — max orders/day, cooldowns, session windows (→ IMPLEMENTATION_BACKLOG Prompt 2)
- [x] **Broker-vs-internal reconciliation** — position/cash sync checks (→ IMPLEMENTATION_BACKLOG Prompt 3)
- [x] **Data provider abstraction** — support Alpha Vantage, Massive/Polygon (→ IMPLEMENTATION_BACKLOG); IEX Cloud removed (shut down Apr 2025)

### Tier 2 — Medium Priority (Enhancement)
- [x] **Multi-day trial runner** — 5-day fixed trials with statistical aggregation
- [x] **Execution telemetry dashboards** — fill rate, slippage, latency by symbol
- [x] **Promotion framework design** — formal framework doc + weekly review template
- [x] **UK test plan** — regime selection, symbol baskets, statistical significance
- [ ] **ADX trend filter** — don't trade choppy markets (ADX < 25)
- [x] **ATR indicator** — volatility-scaled stops for risk manager
- [ ] **Walk-forward backtesting** — detect overfitting
- [ ] **Daily performance reports** — email summary of P&L, metrics
- [ ] **Pairs trading strategy** — mean-reversion on spreads

### Tier 3 — Advanced (Enterprise/ML)
- [x] **Risk architecture blind-spot review** — model drift, execution drift, concentration (→ IMPLEMENTATION_BACKLOG Prompt 7)
- [ ] **LSTM price predictor** — train on 5y history, forecast 1d ahead
- [ ] **XGBoost classifier** — binary direction prediction
- [ ] **NN strategy integration** — run trained models as strategies
- [ ] **Correlation-based position limits** — prevent concentration risk
- [ ] **Multi-strategy voting ensemble** — combine signals from 5+ strategies
- [ ] **WebSocket real-time feeds** — replace polling in Alpaca
- [ ] **REST API dashboard** — FastAPI for portfolio monitoring
- [ ] **Kubernetes deployment** — containerise for cloud/hybrid environments

---

## Troubleshooting — Common Issues

### Issue: Tests Failing After Adding New Strategy

**Symptoms:**
```
FAILED tests/test_strategies.py::TestNewStrategy::test_signal_generation
AssertionError: expected None but got <Signal>
```

**Diagnosis & Fix:**
1. **Insufficient bars:** Strategy needs `min_bars_required()` bars before generating signals
   ```python
   # Wrong: returns signal with only 5 bars when min_bars_required() = 20
   # Fix: add check in generate_signal()
   if len(df) < self.min_bars_required():
       return None
   ```

2. **NaN values in indicator:** Division by zero or invalid calculations
   ```python
   # Wrong: std = 0 → lower_band = NaN
   # Fix: validate before using
   if np.isnan(std) or std == 0:
       return None
   ```

3. **Off-by-one error:** Using wrong index (-1 vs -2)
   ```python
   # Correct pattern for comparing current vs previous:
   curr_value = series.iloc[-1]   # Most recent
   prev_value = series.iloc[-2]   # Previous bar
   ```

**Prevention:**
- Always check `len(df) >= self.min_bars_required()` first
- Test with flat prices (0 volatility edge case)
- Test with insufficient data (should return None, not crash)

---

### Issue: Backtest Performance Worse Than Expected

**Symptoms:**
- Backtest Sharpe: 0.8 but expected 2.5+
- Max drawdown: 45% but expected < 10%
- Win rate: 30% but strategy logic seems sound

**Diagnosis (in priority order):**

1. **Lookahead bias** — strategy sees future data
   ```python
   # Wrong: using future prices
   if df['close'].iloc[-1] > df['close'].iloc[0]:  # Compares across entire history!
       return Signal(...)
   
   # Correct: only use current bar's data
   if df['close'].iloc[-1] > df['close'].iloc[-2]:  # Compares last two bars
       return Signal(...)
   ```
   **Fix:** Use `.iloc[-1]` for current, `.iloc[-2:]` for lookback, never `.iloc[:]`

2. **Survivorship bias** — testing only symbols that survived
   - Some AAPL/MSFT data may have gaps in backtest history
   - **Fix:** Add `validate_data_integrity()` check before backtesting

3. **Overfitting** — strategy works on train data but not test
   - Parameters tuned to 2022-2024 data
   - **Fix:** Run walk-forward validation (6mo train, 1mo test, slide forward)

4. **Wrong transaction costs** — assuming zero commission/slippage
   - Backtest: slippage = 0, commission = 0
   - Real trading: each trade costs 0.1% commission + 0.05% slippage
   - **Fix:** Add costs in RiskManager: `filled_price = price * (1 + slippage + commission)`

5. **Parameter sensitivity** — small changes cause large differences
   - RSI oversold at 30 vs 35 → huge P&L difference
   - **Fix:** Test 5-10 parameter combinations, see if results stable

**Debugging script:**
```python
# Run backtest with different date ranges to check stability
for year in [2022, 2023, 2024]:
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    results = engine.run(start, end)
    print(f"{year}: Sharpe={results.sharpe:.2f}, DD={results.max_dd:.2%}")
```

---

### Issue: Strategy Not Generating Any Signals

**Symptoms:**
- 252 trading days but 0 signals
- Total trades: 0
- No errors in logs

**Diagnosis:**

1. **min_bars_required() too high**
   ```python
   # If min_bars_required() = 252, won't signal until year end!
   def min_bars_required(self) -> int:
       return min(len(self._bar_history), self.lookback_period)  # Wrong!
   
   # Fix: return constant, not dynamic
   def min_bars_required(self) -> int:
       return self.lookback_period  # e.g., 20 bars
   ```

2. **Signal condition never true**
   ```python
   # Debug: add temporary logging
   if close > upper_band:  # Condition always false?
       logging.info(f"SIGNAL: close={close}, upper={upper_band}")
       return Signal(...)
   
   # Add test case that triggers condition
   prices = [100, 102, 104, 106, 108, 110]  # Clear uptrend
   sig = feed_prices(strategy, "TEST", prices)
   assert sig is not None  # Should trigger signal
   ```

3. **Metadata not captured**
   ```python
   # Strategy returns None but should return signal?
   df = self.get_history_df(symbol)
   print(f"DEBUG: {len(df)} bars, min required: {self.min_bars_required()}")
   print(f"DEBUG: close={df['close'].values[-3:]}")  # Last 3 closes
   ```

**Prevention:**
- Write test case for each signal condition FIRST (TDD)
- Log intermediate values in strategy for debugging
- Test with synthetic data that SHOULD trigger signal

---

### Issue: Risk Manager Rejecting Valid Signals

**Symptoms:**
```
Signal generated but RiskManager.approve_signal() returned None
0 trades executed even with signals
```

**Common causes:**

1. **Position already open** (prevents duplicate entry)
   ```python
   # RiskManager checks: if symbol in positions, reject new LONG
   # Fix: must CLOSE position first (signal CLOSE type)
   strategy.generate_signal()  # Returns LONG
   risk.approve_signal(signal)  # Returns None: already own AAPL!
   ```

2. **Insufficient capital** (position size exceeds portfolio)
   ```python
   # RiskManager calculates: qty = (strength × max_pos_pct × portfolio) / price
   # If portfolio=$10k, max_pos_pct=10%, price=$150: max qty = 6 shares
   # But if only $1k available, qty rounds to 0 → order rejected
   ```

3. **Circuit breaker active** (max drawdown exceeded)
   ```python
   # portfolio lost 20%+ → circuit_breaker halts all trades
   # Fix: restart after reviewing losses, reset settings.risk.max_drawdown_pct
   ```

**Debugging:**
```python
# Add logging to understand which risk rule fired
order = risk.approve_signal(signal)
if order is None:
    portfolio_value = broker.get_portfolio_value()
    positions = broker.get_positions()
    print(f"Rejected because: {len(positions)}/{settings.risk.max_open_positions} positions open")
    print(f"Portfolio value: ${portfolio_value}")
    print(f"Max position size: ${portfolio_value * settings.risk.max_position_pct}")
```

---

### Issue: Paper Trading Crashes With Alpaca Connection Error

**Symptoms:**
```
alpaca.APIError: <HTTPStatusCode.UNAUTHENTICATED: 401>
```

**Fix:**
1. Verify `.env` file exists in `trading-bot/` directory
2. Check API keys are correct: https://app.alpaca.markets → Settings → API Keys
3. Confirm keys are in `.env` (not `.env.example`):
   ```bash
   ALPACA_API_KEY=your_actual_key_here
   ALPACA_SECRET_KEY=your_actual_secret_here
   ```
4. Restart Python process (reload environment variables)
5. Test connection: `python -c "from alpaca_py import StockHistoricalDataClient; print('OK')"`

---

### Issue: Backtest Runs Slowly (> 30 seconds for 5 years)

**Symptoms:**
- 5y backtest takes 2+ minutes
- Paper trading updates prices slowly

**Optimization steps:**

1. **Profile to find bottleneck:**
   ```python
   import cProfile
   cProfile.run('engine.run("2019-01-01", "2024-01-01")')
   ```

2. **Common causes:**
   - Strategy computing full rolling window every bar
   - Indicator libraries not vectorized
   - Fetching data from network during backtest

3. **Fixes:**
   ```python
   # Slow: compute SMA from scratch each bar
   def generate_signal(self, symbol):
       close = self.get_history_df(symbol)["close"]
       for i in range(20, len(close)):
           ma = close.iloc[i-20:i].mean()  # O(N²) complexity!
   
   # Fast: use pandas rolling (vectorized)
   def generate_signal(self, symbol):
       close = self.get_history_df(symbol)["close"]
       ma = close.rolling(20).mean()  # O(N) complexity
   ```

---

### Issue: Strategy Parameter Sensitivity

**Symptom:** Small change in parameter (20 vs 21-day MA) → total P&L changes from +30% to -10%

**This is overfitting.** The strategy is not robust.

**Fix:**
1. Test parameter sensitivity:
   ```python
   results = {}
   for period in range(15, 50):
       engine.settings.strategy.ma_period = period
       r = engine.run("2022-01-01", "2024-01-01")
       results[period] = r.sharpe
   
   # Plot: should be smooth curve, not spiky
   import matplotlib.pyplot as plt
   plt.plot(results.keys(), results.values())
   plt.xlabel("MA Period")
   plt.ylabel("Sharpe Ratio")
   ```

2. If spiky → overfitted. Solution:
   - Use larger timeframe (broader MA periods)
   - Add regime filters (don't trade choppy markets)
   - Diversify strategies (don't depend on single parameter)

---

## CI/CD Pipeline Setup

Automated testing before deployment (prevent bugs reaching production).

### Local CI: Pre-commit Hooks

Install `pre-commit` to run tests on every commit:

```bash
pip install pre-commit

# Create .pre-commit-config.yaml in repo root
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/ -v
        language: system
        pass_filenames: false
        always_run: true
        stages: [commit]
      
      - id: black
        name: black
        entry: black src/ tests/ config/
        language: system
        types: [python]
        stages: [commit]
      
      - id: flake8
        name: flake8
        entry: flake8 src/ tests/
        language: system
        types: [python]
        stages: [commit]
EOF

pre-commit install
```

Now every commit runs:
- ✓ pytest (28+ tests)
- ✓ black (code formatting)
- ✓ flake8 (linting)

Commit will be blocked if any fail.

### GitHub Actions (CI/CD in Cloud)

Create `.github/workflows/test.yml`:

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

Benefits:
- Runs tests on every push
- Blocks merge if tests fail
- Tests multiple Python versions
- Generates coverage reports

### Deployment Checklist

Before deploying to paper trading:

```bash
# 1. Run full test suite
pytest tests/ -v --tb=short

# 2. Run backtest on multiple periods
python main.py backtest --start 2022-01-01 --end 2024-01-01
python main.py backtest --start 2024-01-01 --end 2025-01-01

# 3. Code quality checks
black --check src/ tests/
flake8 src/ tests/
mypy src/ --ignore-missing-imports

# 4. Check test coverage
pytest tests/ --cov=src --cov-report=term-missing

# 5. Verify no uncommitted changes
git status

# 6. Create release tag
git tag -a v0.1.0 -m "First production release"
git push origin v0.1.0

# 7. Deploy
python main.py paper --strategy ma_crossover
```

---

## Resources

### Strategic Books & References

**Systematic Trading Strategy**
- *Systematic Trading: A Unique New Method for Designing Trading Systems* by Robert D. Pardo (2nd ed, 2019)
  - Core reference for backtesting methodology, risk management, and strategy evaluation
  - Pattern: Analyze → Design → Build → Verify → Optimize

- *Machine Learning for Asset Managers* by Cédric Bailly (2022)
  - Statistical foundations for feature engineering and model selection
  - Lookahead bias detection, backtest overfitting, Deflated Sharpe ratio

**Data Science & Quantitative Finance**
- *Advances in Financial Machine Learning* by Marcos López de Prado (2018)
  - Industry standard for triple-barrier labeling, combinatorial purged cross-validation, feature importance
  - How to avoid 99% of backtesting pitfalls

- *Machine Learning for Quantitative Finance* by Giuseppe A. Paleologo (2023)
  - ML pipeline for trading: preprocessing → model selection → backtesting → deployment

**Risk Management**
- *The Black Swan* by Nassim Nicholas Taleb (2007)
  - Statistical tail risks, fat tails in finance, risk management philosophy
  - Why historical value-at-risk models fail

- *Portfolio Management Formulas* by Ralph Vince (2nd ed, 2009)
  - Position sizing theory: fixed fractional, Kelly criterion, optimal f, secure f

**Trading Psychology & Execution**
- *Fooled by Randomness* by Nassim Nicholas Taleb (2001)
  - How to distinguish skill from luck in trading systems
  - Why backtests lie: curve-fitting, multiple comparisons, selection bias

### Academic Papers & Whitepapers

**Backtesting Methodology**
- Bailey et al. (2015): "Deflated Sharpe Ratio" — Probability of backtest overstatement
  - SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
  - Use to validate strategy signal quality

- De Prado (2018): "Advances in Financial ML" (free chapter on backtesting)
  - Combinatorial purged k-fold cross-validation
  - How to prevent lookahead bias and in-sample overfitting

**Technical Indicators & Signals**
- Bollinger, J. (1992): "Bollinger Bands" — Volatility-based mean reversion triggers
  - Original paper: *New Concepts in Technical Trading Systems*
  - Foundation for entry at lower band, exit at middle band

- Wilder, J. W. (1978): "New Concepts in Technical Trading Systems"
  - RSI (Relative Strength Index): overbought (>70) / oversold (<30) calibration
  - ATR (Average True Range): volatility measure for position sizing

**Risk Management**
- Artzner et al. (1999): "Coherent Measures of Risk"
  - Mathematical foundations for Expected Shortfall (CVaR) vs Value-at-Risk (VaR)
  - Why portfolio risk is nonlinear (correlation breakdown during crises)

### Online Tools & Python Libraries

**Backtesting Frameworks**
- **Backtrader**: Full event-driven backtester (Python)
  - Comparable to our implementation; good for multi-timeframe strategies
  - Doc: https://www.backtrader.com/

- **VectorBT**: Vectorized backtester (pandas/numpy)
  - Fast (milliseconds for 20+ years), good for optimization
  - Doc: https://vectorbt.pro/

- **MLflow**: Track experiments, log metrics, serve models
  - Essential for strategy hyperparameter optimization
  - Doc: https://mlflow.org/

**Technical Indicators**
- **pandas-ta**: 200+ TA indicators, pandas syntax
  - Already integrated; covers Bollinger Bands, RSI, MACD, ATR, ADX
  - Doc: https://github.com/twopirllc/pandas-ta

- **TA-Lib**: Industry-standard C library with Python bindings
  - 150+ indicators, highest performance
  - Doc: https://ta-lib.org/

**Data Sources & APIs**
- **EODHD (PRIMARY)**: OHLCV, fundamentals, corporate actions, forex (API key required)
  - Current integration in settings.py `source: 'eodhd'` (default)
  - Implementation: `EODHDProvider` in `src/data/providers.py`
  - Supports UK LSE (`.LSE` suffix), US (`.US`), forex (`.FOREX`), crypto (`.CC`)
  - See ADR-022 and `docs/DATA_PROVIDERS_REFERENCE.md` §2.0 for full details

- **yfinance (FALLBACK)**: Free OHLCV data (Yahoo Finance, no API key)
  - Fallback integration in settings.py `fallback_sources: ['yfinance']`
  - Suitable for development when no EODHD API key is available; not recommended for production

- **Alpaca Markets API**: Commission-free equity trading, paper trading, real-time data
  - Integration: `src/execution/broker.py` (`AlpacaBroker`)
  - Paper trading enables live backtesting before capital deployment

- **Alternative Data Sources** (Tier 2+)
  - Massive (Polygon.io): High-resolution minute/second bars, tick data, options chains, S3 flat files — implemented
  - Alpha Vantage: US equity OHLCV fallback, server-side indicators — scaffolded (Step 29)
  - Twelve Data: 50+ global exchanges, crypto, forex

**Machine Learning**
- **scikit-learn**: Classification, regression, ensemble models
  - Good for: feature selection, cross-validation, metrics
  - Doc: https://scikit-learn.org/

- **XGBoost / LightGBM**: Gradient boosting (tabular data)
  - Standard in quant hedge funds for alpha generation
  - Docs: https://xgboost.readthedocs.io/ | https://lightgbm.readthedocs.io/

- **PyTorch / TensorFlow**: Neural networks (Tier 3)
  - LSTM for time-series prediction
  - Transformers for multi-asset correlation learning

### Monitoring & Production

**Backtesting & Paper Trading Dashboards**
- **Grafana**: Metrics visualization, port 3000
  - Visualize: daily returns, Sharpe ratio, drawdown, win rate
  - Setup: 1-2 hours for basic dashboard

- **TensorBoard**: PyTorch/TensorFlow metrics logging
  - Used in Tier 3 for neural network training curves

- **Alpaca Trading Dashboard**: Built-in paper trading monitor
  - View: portfolio value, positions, P&L, active orders
  - Access: https://app.alpaca.markets/dashboard

**Deployment & CI/CD**
- **GitHub Actions**: Free CI/CD (already covered in this guide)
  - Pre-commit hooks: pytest, black, flake8

- **Docker**: Containerize bot for production
  - Isolate Python environment, run anywhere (cloud, VPS, local)

- **Kubernetes**: Orchestrate multiple bot instances (Tier 3)
  - Auto-restart on crash, horizontal scaling, persistent volumes

### Trading Concepts Glossary

| Term | Definition | Application |
|------|-----------|-------------|
| **Sharpe Ratio** | Return / Volatility (excess return per unit of risk) | Target > 1.0 for research, > 2.0 for deployment |
| **Drawdown** | Peak-to-trough loss during strategy execution | Max drawdown: -20% is typical; circuit break at -30% |
| **Win Rate** | Profitable trades / Total trades | 50-60% is normal for systematic strategies |
| **Profit Factor** | Gross profit / Gross loss (should be > 1.5) | Below 1.5: strategy is marginal |
| **Kelly Criterion** | f* = (p × b - q) / b (optimal position size) | Leverage = Kelly % × 1.25 (safety margin) |
| **Max Position %** | Max capital in single symbol | 10% default; controls idiosyncratic risk |
| **Circuit Breaker** | Stop all trading if daily loss > threshold | 2% portfolio loss typical; prevent cascading failures |
| **Lookahead Bias** | Using future data in backtest accidentally | Use `min_bars_required()` to enforce lookback window |
| **Curve Fitting** | Overfitting parameters to historical data | Validate on out-of-sample period (25% of data) |
| **Equity Curve** | Cumulative portfolio value over time | Should show monotonic increase; dips = volatility/drawdown |

### Key Metrics to Track

For each strategy, calculate and log:

1. **Return Metrics**
   - Total return: (Final Value - Initial) / Initial
   - Annual return: (Total Return) ^ (1 / Years)
   - Alpha: Excess return over S&P 500 benchmark

2. **Risk Metrics**
   - Volatility (Std Dev of daily returns)
   - Max drawdown: Largest peak-to-trough loss
   - Calmar ratio: Annual return / Max drawdown (target > 1.0)

3. **Efficiency Metrics**
   - Sharpe ratio: Return / Volatility (target > 2.0)
   - Sortino ratio: Return / Downside volatility (penalizes losses)
   - Win rate: Profitable days / Total trading days

4. **Production Readiness**
   - Trades per year: Order count (too many = slippage risk)
   - Trade cost: Avg slippage + commission per trade
   - Correlation with other strategies: Should be < 0.3 (diversification)

---

## Quick Prompt Reference

### Research & Concept Prompts (LibreChat)

**Explain Kelly Criterion:**
> Explain the Kelly criterion for position sizing. Give:
> 1. The formula: f* = (p × b - q) / b  where p = win prob, b = win/loss ratio, q = loss prob
> 2. Example: $100k portfolio, 55% win rate, 1.5:1 win/loss ratio
> 3. Limitations: requires accurate p & b estimates, full repay fraction is risky
> 4. Practical: use f*/2 to f*/4 for safety (fractional Kelly)

**Analyze Backtest Discrepancies:**
> My backtest shows 40% return but live trading gives 5%. List causes in priority order:
> 1. What's most likely: lookahead bias, overfitting, slippage, or regime change?
> 2. How to diagnose each
> 3. What to fix first

**Risk Management for Retail:**
> What risk controls should a $10k retail trading account use?
> Prioritize by importance. Include: position sizing, stop-losses, correlation limits, daily loss limits.
> What's achievable with Alpaca Paper Trading API?

---

### Implementation Prompts (Claude Code or Aider)

**Add a New Strategy:**
> Create a new strategy file: `src/strategies/rsi_adx_filter.py`
> 
> Logic:
> - Entry: RSI < 30 AND ADX > 25 (strong trend)
> - Exit: RSI > 70 OR ADX < 15 (trend broken)
> 
> Requirements:
> - Follow bellinger_bands.py pattern
> - Include docstring
> - Set correct `min_bars_required()`
> - Register in main.py
> - Add 5+ test cases

**Add an Indicator:**
> Create `src/indicators/atr.py` (Average True Range)
> 
> Formula:
> - True Range = max(H-L, abs(H-PC), abs(L-PC))
> - ATR = rolling average over 14 periods
> 
> Requirements:
> - Return pandas Series
> - NaN for first N bars
> - Add unit tests vs TA-Lib

---

### Debugging Prompts

**Debug Failing Tests:**
> [Paste test output]
> 
> Analyze:
> 1. Root cause (assertion failure location)
> 2. Source code bug
> 3. How to fix
> 4. Prevention (new test case)

**Slow Backtest:**
> Backtest takes 5 min for 5 years. Analyze:
> 1. Bottleneck (calc, I/O, memory)?
> 2. How to profile?
> 3. Optimization approach?

---

### Architecture Prompts

**Design Multi-Strategy System:**
> How should I run 5 strategies simultaneously on different symbol lists?
> Design for:
> 1. No position conflicts
> 2. Strategy switching without restart
> 3. Shared position tracking
> 4. Atomic order placement

---

### One-Liners

**Run all tests:**
```bash
pytest tests/ -v --tb=short
```

**Backtest default symbols:**
```bash
python main.py backtest --start 2023-01-01 --end 2024-01-01
```

**Run specific test:**
```bash
pytest tests/test_strategies.py::TestBollingerBandsStrategy -v
```

**Check with coverage:**
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

---

## FAQ

### Strategy Development

**Q: How do I add a new strategy to the platform?**

A: Follow Pattern 3 from Phase 3: Implementation.
1. Create `src/strategies/my_strategy.py` inheriting from `BaseStrategy`
2. Implement `min_bars_required()` (lookback window)
3. Implement `generate_signal(symbol)` returning `Signal` or `None`
4. Register in `main.py`: Add to `STRATEGY_REGISTRY`
5. Add tests in `tests/test_strategies.py`: At least 6 test cases (no signal, before min bars, flat prices, signal generation, metadata, inheritance)
6. Run: `pytest tests/test_strategies.py::TestYourStrategy -v`
7. Backtest: `python main.py backtest --strategy my_strategy`

**Q: What's the minimum bars requirement? Why?**

A: `min_bars_required()` enforces lookback to prevent lookahead bias. For example:
- Moving Average (20-day period): `min_bars_required() = 21` (need 20 prior bars + current)
- RSI (14-day period): `min_bars_required() = 15` (14 prior + current)
- Bollinger Bands (20-day period): `min_bars_required() = 21`

Without this, your strategy would use bar N-1 to decide at bar N, which is unrealistic.

**Q: How do I test my strategy without trading real money?**

A: Use the backtesting engine in two stages:
1. **Offline backtest** (historical data): `python main.py backtest --start 2023-01-01 --end 2024-01-01`
2. **Paper trading** (sandbox): `python main.py paper --strategy my_strategy` (runs live against Alpaca paper account)

Paper trading simulates real execution: slippage, rejected orders, liquidity constraints.

**Q: How do I ensure my strategy isn't curve-fit to historical data?**

A: Use out-of-sample validation:
1. Split dataset: 70% training (2023-2024), 30% test (2024 Q1-Q2)
2. Optimize parameters on training set only
3. Validate final metrics on test set
4. If test Sharpe < 70% of training Sharpe, strategy is overfit

Alternatively, use `min_bars_required()` for walk-forward validation.

**Q: What's the difference between strength and signal type?**

A: 
- **Signal Type** (`LONG`, `CLOSE`, `SHORT`): Direction of trade
- **Strength** (0.0 - 1.0): Confidence in signal, controls position sizing
  - Strength 0.5 → position = 5% of portfolio
  - Strength 1.0 → position = 10% of portfolio (max)

Example: Bollinger Bands at lower band = strength 1.0 (high conviction)

### Backtesting & Performance

**Q: My backtest shows 50% return but paper trading shows only 5%. Why?**

A: Common causes (in priority order):
1. **Lookahead bias**: Check `min_bars_required()` — are you using future data?
2. **Slippage not modeled**: Backtest assumes instant fills; paper trading has latency
3. **Parameter overfitting**: Reoptimize on recent data to check
4. **Survivorship bias**: Dataset includes delisted stocks; check yfinance for gaps
5. **Market regime change**: 2023 uptrend ≠ 2024 downtrend; validate on different periods

Run diagnostic: `pytest tests/test_backtesting.py -v` to test for lookahead.

**Q: How do I know when my backtest results are statistically significant?**

A: Use the Deflated Sharpe Ratio heuristic:
- Sharpe > 2.0: Very likely real (90%+ confidence)
- Sharpe 1.5-2.0: Likely real (70% confidence)
- Sharpe 1.0-1.5: Marginal (50% confidence, risky for deployment)
- Sharpe < 1.0: Noise (don't trade)

Multi-strategy backtest Sharpe is lower than single-strategy by √N (diversification penalty).

**Q: Why is my backtest running slowly?**

A: Check in priority order (see Troubleshooting section for detailed diagnosis):
1. **Vectorization**: Use pandas `.values` instead of `.iterrows()` — 100× faster
2. **Data loading**: Cache OHLCV data in SQLite, not yfinance API calls each run
3. **Calculation overhead**: Pre-calculate indicators in `generate_signal()`, don't recalculate each bar
4. **Too many signals**: If > 500 trades/year, filter signals in risk manager

Benchmark: 5 years of daily data on 5 symbols should backtest in < 10 seconds.

### Risk Management

**Q: What's the difference between stop-loss and circuit breaker?**

A:
- **Stop-Loss** (5% default): Per-trade protection — exit if position loses 5%
- **Circuit Breaker** (2% daily loss default): Portfolio protection — stop all trading if daily portfolio loss > 2%

Example: 3 positions each down 2% = 6% portfolio loss → circuit breaker triggers, no new trades.

**Q: How do I prevent the risk manager from rejecting my signals?**

A:
1. **Check max_position_pct**: Current position size < 10% portfolio
2. **Check max_portfolio_risk**: Sum of all position risks < 2% of portfolio
3. **Check open_positions**: Don't open another LONG on same symbol (no doubles)
4. **Check stop-loss**: Position not already at stop target

Validate with: `python -c "from src.risk_manager import RiskManager; rm = RiskManager(settings); print(rm.can_trade('AAPL', 'LONG'))"`

**Q: How should I size my positions?**

A: Use the formula in DATA_MODELS.md:
```
position_size = strength × max_position_pct × portfolio_value / entry_price
```

Example:
- Portfolio: $100k, max 10%, strength 0.8, AAPL $150
- Position: 0.8 × 0.10 × $100k / $150 = 533 shares = ~$80k

Conservative approach: Use strength 0.5 minimum until strategy proves itself.

### Data & Configuration

**Q: How do I add a new stock symbol to track?**

A: Edit `config/settings.py`:
```python
symbols: list = field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "YOUR_SYMBOL"])
```

Then backtest: `python main.py backtest --symbols AAPL,YOUR_SYMBOL`

**Q: How do I use data beyond yfinance (Massive/Polygon.io)?**

A: Massive (Polygon.io) is already implemented. Set `data.source = "polygon"` in `config/settings.py`
and ensure `POLYGON_API_KEY` is in `.env`. For Alpha Vantage (Step 29 in backlog):
1. Implement `AlphaVantageProvider` in `src/data/providers.py`
2. Add `ALPHA_VANTAGE_API_KEY` to `.env`
3. Set `data.source = "alpha_vantage"`

Note: IEX Cloud was removed from this project — it shut down in April 2025 and is no longer operational.
For now, yfinance is sufficient for all 4 strategies.

**Q: How do I change the backtest time period?**

A: Command-line override:
```bash
python main.py backtest --start 2024-01-01 --end 2024-06-30
```

Or in `config/settings.py`:
```python
lookback_days: int = 180  # Last 6 months
```

### Testing & Debugging

**Q: How many test cases should I write for a new strategy?**

A: Minimum 6:
1. **No signal before min_bars**: Ensure `min_bars_required()` enforcement
2. **Realistic price sequence**: LONG/CLOSE signals generate without error
3. **Edge case: flat prices**: No signal if std=0 (zero volatility)
4. **Edge case: insufficient data**: NaN handling
5. **Metadata completeness**: Signal contains all required fields (band values, etc.)
6. **Inheritance compliance**: Strategy inherits BaseStrategy properties

Write tests that WILL trigger signals to validate the logic.

**Q: My test passes locally but fails in GitHub Actions. Why?**

A: Common causes:
1. **Relative paths**: Use `Path(__file__).parent / "data.csv"` instead of hardcoded paths
2. **Floating-point precision**: Use `pytest.approx()` for float comparisons: `assert result == pytest.approx(1.234, abs=0.001)`
3. **Timezone assumptions**: Market data might be UTC vs EST; use `pytz` library
4. **Random seed not set**: Add `np.random.seed(42)` at test start if using synthetic data

Run locally with: `pytest tests/ -v` to match CI environment.

**Q: How do I debug a strategy that generates no signals?**

A: Follow the Troubleshooting section, but quick checklist:
1. Check `min_bars_required()`: Backtest starts after warm-up window?
2. Log intermediate calculations: Add `print(f"Signal condition: {condition}")` in `generate_signal()`
3. Validate data: `df = self.get_history_df(symbol); print(df.tail())`
4. Test with synthetic data: Create a test case with known good price sequence

---

### Admin & Deployment

**Q: How do I set up the pre-commit hook to run tests automatically?**

A: Check CI/CD Pipeline section, but quick setup:
```bash
pip install pre-commit
pre-commit install
git add .pre-commit-config.yaml
git commit -m "Add pre-commit hooks"
```

Now `pytest`, `black`, `flake8` run on every commit.

**Q: Can I run the bot in the background on a VPS?**

A: Yes, use:
1. **systemd service** (production): Add `trading-bot.service` to `/etc/systemd/system/`
2. **screen / tmux** (temporary): `screen -S bot && python main.py paper --strategy ma_crossover`
3. **Docker** (containerized): Build image, deploy to cloud

See Deployment Checklist in CI/CD Pipeline section.

**Q: What Python version should I use?**

A: **Python 3.10+** (required by type hints and alpaca-py)

Check: `python --version` → should be 3.10.x or 3.11.x or 3.12.x

**Q: How do I update alpaca-py or pandas without breaking everything?**

A: Use `requirements-dev.txt` with pinned versions:
```
pandas==2.0.3
alpaca-py==0.18.3
yfinance==0.2.28
```

To upgrade safely:
```bash
pip install --upgrade pandas --dry-run  # Preview changes
pip install --upgrade pandas  # Commit
pytest tests/ -v  # Verify nothing broke
git add requirements.txt && git commit -m "Upgrade pandas to 2.1.0"
```

**Q: My backtest shows great returns but I'm nervous about deploying. Anything else to check?**

A: Deployment Checklist in CI/CD Pipeline section covers this. But quick summary:
1. ✅ Backtest Sharpe > 1.5 on 2+ year dataset
2. ✅ Walk-forward validation: test set Sharpe > 70% of training Sharpe
3. ✅ Max drawdown scenario: backtest would survive -40% market crash
4. ✅ Paper trading for 2+ weeks: real slippage, no curve-fit surprises
5. ✅ Code review: deepseek-coder finds logical errors
6. ✅ Tests passing: 100% pass rate on CI/CD
7. ✅ Production monitoring: Alerts on max drawdown > threshold

Once all clear, deploy to live trading with position_size = 50% of backtested (conservative start).
