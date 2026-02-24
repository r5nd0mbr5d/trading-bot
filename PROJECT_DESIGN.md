# PROJECT_DESIGN.md — LLM Project Design Document (LPDD)

**Version:** 1.0
**Last Updated:** Feb 24, 2026
**Status:** ACTIVE — primary architectural authority for this repository

> This is the canonical design document for the trading bot project.
> It is written for LLM-first consumption and maintained as a living record.
> Humans and LLMs alike should read this before making structural decisions.
>
> **Reading order for a new LLM session:**
> 1. This file (`PROJECT_DESIGN.md`) — decisions, constraints, debt, history
> 2. `CLAUDE.md` — session context, invariants, quick-reference conventions
> 3. `IMPLEMENTATION_BACKLOG.md` — what to build next and in what order
> 4. `.python-style-guide.md` — how to write the code

---

## §0 LLM Operating Instructions

### How to read this document
- **§1–§2**: What this project is and its verified current state — read once per session
- **§3 ADRs**: Why things are the way they are — consult before changing any structural component
- **§4 RFCs**: What is being proposed but not yet decided — contribute here when raising new design questions
- **§5 Technical Debt**: Known issues accepted as debt — do not "fix" these without the corresponding backlog step
- **§6 Evolution Log**: What changed and when — append entries here when completing major steps
- **§7 Constraints**: Hard rules that cannot change without an ADR

### How to update this document
- **Completing a backlog step** → mark the corresponding RFC as ACCEPTED or CLOSED; append to §6 Evolution Log
- **Making a new structural decision** → add an ADR to §3; reference the ADR number in commit messages and backlog steps
- **Raising a design question** → add an RFC to §4 with status PROPOSED; link to the relevant backlog step
- **Discovering new technical debt** → add an entry to §5; create a backlog step if actionable
- **Never** retroactively change ACCEPTED ADRs — supersede them with a new ADR instead
- **Always** update `Last Updated` at the top of this file when making changes

---

## §1 Project Identity

### Purpose
Enterprise-grade algorithmic trading platform for UK-first equities (FTSE 100/250 + liquid ETFs), supporting:
1. Systematic rule-based strategy development and backtesting
2. ML/research track (XGBoost → LSTM promotion pipeline)
3. Paper trading via Alpaca and live trading via IBKR

### Current Phase
**Phase: Paper Trial Validation** — Step 1 backtest signed off (Feb 24, 2026). Awaiting MO-2: 3 consecutive in-window paper sessions with fills.

### Non-Goals
- Real-time high-frequency trading (sub-second execution)
- Options, futures, or crypto (equities only until live gate is passed)
- Multi-user / multi-tenant deployment
- US equities as primary focus (UK-first; US equities only when justified by risk-adjusted return improvement)

### Guiding Philosophy
> "Correctness before performance. Paper before live. Evidence before promotion."

---

## §2 Architecture Snapshot

### Verified Current State (Feb 24, 2026)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RUNTIME LAYER                               │
│                                                                     │
│  main.py CLI (956 lines — reduced, still refactor target via RFC-001)│
│    │                                                                 │
│    ├─ MarketDataFeed ──► HistoricalDataProvider (Protocol)          │
│    │        ├─ YFinanceProvider       ✅ Implemented                │
│    │        ├─ PolygonProvider        ✅ Implemented (Step 24)      │
│    │        ├─ AlphaVantageProvider   ✅ Implemented (Step 29)      │
│    │        └─ MassiveWebSocketFeed   ✅ Scaffold (Step 30 pending) │
│    │                                                                 │
│    ├─ BaseStrategy.generate_signal() → Signal [strength ∈ [0,1]]   │
│    │        ├─ MACrossoverStrategy    ✅                            │
│    │        ├─ RSIMomentumStrategy    ✅                            │
│    │        ├─ MACDCrossoverStrategy  ✅                            │
│    │        ├─ BollingerBandsStrategy ✅                            │
│    │        └─ ADXFilterStrategy      ✅ (wrapper)                  │
│    │                                                                 │
│    ├─ RiskManager.approve_signal()   ✅ ONLY path Signal → Order    │
│    │        ├─ VaR gate (historical simulation, 252-day rolling)    │
│    │        ├─ Circuit breakers (drawdown / intraday / consecutive) │
│    │        ├─ KillSwitch (SQLite-backed, survives restart)         │
│    │        └─ PaperGuardrails (UK session window, position limits) │
│    │                                                                 │
│    ├─ Broker                                                        │
│    │        ├─ AlpacaBroker           ✅ Paper trading              │
│    │        ├─ IBKRBroker             ✅ Live trading               │
│    │        └─ PaperBroker            ✅ Backtest only              │
│    │                                                                 │
│    ├─ AuditLogger (async queue → SQLite audit_log)  ✅             │
│    └─ PortfolioTracker + FX normalisation (GBP base) ✅            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                               │
│  SQLite (trading.db / trading_paper.db):                            │
│    ├─ audit_log        — all signals / orders / fills / events      │
│    ├─ strategies       — registry: metadata + SHA256 + lifecycle    │
│    └─ kill_switch      — persistent on/off flag                     │
│                                                                     │
│  Parquet (research/data/snapshots/):                                │
│    └─ Historical OHLCV for offline research (snapshot_id hash)      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RESEARCH LAYER (isolated)                        │
│  research/data/      — features.py, labels.py, splits.py  ✅       │
│  research/models/    — XGBoost pipeline ✅; LSTM deferred          │
│  research/experiments/ — walk-forward harness ✅                   │
│  research/bridge/    — strategy_bridge.py ✅                       │
│                                                                     │
│  Promotion path: R1 → R2 → R3 (paper trial) → R4 (live gate)      │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Metrics (Step 1 sign-off, Feb 24 2026)
- Test suite: **405 tests passing**
- Backtest result (uk_paper, 2025-01-01 → 2026-01-01): 93 signals, 26 trades, Sharpe 1.23, Return 1.10%, Max DD 0.90%
- Filled order criterion (Step 1): ✅ 26 trades >> 5 minimum

---

## §3 Architecture Decision Records (ADRs)

> Format: each ADR records the **context** (why the decision was needed), the **decision** (what was chosen), the **consequences** (trade-offs), and **status**.
> Status values: `PROPOSED` | `ACCEPTED` | `DEPRECATED` | `SUPERSEDED by ADR-XXX` | `DEFERRED`

---

### ADR-001: Event-Driven Backtesting
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ2 (docs/ARCHITECTURE_DECISIONS.md §AQ2)

**Context:** Two backtesting paradigms exist — vectorized (fast, all bars at once) and event-driven (slower, bar-by-bar).

**Decision:** Event-driven only. `backtest/engine.py` replays bars sequentially; orders buffer at bar[t] close and fill at bar[t+1] open.

**Consequences:**
- ✅ Zero lookahead parity with live paper runtime — identical signal/risk/kill-switch path in both modes
- ✅ Strategy registry, risk gates, circuit breakers, and kill switch all fire during backtest as in live
- ❌ ~3–10× slower than vectorized for large backtests — acceptable: 3-year daily backtest on 15 symbols runs in <5s

**Alternatives Considered:** `backtrader`, `zipline`, `vectorbt` — all rejected because they cannot guarantee identical code paths with the live runtime.

---

### ADR-002: `ib_insync` for IBKR Integration
**Status:** ACCEPTED
**Date:** 2026-02-23
**Superseded by:** N/A (see ADR-011 for future evaluation)

**Context:** IBKR TWS exposes a socket API. The official library (`ibapi`) is raw and callback-heavy. `ib_insync` is a mature third-party asyncio-native wrapper.

**Decision:** Use `ib_insync`. `IBKRBroker` wraps it with a `_connect()` retry loop and clientId auto-increment on collision.

**Consequences:**
- ✅ asyncio-native, integrates cleanly with the paper trading event loop
- ✅ `IB()` object, `Trade` objects, `waitOnUpdate()` — far simpler than raw `ibapi`
- ❌ Third-party: no IBKR SLA; could fall behind TWS API changes
- ❌ IBKR released an official Python WebSocket API (`ibkr_python_ws`) in late 2025 — evaluate before any major IBKRBroker refactor (see ADR-011)

**Alternatives Considered:** Raw `ibapi` — rejected (no async support, sleep-based synchronisation, fragile); `ibkr_python_ws` — deferred to ADR-011.

---

### ADR-003: Hybrid SQLite + Parquet Storage
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ1

**Context:** The platform needs both operational data storage (audit log, registry, kill switch — random access, ACID) and research data storage (10M+ rows OHLCV — columnar, bulk read).

**Decision:** SQLite for all operational data; Parquet (`research/data/snapshots/`) for research OHLCV. No TimescaleDB or PostgreSQL.

**Consequences:**
- ✅ Zero deployment complexity — file-based, no server process
- ✅ SQLite ACID guarantees for audit log and kill switch
- ✅ Parquet columnar format ideal for ML feature computation
- ❌ SQLite struggles above ~10M OHLCV rows — addressed by Step 34 (persistent market data cache) before live scale

---

### ADR-004: Tiered Data Provider Stack
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ4

**Context:** Multiple data providers exist with different cost, reliability, and coverage trade-offs.

**Decision:** Three-tier stack with a unified `HistoricalDataProvider` protocol:

| Tier | Provider | Use | Cost |
|---|---|---|---|
| 1 | yfinance | Development, backtesting | Free (unofficial) |
| 2 | Massive (Polygon.io) | Production UK equities | Paid |
| 3 | Alpha Vantage | US equities fallback | Free (25 req/day) |

**Consequences:**
- ✅ Swappable providers via protocol — strategies never touch provider code
- ✅ Free development tier; production tier available when needed
- ❌ yfinance is unofficial (no SLA, 15–30 min LSE delay) — acceptable for paper, not production
- ❌ Alpha Vantage 25 req/day limit requires Step 34 (persistent cache) before use

**Note:** IEX Cloud was in original design; **permanently removed April 2025** (provider shut down). See session notes Feb 24, 2026.

---

### ADR-005: XGBoost Before LSTM
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ7

**Context:** Multiple ML architectures considered for direction-classification on OHLCV features.

**Decision:** XGBoost is the first and only required model. LSTM is scaffolded but must not be implemented until XGBoost passes all promotion gates (R1 → R3 paper trial).

**Consequences:**
- ✅ XGBoost is best-in-class for tabular data in small-data regime (500–5000 rows per fold)
- ✅ Native SHAP interpretability — required for governance
- ✅ CPU training in minutes vs. GPU-hours for LSTM
- ❌ XGBoost cannot capture sequential temporal dependencies as well as LSTM — acceptable for daily-bar strategies

---

### ADR-006: Polling-Based Streaming for Daily-Bar Strategies
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ5

**Context:** Daily-bar strategies do not require sub-second data. WebSocket streaming adds complexity.

**Decision:** Polling with exponential backoff and heartbeat lifecycle events. No WebSocket for current strategy set.

**Consequences:**
- ✅ Simple, reliable, fully tested
- ✅ Same kill-switch and audit path as live runtime
- ❌ Not suitable for intraday strategies — address when/if intraday strategies are added (Step 30 scaffolded)

---

### ADR-007: Alpaca for Paper, IBKR for Live
**Status:** ACCEPTED
**Date:** 2026-02-23

**Context:** Paper trading requires a broker with a free sandbox. Live trading requires a UK-capable broker.

**Decision:** Alpaca for paper trading (free paper account, no real money, well-documented API). IBKR for live trading (supports UK LSE equities, robust TWS API).

**Consequences:**
- ✅ Zero cost for paper development phase
- ✅ IBKR supports `.L` LSE symbols natively
- ❌ Broker-switch means some reconciliation logic has to work with both APIs — handled by `BrokerBase` abstraction (see ADR-010 for unification gap)

---

### ADR-008: Research-Runtime Isolation Boundary
**Status:** ACCEPTED
**Date:** 2026-02-23
**Ref:** AQ8 / R5 risk register

**Context:** Research code (ML training, feature engineering) must not import from the runtime layer (`src/`) or it can introduce lookahead bias or unintended coupling.

**Decision:** `research/` must not import from `src/` at module level. The only permitted crossing is via `research/bridge/strategy_bridge.py` which promotes validated candidates into the registry.

**Consequences:**
- ✅ Guaranteed research/runtime isolation — ML training cannot accidentally use live broker objects
- ✅ Enforced by CI guard (Step 26)
- ❌ Research code must duplicate some data model definitions — acceptable; `src/data/models.py` types may be re-imported via bridge only

---

### ADR-009: UK-First Strategy Development
**Status:** ACCEPTED
**Date:** 2026-02-23

**Context:** Project originally designed for US equities. Pivoted to UK-first after user direction.

**Decision:** UK/London session first. Base currency GBP. Universe: FTSE 100/250 + liquid ETFs. US equities only added when justified by risk-adjusted return improvement.

**Consequences:**
- ✅ UK session guardrails (08:00–16:00 UTC) enforced in `PaperGuardrails`
- ✅ GBP FX normalisation in `PortfolioTracker`
- ✅ UK tax export (`uk_tax_export` flow) preserved
- ❌ yfinance LSE data has 15–30 min delay and `.L` suffix quirks — managed by `enable_stale_check=False` in `uk_paper` profile

---

### ADR-010: `main.py` Refactor Target Architecture
**Status:** PROPOSED → See RFC-001
**Date:** 2026-02-24
**Ref:** Steps 37, 38, 43

**Context:** `main.py` has grown to 1,938 lines with 0 classes, 27 internal imports, and a 981-line `cmd_paper` function containing a 280-line `on_bar` closure. This is a known god module (see structural review, Feb 24 2026).

**Decision (proposed):** Extract into:
```
main.py                     (~150 lines — entry point only)
src/trading/loop.py         (TradingLoopHandler class — on_bar as methods)
src/trading/stream_events.py (heartbeat / error callbacks)
src/execution/resilience.py (_run_broker_operation)
src/cli/arguments.py        (ArgumentParser + dispatch)
```

**Consequences (projected):**
- ✅ `on_bar` becomes independently testable as class methods
- ✅ Remaining test imports decouple from `main.py` private functions
- ✅ Broker retry logic moves to the correct layer
- ❌ Large refactor — must be done with full test suite passing at each step

**Acceptance Criteria:** `main.py` ≤ 150 lines; all 405+ tests pass; no regressions.

---

### ADR-011: Evaluate `ibkr_python_ws` as IBKR Integration Path
**Status:** DEFERRED
**Date:** 2026-02-24
**Ref:** IBKR Quant article (saved in `tmp/`)

**Context:** IBKR released an official Python WebSocket API (`ibkr_python_ws`) in late 2025. It is IBKR-maintained and WebSocket-native, unlike `ib_insync` (third-party, TWS socket).

**Decision:** Deferred. `ib_insync` is working. Evaluate `ibkr_python_ws` before any major `IBKRBroker` refactor.

**Trigger for re-evaluation:** `ib_insync` falls significantly behind a major TWS API version OR `ibkr_python_ws` reaches stable release with full feature parity.

---

### ADR-012: QuantConnect / LEAN as Cross-Validation Layer
**Status:** ACCEPTED (low priority)
**Date:** 2026-02-24
**Ref:** Step 36

**Context:** QuantConnect provides free cloud backtesting with 150+ built-in indicators and production-grade reality modelling (slippage, fills, commissions) — capabilities the current engine lacks.

**Decision:** Use QuantConnect free cloud tier to cross-validate top strategies (MA Crossover, RSI Momentum). Do not migrate the runtime to LEAN — the custom engine is working and test-covered.

**Consequences:**
- ✅ Independent slippage/fill reality check against Step 1 results
- ✅ Free (cloud backtest, 1 node, minute bars, UK/LSE supported)
- ❌ LEAN-CLI local coding requires $60/mo paid tier — not needed for this task
- ❌ Migration to LEAN would reset 405 tests and rewrite all 4 strategies — not justified

---

## §4 Active RFCs (Change Proposals)

> RFCs are proposals that have not yet been fully implemented. They become ADRs once accepted and completed.
> Status values: `PROPOSED` | `ACCEPTED` | `IN PROGRESS` | `CLOSED` | `REJECTED` | `DEFERRED`

---

### RFC-001: Extract Trading Loop from `main.py`
**Status:** IN PROGRESS
**Date:** 2026-02-24
**Target Backlog Steps:** 37, 38, 43
**Author:** Structural review (Feb 24, 2026)

**Problem:** `main.py` remains oversized (956 lines) and still anchors too much runtime orchestration. Core extraction has landed, but full entrypoint slimming and test decoupling are incomplete.

**Proposed Change:**
- Create `src/trading/loop.py` with `TradingLoopHandler` class
- Methods: `on_bar()`, `_check_data_quality()`, `_generate_signal()`, `_gate_risk()`, `_submit_order()`, `_snapshot_portfolio()`
- Create `src/trading/stream_events.py` for `on_stream_heartbeat` / `on_stream_error`
- Move `_run_broker_operation` to `src/execution/resilience.py` (Step 38)
- Move `ArgumentParser` to `src/cli/arguments.py` (Step 43, after Step 37)

**Acceptance Criteria:**
- `main.py` ≤ 150 lines
- Each `TradingLoopHandler` method independently unit-testable
- All 405+ tests pass; remaining tests updated to import from new module paths
- No regressions in paper trading behaviour

**Implementation Order:** Step 38 (quick, no conflicts) → Step 39 (trivial) → Step 37 (main extraction) → Step 43 (CLI cleanup)

**Progress Update (Feb 24, 2026):**
- ✅ `src/trading/loop.py` extracted with `TradingLoopHandler`
- ✅ `src/trading/stream_events.py` extracted
- ✅ `src/execution/resilience.py` extracted and wired
- ✅ `src/cli/arguments.py` extraction completed
- ⚠️ Remaining: final `main.py` reduction and test import decoupling from `main.py` (15 test files still import `main.py`, re-validated in latest Feb 24 sweep)
- 🔎 Latest verification snapshot: `main.py` line count remains 956; `tests/*` imports from `main.py` remain 15 (status unchanged)

---

### RFC-002: Unified `BrokerBase` Interface
**Status:** CLOSED
**Date:** 2026-02-24
**Target Backlog Step:** 40
**Author:** Structural review (Feb 24, 2026)

**Problem:** `AlpacaBroker` and `PaperBroker` inherit from `BrokerBase`. `IBKRBroker` does not — it reimplements the interface independently with inconsistent error handling (`AlpacaBroker` logs silently; `IBKRBroker` raises `RuntimeError`).

**Proposed Change:**
- Make `IBKRBroker` inherit `BrokerBase`
- Align error handling: classify errors as `transient` (retry) or `terminal` (halt) consistently across all brokers
- Add IBKR-specific error code table to `src/execution/resilience.py`

**Acceptance Criteria:**
- `isinstance(broker, BrokerBase)` is `True` for all three broker implementations
- Error handling contract documented in `BrokerBase` docstring
- `tests/test_ibkr_broker.py` still passes

**Completion Note (Feb 24, 2026):** `IBKRBroker` now inherits `BrokerBase`; interface parity objective met.

---

### RFC-003: Signal and Timestamp Validation at Dataclass Level
**Status:** CLOSED
**Date:** 2026-02-24
**Target Backlog Step:** 41

**Problem:** `CLAUDE.md` documents `Signal.strength ∈ [0.0, 1.0]` and UTC-aware timestamps as hard invariants, but neither is enforced in `src/data/models.py`. Violations are silent at construction time.

**Proposed Change:**
- Add `__post_init__` to `Signal`: `if not 0.0 <= self.strength <= 1.0: raise ValueError`
- Add timezone-awareness check to `Signal`, `Order`, `Bar`: `if self.timestamp.tzinfo is None: raise ValueError`

**Acceptance Criteria:**
- `Signal(strength=1.5, ...)` raises `ValueError` at construction
- `Bar(timestamp=datetime.now(), ...)` raises `ValueError` (naive datetime)
- Tests in `tests/test_models.py` cover all cases

**Completion Note (Feb 24, 2026):** Dataclass-level `__post_init__` validation is implemented for strength bounds and UTC-aware timestamps; model tests added.

---

## §5 Technical Debt Register

> Known issues that are accepted as debt with a plan to address them.
> Each entry links to the backlog step that resolves it.

| ID | Description | Severity | Backlog Step | Notes |
|---|---|---|---|---|
| **TD-001** | `main.py` remains oversized (956 lines) | HIGH | Steps 37–43 | Reduced from 1,938 lines; additional extraction still required (latest verification: unchanged at 956 lines) |
| **TD-002** | 15 test files importing from `main.py` | HIGH | Step 37 follow-on | Hidden coupling remains; tests should import source modules directly (re-validated Feb 24, 2026; latest verification unchanged at 15 files) |
| **TD-003** | `IBKRBroker` does not inherit `BrokerBase` | LOW (RESOLVED) | Step 40 | Resolved Feb 24, 2026 |
| **TD-004** | `Signal.strength` not validated at construction | LOW (RESOLVED) | Step 41 | Resolved Feb 24, 2026 |
| **TD-005** | Missing `research/__init__.py` | LOW (RESOLVED) | Step 39 | Resolved Feb 24, 2026 |
| **TD-006** | No persistent market data cache | HIGH | Step 34 | In-memory only; Alpha Vantage 25 req/day quota exhausted in one session |
| **TD-007** | Reporting modules are function-bags, not classes | LOW | Step 42 | `execution_dashboard.py`, `broker_reconciliation.py`, `session_summary.py` each open independent SQLite connections |
| **TD-008** | `approve_signal()` is 240 lines with no decomposition | LOW | Future | Each risk gate is a nested block; testable only as a whole; not blocking |
| **TD-009** | `ibkr_python_ws` not yet evaluated as `ib_insync` replacement | LOW | ADR-011 | Deferred until `ib_insync` shows incompatibility with a TWS API version |

---

## §6 Evolution Log

> Append-only. Record major decisions, completions, and pivots in chronological order.
> Format: `[Date] [Author] — [What changed and why]`

---

**[2026-02-23] Session (Claude Sonnet 4.6)**
- Completed Prompts 1–7, Steps 1–23 (paper trial automation, risk controls, UK guardrails, backtest engine, promotion framework)
- 405 tests passing
- Stale-data guard investigation: MA Crossover / 1-min bar incompatibility identified; `enable_stale_check=False` added to `uk_paper` profile
- IEX Cloud permanently removed (shut down April 2025) from all 9 files

**[2026-02-24] Session (Claude Sonnet 4.6)**
- **Step 1 signed off (Option A — daily backtest)**: 93 signals, 26 trades, Sharpe 1.23, Return 1.10%, Max DD 0.90%
- MO-1 closed; MO-2 (in-window paper sessions) remains open
- Polygon.io → Massive rebrand confirmed (Oct 2025); no code changes needed; `api.polygon.io` still valid
- `docs/MASSIVE_API_REFERENCE.md` created (LLM-optimised REST/WebSocket/Flat Files reference)
- `docs/DATA_PROVIDERS_REFERENCE.md` created (all 10 providers, prompts, agent matrix)
- Steps 29–36 added to backlog (Alpha Vantage, WebSocket, Flat Files, LSTM, Benzinga, Market Data Cache, QuantConnect cross-validation)
- `ALPHA_VANTAGE_API_KEY` added to `.env`
- Step 34 (Market Data Cache) added as CRITICAL, blocking Steps 29–31
- Structural review completed: `main.py` identified as 1,938-line god module; Steps 37–43 added
- `.python-style-guide.md` expanded to v1.1 with Hitchhiker's Guide design concepts (Sections 10–16)
- `CLAUDE.md` updated: style guide rules embedded directly; "auto-loaded" claim corrected to explicit mandatory-read instruction
- ADR-012 (QuantConnect cross-validation) and ADRs 001–011 formalised in this document

**[2026-02-24] Session (GitHub Copilot / GPT-5.3-Codex)**
- Step 1A operational runbook progressed with dedicated wrappers:
    - functional any-time path: `run_step1a_functional.ps1`
    - market in-window path: `run_step1a_market.ps1`
    - guarded market scheduler-friendly path: `run_step1a_market_if_window.ps1`
- Functional validation track (A1) completed and evidenced (`step1a_burnin_latest.json` shows `runs_passed=1`, `commands_passed=true`, `drift_flag_count=0`)
- RFC/debt synchronization update:
    - RFC-002 closed (BrokerBase unification objective met)
    - RFC-003 closed (model-level invariant enforcement landed)
    - TD-003/TD-004/TD-005 marked resolved
    - RFC-001 kept in progress (main.py still above target size; test import decoupling pending)
- LPDD consistency sweep:
    - Re-validated test coupling count (`tests/*` imports from `main.py`: 15)
    - Updated ADR-010 wording, RFC-001 acceptance/progress text, and TD-002 note to remove stale 18-file reference
- Follow-up re-validation:
    - Re-ran `tests/*` import scan; coupling count remains 15 and RFC-001/TD-002 status is unchanged
- Additional LPDD verification pass:
    - Re-checked `main.py` and test coupling metrics; values remain `956` lines and `15` test imports from `main.py` (no RFC/debt status change)

---

## §7 Hard Constraints (Never Break Without an ADR)

These are non-negotiable. Changing any of them requires a new ADR documenting the context, decision, and consequences.

1. **`RiskManager.approve_signal()` is the sole Signal→Order path.** No order may be submitted from a strategy, main loop, or test without passing through `RiskManager`.

2. **`BacktestEngine` uses `PaperBroker` exclusively.** Never substitute `AlpacaBroker` or `IBKRBroker` in backtest mode. The broker setting in `config/settings.py` is ignored by `backtest/engine.py` by design.

3. **`generate_signal()` must return `None` if `len(df) < min_bars_required()`.** This is the lookahead-bias gate. Any strategy that reads from the future (directly or through an indicator) is invalid.

4. **Signal `strength` must be in `[0.0, 1.0]`.** It linearly scales position size. Values outside this range produce undefined risk behaviour.

5. **All timestamps must be timezone-aware (UTC).** Naive datetimes anywhere in the pipeline (feeds → strategies → risk → broker → audit) are a bug.

6. **Research layer (`research/`) must not import from runtime layer (`src/`) at module level.** Only `research/bridge/strategy_bridge.py` may cross this boundary.

7. **Every strategy promotion requires a dated artifact trail.** Artifacts in `research/experiments/<id>/` and `reports/promotions/` are mandatory. No promotion checklist JSON = no promotion.

8. **Never hardcode ticker symbols or dates outside `config/settings.py`.** All symbols must flow from `DataConfig.symbols`; all date ranges from `BacktestConfig`.

---

## §8 Key Document Map

> Quick reference to the most important files in the repository.

| Document | Purpose | When to Read |
|---|---|---|
| `PROJECT_DESIGN.md` (this file) | Decisions, constraints, debt, history | Start of every design session |
| `CLAUDE.md` | Session context, quick-reference invariants, LLM instructions | Every session |
| `IMPLEMENTATION_BACKLOG.md` | What to build next, prompts, step-by-step tasks | When picking up a task |
| `.python-style-guide.md` | How to write code (16 sections, gotchas, patterns) | Before writing non-trivial code |
| `docs/ARCHITECTURE_DECISIONS.md` | Full AQ1–AQ9 decisions with rationale, architecture diagram, milestone plan | When working on a structural component |
| `docs/DATA_PROVIDERS_REFERENCE.md` | All 10 data providers, prompts, free tier limits | When working on data or research steps |
| `docs/MASSIVE_API_REFERENCE.md` | Massive/Polygon REST, WebSocket, Flat Files reference | Steps 29–31 |
| `DOCUMENTATION_INDEX.md` | Index of all 25 docs | When looking for a specific reference |
| `research/README.md` | Research track pipeline, CLI, troubleshooting | Research steps |
| `research/specs/ML_BASELINE_SPEC.md` | XGBoost/LSTM governance spec | Steps 25, 32 |
