# PROJECT_DESIGN.md — LLM Project Design Document (LPDD)

**Version:** 1.3
**Last Updated:** Feb 25, 2026
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
**Phase: Paper Trial Validation** — Step 1 backtest signed off (Feb 24, 2026). Awaiting MO-2: 3 consecutive in-window paper sessions with fills. Latest Step 1A report remains non-qualifying (`signoff_ready=false`).

### Non-Goals
- Real-time high-frequency trading (sub-second execution)
- Options or futures (derivatives; out of scope indefinitely)
- Crypto as primary focus — spot crypto (BTC/USD) is a planned secondary asset class (see ADR-015); full crypto support is gated behind MO-2 equity live gate
- Multi-user / multi-tenant deployment
- US equities as primary focus (UK-first; US equities only when justified by risk-adjusted return improvement)

### Guiding Philosophy
> "Correctness before performance. Paper before live. Evidence before promotion."

---

## §2 Architecture Snapshot

### Verified Current State (Feb 25, 2026)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RUNTIME LAYER                               │
│                                                                     │
│  main.py CLI (55 lines — entrypoint-only wiring)                     │
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
│    │        ├─ OBVMomentumStrategy    ✅ (Step 48)                  │
│    │        ├─ StochasticOscillator   ✅ (Step 48)                  │
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
│    ├─ DailyReportGenerator (JSON + optional email) ✅ (Step 47)    │
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

### Key Metrics (Feb 25, 2026 — post Steps 33/44/45/47/48/50/51/52/53)
- Test suite: **466 tests passing**
- `main.py` line count: **62 lines** (entrypoint-only; target ≤150 ✅)
- Test files importing `main.py`: **0** (target 0 ✅)
- Strategies registered: **8** (MA, RSI, MACD, Bollinger, ADX, OBV, Stochastic, ATR Stops)
- Backtest result (uk_paper, 2025-01-01 → 2026-01-01): 93 signals, 26 trades, Sharpe 1.23, Return 1.10%, Max DD 0.90%

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
**Status:** SUPERSEDED BY ADR-013
**Date:** 2026-02-24
**Superseded:** 2026-02-25 (Steps 37–44 completed; see ADR-013)

**Context:** `main.py` had grown to 1,938 lines. This ADR proposed the extraction strategy.

**Decision:** Extracted into layered modules (see ADR-013 for full record). Implementation complete Feb 25, 2026.

**Outcome:** `main.py` = 62 lines; 0 test imports from `main.py`; 445 tests passing. RFC-001 CLOSED.

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

### ADR-013: Trading Loop Extraction Architecture
**Status:** ACCEPTED
**Date:** 2026-02-25
**Ref:** Steps 37–44 (COMPLETED), RFC-001 (CLOSED)

**Context:** `main.py` grew to 1,938 lines with a 981-line `cmd_paper` function and 280-line `on_bar` closure capturing 10+ outer-scope variables. Steps 37–43 decomposed this into extracted modules.

**Decision:** Introduce a layered extraction:
```
src/trading/loop.py         — TradingLoopHandler class; on_bar as methods
src/trading/stream_events.py — heartbeat / error stream callbacks
src/execution/resilience.py  — run_broker_operation retry wrapper
src/cli/arguments.py         — ArgumentParser + dispatch table
```
`main.py` remains the entry point but delegates to these modules.

**Consequences:**
- ✅ Each `TradingLoopHandler` method is independently unit-testable
- ✅ Broker retry logic sits in the execution layer, not the CLI
- ✅ `main.py` slimmed to 55-line entrypoint-only wiring (target ≤150 met)
- ✅ Test import decoupling complete (`tests/*` imports from `main.py`: 0)
- ✅ 436 tests passing post-extraction and final slimming (no regressions)

---

### ADR-014: Single-Strategy-Per-Run Composition (Ensemble Deferred)
**Status:** ACCEPTED
**Date:** 2026-02-25

**Context:** With 7 strategies now registered (MA, RSI, MACD, Bollinger, ADX, OBV, Stochastic), the question arises: should the paper runtime run one strategy or all simultaneously?

**Decision:** Single-strategy-per-run for paper and live modes. The CLI `--strategy` flag selects which strategy to activate. Multi-strategy ensemble voting is deferred to Tier 3 (Step future-ensemble) and requires passing at least one strategy through Gate B (live) first.

**Consequences:**
- ✅ Simple mental model — one strategy, one set of signals, traceable audit trail
- ✅ No cross-strategy correlation amplification risk during validation phase
- ✅ Clean promotion path: one strategy → paper → live, independently verified
- ❌ No diversification benefit during paper phase — acceptable: diversity is a live-trading concern
- ❌ Running 7 strategies requires 7 separate paper sessions — acceptable until ensemble infrastructure is built

**Alternatives Considered:** Ensemble voting (average signal strengths, majority vote) — deferred; multi-strategy position book — deferred. Both require correlation-based position limits (Step 51) to be implemented first.

---

### ADR-015: Integrate Spot Crypto (BTC/USD) into Existing Platform
**Status:** PROPOSED
**Date:** 2026-02-25

**Context:** User request to evaluate whether BTC should be a separate parallel trading bot or integrated into the existing platform. The existing architecture is built around UK equities (LSE symbols) with Alpaca as the paper broker and equity session guardrails (08:00–16:00 UTC). Crypto trades 24/7, is USD-denominated, and has different volatility characteristics. A reference implementation ([zach1502/LSTM-Algorithmic-Trading-Bot](https://github.com/zach1502/LSTM-Algorithmic-Trading-Bot)) was reviewed: it uses a Binance direct integration with 1-second BTC/USDT bars and a single LSTM strategy.

**Decision:** Integrate into the existing platform rather than a separate bot. Rationale:
1. Alpaca's free paper account already handles `BTC/USD` on the same `TradingClient` API — no second account or broker needed
2. yfinance supports `BTC-USD` as a ticker — the existing `DataFeed` works unchanged
3. All 8 strategies (MA, RSI, MACD, Bollinger, ADX, OBV, Stochastic, ATR) are asset-class agnostic — they operate on OHLCV regardless of asset type
4. `RiskManager.approve_signal()` already gates everything — crypto just needs different limit values
5. Two separate bots would mean duplicate audit trails, no cross-asset correlation control, and no unified P&L

**Consequences:**
- ✅ Single audit trail and unified P&L for equities + crypto
- ✅ Cross-asset correlation control via `CorrelationConfig` (BTC column added to correlation matrix)
- ✅ No additional broker integration work — Alpaca `TradingClient` handles both
- ❌ `PaperGuardrailsConfig` session window (08:00–16:00 UTC) must be bypassable per asset class — crypto is 24/7
- ❌ `enforce_market_hours = True` in `Settings` must support per-symbol override — see Step 54
- ❌ Alpaca uses `BTC/USD` format; yfinance uses `BTC-USD` — symbol normalization utility required (Step 55)
- ❌ Crypto requires different risk calibration: higher stop-loss %, tighter max position %, different slippage preset (Step 56)
- ❌ BTC correlation with FTSE 100 equities is low in normal regimes but spikes during risk-off events — correlation matrix must include BTC (Step 56)
- ❌ Crypto integration is gated behind MO-2 (3 in-window equity paper sessions); do not add BTC to live symbols list until equity live gate is passed

**Reference:** zach1502 repo — useful for LSTM feature engineering patterns (Step 57) and `skorch` PyTorch wrapper; not used for broker integration (we use Alpaca, not Binance).

**Implements:** Steps 54–57

---

## §4 Active RFCs (Change Proposals)

> RFCs are proposals that have not yet been fully implemented. They become ADRs once accepted and completed.
> Status values: `PROPOSED` | `ACCEPTED` | `IN PROGRESS` | `CLOSED` | `REJECTED` | `DEFERRED`

---

### RFC-001: Extract Trading Loop from `main.py`
**Status:** CLOSED
**Date:** 2026-02-24
**Target Backlog Steps:** 37–44
**Author:** Structural review (Feb 24, 2026)

**Problem:** `main.py` was 1,938 lines. Steps 37–43 created the extraction layer (loop.py, stream_events.py, resilience.py, arguments.py); Step 44 completed final slimming and test decoupling.

**Proposed Change:**
- ✅ Create `src/trading/loop.py` with `TradingLoopHandler` — DONE
- ✅ Create `src/trading/stream_events.py` — DONE
- ✅ Move `_run_broker_operation` to `src/execution/resilience.py` — DONE
- ✅ Move `ArgumentParser` to `src/cli/arguments.py` — DONE
- ✅ Delete remaining inlined logic from `main.py` so it contains only wiring (≤150 lines) — DONE (Step 44)
- ✅ Update tests to import from `src/` modules rather than `main.py` — DONE (Step 44)

**Acceptance Criteria:**
- `main.py` ≤ 150 lines
- Each `TradingLoopHandler` method independently unit-testable
- All 436+ tests pass; tests import from `src/` not `main.py`
- No regressions in paper trading behaviour

**Verified Metrics (Feb 25, 2026):**
- `main.py` line count: **55** (target ≤150 — ✅ met)
- Test files importing `main.py`: **0** (target 0 — ✅ met)
- Full regression suite: **436 passed**

**Completion Note (Feb 25, 2026):** Step 44 completed; `main.py` is entrypoint-only and test coupling to `main.py` is removed.

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

### RFC-004: MO-2 Completion — In-Window Paper Session Sign-Off
**Status:** PROPOSED
**Date:** 2026-02-25
**Target:** MO-2 (Operational Milestone)

**Problem:** MO-2 requires 3 consecutive in-window paper sessions (08:00–16:00 UTC, LSE market hours) with real fills. Step 1A burn-in is running but has only achieved `non_qualifying_test_mode=true`, `signoff_ready=false` — likely because sessions run outside market hours and therefore produce no live fills.

**Proposed Change:**
- Run 3 consecutive in-window paper sessions during LSE market hours (Mon–Fri, 08:00–16:00 UTC)
- Each session must produce at least 1 filled order
- Capture `step1a_burnin_latest.json` artefacts with `signoff_ready=true` for each run
- Link artefact paths in the Evidence Log under MO-2

**Acceptance Criteria:**
- `runs_passed ≥ 3` in burn-in tracker
- `signoff_ready=true` for each of the 3 runs
- `non_qualifying_test_mode=false` for all 3 runs
- Artefacts committed to `reports/burnin/` with ISO timestamps

**Operator note:** This requires the bot operator to schedule runs during LSE market hours. It cannot be automated end-to-end by an LLM. See `UK_OPERATIONS.md` for the operational runbook.

---

## §5 Technical Debt Register

> Known issues that are accepted as debt with a plan to address them.
> Each entry links to the backlog step that resolves it.

| ID | Description | Severity | Backlog Step | Notes |
|---|---|---|---|---|
| **TD-001** | `main.py` oversized — 1,077 lines (target ≤150) | HIGH (RESOLVED) | Step 44 | Resolved Feb 25, 2026 — `main.py` reduced to 55 lines |
| **TD-002** | 15 test files importing from `main.py` | HIGH (RESOLVED) | Step 44 | Resolved Feb 25, 2026 — tests import from `src/` modules; count now 0 |
| **TD-003** | `IBKRBroker` does not inherit `BrokerBase` | LOW (RESOLVED) | Step 40 | Resolved Feb 24, 2026 |
| **TD-004** | `Signal.strength` not validated at construction | LOW (RESOLVED) | Step 41 | Resolved Feb 24, 2026 |
| **TD-005** | Missing `research/__init__.py` | LOW (RESOLVED) | Step 39 | Resolved Feb 24, 2026 |
| **TD-006** | No persistent market data cache | LOW (RESOLVED) | Step 34 | Resolved Feb 24, 2026 — SQLite + Parquet hybrid cache implemented |
| **TD-007** | Reporting modules function-bag pattern | LOW (RESOLVED) | Step 42 | Resolved Feb 24, 2026 — `ReportingEngine` shared class implemented |
| **TD-008** | `approve_signal()` is 240 lines with no decomposition | LOW | Future | Each risk gate is a nested block; testable only as a whole; not blocking current phase |
| **TD-009** | `ibkr_python_ws` not yet evaluated as `ib_insync` replacement | LOW | ADR-011 | Deferred until `ib_insync` shows incompatibility with a TWS API version |
| **TD-010** | Step 1A burn-in not yet signed off | HIGH | MO-2 / RFC-004 | Latest artefact: `signoff_ready=false`, `non_qualifying_test_mode=true` — runs are outside market hours |
| **TD-011** | No correlation-based position limits | MEDIUM (RESOLVED) | Step 51 | Resolved Feb 24, 2026 — correlation matrix gate added to `RiskManager` with `CORRELATION_LIMIT` audit events |
| **TD-012** | No ATR volatility-scaled stops | LOW (RESOLVED) | Step 50 | Resolved Feb 24, 2026 — `ATRStopsStrategy` added with ATR-derived stop metadata |
| **TD-013** | Slippage model is fixed basis points only | LOW (RESOLVED) | Step 52 | Resolved Feb 24, 2026 — scenario-based spread/impact slippage and IBKR UK commission model added |
| **TD-014** | No test coverage threshold enforced | LOW (RESOLVED) | Step 53 | Resolved Feb 24, 2026 — `pytest-cov` added with CI gate (`--cov=src --cov-fail-under=90`) and coverage reporting baseline established |

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
- Latest LPDD verification pass:
    - Re-ran debt metrics after design sync commits; `main.py` remains `956` lines and `tests/*` imports from `main.py` remain `15` (RFC-001/TD-001/TD-002 unchanged)
- Queue-state sweep (all applicable open items):
    - RFC-001 / TD-001 / TD-002 remain open with unchanged metrics (`main.py` = `956` lines; `tests/*` importing `main.py` = `15`)
    - MO-2 remains open; latest Step 1A artifact is non-qualifying (`non_qualifying_test_mode=true`, `signoff_ready=false`)

**[2026-02-25] Session (Claude Sonnet 4.6)**
- LPDD archive pass: 6 redundant docs moved to `archive/` (PROJECT_ROADMAP, STEP1_DIAGNOSIS, SESSION_SUMMARY_STALEDATA_INVESTIGATION, PROJECT_REVIEW_COMPLETE, TASK_MATRIX_DAILY, EXECUTION_FLOW_REVIEW)
- `.github/copilot-instructions.md` created — Copilot workspace instructions referencing LPDD system
- `docs/ARCHITECTURE_DECISIONS.md` demoted to detail reference; LPDD (§3) is now canonical ADR source
- `EXECUTION_FLOW.md` annotated with architecture snapshot note pointing to §2
- `DOCUMENTATION_INDEX.md` updated: Copilot instructions as Doc 27, PROJECT_ROADMAP archived, How-to-Use guides updated to lead with LPDD
- LPDD verified metrics: `main.py` = **1,077 lines**; test imports from `main.py` = **15** (RFC-001 not closed)
- ADR-013 added (trading loop extraction — partial; RFC-001 still open)
- RFC-004 added (MO-2 completion — PROPOSED)
- TD-006 and TD-007 marked RESOLVED; TD-010 added (Step 1A burn-in not signed off)
- Steps 44–49 added to IMPLEMENTATION_BACKLOG (new items: main.py final slimming, walk-forward harness, daemon, daily report, indicators, REST API)
- §9 Operational Milestones added to this document

**[2026-02-25] LPDD Review (Claude Sonnet 4.6)**
- Verified post-Copilot state: 445 tests passing; `main.py` = 62 lines; 0 test imports from `main.py`
- §2 Architecture Snapshot updated to Feb 25, 2026 with verified metrics
- ADR-010 superseded by ADR-013 (execution complete)
- ADR-014 added: Single-strategy-per-run composition (ensemble deferred to Tier 3)
- TD-011 added: No correlation-based position limits (Step 51)
- TD-012 added: No ATR volatility-scaled stops (Step 50)
- TD-013 added: Slippage model is fixed basis points only (Step 52)
- TD-014 added: No test coverage threshold enforced (Step 53)
- Steps 50–53 added to IMPLEMENTATION_BACKLOG (ATR stops, correlation limits, slippage model, coverage gate)

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Step 44 completed end-to-end:
    - extracted runtime handlers to `src/cli/runtime.py`
    - slimmed `main.py` to entrypoint-only wiring (55 lines)
    - decoupled tests from `main.py` imports (15 → 0)
    - updated monkeypatch targets to runtime/resilience modules
- Validation:
    - `python -m pytest tests/ -v` → **436 passed**
- Governance updates:
    - RFC-001 CLOSED
    - TD-001 and TD-002 marked RESOLVED
    - ADR-013 updated to fully accepted completion state
- Step 48 completed:
    - added `OBVMomentumStrategy` and `StochasticOscillatorStrategy`
    - added `OBVConfig` / `StochasticConfig` and runtime registration
    - strategy tests expanded
    - validation: `python -m pytest tests/ -v` → **442 passed**
- Step 47 completed:
    - added `DailyReportGenerator` in `src/audit/daily_report.py`
    - added `daily_report` CLI mode (`src/cli/arguments.py` + `src/cli/runtime.py`)
    - added `tests/test_daily_report.py`
    - validation: `python -m pytest tests/ -v` → **445 passed**

**[2026-02-24] Session (GitHub Copilot / GPT-5.3-Codex)**
- Step 51 completed:
    - added `CorrelationConfig` and static UK matrix config (`config/uk_correlations.json`)
    - implemented `_check_correlation_limit()` in `RiskManager` (reject/scale modes)
    - added runtime audit event emission for `CORRELATION_LIMIT` rejections
    - added `tests/test_risk_correlation.py`
    - validation: `python -m pytest tests/ -v` → **448 passed**
- Step 50 completed:
    - added `ATRConfig` and `ATRStopsStrategy`
    - registered `atr_stops` in runtime strategy map
    - added strategy tests for ATR signal and metadata behavior
    - validation: `python -m pytest tests/ -v` → **451 passed**
- Step 52 completed:
    - added `SlippageConfig` and `SlippageModel` with scenario presets (`optimistic`, `realistic`, `pessimistic`)
    - updated backtest fill logic for volume-weighted spread, market-impact add-on, and IBKR UK commission floor
    - added `tests/test_slippage.py` regression coverage
    - validation: `python -m pytest tests/ -v` → **453 passed**
- Step 45 completed:
    - added `WalkForwardConfig` and new `WalkForwardHarness` for configurable split windows and in-sample parameter search
    - added aggregate walk-forward metrics including return, Sharpe, max drawdown, and overfitting ratio
    - added JSON persistence to `backtest/walk_forward_results.json`
    - expanded walk-forward tests with mock strategy coverage and compatibility checks
    - validation: `python -m pytest tests/ -v` → **454 passed**
- Step 53 completed:
    - added `pytest-cov` dependency and coverage threshold config (`fail_under = 90`)
    - added CI workflow gate running `python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90`
    - added targeted critical-path tests for `src/trading/loop.py` in `tests/test_trading_loop_handler.py`
    - current measured source coverage: **76.73%** (gate active and expected to fail until additional coverage work lands)
    - regression validation: `python -m pytest tests/ -v` → **458 passed**
- Step 33 completed:
    - added `research/data/news_features.py` for Polygon news fetch + daily sentiment aggregation
    - implemented features: `sentiment_score`, `article_count`, `benzinga_count`, `earnings_proximity`
    - added §3g News/Sentiment Features in `research/specs/FEATURE_LABEL_SPEC.md`
    - added mocked-news test suite `tests/test_news_features.py`
    - validation: `python -m pytest tests/test_news_features.py -v` → **8 passed**
    - regression validation: `python -m pytest tests/ -v` → **466 passed**

**[2026-02-25] Crypto Design Session (Claude Sonnet 4.6)**
- Reviewed [zach1502/LSTM-Algorithmic-Trading-Bot](https://github.com/zach1502/LSTM-Algorithmic-Trading-Bot): Binance/BTC LSTM bot with 21-indicator feature set, `skorch` PyTorch wrapper, confidence-scaled signal generation
- Decision: integrate BTC/USD as a secondary asset class into the existing platform (not a separate bot) — see ADR-015
- §1 Non-Goals updated: "crypto" removed from absolute non-goals; BTC spot integration gated behind MO-2
- Key metrics updated: strategies = 8 (ATR Stops added by Copilot in Step 50); tests = 466
- ADR-015 added: integrated crypto support; Steps 54–57 defined (asset-class metadata, symbol normalization, crypto risk overlay, BTC LSTM features)
- Step 33 confirmed completed (Copilot); IMPLEMENTATION_BACKLOG executive summary to be updated in next pass
- `docs/MASSIVE_API_REFERENCE.md`, `IMPLEMENTATION_BACKLOG.md`, `docs/DATA_PROVIDERS_REFERENCE.md` updated in prior commit (`d6971bf`) to reflect free `/v2/reference/news` endpoint for Step 33

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
| `.github/copilot-instructions.md` | GitHub Copilot workspace instructions (LPDD-aware) | Auto-read by Copilot |
| `docs/ARCHITECTURE_DECISIONS.md` | Full AQ1–AQ9 decisions with rationale — detail reference | When you need full rationale behind ADR-001–009 |
| `docs/DATA_PROVIDERS_REFERENCE.md` | All 10 data providers, prompts, free tier limits | When working on data or research steps |
| `docs/MASSIVE_API_REFERENCE.md` | Massive/Polygon REST, WebSocket, Flat Files reference | Steps 29–31 |
| `DOCUMENTATION_INDEX.md` | Index of all 28 docs | When looking for a specific reference |
| `research/README.md` | Research track pipeline, CLI, troubleshooting | Research steps |
| `research/specs/ML_BASELINE_SPEC.md` | XGBoost/LSTM governance spec | Steps 25, 32 |

---

## §9 Operational Milestones Tracker

> Milestones that require human/operator action and cannot be automated by an LLM.
> These are distinct from backlog steps (which are code/documentation changes).
> Update status and evidence links here when milestones are achieved.

| ID | Milestone | Status | Evidence Required |
|---|---|---|---|
| **MO-1** | Step 1 signed off — architecture proven end-to-end via daily backtest | ✅ CLOSED (Feb 24, 2026) | 93 signals, 26 trades, Sharpe 1.23, Return 1.10%, Max DD 0.90% |
| **MO-2** | 3 consecutive in-window paper sessions with fills | ⏳ OPEN | `reports/burnin/` artefacts with `signoff_ready=true` × 3 |
| **MO-3** | Vendor credentials for historical tick backfills (e.g. Massive API key) | ⏳ OPEN | `.env` populated; test fetch successful |
| **MO-4** | Live/backfill commands executed for target symbols; manifests retained | ⏳ OPEN | Backfill manifests in `research/data/` with date/symbol evidence |
| **MO-5** | Final human review of promotion-gate evidence checklists before Gate A | ⏳ OPEN | Signed promotion checklist JSON with reviewer name + date |
| **MO-6** | Human approval of risk/governance closeout filings | ⏳ OPEN | Dated sign-off in `reports/promotions/` |
| **MO-7** | Complete R1/R2 residuals + R3 runtime evidence in `RESEARCH_PROMOTION_POLICY.md` | ⏳ OPEN | Dated artefact links in research spec |
| **MO-8** | Production-run sign-off referenced by `FEATURE_LABEL_SPEC.md` (experiment outputs + reviewer trace) | ⏳ OPEN | Real experiment outputs committed with reviewer/date |

**Critical path:** MO-2 blocks promotion to live trading. MO-3/MO-4 gate full research pipeline. MO-5/MO-6 are the final human sign-off layer before Gate B (live). MO-7/MO-8 are research-specific governance requirements.

**Current blocker (Feb 25, 2026):** MO-2 Step 1A burn-in artefacts show `non_qualifying_test_mode=true` — sessions are running outside LSE market hours. Operator must schedule 3 runs during 08:00–16:00 UTC, Mon–Fri. See RFC-004 and `UK_OPERATIONS.md`.
