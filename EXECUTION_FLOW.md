# Execution Flow Architecture

**Purpose**: Map the startup and runtime sequences for each bot mode to understand control flow, dependencies, and decision points.

**Quick Start**: Choose your mode below:
- [Paper Trading Flow](#paper-trading-flow) — Async loop with real-time bar processing
- [Backtest Flow](#backtest-flow) — Synchronous replay engine
- [Research Mode Flow](#research-flow) — Feature engineering & model artifacts
- [Health Check Flow](#healthcheck) — Broker connectivity verification

---

## Paper Trading Flow

**Entry Point**: `main.py::cmd_paper()`

```
Start
  ↓
[cmd_paper] ---- config validation ──→ [Config] ← settings.py
  ↓
broker_init ──→ [IBKRBroker/AlpacaBroker] ← .env credentials
  ↓
[MarketDataFeed.stream()] ──→ yfinance | Polygon WebSocket
  ↓
AsyncIO Event Loop
  ├─ on_bar() ← called per bar (1-min or user interval)
  │  ├─ bar ← {symbol, timestamp, OHLCV, from_provider}
  │  │
  │  ├─ check_bar() ←─ [DataQualityGuard] ← kill_switch.db
  │  │  └─ Blocks if stale, corrupted, or kill_switch active
  │  │
  │  ├─ generate_signal(symbol) ←─ [Strategy] ← registered_strategies
  │  │  ├─ MA Crossover | RSI Momentum | Bollinger Bands | MACD
  │  │  ├─ DataFrame lookup via [HistoricalData]
  │  │  └─ Returns Signal{symbol, side, strength, metadata}
  │  │
  │  ├─ approve_signal(signal) ←─ [RiskManager]
  │  │  ├─ VaR gate ← portfolio history
  │  │  ├─ PaperGuardrails ← config (max orders/day, cooldown, etc.)
  │  │  ├─ OrderLimits ← per-strategy caps
  │  │  └─ Returns Order | None
  │  │
  │  ├─ submit_order(order) ←─ [IBKRBroker/AlpacaBroker]
  │  │  ├─ broker_operation() + retry logic (3x exponential backoff)
  │  │  └─ Logs to [AuditLogger] (audit events table)
  │  │
  │  ├─ fill_monitor() ← poll for fills every 5s
  │  │  ├─ on_fill() ← broker callback
  │  │  ├─ broker_reconciliation()
  │  │  └─ Portfolio.update_position()
  │  │
  │  └─ snapshot_portfolio() ← every N bars
  │     └─ FX conversion ← fx_snapshot (GBX.L or USD)
  │
  ├─ on_stream_heartbeat() ← every 30s
  │  └─ keep-alive signal, broker health check
  │
  └─ on_stream_error(error) ← exception handler
     ├─ Reconnect with backoff
     └─ Alert via logger
     
  [Session ends at 16:00 UTC or session_end_time config]
     ↓
  [Shutdown]
     ├─ Close broker connection
     ├─ Finalize audit log
     ├─ Export paper_session_summary.json
     └─ Rotate database (if rotate_db=True)
```

**Key Modules**:
- `main.py::cmd_paper()` — CLI entry, async loop orchestration
- `src/data/feeds.py::MarketDataFeed` — Bar emission (yfinance polling or WebSocket)
- `src/strategies/*.py::BaseStrategy` — Signal generation via technical indicators
- `src/risk/manager.py::RiskManager` — Multi-gate approval (VaR, guardrails, limits)
- `src/execution/broker.py::IBKRBroker/AlpacaBroker` — Order submission & fill monitoring
- `src/audit/logger.py::AuditLogger` — Immutable event log to `audit_events` table
- `src/portfolio/tracker.py::PortfolioTracker` — Position & P&L tracking

**Decision Points**:
1. **Data Quality Gate**: Kill-switch blocks if stale/corrupt data detected
2. **Signal Generation**: Returns `None` if insufficient bars (lookahead protection)
3. **VaR Gate**: Blocks if portfolio VAR exceeds limit
4. **Guardrail Checks**: Blocks if daily order limit or per-symbol cooldown exceeded
5. **Order Submission**: Retries 3x with exponential backoff; logs all failures

---

## Backtest Flow

**Entry Point**: `main.py::cmd_backtest()` / `backtest/engine.py::BacktestEngine.run()`

```
Start
  ↓
[cmd_backtest] ← config: symbols, dates, strategy, initial_cash
  ↓
[BacktestEngine.run()]
  ├─ Load historical bars ← [HistoricalDataFeed] (yfinance/Polygon)
  ├─ Sort chronologically (prevent lookahead bias)
  │
  ├─ for each bar (in order, oldest to newest):
  │  │
  │  ├─ Bar replay ← {symbol, ts, OHLCV}
  │  │
  │  ├─ on_bar() ← same logic as paper trading
  │  │  ├─ generate_signal() | approve_signal() | submit_order()
  │  │  └─ (but returns early if insufficient bars)
  │  │
  │  ├─ [PaperBroker.submit_order()] ← deterministic fills
  │  │  ├─ Fill price = close price (no slippage default)
  │  │  ├─ Fill time = bar timestamp
  │  │  └─ (modeled slippage optional via config)
  │  │
  │  ├─ Portfolio.update_fill()
  │  │
  │  └─ Record metrics for this bar
  │
  ├─ Aggregate results:
  │  ├─ Total return, Sharpe ratio, max drawdown
  │  ├─ Trade count, win rate, profit factor
  │  └─ Per-symbol P&L breakdown
  │
  └─ Export report
     ├─ JSON summary
     ├─ Trade ledger CSV
     └─ Charts (optional,Plotly/Matplotlib)
```

**Key Modules**:
- `backtest/engine.py::BacktestEngine` — Bar replay, zero-lookahead
- `src/execution/broker.py::PaperBroker` — Deterministic fills (backtest-only)
- `src/data/feeds.py::HistoricalDataFeed` — Fetch historical OHLCV
- `src/portfolio/tracker.py::PortfolioTracker` — Same as paper, but no real execution

**Decision Points**:
1. **Chronological Order**: Bars must be sorted oldest→newest to prevent lookahead
2. **Min Bars Required**: Strategy skips signal if `len(df) < min_bars_required()`
3. **Slippage Model**: Optional spread/commission applied per fill

---

## Research Flow

**Entry Point**: `main.py::research_train_xgboost()` / `research/experiments/xgboost_pipeline.py`

```
Start
  ↓
[research_train_xgboost] ← config JSON (model type, symbols, date range)
  ↓
[XGBoostPipeline.run()]
  ├─ Load historical bars
  │  ├─ [HistoricalDataFeed] (yfinance or Polygon)
  │  └─ Store in [MarketDataStore] (SQLite cache + Parquet)
  │
  ├─ Feature engineering
  │  ├─ [compute_features()] ← technical indicators
  │  │  ├─ MA, RSI, Bollinger Bands, MACD, ATR, ADX
  │  │  └─ Output: feature_matrix (N_bars × N_features)
  │  │
  │  └─ Label generation
  │     ├─ [compute_labels()] ← forward returns
  │     │  ├─ Binary:   return > 0% → 1, else 0
  │     │  └─ Ternary:  -1% < return ≤ 0% → 0, etc.
  │     └─ Output: label_vector (N_bars,)
  │
  ├─ Data splits
  │  ├─ [WalkForwardSplits] or [TimeSeriesSplit]
  │  ├─ Train set (2024-01-01 to 2024-08-31)
  │  ├─ Validation set (2024-09-01 to 2024-11-30)
  │  └─ Test set (2024-12-01 to 2024-12-31)
  │
  ├─ Model training
  │  ├─ [XGBoostModel] (or LSTMModel, RandomForestModel)
  │  ├─ Hyperparameter tuning (Optuna or grid search)
  │  ├─ Cross-validation (k-fold or walk-forward)
  │  └─ Save trained model to artifacts/
  │
  ├─ Evaluation
  │  ├─ Compute R2, Sharpe, max_dd, etc. on test set
  │  ├─ Feature importance ranking
  │  └─ Generate training_report.json
  │
  ├─ Promotion gate (R2 research gate)
  │  ├─ Check: R2 ≥ 0.15 on test set?
  │  ├─ If yes → `promotion_check.json {status: "pass"}`
  │  └─ If no → `promotion_check.json {status: "fail", reason: "R2 too low"}`
  │
  └─ Register candidate
     ├─ [research_register_candidate()]
     ├─ Store: model_id, artifact paths, metrics
     └─ New entry in trading.db (strategies table)
```

**Key Modules**:
- `research/experiments/xgboost_pipeline.py::XGBoostPipeline` — Orchestrator
- `research/data/features.py::compute_features()` — Indicator calculation
- `research/data/labels.py::compute_labels()` — Forward return labeling
- `research/data/splits.py::WalkForwardSplits` — Temporal splits
- `research/models/xgboost_model.py::XGBoostModel` — Training & prediction
- `src/promotions/checklist.py::promotion_gate()` — R2/Sharpe thresholds

---

## Health Check Flow

**Entry Point**: `main.py::cmd_uk_health_check()` / `uk_health_check.sh`

```
Start
  ↓
[cmd_uk_health_check] ← --profile uk_paper --strict-health
  ↓
Verify broker connectivity
  ├─ [IBKRBroker.connect()] ← TWS/Gateway alive?
  ├─ Ping account (DU...) ← paper vs live mode
  ├─ Check all farms online
  └─ Log status per farm (HKFE, IDEAL, etc.)
  
Verify data feeds
  ├─ [MarketDataFeed] ← yfinance working?
  ├─ Sample AAPL fetch ← recent close price
  ├─ Check timestamp freshness
  └─ Measure latency
  
Verify database state
  ├─ [trading_paper.db] ← accessible?
  ├─ Check schema (tables exist)
  ├─ Verify audit_events perms (write test)
  └─ Rotation point check (ready for archive?)
  
Verify credentials
  ├─ .env file loaded
  ├─ POLYGON_API_KEY present
  ├─ IB account info valid
  └─ Broker endpoint reachability
  
Exit codes:
  ├─ 0 ← all checks passed
  ├─ 1 ← ≥1 check failed (--strict-health enforces)
  └─ Detailed log to console + health_check_report.json
```

**Key Modules**:
- `main.py::cmd_uk_health_check()` — CLI entry
- `src/execution/broker.py::IBKRBroker.health_check()` — Broker checks
- `src/data/feeds.py::MarketDataFeed.health_check()` — Data feed checks
- `src/audit/logger.py::verify_audit_log()` — Database checks

---

## Class Hierarchy Quick Reference

```
BaseStrategy (src/strategies/base.py)
├─ MAStrategy (ma_crossover.py)
├─ RSIMomentumStrategy (rsi_momentum.py)
├─ BollingerBandsStrategy (bollinger_bands.py)
└─ MACDCrossoverStrategy (macd_crossover.py)

BrokerBase (src/execution/broker.py)
├─ PaperBroker (backtest/paper mode)
├─ IBKRBroker (production paper + live)
└─ AlpacaBroker (alternative paper)

RiskManager (src/risk/manager.py)
├─ VaR gate
├─ PaperGuardrails
├─ OrderLimits
└─ DataQualityGuard

PortfolioTracker (src/portfolio/tracker.py)
├─ Position tracking
├─ P&L calculation
└─ FX conversion
```

---

## Async Event Handling (Paper Mode Detail)

```
AsyncIO EventLoop (src/trading/loop.py or cmd_paper)
│
├─ Stream consumer ← bar events (1 per minute or configured interval)
│  └─ on_bar(symbol, bar) ← queued and processed sequentially
│
├─ Fill monitor ← polls every 5s for fills (async task)
│  └─ on_fill(order_id, filled_qty, fill_price) ← broker callback
│
├─ Heartbeat ← every 30s (keep-alive)
│  └─ broker.ping() | data_feed.ping()
│
├─ Error handler ← exceptions in any task
│  └─ on_stream_error(error) ← log + reconnect attempt
│
└─ Session timeout ← timer checks 16:00 UTC
   └─ Graceful shutdown, close connections
```

---

## Execution Sequence Diagram (Paper Mode, Single Bar)

```
Time    Actor           Action                            Notes
────────────────────────────────────────────────────────────────────
  T     MarketDataFeed  Emit bar ─────────────────────┐
         (yfinance)      {symbol: "AAPL",             │ 1-min aggregation
                          ts: 2026-02-24 08:34:00,     │ from market feed
                          close: 185.32, ...}          │
                                                        ├─→ on_bar()
  T+1   DataQuality     check_bar() ─────────────────┐
                        Kill-switch? Stale data?      │
                        ✓ PASS or ✗ BLOCK             │
                                                        ├─→ Strategy
  T+2   Strategy        generate_signal() ───────────┐
  (Async) (MAStrategy)   Min bars? MA40 crossover?    │
                        ✓ Signal | None               │
                                                        ├─→ RiskManager
  T+3   RiskManager     approve_signal() ───────────┐
                        ├─ VaR gate: OK?              │
                        ├─ Daily limit OK?            │
                        ├─ Symbol cooldown OK?        │
                        └─ Return Order | None        │
                                                        ├─→ Broker
  T+4   IBKRBroker      submit_order() ────────────┐
                        Retry logic (3x):            │
                        ├─ Attempt 1: timeout        │
                        ├─ Retry after 1s: success   │
                        └─ Return order_id = 12345   │
                                                        ├─→ AuditLog
  T+5   AuditLogger      Log "ORDER_SUBMITTED" ────┐
                        {ts, order_id, symbol, ...}  │
                                                        │
  T+5-10 (async task)  Fill monitor polls           ├─ (poll every 5s)
                                                        │
  T+10  Broker          on_fill() callback ────────┐
                        {order_id: 12345,            │
                         filled_qty: 100,            │
                         fill_price: 185.25}         │
                                                        ├─→ Portfolio
  T+11  Portfolio       update_position() ────────┐
                        Calc realized P&L,          │
                        Update cash balance         │
                                                        ├─→ AuditLog
  T+12  AuditLogger      Log "ORDER_FILLED" ──────┐
                        {ts, order_id, fill_price}  │
                                                        │
  T+12+ (every N bars) snapshot_portfolio() ──────┐
                        FX conversion (GBX→USD)     │
                        Export to portfolio_snapshot │
                                                        │
────────────────────────────────────────────────────────────────────
Total wall clock: ~1 second (bar received to fill)
```

---

## Decision Tree (Per Bar)

```
Bar received from feed
│
├─ Is kill-switch active?
│  └─ YES → SKIP, log "KILL_SWITCH_TRIGGERED"
│  └─ NO  → continue
│
├─ Is data stale (> 1 hour old)?
│  └─ YES → BLOCK, log "STALE_DATA_GUARD" (unless enable_stale_check=False)
│  └─ NO  → continue
│
├─ Does strategy have min bars?
│  └─ NO  → SKIP, log "INSUFFICIENT_BARS"
│  └─ YES → continue
│
├─ Did strategy generate signal?
│  └─ NO  → SKIP, no signal this bar
│  └─ YES → continue
│
├─ Does signal pass VaR gate?
│  └─ NO  → BLOCK, log "VaR_EXCEEDED"
│  └─ YES → continue
│
├─ Is daily order limit reached?
│  └─ YES → BLOCK, log "DAILY_LIMIT_EXCEEDED"
│  └─ NO  → continue
│
├─ Is symbol in cooldown (after recent reject)?
│  └─ YES → BLOCK, log "SYMBOL_COOLDOWN_ACTIVE"
│  └─ NO  → continue
│
├─ Are we in session window (08:00-16:00 UTC)?
│  └─ NO  → BLOCK, log "SESSION_WINDOW_CLOSED"
│  └─ YES → continue
│
├─ Submit order ──→ [Broker]
│  ├─ Success   → Log "ORDER_SUBMITTED", wait for fill
│  └─ Failure   → Retry 3x, then log "ORDER_REJECTED"
│
└─ Monitor fill (async)
   ├─ Filled    → Log "ORDER_FILLED", update portfolio
   ├─ Partial   → Log "ORDER_PARTIALLY_FILLED"
   └─ Rejected  → Log "ORDER_REJECTED", increment reject counter
```

---

## How to Use This Document

1. **For onboarding**: Start with the mode-specific flow (Paper / Backtest / Research)
2. **For debugging**: Jump to the decision tree or execution sequence diagram
3. **For design review**: Check class hierarchy and module dependencies
4. **For tracing a specific issue**: Use the decision tree to identify where it's blocked

---

**Related Documents**:
- [.python-style-guide.md](.python-style-guide.md) — Code standards
- [CLAUDE.md](CLAUDE.md) — Architecture overview + session context
- [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) — Development tasks
- [main.py](main.py) — Entry point & CLI commands

