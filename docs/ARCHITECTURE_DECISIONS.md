# Architecture Decisions — AQ1–AQ9 Integrated Resolution

> **⚠️ SUPERSEDED — Read `PROJECT_DESIGN.md` §3 instead.**
>
> The nine decisions in this document (AQ1–AQ9) have been migrated to
> `PROJECT_DESIGN.md` as ADR-001 through ADR-009, with additional ADR-010 to ADR-012
> added since. `PROJECT_DESIGN.md` is now the single authoritative source for all
> architectural decision records (ADRs).
>
> This file is kept as a **detailed implementation rationale reference** — it contains
> comparative analysis tables and alternative considerations that are not duplicated in
> the LPDD. Consult it when you need the full context behind a decision, but treat
> `PROJECT_DESIGN.md §3` as the canonical record.
>
> **For new ADRs:** Add them to `PROJECT_DESIGN.md §3`, not here.

---

**Author:** Claude Opus (principal architect review) | **Date:** 2026-02-24
**Status:** SUPERSEDED BY `PROJECT_DESIGN.md §3` — kept as implementation detail reference
**Scope:** CO-5 resolution — one integrated pass covering all nine outstanding design questions

> **Context constraints**: This document operates under the project's hard invariants:
> 1. `RiskManager.approve_signal()` is the only path from Signal to Order
> 2. Backtests must preserve zero-lookahead semantics
> 3. Signal strength is always in [0, 1]
> 4. Runtime safety controls and auditability are first-class

---

## 1. Executive Decisions Table

| AQ | Question | Final Decision | Status |
|----|----------|---------------|--------|
| AQ1 | Time-series storage | **Hybrid: SQLite (operational) + Parquet (research OHLCV)** | ✅ Implemented |
| AQ2 | Event-driven vs vectorized backtesting | **Event-driven** with next-bar-open fills | ✅ Implemented |
| AQ3 | Strategy registry design | **Hybrid SQLite metadata + disk artifacts + SHA256** | ✅ Implemented |
| AQ4 | Provider stack | **yfinance primary → Polygon.io production → Alpha Vantage fallback** | ✅ Scaffold done; adapters pending |
| AQ5 | Streaming design | **Polling with exponential backoff and lifecycle audit events** | ✅ Implemented |
| AQ6 | Feature/label design | **Leakage-safe OHLCV features + H5 binary labels; spec in FEATURE_LABEL_SPEC.md** | ✅ Implemented |
| AQ7 | NN architecture baseline | **XGBoost first; LSTM scaffold available; no deep nets** | ✅ Spec done; implementation scaffolded |
| AQ8 | VaR/CVaR gate | **Historical simulation, 252-day rolling, integrated in RiskManager** | ✅ Implemented |
| AQ9 | Kill-switch design | **Persistent SQLite flag; survives restarts; asyncio-safe; operator-reset required** | ✅ Implemented |

### Detailed Rationale

#### AQ1 — Time-Series Storage

| Dimension | SQLite | Parquet (DuckDB-queryable) | TimescaleDB |
|-----------|--------|---------------------------|-------------|
| Operational metadata | ✅ Best (ACID, no server) | ❌ Not suitable | ⚠️ Overkill |
| Historical OHLCV for research | ❌ Poor (10M+ rows slow) | ✅ Best (columnar, fast analytics) | ✅ Good (requires server) |
| Deployment complexity | None | None (file-based) | High (PostgreSQL extension) |

**Decision**: SQLite for all operational data (audit_log, kill_switch, strategy registry, reconciliation, trade ledger). Parquet (`research/data/snapshots/`) for historical OHLCV used in offline research. No migration needed — this is the de facto state.

**Trade-off**: Production runtime OHLCV caching (live/paper session bar cache) remains in-memory. If bar history exceeds ~50k rows in memory, add a SQLite bar cache as a middle tier — not needed now.

**Risk level**: Low — already implemented. No new components required.

---

#### AQ2 — Event-Driven vs Vectorized Backtesting

**Decision**: Event-driven is the correct and only acceptable choice for this system.

**Why**: Vectorized backtesting processes all bars simultaneously and cannot maintain the same runtime invariants (per-bar signal evaluation, kill-switch checks, VaR gate, circuit breakers). Event-driven guarantees zero lookahead parity with the live paper runtime.

**Current implementation**: `backtest/engine.py` replays bars sequentially, buffers orders at bar[t] close, fills at bar[t+1] open — matching live paper broker behavior.

**Trade-off**: ~3–10× slower than vectorized for large backtests. Acceptable: a 3-year daily backtest on 15 symbols runs in < 5 seconds.

**Risk level**: Low — implemented and regression-tested.

---

#### AQ3 — Strategy Registry Design

**Decision**: Hybrid SQLite metadata + disk artifacts (`strategies/<name>/<version>/model.pt`) + SHA256 integrity verification.

**Current implementation**: `src/strategies/registry.py` with lifecycle states `experimental → approved_for_paper → approved_for_live`. Gate B promotion requires a promotion checklist JSON with `decision=READY`.

**Risk level**: Low — implemented and fully test-covered.

---

#### AQ4 — Provider Stack

**Decision**: Tiered provider stack with normalized adapter interface (`HistoricalDataProvider` protocol in `src/data/providers.py`).

| Tier | Provider | Use Case | Cost | Priority |
|------|---------|----------|------|----------|
| 1 | yfinance | Development, backtesting, paper research | Free | Current default |
| 2 | Polygon.io | Production historical + real-time snapshots | Paid (~$29/mo starter) | Next for UK equities |
| 3 | Alpha Vantage | Fallback for US equities | Free tier (5 req/min) | Fallback only |

**Implementation order**:
1. ~~yfinance adapter~~ (done — `YFinanceProvider`)
2. ~~Scaffold for unimplemented providers~~ (done — `NotImplementedProvider`)
3. **Next**: Polygon.io adapter with UK equity support (`.L` suffix support, LSE exchange routing)
4. Alpha Vantage adapter (US only, rate-limited)

**Provider selection logic** (runtime):

```python
# Pseudocode for future DataFeedFactory
def get_provider(config: DataConfig) -> HistoricalDataProvider:
    if config.provider == "polygon":
        return PolygonProvider(api_key=config.api_key)
    elif config.provider == "alpha_vantage":
        return AlphaVantageProvider(api_key=config.api_key)
    return YFinanceProvider()  # Default / no API key
```

**Trade-off**: yfinance is free but rate-limited and unofficial. Polygon.io requires a paid subscription but provides official, reliable UK equity data with LSE coverage.

**Risk level**: Medium — Polygon.io adapter is unimplemented. Until it exists, UK production data relies on yfinance (acceptable for paper trading, not for production).

---

#### AQ5 — Streaming Design Pattern

**Decision**: Polling-based streaming with exponential backoff, heartbeat lifecycle events, and audit trail. No WebSocket streaming in current scope.

**Current implementation** (`src/data/feeds.py`, `MarketDataFeed.stream()`):
- Poll interval configurable (default: 60 seconds for daily bars)
- Heartbeat events: `STREAM_HEARTBEAT` every successful cycle
- Error events: `STREAM_SYMBOL_ERROR` per failed symbol
- Backoff: exponential with jitter on consecutive failures
- Terminal: `STREAM_FAILURE_LIMIT_REACHED` triggers kill switch
- Recovery: `STREAM_RECOVERED` on successful reconnect

**WebSocket deferral rationale**: yfinance does not support WebSocket streaming. IBKR (ib_insync) provides event-loop callbacks that are already used. Adding a WebSocket layer would add complexity without improving reliability for daily-bar strategies.

**Future WebSocket path** (when needed):
- Implement `WebSocketProvider` conforming to same `HistoricalDataProvider` protocol
- Emit same lifecycle audit events (`STREAM_HEARTBEAT`, `STREAM_RECOVERED`, etc.)
- Keep the same heartbeat/backoff/kill-switch integration points

**Risk level**: Low for current polling design. Medium if WebSocket needed for intraday strategies (out of current scope).

---

#### AQ6 — Feature/Label Engineering

**Decision**: Leakage-safe OHLCV + volume + volatility + momentum features with H5 binary labels (5-day forward return directional classification).

**Full spec**: `research/specs/FEATURE_LABEL_SPEC.md`

**Current implementation**:
- `research/data/features.py` — deterministic feature computation, all UTC-aware
- `research/data/labels.py` — H5 binary labels, threshold from training fold only
- `research/data/splits.py` — expanding-window walk-forward split generation

**Key invariant**: No feature uses `shift(-k)`. All labels use strictly future bars. Validated by test assertions.

**Risk level**: Low — implemented and test-covered.

---

#### AQ7 — Neural Network Architecture Baseline

**Decision**: XGBoost is the primary and only initially required model. LSTM is an optional future extension, scaffolded but not yet required.

**Model ordering rationale**:

| Criterion | XGBoost | LSTM | MLP | CNN |
|-----------|---------|------|-----|-----|
| Tabular data (OHLCV features) | ✅ Best | ⚠️ Overengineered | ⚠️ Moderate | ❌ Wrong inductive bias |
| Interpretability (SHAP) | ✅ Native | ❌ None | ❌ None | ❌ None |
| Small-data performance (500–5000 rows) | ✅ Excellent | ❌ Needs thousands | ⚠️ Moderate | ❌ Poor |
| Training speed (CPU) | ✅ Minutes | ❌ Hours (GPU preferred) | ⚠️ Fast | ⚠️ Moderate |
| Governance (feature importance) | ✅ Required | ❌ Not available | ❌ Not available | ❌ Not available |

**Full spec**: `research/specs/ML_BASELINE_SPEC.md`

**Implementation scaffold**: `research/models/` (Copilot task P8 — pending)

**Risk level**: Low for XGBoost. Medium for LSTM (do not implement until XGBoost passes all promotion gates).

---

#### AQ8 — VaR/CVaR Gate Design

**Decision**: Historical simulation VaR at 95% confidence, 252-day rolling window, integrated as a hard gate in `RiskManager.approve_signal()`. CVaR provided for reporting only (not a hard gate).

**Current implementation**: `src/risk/var.py` — `PortfolioVaR` class + `historical_var_cvar()` standalone function.

**Integration point**: `RiskManager.approve_signal()` calls `PortfolioVaR.update()` and rejects new signals if 1-day VaR > `max_var_pct` (default 5%).

**Risk level**: Low — implemented and fully test-covered.

---

#### AQ9 — Kill-Switch Design

**Decision**: Persistent SQLite flag that survives process restarts. Triggered by circuit breakers and streaming failure limit. Requires explicit operator reset. asyncio-safe via `threading.Lock`.

**Current implementation**: `src/risk/kill_switch.py` — `KillSwitch` class with SQLite-backed state.

**Trigger sources** (as implemented):
- Max drawdown circuit breaker
- Intraday loss circuit breaker
- Consecutive loss circuit breaker
- VaR gate overflow
- Stream failure limit (`STREAM_FAILURE_LIMIT_REACHED`)
- Broker circuit breaker (`BROKER_CIRCUIT_BREAKER_HALT`)
- ML strategy emergency halt (`ml_strategy_emergency_halt`)

**Risk level**: Low — implemented and test-covered. No changes needed.

---

## 2. Unified Target Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RUNTIME LAYER                                │
│  main.py CLI ─────────────────────────────────────────────────────── │
│    │                                                                  │
│    ├─ DataFeedFactory ──► HistoricalDataProvider (Protocol)          │
│    │        │                  ├─ YFinanceProvider (current)          │
│    │        │                  ├─ PolygonProvider (next)             │
│    │        │                  └─ AlphaVantageProvider (fallback)    │
│    │        │                                                         │
│    │        ▼                                                         │
│    │   MarketDataFeed.stream()  ◄── heartbeat/backoff/lifecycle      │
│    │        │                       events → AuditLogger             │
│    │        ▼                                                         │
│    ├─ BaseStrategy.generate_signal()  ─►  Signal[strength ∈ [0,1]]  │
│    │                                                                  │
│    ├─ RiskManager.approve_signal() ◄─────────────────────────────── │
│    │        │  ├─ VaR gate (src/risk/var.py)                         │
│    │        │  ├─ Circuit breakers (drawdown/intraday/consecutive)   │
│    │        │  ├─ Kill switch check (src/risk/kill_switch.py)        │
│    │        │  └─ Paper guardrails (src/risk/paper_guardrails.py)    │
│    │        ▼                                                         │
│    ├─ Broker (AlpacaBroker | IBKRBroker | PaperBroker)              │
│    │        │  └─ Outage resilience: bounded retry + circuit breaker │
│    │        ▼                                                         │
│    ├─ AuditLogger (async queue → SQLite audit_log)                   │
│    └─ PortfolioTracker + FX normalization (GBP base)                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                │
│  SQLite (trading.db):                                                │
│    ├─ audit_log (all signals/orders/fills/events)                   │
│    ├─ strategies (registry: metadata + SHA256 + lifecycle)          │
│    └─ kill_switch (persistent on/off flag)                           │
│                                                                      │
│  Parquet (research/data/snapshots/):                                 │
│    └─ Historical OHLCV for offline research (snapshot_id hash)      │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RESEARCH LAYER (isolated)                    │
│  research/data/      — features.py, labels.py, splits.py            │
│  research/models/    — XGBoost training scaffold (P8 pending)       │
│  research/experiments/ — walk-forward harness (R2 ticket done)      │
│  research/bridge/    — strategy_bridge.py (candidate → registry)    │
│  research/specs/     — governance specs (P1/P3/P5/P7/P9 complete)  │
│                                                                      │
│  Promotion path: R1 (research gate) → R2 (runtime integration)      │
│               → R3 (paper trial) → R4 (live gate)                   │
└──────────────────────────────────────────────────────────────────────┘
```

**Key architecture invariants** (immutable):
1. `RiskManager.approve_signal()` is the sole Signal→Order path — no bypass
2. `BacktestEngine` uses `PaperBroker`, never `AlpacaBroker` or `IBKRBroker`
3. All timestamps UTC-aware throughout (feeds → strategies → risk → broker → audit)
4. Research layer is isolated from runtime layer (no imports crossing the boundary)
5. Every strategy promotion requires a dated artifact trail in `research/experiments/` and `reports/promotions/`

---

## 3. Promotion-Ready Milestone Plan

The following 6 milestones represent the remaining actionable development work. All are ordered by dependency.

| # | Title | Scope | Owner | Dependencies | Acceptance Criteria | Effort |
|---|-------|-------|-------|-------------|---------------------|--------|
| M1 | Polygon.io Provider Adapter | Implement `PolygonProvider` conforming to `HistoricalDataProvider` protocol; UK `.L` symbol support; API key via env var | Copilot | AQ4 decision (done) | Adapter fetches UK OHLCV; tests mock Polygon API; existing feed tests unchanged | M |
| M2 | XGBoost Training Pipeline | Implement `research/models/train_xgboost.py` per ML_BASELINE_SPEC.md; fold-level train/calibrate/evaluate; artifact save/load with SHA256 | Copilot | R1/R2 research tickets (done), feature/label modules (done) | Model trains on fold data; SHAP importance computed; artifact saves+loads with hash check | L |
| M3 | Walk-Forward Experiment Report | Produce first real walk-forward report on MVU (15 UK symbols, 2018–2024, 8 folds) using rule-based strategy | Copilot + Manual | M1 (Polygon data), features/labels (done) | `promotion_check.json` generated; metrics within expected ranges; no leakage detected | M |
| M4 | IBKR In-Window Paper Session Sign-Off | Complete Step 1 in-window run: ≥5 trades, strict reconcile passes, exports verified | Manual Operator | Step 1/1A runbook (MO-1/MO-2) | All Step 1 Go/No-Go criteria met (see IMPLEMENTATION_BACKLOG.md §Step 1) | S |
| M5 | Research → Paper Trial Promotion | Promote first rule-based research candidate (`ma_crossover_research`) to `approved_for_paper` after ≥30 closed paper trades | Copilot + Manual | M4, M3 | `promotion_checklist.json → decision=READY`; `registry.promote(... "approved_for_paper")` succeeds | S |
| M6 | Alpha Vantage Provider Adapter | Implement `AlphaVantageProvider` as fallback; rate-limit awareness; US equities only | Copilot | M1 (Polygon pattern to follow) | Adapter fetches US OHLCV within rate limits; graceful degradation on limit exceeded | S |

**Legend**: S = < 4 hours, M = 4–8 hours, L = 8–16 hours

---

## 4. Immediate Next 3 Actions

### Action 1 (Copilot — Implementable immediately)

**Polygon.io Provider Adapter** (M1)

```python
# Target: src/data/providers.py — add PolygonProvider
# Interface: HistoricalDataProvider protocol (already defined)
# Key behaviour:
#   - Accept POLYGON_API_KEY from env var
#   - Support .L suffix routing to LSE (polygon ticker: "SHEL:XLON" pattern)
#   - Return adjusted OHLCV DataFrame with UTC-aware DatetimeIndex
#   - Raise ProviderError (not crash) on API errors / rate limits
# Tests: mock HTTP responses; verify column names + UTC index; .L routing
```

### Action 2 (Copilot — Implementable immediately, no manual window required)

**XGBoost Training Pipeline** (M2) — use existing research snapshots + features + labels

```python
# Target: research/models/train_xgboost.py
# Inputs: snapshot_id from research/data/snapshots/ + ExperimentConfig
# Outputs: research/models/artifacts/<model_id>/{model.bin, metadata.json}
# Per-fold: train → Platt calibration → threshold optimization on val → OOS eval
# Evidence: fold_F*.json + aggregate_summary.json + SHAP top-20 per fold
# Tests: train on synthetic 100-row dataset; verify artifact save/load + hash check
```

### Action 3 (Manual Operator — requires 08:00–16:00 UTC session window)

**IBKR In-Window Paper Session** (M4)

```bash
# Pre-check (must pass):
python main.py uk_health_check --profile uk_paper --strict-health

# Trial (08:00-16:00 UTC only):
python main.py paper_trial --confirm-paper-trial --profile uk_paper \
  --paper-duration-seconds 1800 --skip-rotate

# Post-run:
python main.py paper_session_summary --profile uk_paper --output-dir reports/uk_tax
python main.py uk_tax_export --profile uk_paper --output-dir reports/uk_tax
python main.py paper_reconcile --profile uk_paper --output-dir reports/uk_tax \
  --expected-json reports/uk_tax/paper_session_summary.json --strict-reconcile
```

Success criteria: `filled_order_count ≥ 5`, strict reconcile exits 0.

---

## 5. Risk Register

| # | Failure Mode | Trigger Signal | Detection Metric | Mitigation | Rollback |
|---|-------------|----------------|-----------------|------------|---------|
| R1 | Polygon.io UK ticker mismatch | `.L` suffix not mapped to Polygon exchange convention | Provider returns empty DataFrame or ProviderError | Pre-validate ticker on adapter init; log all failed lookups | Fall back to YFinanceProvider for failed symbols |
| R2 | XGBoost model leakage undetected | OOS win rate >> train win rate (appears too good) | Overfitting score < 0 (OOS > train) | Leakage detection test: shuffle label→feature alignment and verify metric collapse | Reject candidate; flag for investigation; do not promote |
| R3 | Walk-forward fold insufficient data | Some folds < 20 closed trades | `n_folds_insufficient_data > 3` in aggregate summary | Widen fold test windows; increase universe size; accept insufficient-data flag and note in report | Block promotion; extend data date range before retry |
| R4 | IBKR in-window session no fills | Session runs in correct window but signal count = 0 | `signal_count > 0` but `filled_order_count = 0` | Verify strategy has qualifying signals at current price levels; check paper guardrail logs; reduce position-size threshold | Switch to more liquid strategy (bollinger_bands) for burn-in |
| R5 | Research layer imports runtime code | Research module accidentally imports `src/` runtime paths | CI lint check: `grep -r "from src" research/` fails | Enforce research isolation in CI (add to test suite) | Revert import; enforce import boundary in `research/__init__.py` |

---

## 6. Backlog Patch Snippets

Paste these directly into `IMPLEMENTATION_BACKLOG.md` to update the relevant sections.

### 6a — New Step Entries

```markdown
### Step 24: Polygon.io Provider Adapter (AQ4-M1)
**Status**: NOT STARTED
**Priority**: HIGH
**Intended Agent**: Copilot
**Execution Prompt**: Implement PolygonProvider conforming to HistoricalDataProvider protocol with UK .L symbol routing, API key via env var, UTC-aware output, and focused tests.

**Acceptance Criteria**:
- Adapter fetches UK OHLCV (tested against mock API)
- .L suffix resolves to correct Polygon exchange convention
- Existing YFinanceProvider tests are unaffected

**Estimated Effort**: M (4–8 hours)

---

### Step 25: XGBoost Training Pipeline (AQ7-M2)
**Status**: NOT STARTED
**Priority**: HIGH
**Intended Agent**: Copilot
**Execution Prompt**: Implement research/models/train_xgboost.py per ML_BASELINE_SPEC.md; fold-level train/calibrate/eval; artifact save/load with SHA256; SHAP importance; focused tests.

**Acceptance Criteria**:
- Trains on fold data; SHAP per-fold output present
- Artifact saves and loads with hash verification
- fold_F*.json + aggregate_summary.json + promotion_check.json generated

**Estimated Effort**: L (8–16 hours)

---

### Step 26: Research Isolation CI Guard (R5 risk mitigation)
**Status**: NOT STARTED
**Priority**: MEDIUM
**Intended Agent**: Copilot
**Execution Prompt**: Add a test that asserts no file under research/ imports from src/ at module level. Prevents research/runtime boundary violations.

**Acceptance Criteria**:
- Test passes in clean state
- Test fails if any research/ module imports from src/

**Estimated Effort**: S (< 2 hours)
```

### 6b — Claude Opus Queue Updates

```markdown
### Claude Opus Queue — Completed Items (Feb 24, 2026)

- **CO-1** ✅ COMPLETED Feb 24: RESEARCH_PROMOTION_POLICY.md checklists updated with accurate stage status, rule-based candidate path clarification, and unblocking dependency map.
- **CO-2** ✅ COMPLETED Feb 24: FEATURE_LABEL_SPEC.md seed policy item resolved; all checklist items now complete.
- **CO-3** ✅ COMPLETED Feb 24: PROJECT_ROADMAP.md triage complete — see docs/ARCHITECTURE_DECISIONS.md §3 for milestone plan.
- **CO-4** ✅ COMPLETED Feb 24: DEVELOPMENT_GUIDE.md strategic checklist triage complete — remaining items are either covered by milestones M1–M6 or explicitly deferred.
- **CO-5** ✅ COMPLETED Feb 24: AQ1–AQ9 decisions resolved in docs/ARCHITECTURE_DECISIONS.md. New Steps 24–26 added.

**Outstanding Items after Feb 24**: 0 (all CO items resolved)
```

### 6c — Outstanding Count Update

Update the Claude Opus Queue header:

```markdown
## Claude Opus Queue (Deferred)

**Outstanding Items**: 0 (all resolved Feb 24, 2026 — see docs/ARCHITECTURE_DECISIONS.md)
```

---

## 7. CO-3 — PROJECT_ROADMAP.md Workstream Triage

The roadmap was written for US equities before the UK-first pivot. This section provides the authoritative triage of all open workstream items.

### Triage Table

| Workstream | Original Status | Current State | Decision |
|-----------|----------------|--------------|----------|
| Phase 1.1: Provider interface | `[ ]` | ✅ Done — `HistoricalDataProvider` protocol in `src/data/providers.py` | Close |
| Phase 1.1: Polygon.io adapter | `[ ]` | Scaffold only | → **Step 24** (M1) — HIGH priority |
| Phase 1.1: Full bars/instruments SQLite schema | `[ ]` | Parquet for research (done); operational SQLite covers audit/registry | **Defer** — not needed until live trading scale |
| Phase 1.1: Backfill job + checkpoint resume | `[ ]` | Research snapshot pipeline (R1 done); live backfill not done | **Defer** — add as Step 27 after Polygon adapter |
| Phase 1.2: Exploratory analysis notebook | `[ ]` | Not started | **Defer** — useful but not on critical path; future sprint |
| Phase 1.3: OHLC/staleness/gap validation | `[ ]` | ✅ Done — `src/risk/data_quality.py`, gap handling in session guards | Close |
| Phase 1.3: Automated Slack/email alerts | `[ ]` | Not started | **Defer** — execution dashboard exists; email MEDIUM priority |
| Phase 2.1: ADX indicator | `[ ]` | Not started | → **Step 28** — HIGH (per CLAUDE.md: "ADX trend filter") |
| Phase 2.1: OBV, VWAP, Stochastic, Keltner, CCI | `[ ]` | Not started | **Tier 2** — queue after ADX; not blocking paper trial |
| Phase 2.2: Strategy registry enhancements | `[ ]` | ✅ Done — lifecycle states, SHA256, promotion checklist gate | Close |
| Phase 2.3-2.4: Walk-forward, Monte Carlo | `[ ]` | Walk-forward harness done (R2); Monte Carlo not done | Monte Carlo: **Defer** — post-promotion enhancement |
| Phase 2.5: ML/NN integration | `[ ]` | XGBoost pipeline done; training module pending | → **Step 25** (M2) |
| Phase 3: Daemon bot, audit trail | `[ ]` | ✅ Done — paper trial automation, audit logger | Close |
| Phase 3: WebSocket streaming (production) | `[ ]` | Polling resilience done (Step 23); true WS deferred | **Defer** — not needed for daily-bar strategy |
| Phase 3: Live vs backtest comparison | `[ ]` | Execution dashboard + reconciliation report exist | **Partial** — enhance dashboard with backtest overlay (future) |

### Net New Steps from CO-3 Triage

- **Step 27**: ADX trend filter implementation (see §CO-4 below)
- **Step 28**: Daily data quality monitoring report

---

## 8. CO-4 — DEVELOPMENT_GUIDE.md Strategic Checklist Triage

Triage of the Tier 1/2/3 feature priority checklist in DEVELOPMENT_GUIDE.md against current implementation state.

### Tier 1 (Foundation) — Status

| Item | Was | Now |
|------|-----|-----|
| Multiple provider support | `[ ]` | Scaffold done; Polygon Step 24 — **promote to Step 24** |
| OHLCV data persistence (SQLite indexes) | `[ ]` | ✅ Research Parquet + operational SQLite done |
| Incremental backfill | `[ ]` | Research snapshots done; live backfill deferred |
| Statistical profiling notebook | `[ ]` | Defer — future research sprint |
| Factor analysis / correlation matrix | `[ ]` | Defer — research track `notebooks/` |
| Anomaly detection | `[ ]` | ✅ Partially done — data quality guard (`src/risk/data_quality.py`) |
| Regime identification | `[ ]` | ✅ Done via `config/test_regimes.json` + validation protocol |
| Integrity checks (OHLC, volume) | `[ ]` | ✅ Done |
| Survivorship bias handling | `[ ]` | Acknowledged in `research/specs/FEATURE_LABEL_SPEC.md`; not fully mitigated — **defer** |
| Corporate action adjustments | `[ ]` | Handled by `yfinance auto_adjust=True`; formal CA log deferred |
| Automated monitoring alerts | `[ ]` | Execution dashboard exists; email alerts deferred |

### Tier 2 (Enhancement) — Status

| Item | Was | Now |
|------|-----|-----|
| ADX indicator | `[ ]` | NOT DONE — → **Step 27** HIGH |
| OBV, VWAP, Stochastic Oscillator | `[ ]` | Defer — Tier 2, post ADX |
| Keltner Channels, CCI | `[ ]` | Defer — Tier 3 effectively |
| Strategy registry enhancement | `[ ]` | ✅ DONE (lifecycle + SHA256 + promotion gate) |
| Multi-timeframe strategies | `[ ]` | Defer — no intraday data yet |
| Strategy combinations / ensemble voting | `[ ]` | Defer — needs ≥ 2 promoted strategies first |
| Walk-forward optimization | `[ ]` | ✅ DONE (research harness R2) |
| Scenario testing | `[ ]` | Partial — regime test matrix exists; no automated scenario runner |
| Monte Carlo resampling | `[ ]` | Defer — post-promotion enhancement |
| Out-of-sample validation | `[ ]` | ✅ DONE (walk-forward test folds are OOS) |

### Tier 3 (ML/Enterprise) — Status

| Item | Was | Now |
|------|-----|-----|
| Feature engineering pipeline | `[ ]` | ✅ DONE (`research/data/features.py`) |
| Time-aware data splits | `[ ]` | ✅ DONE (`research/data/splits.py`) |
| XGBoost classifier | `[ ]` | Pipeline done (CLI); training scaffold → **Step 25** |
| PyTorch LSTM | `[ ]` | Scaffold spec in `ML_BASELINE_SPEC.md`; implement only after XGBoost passes |
| NN strategy wrapper | `[ ]` | ✅ DONE (research bridge `research/bridge/strategy_bridge.py`) |
| Daemon bot (24/5 continuous) | `[ ]` | Defer — paper trial must pass first |
| WebSocket real-time feeds | `[ ]` | Defer — polling + backoff is sufficient for daily-bar |
| REST API dashboard (FastAPI) | `[ ]` | Defer — Tier 3 stretch goal |
| Kubernetes deployment | `[ ]` | Defer — production phase only |

### Net New Steps from CO-4 Triage

- **Step 27**: ADX trend filter — `src/indicators/adx.py` + `src/strategies/adx_filter.py`, per CLAUDE.md §Indicators
- **Step 28**: Daily data quality monitoring report — extend execution dashboard with scheduled staleness + gap summary

---

## 9. AQ Closure Record

| AQ | Was Open? | Resolution | Evidence |
|----|-----------|-----------|----------|
| AQ1 | Yes | SQLite+Parquet hybrid — already implemented | `src/strategies/registry.py`, `research/data/snapshots.py` |
| AQ2 | Yes | Event-driven — already implemented | `backtest/engine.py` |
| AQ3 | Yes | Hybrid registry — already implemented | `src/strategies/registry.py` |
| AQ4 | Yes | Provider stack tiered; Polygon.io next | `src/data/providers.py` (scaffold done); Step 24 (pending) |
| AQ5 | Yes | Polling + backoff + lifecycle events — implemented | `src/data/feeds.py`, Step 23 |
| AQ6 | Yes | Leakage-safe features/labels — implemented | `research/data/features.py`, `labels.py` |
| AQ7 | Yes | XGBoost first — spec done, implementation pending | `research/specs/ML_BASELINE_SPEC.md`; Step 25 |
| AQ8 | Yes | Historical VaR/CVaR gate — implemented | `src/risk/var.py` |
| AQ9 | Yes | SQLite kill-switch — implemented | `src/risk/kill_switch.py` |

---

**References:**
- `research/specs/UK_UNIVERSE.md` — tradable universe
- `research/specs/FEATURE_LABEL_SPEC.md` — feature/label spec (all items ✅)
- `research/specs/VALIDATION_PROTOCOL.md` — walk-forward protocol
- `research/specs/ML_BASELINE_SPEC.md` — ML governance
- `research/specs/RESEARCH_PROMOTION_POLICY.md` — promotion policy (checklist updated)
- `docs/PROMOTION_FRAMEWORK.md` — Gate A/B institutional framework
- `docs/RISK_ARCHITECTURE_REVIEW.md` — risk gap analysis (all P0/P1 gaps resolved)
- `IMPLEMENTATION_BACKLOG.md` — live task tracking
