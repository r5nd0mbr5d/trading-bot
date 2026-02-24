# Trading Bot — Comprehensive Project Roadmap

Enterprise-grade algorithmic trading platform for US equities. Built on three core pillars with systematic phases.

---

## 📋 Navigation Note

**For current weekly tasks, outstanding prompts, and implementation status, see:** [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)

This roadmap serves as a **reference architecture** and long-term strategic guide. The backlog tracks **active work** with deadlines, blockers, and success criteria.

---

## Executive Summary

| Pillar | Status | Priority | Timeline |
|--------|--------|----------|----------|
| **1. Data Collection & Analysis** | 10% | TIER 1 (foundation) | Weeks 1-2 |
| **2. Strategy Development** | 35% (4 strategies done) | TIER 1-2 | Weeks 2-6 |
| **3. Real-Time Trading & Learning** | 20% (paper trading setup) | TIER 2-3 | Weeks 6+ |

**Current completion:** ~22% of Tier 1 (foundation layer) ✓ → 78% remaining

---

## PILLAR 1: Historical Data Collection & Analysis (10% → 100%)

### Phase 1.1: Data Pipeline (Weeks 1-2)

**Goal:** Ingest and normalize historical OHLCV data, validate quality.

**Files to create/modify:**
- `src/data/providers/base.py` — abstract provider interface
- `src/data/providers/yfinance_adapter.py` — current implementation
- `src/data/providers/polygon_adapter.py` (optional) — high-quality provider
- `src/data/store.py` — SQLite schema & persistence layer
- `src/data/ingestion.py` — backfill + incremental updates
- `config/settings.py` (add) — `PolygonConfig`, `DataStorageConfig`

**Tasks:**
- [ ] Define provider interface (fetch, normalize, validate)
- [ ] Implement Polygon.io adapter (requires API key in .env)
- [ ] Create SQLite schema: `instruments`, `bars`, `trades`, `corporate_actions`
- [ ] Implement backfill job (download 5+ years of data)
- [ ] Add data validation: OHLC ordering, volume checks, gap detection
- [ ] Resume interrupted downloads (track checkpoints)

**Success criteria:**
- Download 5y AAPL/MSFT/GOOGL data in <60s
- Store ~1250 bars/symbol (260 trading days × 5y)
- Validate: 0 gaps, all L ≤ C ≤ H, volume > 0

**Backtest impact:** +0 (foundation only)

---

### Phase 1.2: Exploratory Analysis (Weeks 2-3)

**Goal:** Understand data characteristics, identify trading regimes, anomalies.

**File to create:**
- `notebooks/01_data_exploration.ipynb` — statistical profiling
- `src/analysis/profiler.py` — automated profiling utilities

**Tasks:**
- [ ] Load 5y of AAPL, MSFT, GOOGL, AMZN, TSLA from SQLite
- [ ] Summary statistics: returns (daily/monthly/annual), volatility
- [ ] Correlation matrix: intra-symbol correlations, cross-symbol
- [ ] Trend analysis: rolling 20/50/200-day SMA slopes
- [ ] Seasonality: January effect, day-of-week bias
- [ ] Volatility clustering: GARCH-style analysis
- [ ] Regime detection: Hidden Markov Model (bull/bear/sideways)
- [ ] Anomalies: Gap identification, volume spikes, price outliers

**Success criteria:**
- Identify 3+ trading regimes with distinct characteristics
- Detect seasonality (e.g., Q1 vs Q4 volatility differences)
- Find correlation with macro factors (optional: VIX, market breadth)

**Backtest impact:** +0 (research only)

---

### Phase 1.3: Data Quality & Monitoring (Week 3)

**Goal:** Ensure data integrity at ingestion and runtime.

**Files to create/modify:**
- `src/data/validator.py` — integrity checks, automated alerts
- `src/monitoring/health_check.py` — periodic data quality scans

**Tasks:**
- [ ] Implement OHLC ordering check
- [ ] Volume sanity checks (0 < volume < reasonable_max)
- [ ] Staleness detection (no data for > N hours)
- [ ] Gap detection (missing trading days)
- [ ] Automated Slack/email alerts on failures
- [ ] Daily data quality report (fetch failures, validation issues)

**Success criteria:**
- All backtests start with validated data
- Paper trading halts on data quality failures
- Daily monitoring report sent every morning

**Backtest impact:** -0% (if validation passes)

---

**PILLAR 1 DELIVERABLE:**
- ✓ Historical data in SQLite, normalized + validated
- ✓ 5+ years of clean OHLCV data
- ✓ Analysis notebook showing regime/seasonality insights
- ✓ Ready for strategy research

---

## PILLAR 2: Strategy Development & Evaluation (35% → 100%)

### Phase 2.1: Core Technical Indicators (Weeks 1-4)

**Currently implemented:** MA, RSI, MACD, Bollinger Bands
**To implement in priority order:**

#### Priority A: Volatility & Stops (Week 1)
- [x] **ATR (Average True Range)** — `src/indicators/atr.py`
  - Replace 5% fixed stop with ATR-based (2× ATR)
  - Modify `src/risk/manager.py` to use ATR
  - Test: ATR value matches TA-Lib
  
- [ ] **ADX (Average Directional Index)** — `src/indicators/adx.py`
  - Trend strength filter: only trade if ADX > 25
  - Create strategy `src/strategies/adx_filter.py` (enhance existing with ADX)
  - Test: ADX < 25 in sideways markets, > 25 in trends

#### Priority B: Volume & Flow (Week 2)
- [ ] **OBV (On-Balance Volume)** — `src/indicators/obv.py`
  - Accumulation/distribution signal
  - Create `src/strategies/obv_crossover.py`
  - Test: OBV trend matches price trend

- [ ] **VWAP (Volume-Weighted Average Price)** — `src/indicators/vwap.py`
  - Mean reversion target
  - Modify Bollinger Bands to support VWAP as alternative
  - Test: VWAP within typical Bollinger Band-like range

#### Priority C: Advanced (Weeks 3-4)
- [ ] **Stochastic Oscillator** — `src/indicators/stochastic.py`
  - %K and %D lines
  - Overbought/oversold detection
  
- [ ] **Keltner Channels** — `src/indicators/keltner.py`
  - ATR-based volatility bands
  - Alternative to Bollinger Bands (compare performance)

- [ ] **CCI (Commodity Channel Index)** — `src/indicators/cci.py`
  - Cyclical tops/bottoms identification

**Tasks for each indicator:**
1. Implement core calculation
2. Write unit tests (verify against known values)
3. Create simple strategy using indicator
4. Add to test suite
5. Backtest on 2022-2024 data
6. Document assumptions & limitations

**Success criteria:**
- All indicators pass unit tests
- At least 5 new indicators implemented
- Backtest Sharpe improves or stays flat (not degraded)

**Backtest impact:** +5-15% Sharpe (with proper filtering)

---

### Phase 2.2: Strategy Registry & Versioning (Week 2)

**Goal:** Track strategy versions, parameters, performance, approval status.

**File to create/modify:**
- `src/strategies/registry.py` (enhance existing)
- `src/strategies/strategy_metadata.py` — versioning + metadata

**Tasks:**
- [ ] Extend registry: `strategy_id`, `version`, `status` (experimental/approved_paper/approved_live)
- [ ] Store backtest metrics in registry: Sharpe, DD, win_rate
- [ ] Approval workflow (user confirms before moving to paper)
- [ ] Load strategy with specific version by ID
- [ ] Archive old strategy versions

**Success criteria:**
- Can load any strategy at any version
- Approval status gates paper/live trading
- 10/10 strategies tracked in registry

**Backtest impact:** +0 (infrastructure)

---

### Phase 2.3: New Rule-Based Strategies (Weeks 3-5)

Build 5+ new strategies to improve diversification and risk-adjusted returns.

**Strategies to implement:**

1. **Mean Reversion Ensemble** `src/strategies/mean_reversion_ensemble.py`
   - Combines: Bollinger Bands + RSI oversold + volume confirmation
   - Entry: BB lower band + RSI < 30 + volume > 50-day avg
   - Exit: price > BB middle + RSI > 50
   - Expected: Higher win rate, lower DD

2. **Trend + ADX Filter** `src/strategies/trend_with_filter.py`
   - Base: MA crossover
   - Filter: Only trade if ADX > 25 (strong trend)
   - Entry: Golden cross + ADX > 25
   - Exit: Death cross OR ADX falls below 20
   - Expected: Better risk-adjusted returns, fewer false signals

3. **Volatility Breakout** `src/strategies/volatility_breakout.py`
   - Entry: Close > (20-day high - 2×ATR) OR Close < (20-day low + 2×ATR)
   - Exit: Reverse ATR breakout OR 5% profit target
   - Expected: Capture volatile move starts

4. **Pairs Trading** `src/strategies/pairs_trading.py`
   - Correlated pairs (AAPL/MSFT) mean revert to historical spread
   - Entry: Spread > 2σ away from mean
   - Exit: Spread reverts to mean
   - Expected: Market-neutral, low beta

5. **Sector Rotation** `src/strategies/sector_rotation.py`
   - Buy strongest sector (by momentum)
   - Buy strongest symbol within sector
   - Exit: Sector underperforms
   - Expected: Defensive in downturns

**Tasks per strategy:**
1. Implement logic
2. Add to registry
3. Backtest: show Sharpe, DD, win_rate on 2022-2024
4. Compare vs benchmark (SPY)
5. Document assumptions & limitations
6. Add to test suite

**Success criteria:**
- 5 new strategies, all passing tests
- At least one with Sharpe > 2.0
- Ensemble diversification confirmed (correlation < 0.5)

**Backtest impact:** +10-30% (diversification + regime-specific strategies)

---

### Phase 2.4: Backtesting Infrastructure Enhancements (Weeks 4-5)

**Goal:** Improve backtesting realism and detect overfitting.

**Files to create/modify:**
- `backtest/walk_forward.py` (new) — rolling optimization
- `backtest/monte_carlo.py` (new) — stochastic resampling
- `backtest/metrics.py` (enhance) — add more statistics
- `backtest/report.py` (enhance) — prettier reporting

**Tasks:**
- [ ] **Walk-forward optimization:**
  - 6-month train window → 1-month test window → slide forward 1 month
  - Detect parameter overfitting (train Sharpe >> test Sharpe)
  - Optimize on train set, report on test set
  
- [ ] **Monte Carlo resampling:**
  - Shuffle trade order to test luck vs skill
  - Generate 100 randomized backtest results
  - Check if original backtest in top 10% (lucky, not skill)

- [ ] **Enhanced metrics:**
  - Profit factor (gross profit / gross loss)
  - Kelly criterion optimal f
  - Win rate, average winner/loser
  - Consecutive wins/losses streaks

- [ ] **Prettier reporting:**
  - Equity curve plot (matplotlib)
  - Drawdown chart
  - Parameter sensitivity heatmap
  - Trade list with entry/exit rationale

**Success criteria:**
- Walk-forward shows 80%+ of original Sharpe
- Monte Carlo: original in top 25% (not luck)
- Report is PDF-exportable with charts

**Backtest impact:** ±0 (validation, may reduce reported results if overfitted)

---

### Phase 2.5: Machine Learning Signals (Weeks 5-8, TIER 3)

**Goal:** Integrate neural networks for price prediction & direction classification.

**Files to create:**
- `src/ml/features.py` — feature engineering (indicators → normalized inputs)
- `src/ml/data_splitter.py` — time-aware train/val/test splits
- `src/ml/models/lstm.py` — LSTM for multi-step ahead forecasting
- `src/ml/models/xgboost_classifier.py` — binary direction classification
- `src/ml/experiment_tracker.py` — log all NN training runs
- `src/strategies/neural_net_strategy.py` — wrapper to run trained models
- `notebooks/02_ml_model_development.ipynb` — research notebook

**Requirements:**
- Feature engineering: normalize indicators, create lookback windows
- No lookahead bias: features at t must not see future data
- Time-aware splits: train: 2019-2021, val: 2022, test: 2023, live: 2024+
- Serialize model + metadata (date trained, hyperparams, performance)

**Phase 2.5.1: Feature Engineering**
- [ ] Implement feature engineer with configurable indicators
- [ ] Normalization: StandardScaler on rolling windows
- [ ] Create 10-bar + 20-bar lookback windows
- [ ] No lookahead: features at 'now' are lagged by min_bars

**Phase 2.5.2: LSTM Model**
- [ ] PyTorch LSTM for 5-day ahead price prediction
- [ ] Train on 5y data, validate on 1y, test on 6mo
- [ ] Loss: MSE on normalized returns
- [ ] Generate signals: if predicted_return > 0 → LONG, else CLOSE

**Phase 2.5.3: XGBoost Classifier**
- [ ] Binary classifier: direction up/down (close[t+1] vs close[t])
- [ ] Train on 5y, validate on 1y, test on 6mo
- [ ] Feature importance analysis
- [ ] Generate signals based on predicted probability

**Phase 2.5.4: Integration**
- [ ] Wrap trained models as Strategy subclasses
- [ ] Version model artifacts in `models/checkpoints/`
- [ ] Load model + metadata on strategy init
- [ ] Backtest NN strategies end-to-end

**Success criteria:**
- LSTM Sharpe > 1.5 on test set (2023 data)
- XGBoost accuracy > 55% (direction prediction)
- No lookahead bias in features (validated)
- Model version control + reproducibility

**Backtest impact:** +20-50% Sharpe (if models are skilled)

---

**PILLAR 2 DELIVERABLE:**
- ✓ 10+ rule-based + ML strategies, all backtested & versioned
- ✓ All tests passing (100+ test cases)
- ✓ Walk-forward validation confirms no overfitting
- ✓ Ready for paper trading

---

## PILLAR 3: Real-Time Trading & Learning (20% → 100%)

### Phase 3.1: Live Paper Trading Infrastructure (Weeks 3-4)

**Goal:** Run continuous paper trading bot 24/5 with audit trail.

**Files to create/modify:**
- `src/trading/paper_trader.py` (new) — daemon bot
- `src/trading/audit_log.py` (new) — immutable logging
- `src/trading/event_loop.py` (new) — main trading loop

**Tasks:**
- [ ] **Daemon bot:**
  - Load strategy from registry (by ID + version)
  - Connect to real-time market data feed
  - Generate signals on each new bar
  - Submit orders via Alpaca paper trading
  - Log all events
  - Graceful shutdown + restart capability

- [ ] **Audit trail:**
  - Immutable log: signal → order → fill with timestamps
  - Strategy ID + version for traceability
  - All trades persisted to SQLite
  - Replay capability for post-mortem analysis

- [ ] **Health checks:**
  - Heartbeat: confirms bot is running
  - Data feed health: detect stale/gap data
  - Alpaca connectivity: test auth, test order submission
  - P&L health: alert if daily loss > threshold

**Success criteria:**
- Bot runs 24/5 without manual intervention
- 100% audit trail (no trades missed)
- Graceful recovery from Alpaca outages

**Backtest impact:** +0 (operational)

---

### Phase 3.2: Risk Management Enhancements (Week 4)

**Goal:** Enterprise-grade risk controls beyond position sizing.

**Files to create/modify:**
- `src/risk/position_sizing.py` (enhance) — Kelly criterion, fixed fractional
- `src/risk/correlation_limiter.py` (new) — sector/correlation limits
- `src/risk/var.py` (new) — Value at Risk calculations
- `src/risk/circuit_breaker.py` (enhance) — daily loss halts
- `config/settings.py` (add) — risk parameters

**Tasks:**
- [ ] **Position sizing refinement:**
  - Kelly criterion: f* = edge / odds (risky, use f*/4 or f*/2)
  - Fixed fractional: 2% risk per trade
  - Compare methods, document assumptions

- [ ] **Correlation limits:**
  - Don't hold >30% of portfolio in correlated pairs (ρ > 0.7)
  - Sector exposure limits: max 20% in any one sector
  - Dynamically rebalance if exceeded

- [ ] **VaR calculations:**
  - Historical VaR (95%): worst 5% of daily P&L
  - Parametric VaR: assume normal distribution
  - Report daily: "95% chance of losing < $X tomorrow"

- [ ] **Circuit breaker enhancements:**
  - Current: halt at 20% portfolio drawdown
  - Add: halt at 5% daily loss (during market hours)
  - Add: halt if data feed down for > 5 mins

**Success criteria:**
- Position sizing aligns with risk budget
- Correlation violations < 2% of trades
- Circuit breaker prevents catastrophic losses

**Backtest impact:** -5% to -10% return (but -50% DD reduction)

---

### Phase 3.3: Performance Analysis & Reporting (Weeks 4-5)

**Goal:** Monitor live trading performance, compare vs backtest, catch issues early.

**Files to create/modify:**
- `src/analysis/live_backtest_comparison.py` (new) — live vs backtest reconciliation
- `src/reporting/daily_report.py` (new) — daily P&L email
- `src/reporting/dashboard.py` (new, optional) — real-time web dashboard

**Tasks:**
- [ ] **Live vs backtest comparison:**
  - Capture: actual slippage, commissions, fills
  - Compare vs backtest assumptions
  - Flag if actual Sharpe << backtest Sharpe (overfitting sign)
  - Diagnose: slippage? execution timing? regime change?

- [ ] **Daily report generation:**
  - Email every 4pm: day's P&L, Sharpe YTD, max DD
  - Trade log for the day
  - Alert if unusual activity (no trades, too many trades)
  - Sentiment: bullish/bearish regime

- [ ] **Web dashboard (optional):**
  - Current positions, cash, portfolio value
  - Equity curve chart (year to date)
  - Trade log with entry/exit prices
  - Real-time P&L

**Success criteria:**
- Daily reports sent at consistent time
- Users can diagnose performance issues easily
- Live vs backtest discrepancies identified within 1 day

**Backtest impact:** +0 (monitoring)

---

### Phase 3.4: Automated Learning Loop (Weeks 6-8, TIER 3)

**Goal:** Retrain models on fresh data, adapt strategies to market regime changes.

**Files to create:**
- `src/ml/retraining_scheduler.py` (new) — weekly/monthly retraining
- `src/analysis/regime_detector.py` (new) — detect market regime changes
- `src/strategies/adaptive_params.py` (new) — dynamic parameter adjustment

**Tasks:**
- [ ] **Retraining trigger:**
  - Weekly: retrain LSTM/XGBoost on last 2y data (leaving 3mo for validation)
  - Only deploy if validation Sharpe >= last 2 weeks live Sharpe
  - Keep old model for rollback

- [ ] **Regime detection:**
  - HMM or clustering: identify bull/bear/sideways regimes
  - Trigger strategy parameter changes: e.g., increase ADX threshold in choppy regime
  - Alert users to regime shifts

- [ ] **Parameter adaptation:**
  - Adjust BB period based on volatility
  - Adjust RSI levels based on market condition
  - Document changes in audit trail

**Success criteria:**
- Models retrained weekly without manual intervention
- Regime changes detected within 1 trading day
- Live Sharpe stays within 10% of validation Sharpe

**Backtest impact:** +10-20% (regime adaptation)

---

**PILLAR 3 DELIVERABLE:**
- ✓ 24/5 paper trading bot running continuously
- ✓ Full audit trail (all trades logged)
- ✓ Risk controls preventing catastrophic losses
- ✓ Daily reporting + performance diagnostics
- ✓ Weekly model retraining + regime adaptation
- ✓ Ready for production (with PROD approval workflow)

---

## Testing & Documentation Requirements

### Testing Pyramid

```
Level 3: Integration Tests (50)
  └─ Backtest end-to-end with strategies
  └─ Paper trading with mocked Alpaca
  └─ Risk manager approves/rejects signals

Level 2: Unit Tests (300+, existing 17)
  └─ Indicators compute correctly
  └─ Strategies generate signals properly
  └─ Risk calculations are accurate
  └─ Data validation works

Level 1: Scenario Tests (20+)
  └─ Data gap handling
  └─ Order rejection fallback
  └─ Circuit breaker triggers
  └─ Alpaca outage recovery
```

**Target:** 85%+ code coverage, 0 failing tests before deployment

### Documentation Requirements

**Per Strategy File:**
- Trading logic (entry/exit rules in plain English)
- Historical backtest results (Sharpe, DD, win rate on 3+ periods)
- Known limitations (regime-specific? correlation assumptions?)
- Research references (papers, blog posts, books)

**Architecture Documentation:**
- System design diagram (Pillar 1/2/3 components + data flow)
- Database schema (tables, relationships, indexes)
- Order lifecycle state machine
- Risk control flowchart

**Deployment Documentation:**
- Config file guide (all knobs explained + safe ranges)
- Secrets management (API keys, environment variables)
- Monitoring checklist (what to watch in production)
- Runbooks (common issues + fixes)

---

## Deployment Checklist (Before Going Live)

### Data Quality
- [ ] Automated validation on all ingested data
- [ ] Alerting on data gaps, stale feeds, provider outages
- [ ] Daily data quality report

### Risk Controls
- [ ] VaR, CVaR, correlation limits implemented
- [ ] Daily loss circuit breaker active
- [ ] Position correlation checks on every order
- [ ] Sector exposure limits enforced

### Audit Trail
- [ ] Immutable trade log (database + file)
- [ ] Strategy version tracked per trade
- [ ] All signal/order/fill timestamps recorded
- [ ] Replay capability for post-mortem analysis

### Backtesting Validation
- [ ] Walk-forward optimization (train vs test Sharpe ratio)
- [ ] Out-of-sample tests (hold-out 6mo)
- [ ] Monte Carlo resampling (luck vs skill)
- [ ] Parameter sensitivity analysis (when do strategies break?)

### Documentation
- [ ] All strategies documented (logic, parameters, backtests)
- [ ] Architecture diagrams (system design)
- [ ] Database schema (time-series optimized)
- [ ] Runbooks for common issues

### Testing
- [ ] Unit tests: 85%+ code coverage
- [ ] Integration tests: end-to-end workflows
- [ ] Scenario tests: outages, data gaps, edge cases
- [ ] Performance tests: backtest < 5s, order < 1s, alert < 10s

### Monitoring
- [ ] Real-time P&L dashboards
- [ ] Automated alerts (large losses, execution errors, data gaps)
- [ ] Live vs backtest comparison (daily)
- [ ] Health checks (data feed, Alpaca connectivity, bot heartbeat)

### Performance SLAs
- [ ] Backtest run: < 5 seconds for 5y data
- [ ] Order fill: < 1 second (Alpaca response)
- [ ] Alert generation: < 10 seconds on failure
- [ ] Model retraining: < 30 minutes (weekly)

---

## Timeline Summary

| Phase | Timeline | Pillar | Priority | Status |
|-------|----------|--------|----------|--------|
| **Data pipelines** | Weeks 1-3 | 1 | Tier 1 | 🚧 Not started |
| **Indicators (ATR/ADX/VWAP)** | Weeks 1-4 | 2 | Tier 1 | ⚙️ Partial |
| **New strategies (5+)** | Weeks 3-5 | 2 | Tier 1-2 | 🚧 Not started |
| **Backtest enhancements** | Weeks 4-5 | 2 | Tier 1 | 🚧 Not started |
| **Paper trading infrastructure** | Weeks 3-4 | 3 | Tier 2 | ⚙️  Partial |
| **Risk management enhancements** | Week 4 | 3 | Tier 2 | ⚙️ Partial |
| **Performance reporting** | Weeks 4-5 | 3 | Tier 2 | 🚧 Not started |
| **ML pipelines & training** | Weeks 5-8 | 2 | Tier 3 | 🚧 Not started |
| **Automated retraining loop** | Weeks 6-8 | 3 | Tier 3 | 🚧 Not started |
| **Production deployment** | Week 8+ | All | Go/No-Go | 🚫 Blocked |

**Critical path:** Data pipelines → Indicator library → Strategy diversification → Backtesting validation → Paper trading → Production

---

## Decision Framework

### When to Deploy to Paper Trading
- [ ] 5+ strategies with Sharpe > 1.0 on 2y backtest
- [ ] Walk-forward validation confirms no overfitting (train Sharpe within 20% of test)
- [ ] All unit tests passing (100+ cases)
- [ ] Risk controls: position limits, dailyDrawdown halt, correlation checks active

### When to Deploy to Production
- [ ] 3+ months of paper trading, Sharpe >= 80% of backtest
- [ ] Live vs backtest reconciliation complete (slippage, commissions understood)
- [ ] Risk controls survived 2+ major market moves
- [ ] Approval from risk committee (self-approval initially, escalate if issues)
- [ ] Insurance/broker limits set
- [ ] 24/7 monitoring in place
- [ ] Rollback plan documented

### When to Halt Trading
- [ ] Daily loss > 5% of portfolio → auto-halt
- [ ] Data feed down for > 5 minutes → halt until restored
- [ ] Risk controls triggered (correlation, sector limits)
- [ ] Execution errors > 10% of orders → manual review required
- [ ] Circuit breaker: consecutive losing trades > 10 → manual review

---

## Quick Start (Next 30 days)

**Week 1:**
```bash
# Setup data pipeline
1. Create src/data/providers/ directory
2. Implement data store schema (SQLite)
3. Download 5y of AAPL/MSFT/GOOGL data
4. Validate data integrity (all OHLC tests pass)
```

**Week 2:**
```bash
# EDA & indicators
1. Run exploratory analysis notebook
2. Implement ATR indicator
3. Modify risk manager to use ATR for stops
4. Test on existing backtest (should improve risk-adjusted returns)
```

**Week 3:**
```bash
# New strategies
1. Add ADX indicator
2. Implement trend-filtered MA crossover (MA + ADX)
3. Backtest new strategy on 2022-2024
4. Compare Sharpe vs baseline strategies
```

**Week 4+:**
```bash
# Expansion
1. Add 3+ more indicators (VWAP, OBV, Stochastic)
2. Implement 3+ new strategies
3. Walk-forward optimization (detect overfitting)
4. Deploy strongest strategy to paper trading
```

---

## Resources

### Books
- "Advances in Financial Machine Learning" — Prado
- "Systematic Trading" — Carver
- "Algorithmic Trading" — Chan

### Papers
- "Trend Following with Managed Futures" — Seymour & Leuthold
- "A Regime-Switching Model for Earnability Forecasting" — Hamilton
- "Walk Forward Analysis" — Pardo

### Libraries
- `pandas-ta` — technical indicators
- `PyTorch` / `XGBoost` — ML models
- `backtrader` — alternative backtesting framework
- `MLflow` — experiment tracking

### Open Questions for Future Sessions

1. Should we implement slippage models (fixed bps vs impact model)?
2. How much historical data is enough? (5y vs 10y vs 20y)
3. Should strategies be market-neutral or directional?
4. What is acceptable maximum drawdown for production? (10%? 20%?)
5. Should we trade crypto in addition to equities?
6. How frequently should models be retrained? (weekly? monthly?)

