# PROJECT_DESIGN.md — LLM Project Design Document (LPDD)

**Version:** 1.5
**Last Updated:** Feb 26, 2026
**Status:** ACTIVE — primary architectural authority for this repository

> This is the canonical design document for the trading bot project.
> It is written for LLM-first consumption and maintained as a living record.
> Humans and LLMs alike should read this before making structural decisions.
>
> **Reading order for a new LLM session:**
> 1. `SESSION_LOG.md` (last 2–3 entries) — what happened recently; handoff notes
> 2. `SESSION_TOPOLOGY.md` §5 — identify your session type
> 3. This file (`PROJECT_DESIGN.md`) — decisions, constraints, debt, history
> 4. `CLAUDE.md` — session context, invariants, quick-reference conventions
> 5. `IMPLEMENTATION_BACKLOG.md` — what to build next and in what order
> 6. `.python-style-guide.md` — how to write the code

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

### Key Metrics (Feb 25, 2026 — post Steps 33/44/45/46/47/48/49/50–56/58/59/60/61/63)
- Test suite: **551 tests passing**
- `main.py` line count: **62 lines** (entrypoint-only; target ≤150 ✅)
- Test files importing `main.py`: **0** (target 0 ✅)
- Strategies registered: **8** (MA, RSI, MACD, Bollinger, ADX, OBV, Stochastic, ATR Stops)
- Asset classes: **2** (EQUITY via IBKR/Alpaca paper; CRYPTO via Coinbase sandbox primary + Binance testnet fallback — BTCGBP)
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

### ADR-015: Integrate Spot Crypto (BTCGBP) — Coinbase Primary / Binance Fallback
**Status:** ACCEPTED
**Date:** 2026-02-25
**Updated:** 2026-02-25 (v3: Coinbase as primary; Binance retained as fallback)

**Context:** UK-based operator working in GBP. Integration of BTC spot trading into the existing platform. Initial decision was Binance (Steps 54–58, all completed). Operator revised to **Coinbase as primary crypto broker** with Binance retained as fallback. Rationale: Coinbase UK Limited is FCA-registered as a crypto asset firm; Binance's UK regulated entity was required to cease regulated activities by the FCA (2021). Coinbase Advanced Trade API uses `BTC-GBP` product IDs (dash format), which is identical to yfinance's ticker format — no extra normalisation for data feeds.

**Decision:** Integrate into the existing platform using **Coinbase as primary crypto broker** and **BTCGBP/BTC-GBP** as the primary pair. Binance is retained as a fallback broker (already implemented). Rationale:
1. `CoinbaseBroker` uses `BTC-GBP` symbol format — matches yfinance natively, no normalisation overhead
2. Coinbase UK Limited FCA-registered — more appropriate for a UK/GBP operator
3. `BinanceBroker` already implemented (Step 58) — zero wasted work; becomes the fallback
4. All strategy modules are asset-class agnostic — OHLCV is OHLCV regardless of broker
5. `RiskManager.approve_signal()` gates everything — broker switch is transparent to risk layer
6. Coinbase Advanced Trade API sandbox available for paper crypto testing

**Broker architecture (post-ADR-015):**
| Mode | Equities | Crypto (primary) | Crypto (fallback) |
|---|---|---|---|
| Paper / simulation | `AlpacaBroker` (paper=True) | `CoinbaseBroker` (sandbox=True) | `BinanceBroker` (testnet=True) |
| Live | `IBKRBroker` | `CoinbaseBroker` (sandbox=False) — gated MO-2 | `BinanceBroker` (testnet=False) |

**Fallback routing:** `BrokerConfig.crypto_primary_provider = "coinbase"`, `BrokerConfig.crypto_fallback_provider = "binance"`. The broker factory attempts primary; on `BrokerConnectionError` it logs a warning and routes to the fallback.

**Consequences (completed):**
- ✅ `AssetClass` enum + `is_crypto()` + session-window bypass (Step 54)
- ✅ Symbol normalisation (`src/data/symbol_utils.py`) for BTCGBP/BTC-GBP across providers (Step 55)
- ✅ `BinanceBroker(BrokerBase)` with testnet support (Step 58) — now the fallback
- ✅ Crypto risk overlay: position cap, ATR stops, BTCGBP in correlation matrix (Step 56)

**Consequences (pending):**
- ❌ Crypto live gated behind MO-2 — `coinbase_sandbox` and `binance_testnet` must remain True until equity live gate passes

**Reference:** zach1502 repo — LSTM feature patterns (Step 57), `skorch` PyTorch wrapper.

**Implements:** Steps 54–58 ✅, Step 63 ✅

---

### ADR-016: Session Topology for LLM-Managed Sessions
**Status:** ACCEPTED
**Date:** 2026-02-25
**Author:** Architecture review (Feb 25, 2026)

**Context:** GitHub Copilot and Claude Opus sessions are stateless by default. Each new session re-reads the entire project from scratch, risking wasted context, repeated investigations, and contradicted decisions. The LPDD system provides structural documentation but no protocol for how sessions hand off state to each other.

**Decision:** Introduce a two-file session management layer:
1. `SESSION_TOPOLOGY.md` — defines 6 session types (IMPL, ARCH, RSRCH, OPS, DEBUG, REVIEW) with pre-read checklists, scope guards, context loading priorities, and an agent routing decision tree
2. `SESSION_LOG.md` — append-only journal of session work with structured entries (goal, outcome, queue changes, files modified, test baseline, handoff notes)

VS Code integration via `.vscode/session.code-snippets` (4 snippets: `slog`, `slog-short`, `slog-queue`, `stype`).

The reading order in `.github/copilot-instructions.md` is updated to start with `SESSION_LOG.md` and `SESSION_TOPOLOGY.md` before the existing LPDD docs.

**Rationale:**
1. Session continuity — structured handoff notes prevent context loss between sessions
2. Type-appropriate context loading — DEBUG sessions don’t need to read research specs; IMPL sessions don’t need full ADR history
3. Scope guards — prevent session type drift (e.g., a DEBUG session accidentally making architectural decisions)
4. Auditability — the session log provides a chronological record of all LLM interactions with the project

**Consequences:**
- Every session must append to `SESSION_LOG.md` before ending
- `SESSION_LOG.md` rotates at 50 entries (archive older entries)
- Reading order in copilot-instructions expanded from 4 to 6 items
- No code changes — this is purely a process/documentation decision

---

### ADR-017: Multi-Agent Handoff Protocol + Custom Agent Roles
**Status:** ACCEPTED
**Date:** 2026-02-25
**Author:** Architecture review (Feb 25, 2026)
**Ref:** SESSION_TOPOLOGY.md §6b–§6d

**Context:** The project uses multiple LLM agent types (Copilot Local, Claude Opus, Background agents) and operator sessions. ADR-016 established session types and routing but did not define how agents formally hand off to each other. VS Code now supports multi-agent session management (agent type selection, session list, parallel sessions) and custom agents via `.agent.md` files.

**Decision:**
1. **Handoff protocol** (SESSION_TOPOLOGY.md §6b): explicit handoff matrix defining when each session type hands off, what must be included, and what the receiving agent must produce.
2. **Handoff packet template** (§6c): mandatory structured template for inter-agent handoffs (goal, done, remains, blockers, files, commands, evidence, test baseline).
3. **Pre-handoff gate** (§6d): ARCH and REVIEW sessions must run `lpdd_consistency_check.py` before handing off.
4. **Custom agent roles** (`.github/agents/*.agent.md`): three role-specific agents with scope guards:
   - `lpdd-auditor.agent.md` — governance drift detection (REVIEW type, docs-only edits)
   - `ops-runner.agent.md` — MO-* milestone execution (OPS type, scripts + evidence only)
   - `research-reviewer.agent.md` — ML experiment and paper review (RSRCH type, research/ only)
5. **VS Code workspace settings** (`.vscode/settings.json`): enable `chat.viewSessions.enabled`, `chat.agentsControl.enabled`, `chat.agent.enabled` for session audit trail and agent selection.

**Rationale:**
1. Formalized handoff prevents context loss when switching between agent types
2. Role-specific agents enforce scope guards automatically via `.agent.md` instructions
3. Pre-handoff gate catches governance drift before it propagates across session boundaries
4. VS Code settings ensure multi-agent features are active for all developers

**Consequences:**
- All cross-type handoffs must include a handoff packet in SESSION_LOG.md
- ARCH/REVIEW sessions gain an additional end-of-session gate (consistency check)
- Three new `.agent.md` files to maintain alongside the main copilot-instructions
- VS Code settings.json is now a tracked file in the repository

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

**Problem:** MO-2 requires 3 consecutive in-window paper sessions (08:00–16:00 UTC, LSE market hours) with real fills. Step 1A burn-in remains `signoff_ready=false`; current blockers are a mix of in-window execution constraints and symbol-data availability instability on 1-minute UK bars.

**Proposed Change:**
- Run 3 consecutive in-window paper sessions during LSE market hours (Mon–Fri, 08:00–16:00 UTC)
- Keep symbol-data preflight gate enabled so low-availability runs fail fast before consuming full session time
- Each session must produce at least 1 filled order
- Capture `step1a_burnin_latest.json` artefacts with `signoff_ready=true` for each run
- Link artefact paths in the Evidence Log under MO-2

**Acceptance Criteria:**
- `runs_passed ≥ 3` in burn-in tracker
- `signoff_ready=true` for each of the 3 runs
- `non_qualifying_test_mode=false` for all 3 runs
- Artefacts committed to `reports/uk_tax/step1a_burnin/` with ISO timestamps

**Operator note:** This requires the bot operator to schedule runs during LSE market hours. It cannot be automated end-to-end by an LLM. Use `./scripts/run_mo2_end_to_end.ps1` with symbol preflight enabled (default) and inspect per-run `00_symbol_data_preflight.json`. For active-run decisioning, use `docs/MO2_LIVE_PROGRESS_PROMPT.md`. See `UK_OPERATIONS.md` for the operational runbook.

---

### RFC-005: YFinance Request-Type Retry Policy + Local Store Sizing Decision
**Status:** PROPOSED
**Date:** 2026-02-25
**Target Backlog Step:** 73

**Problem:** Intermittent yfinance false negatives can appear as empty/noisy responses for otherwise healthy symbols, especially on intraday windows. Current behavior has stream-cycle backoff but no explicit per-request retry policy by call type. Separately, local cache exists but no explicit sizing decision has been documented for sustained yfinance-first intraday retention.

**Proposed Change:**
- Add yfinance-only retry controls in config, scoped by request type:
    - `period` calls (rolling windows)
    - `start/end` calls (anchored windows)
- Keep retry bounded with explicit max attempts and exponential backoff per call type
- Add attempt/exhaustion observability in provider logs (symbol, interval, request type, attempt)
- Produce a documented local-store sizing estimate and operational recommendation for UK universe retention

**Acceptance Criteria:**
- Retry controls are configurable and apply only to `YFinanceProvider`
- Distinct retry behavior is enforced for `period` and `start/end` request paths
- Tests cover success-after-retry and exhausted-retry behavior for both call types
- A feasibility memo exists with assumptions, storage growth estimates, and go/no-go recommendation

---

### RFC-006: Step1A Auto Client-ID Collision Recovery Wrapper
**Status:** ACCEPTED
**Date:** 2026-02-25
**Target Backlog Step:** 74

**Problem:** Step 1A/MO-2 runs can fail intermittently when the selected IBKR API client ID is already in use (`error 326`). Manual operator retries with ad-hoc `IBKR_CLIENT_ID` changes are error-prone and reduce reproducibility.

**Proposed Change:**
- Add a dedicated Step1A wrapper that:
    - sets candidate `IBKR_CLIENT_ID` values deterministically
    - invokes the existing burn-in script unchanged
    - retries only when collision evidence is detected in burn-in report output
    - preserves non-collision failure semantics (no masking)

**Acceptance Criteria:**
- Wrapper forwards all Step1A burn-in parameters
- Collision retries are bounded by max attempts and stop immediately on non-collision errors
- Operator runbook points to wrapper as default command path for in-window runs

**Completion Note (Feb 25, 2026):** Implemented as `scripts/run_step1a_burnin_auto_client.ps1`; backlog checklist updated to use wrapper command.

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
| **TD-015** | ATR warm-up period not enforced in `min_bars_required()` | LOW | Step 50 / future | `ATRStopsStrategy.min_bars_required()` returns `atr_period` but ATR is sensitive to series start date — long lookback bars (2,000+) affect recent ATR values. `min_bars_required()` should enforce a minimum of 3× `atr_period` as burn-in. Noted by Robot Wealth / Longmore 2017 commenter. |
| **TD-016** | LPDD queue/doc hygiene drift (stale snapshots + encoding noise) | LOW (RESOLVED) | Step 71 | Resolved Feb 25, 2026 — normalized authoritative queue block, aligned reading-order references, added LPDD sync checklist, and introduced `scripts/lpdd_consistency_check.py` with test coverage. |
| **TD-017** | UK intraday symbol availability instability can block MO-2 fills | MEDIUM (RESOLVED) | Step 72 | Resolved Feb 25, 2026 — added symbol-universe health evaluation, strict paper-trial block by availability threshold, and optional deterministic remediation with audit visibility. |
| **TD-018** | No request-type-specific yfinance retry policy; local cache sizing decision undocumented | MEDIUM | Step 73 / RFC-005 | Intermittent provider false negatives may cause avoidable run instability; design/implementation tracked under Step 73 with explicit feasibility note requirement. |
| **TD-019** | Step1A runs rely on manual IBKR client-id selection, causing avoidable collision failures | MEDIUM (RESOLVED) | Step 74 / RFC-006 | Resolved Feb 25, 2026 — added auto client-id wrapper with bounded retry on collision evidence and non-collision fail-fast behavior. |
| **TD-020** | Git/repository hygiene risk: tracked `.env`, tracked runtime DB artifacts, mixed stash content, and CI/pre-commit policy drift | HIGH | Step 76 / ops secret rotation | Step 76 completed (Feb 26, 2026): `.env` and runtime DB artifacts untracked, CI policy checks added, and stash/commit hygiene runbook added. **Remaining blocker:** operator credential rotation and post-rotation verification. |

---

## §6 Evolution Log

### [2026-02-25] Step 70 — External Literature Deep-Review Synthesis Pack
- Full synthesis pack created in `research/tickets/external_literature_deep_review_2026-02.md`.
- All required sources scored and verdicts mapped using Step 64 rubric.
- No "adopt now" candidates; four "research first" sources identified for future research framing only.
- Actionable recommendations: broker adapter conformance checks, integration maturity labels, release-provenance checklist, RL research caveats (all mapped to Copilot/ops subtasks or research notes).
- All recommendations and rejections explicitly mapped to LPDD hard invariants; no roadmap or architecture changes made.
- Validation: all required review inputs covered, meta-analyses included, YAML stubs generated for scored sources, and summary matrix included in synthesis pack.
- No new tickets created; all recommendations are subtask-level or research-note only.

> Append-only. Record major decisions, completions, and pivots in chronological order.
> Format: `[Date] [Author] — [What changed and why]`

---

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Completed Step 73: yfinance request-type retry controls + local-store feasibility closeout:
    - finalized settings-scoped yfinance retry policy (`period` vs `start/end`) and runtime provider wiring
    - expanded retry coverage tests to include both request-type success-after-retry and retry-exhausted paths
    - validated targeted provider/feed tests and full suite
    - updated backlog queue state: Step 73 moved IN PROGRESS → COMPLETED

**[2026-02-25] Session (Copilot / Claude Opus 4.6)**
- Implemented multi-agent handoff protocol and custom agent roles (ADR-017):
    - added SESSION_TOPOLOGY.md §6b (handoff matrix with 9 cross-type scenarios), §6c (handoff packet template), §6d (pre-handoff consistency gate)
    - created 3 custom agent definitions: `.github/agents/lpdd-auditor.agent.md`, `ops-runner.agent.md`, `research-reviewer.agent.md`
    - created `.vscode/settings.json` with `chat.viewSessions.enabled`, `chat.agentsControl.enabled`, `chat.agent.enabled`
    - updated PROJECT_DESIGN.md §10 agent assignment matrix with custom agent roles table
    - added ADR-017, Step 75 ticket, updated governance doc references

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Completed Step 74: added Step1A auto client-id collision recovery wrapper:
    - new `scripts/run_step1a_burnin_auto_client.ps1` retries with incremented `IBKR_CLIENT_ID` values when collision evidence is detected
    - preserves non-collision failures (no hidden retries) and restores original env state after run
    - updated `IMPLEMENTATION_BACKLOG.md` in-window checklist to use wrapper command
    - wired `scripts/run_step1a_market.ps1` to use the wrapper so window-guarded and MO-2 orchestrated runs inherit collision recovery

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Added RFC-006 and resolved TD-019 to formalize Step1A client-id collision mitigation in LPDD.

**[2026-02-26] Session (GitHub Copilot / GPT-5.3-Codex)**
- Integrated Git/repository-governance audit findings into LPDD process:
    - added TD-020 to track Git hygiene production-readiness gap (tracked `.env`, tracked runtime DB artifacts, mixed stash risk, CI/pre-commit alignment drift)
    - added Step 76 in `IMPLEMENTATION_BACKLOG.md` for non-destructive hygiene hardening and commit-boundary enforcement
    - extended `SESSION_TOPOLOGY.md` REVIEW scope to include Git hygiene audits with mandatory repo-policy pre-reads
    - clarified agent ownership in §10 for Git hygiene auditing, implementation, and secret rotation decisions

**[2026-02-26] Session (GitHub Copilot / GPT-5.3-Codex)**
- Completed Step 76: Git/Repo hygiene hardening + secret/artifact de-risk (non-destructive):
    - updated `.gitignore` with targeted env/runtime/cache/coverage ignore rules while retaining `.env.example`
    - untracked `.env` and local runtime DB artifacts via `git rm --cached` (local files preserved)
    - added CI policy-check stage (black/isort/flake8 + LPDD consistency checker) before test-and-coverage job
    - added operator runbook section for stash-safe restore categories and strict commit boundaries
    - carried forward operator-only secret rotation checklist as the remaining TD-020 closure requirement

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Added IBKR TWS API hardening mapping into the operational Step 1A runbook (`IMPLEMENTATION_BACKLOG.md`):
    - explicit pre-checks for TWS API settings and unique `IBKR_CLIENT_ID`
    - clear distinction between informational startup farm messages (2104/2106/2158) and blocking errors (326/502/socket breaks)
    - logging/triage guidance for failed in-window runs to improve MO-2 reliability and reproducibility

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Progressed open reliability item Step 73 (IN PROGRESS):
    - implemented yfinance request-type retry controls (`period` vs `start/end`) via settings-driven policy
    - wired market-feed provider construction to pass runtime retry config
    - added retry-focused tests (`tests/test_data_providers.py`) and regression validation (`tests/test_data_feed.py`)
    - added local-store sizing feasibility memo (`docs/YFINANCE_LOCAL_STORE_FEASIBILITY.md`)

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Added new LPDD-tracked reliability ticket for yfinance call handling and storage planning:
    - RFC-005 (PROPOSED): request-type-specific yfinance retry policy + local store sizing decision
    - TD-018 added to debt register and linked to Step 73
- Backlog alignment: new Step 73 added in `IMPLEMENTATION_BACKLOG.md` and promoted to the actionable queue

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Added automatic symbol-data preflight gate for Step 1A / MO-2 paper runs:
    - `scripts/run_step1a_burnin.ps1` now checks per-symbol intraday data availability before each run
    - run blocks with `reason=symbol_data_preflight_failed` when availability ratio falls below threshold
    - threshold and preflight controls are configurable via wrapper/orchestrator parameters
- Wired parameter passthrough and reporting updates:
    - `scripts/run_step1a_market.ps1`, `scripts/run_step1a_market_if_window.ps1`, `scripts/run_mo2_end_to_end.ps1`, and root `run_step1a_market_if_window.ps1`
    - orchestration reports now include preflight gate configuration for traceability
- Added follow-up implementation ticket:
    - Step 72 — UK paper symbol-universe reliability hardening (auto-remediation policy + audit visibility)

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Reviewed external repositories/articles for practical fit against LPDD constraints (UK-first equities, paper-before-live, governance-first):
    - `asavinov/intelligent-trading-bot`, `Mun-Min/ML_Trading_Bot`, `shayleaschreurs/Machine-Learning-Trading-Bot`, `CodeDestroyer19/Neural-Network-MT5-Trading-Bot`, `pskrunner14/trading-bot`, `owocki/pytrader`, `cbailes/awesome-deep-trading`, and listed blog/article sources
- Outcome: retained selective process/workflow improvements; rejected runtime replacement ideas and unsupported high-return claims that conflict with evidence discipline
- Added new backlog tickets from this review:
    - Step 64 — External source triage + reproducibility scorecard
    - Step 65 — Research claim-integrity gate (anti-hype checks)
    - Step 66 — Pairs-trading benchmark baseline (UK universe)
    - Step 67 — RL trading feasibility spike (**Needs Claude Opus Review**)
    - Step 68 — Deep-sequence governance gate (**Needs Claude Opus Review**)
    - Step 69 — Further Research: UK sentiment data utility validation
- Follow-up backlog addition (deferred research request):
    - Step 70 — Further Research: external literature deep-review synthesis pack (full pass over `awesome-deep-trading` meta/systematic-review list + prior run sources)

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
- Decision: integrate BTC as a secondary asset class into the existing platform (not a separate bot) — see ADR-015
- **Revised to Binance** (not Alpaca) as the crypto broker: operator is UK/GBP-based; `BTCGBP` pair selected to avoid USD FX exposure; Binance testnet for paper crypto simulation
- §1 Non-Goals updated: "crypto" removed from absolute non-goals; BTC spot gated behind MO-2 equity live gate
- Key metrics updated: strategies = 8 (ATR Stops added by Copilot in Step 50); tests = 466
- ADR-015 added: integrated crypto support via Binance; Steps 54–58 defined (asset-class metadata, symbol normalisation, BinanceBroker, crypto risk overlay, BTC LSTM features)
- Step 33 confirmed completed (Copilot); IMPLEMENTATION_BACKLOG executive summary updated
- `docs/MASSIVE_API_REFERENCE.md`, `IMPLEMENTATION_BACKLOG.md`, `docs/DATA_PROVIDERS_REFERENCE.md` updated in prior commit (`d6971bf`) to reflect free `/v2/reference/news` endpoint for Step 33

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex)**
- Step 54 completed:
    - added `AssetClass` enum in `src/data/models.py`
    - added `symbol_asset_class_map` and `Settings.is_crypto(symbol)` in `config/settings.py`
    - added crypto session-window bypass in `PaperGuardrails` and market-hours bypass in `TradingLoopHandler`
    - added `tests/test_asset_class.py`
    - validation: focused guardrail + loop suite → **61 passed**
- Step 55 completed:
    - added `src/data/symbol_utils.py` with provider-specific normalization rules
    - wired yfinance normalization in `MarketDataFeed` and Alpaca normalization in `AlpacaBroker`
    - added `DataConfig.crypto_symbols`
    - added `tests/test_symbol_utils.py` + data-feed normalization regression
    - smoke validation: BTCGBP backtest ran successfully (signals/trades generated)
    - validation: symbol/feed suite → **20 passed**
- Step 56 completed:
    - added `CryptoRiskConfig` and wired crypto risk overlays in `RiskManager`
    - added crypto exposure cap gate (`CRYPTO_EXPOSURE_LIMIT`)
    - updated `config/uk_correlations.json` with `BTCGBP` row/column
    - added `crypto` slippage preset (50 bps spread, zero commission floor)
    - added `tests/test_crypto_risk.py` and slippage regression update
    - validation: crypto risk + slippage suite → **7 passed**
- Step 58 completed:
    - implemented `BinanceBroker(BrokerBase)` in `src/execution/broker.py`
    - added Binance auth/testnet fields to `BrokerConfig`
    - added `binance` + `python-binance` dependencies
    - routed crypto sessions to `BinanceBroker` in runtime broker factory
    - added mocked `tests/test_binance_broker.py`
    - validation: binance + broker regression suite → **32 passed**
- Full regression validation after Steps 54/55/56/58:
    - `python -m pytest tests/ -v` → **498 passed, 9 warnings**

**[2026-02-25] ML Methodology Review (Claude Sonnet 4.6)**
- Reviewed Robot Wealth / Longmore 2017 "Getting Started with Neural Networks for Algo Trading"
- 4 new backlog steps added (Steps 59–62):
    - Step 59: class imbalance handling (`scale_pos_weight`, PR-AUC gate — `PERCEPTRON+BALANCED` equivalent)
    - Step 60: data mining bias guard (multiple-testing pre-registration, Bonferroni-adjusted alpha)
    - Step 61: cost-aware threshold target labeling (profitable-after-costs label, 45 bps threshold)
    - Step 62: feedforward MLP baseline (pre-LSTM gate — MLP must beat XGBoost before LSTM attempted)
- TD-015 added: ATR warm-up period not enforced in `min_bars_required()` (Longmore commenter observation)
- §2 key metrics updated: 498 tests, asset classes = 2 (equity + crypto BTCGBP)
- Step 32 (LSTM) now gated behind Step 62 (MLP) — complexity must be justified stepwise
- IMPLEMENTATION_BACKLOG executive summary: 67→71 total, Not Started 9→13

**[2026-02-25] Coinbase + LPDD Autonomy Session (Claude Sonnet 4.6 → GitHub Copilot)**
- ADR-015 revised (v3): **Coinbase as primary crypto broker**, Binance retained as fallback
  - Rationale: Coinbase UK Limited is FCA-registered; Binance UK entity ceased regulated activities per FCA (2021)
  - `BTC-GBP` product ID matches yfinance ticker natively — zero normalisation overhead for data feeds
- Broker architecture updated: `CoinbaseBroker(sandbox=True)` primary, `BinanceBroker(testnet=True)` fallback; factory routes with `BrokerConnectionError` fallback
- Step 63 (CoinbaseBroker) added to IMPLEMENTATION_BACKLOG — HIGH priority, NOT STARTED
- **LPDD Copilot autonomous pickup system added:**
  - `## Copilot Task Queue` section added to IMPLEMENTATION_BACKLOG.md (3 sub-tables: Immediately Actionable / Needs Claude Opus / Operational)
  - `.github/copilot-instructions.md` fully rewritten with 8-step Task Pickup Protocol + escalation criteria
  - §10 Agent Assignment Matrix added to PROJECT_DESIGN.md (task → agent routing table + per-step assignments)
- **PDF research review** — two papers analysed for design insights:
  - *Peng et al. 2022* (AishaRL.pdf): PPO-based crypto trading bot with CNN-LSTM; key insight — bounded-range indicators (RSI, CMF) preferred for RL over time-dependent indicators (Bollinger Bands) to avoid temporal bias in experience replay; different indicator categories minimise correlated features; market-cycle-aware train/test splitting
  - *Azhikodan et al. 2019* (ICICSE.pdf): DDPG stock trading bot with RCNN sentiment analysis; key insight — binary reward functions outperformed continuous reward (avoidance of local minima); news sentiment as additional environment observation boosted RL agent performance; validates Step 33 (news features) + Step 61 (binary threshold labels)
- IMPLEMENTATION_BACKLOG executive summary: 71→72 total, Completed 61, Not Started 10, 498 tests
- PROJECT_DESIGN.md version bumped to 1.4

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Queue Closure Pass**
- Completed all Copilot-actionable queue steps: **46, 49, 59, 60, 61, 63**
- Step 63 completed:
    - implemented `CoinbaseBroker(BrokerBase)` with sandbox/live URL routing and GBP account parsing
    - added `BrokerConnectionError` + runtime crypto provider factory (`coinbase` primary, `binance` fallback)
    - added Coinbase config/env fields and symbol normalisation (`BTCGBP`/`BTC/GBP` → `BTC-GBP`)
    - added tests: `tests/test_coinbase_broker.py`, `tests/test_broker_factory.py`, symbol normalisation coverage
- Step 46 completed:
    - added portable paper daemon (`scripts/daemon.py`) with UK session window checks, crash retry backoff, and `logs/daemon.log`
    - added launcher `scripts/daemon_start.sh` and `tests/test_daemon.py`
- Step 49 completed:
    - added read-only FastAPI scaffold in `src/api/` with `/status`, `/positions`, `/signals`, `/orders`, `/metrics`
    - added `scripts/api_server.py` and integration test `tests/test_api.py`
- Steps 59/60/61 completed:
    - added `research/training/label_utils.py` (`compute_class_weights`, `compute_threshold_label`)
    - wired `scale_pos_weight` into XGBoost training path; added PR-AUC/ROC-AUC to experiment aggregates
    - added hypothesis pre-registration schema + Bonferroni metadata propagation to reports
    - added promotion caution flag for non-preregistered hypotheses
    - added/revised specs: `FEATURE_LABEL_SPEC.md`, `RESEARCH_PROMOTION_POLICY.md`, `RESEARCH_SPEC.md`
- Validation:
    - full regression: `python -m pytest tests/ -v` → **521 passed, 9 warnings**
- Queue state after pass:
    - Copilot actionable queue: **0**
    - Remaining not-started work is Opus-gated (`32`, `57`, `62`) plus operator milestones (MO-2+)

**[2026-02-25] Session Topology System (Claude Opus 4.6)**
- ADR-016 added: Session Topology for LLM-Managed Sessions
- Created `SESSION_TOPOLOGY.md` (v1.0) — 6 session types with pre-read checklists, scope guards, context loading priorities, routing decision tree, and continuity patterns
- Created `SESSION_LOG.md` — append-only session journal with 3 seed entries from recent work
- Created `.vscode/session.code-snippets` — 4 snippets (`slog`, `slog-short`, `slog-queue`, `stype`)
- Updated `.github/copilot-instructions.md` — reading order expanded from 4 to 6 items; session protocol section added
- Updated `DOCUMENTATION_INDEX.md` with new files
- Updated `PROJECT_DESIGN.md` §8 Key Document Map with `SESSION_TOPOLOGY.md` and `SESSION_LOG.md`

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 64 Complete**
- Completed Step 64 (External source triage + reproducibility scorecard)
    - added rubric: `docs/SOURCE_REVIEW_RUBRIC.md`
    - added template: `research/specs/SOURCE_REVIEW_TEMPLATE.md`
    - added utility: `scripts/source_review.py` (weighted score + verdict mapping)
    - added seed review artifact: `research/tickets/source_reviews/asavinov_intelligent_trading_bot.yaml`
    - added tests: `tests/test_source_review.py`
- Validation:
    - `python -m pytest tests/test_source_review.py -q` → **7 passed**
    - `python scripts/source_review.py research/tickets/source_reviews/asavinov_intelligent_trading_bot.yaml` → score **61.75**, verdict **Research first**
- Added follow-up LPDD hygiene backlog ticket:
    - Step 71 — queue consistency + encoding cleanup + LPDD consistency checker

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 71 Complete**
- Completed Step 71 (LPDD process hygiene + queue consistency pass)
    - normalized queue authority in `IMPLEMENTATION_BACKLOG.md` to the top `Copilot Task Queue` section
    - removed stale duplicate queue snapshot block in active top-of-file section and clarified legacy-queue policy
    - aligned session-topology-first reading-order references across `IMPLEMENTATION_BACKLOG.md`, `.github/copilot-instructions.md`, and `DOCUMENTATION_INDEX.md`
    - fixed `IMPL_BACKLOG.md` typo references in `SESSION_TOPOLOGY.md` (`IMPLEMENTATION_BACKLOG.md`)
    - added `SESSION_TOPOLOGY.md` §10 LPDD end-of-session sync checklist
    - added `scripts/lpdd_consistency_check.py` + `tests/test_lpdd_consistency_check.py`
- Validation:
    - `python -m pytest tests/test_lpdd_consistency_check.py -q` → **4 passed**
    - `python scripts/lpdd_consistency_check.py --root .` → **passed**

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 72 Complete**
- Completed Step 72 (UK paper symbol-universe reliability hardening)
    - added `src/data/symbol_health.py` with symbol availability evaluation and strict/remediation policy decisions
    - added `Settings` controls for strict mode, availability threshold, min bars, preflight window, and remediation limits
    - wired policy into `cmd_paper_trial()` startup so strict mode blocks low-availability runs before stream startup
    - added `SYMBOL_UNIVERSE_REMEDIATED` audit event when remediation changes active symbols
    - added tests: `tests/test_symbol_health.py` and runtime integration cases in `tests/test_main_paper_trial.py`
- Validation:
    - `python -m pytest tests/test_symbol_health.py tests/test_main_paper_trial.py -v` → **8 passed**

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 65 Complete**
- Completed Step 65 (Research claim-integrity gate; anti-hype caution checks)
    - updated `research/specs/RESEARCH_PROMOTION_POLICY.md` with required claim-integrity fields (OOS period, costs/slippage, max drawdown, turnover, tested variants)
    - updated `research/specs/RESEARCH_SPEC.md` with claim-integrity discipline note
    - extended `research/experiments/harness.py` promotion outputs with `claim_integrity`, `caution_flags`, and reviewer caution text
    - added `high_return_claim_unverified` caution when annualized return > 100% and evidence is incomplete
    - extended `tests/test_research_harness.py` for caution-trigger and clean-pass coverage
- Validation:
    - `python -m pytest tests/test_research_harness.py -q` → **6 passed**

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 66 Complete**
- Completed Step 66 (Pairs-trading benchmark baseline)
    - added `src/strategies/pairs_mean_reversion.py` with rolling z-score spread logic and max-holding-bar exits
    - added pairs strategy config fields in `config/settings.py`
    - registered runtime strategy key `pairs_mean_reversion` in `src/cli/runtime.py`
    - added pairs strategy tests in `tests/test_strategies.py` (min bars, entry, max-holding exit)
    - updated `research/specs/RESEARCH_SPEC.md` benchmark-comparison note for ML experiment discipline
- Validation:
    - `python -m pytest tests/test_strategies.py -q` → **30 passed**

**[2026-02-25] Session (GitHub Copilot / GPT-5.3-Codex) — Step 69 Complete**
- Completed Step 69 (UK sentiment data utility validation ticket)
    - added `research/tickets/uk_sentiment_validation.md` with two candidate UK-compatible sentiment data paths
    - added constrained offline experiment plan and explicit validation thresholds (`PR-AUC +0.02`, max drawdown deterioration `<=5%`)
    - added recommendation template (`proceed` / `park` / `reject`)
    - updated `research/specs/FEATURE_LABEL_SPEC.md` with optional Step 69 note (no runtime integration)
- Operational review update:
    - highlighted manual-execution scripts for live-window testing in `UK_OPERATIONS.md` §9b

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
| `SESSION_TOPOLOGY.md` | Session types, context routing, handoff protocol | Start of every session (identify type) |
| `SESSION_LOG.md` | Append-only session journal with structured handoff entries | Start of every session (read last 2–3) |
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

---

## §10 Agent Assignment Matrix

> Defines which LLM agent handles which category of work.
> **GitHub Copilot** works autonomously from the IMPLEMENTATION_BACKLOG Copilot Task Queue.
> **Claude Opus (this chat)** handles tasks requiring architectural judgment or research methodology decisions.
> **Operator** handles milestones requiring human action.
> **Custom agents** (`.github/agents/*.agent.md`) handle role-specific work with enforced scope guards (ADR-017).

### Assignment Rules

| Task Category | Agent | Rationale |
|---|---|---|
| Implementing a clearly-specced backlog step | **Copilot** | Clear inputs/outputs; follows existing patterns |
| Extending an existing module (new method, new config field) | **Copilot** | Pattern already established |
| Writing tests for completed code | **Copilot** | Deterministic; follows existing test patterns |
| Adding a new broker (`BrokerBase` subclass) | **Copilot** | Pattern: follow `BinanceBroker` |
| Adding a new strategy (`BaseStrategy` subclass) | **Copilot** | Pattern: follow `ma_crossover.py` |
| Updating LPDD after step completion | **Copilot** | Mechanical; instructions in `copilot-instructions.md` |
| LPDD consistency audit / governance drift check | **LPDD Auditor** (custom agent) | Scope-guarded to docs-only; runs consistency check |
| Git/repository hygiene audit and evidence scoring | **LPDD Auditor** (custom agent) | Read-first governance audit with no code mutation |
| Git ignore policy hardening and non-destructive untracking | **Copilot** | Deterministic implementation task with bounded scope |
| Secret rotation and credential lifecycle actions | **Operator** | Human accountability; credential issuance authority |
| Policy-level Git workflow changes (branch model, protected checks, merge policy) | **Claude Opus** | Requires trade-off and governance decision judgment |
| Running MO-* paper trials and burn-in sessions | **Ops Runner** (custom agent) | Scope-guarded to scripts + evidence; no code edits |
| ML experiment review / external paper assessment | **Research Reviewer** (custom agent) | Scope-guarded to research/; enforces claim-integrity |
| Designing a new module interface from scratch | **Claude Opus** | Requires trade-off analysis |
| ML architecture decisions (layers, loss, regularisation) | **Claude Opus** | Domain knowledge + project context required |
| Research methodology (feature selection, target design, evaluation) | **Claude Opus** | High impact on model validity |
| Multi-file refactors with subtle coupling risks | **Claude Opus** | Risk of breaking invariants |
| Evaluating provider/broker trade-offs | **Claude Opus** | Regulatory + technical + cost considerations |
| Reviewing article/paper for backlog additions | **Claude Opus** | Synthesis + project fit judgement |
| Scheduling paper sessions | **Operator** | Human action only |
| Signing off promotion gate evidence | **Operator** | Human accountability required |
| Populating `.env` with credentials | **Operator** | Security — never commit secrets |

### Custom Agent Roles (ADR-017)

| Agent File | Session Type | Scope | When to Use |
|---|---|---|---|
| `.github/agents/lpdd-auditor.agent.md` | REVIEW | Governance docs only (no code) | After multi-doc sessions, periodic hygiene, pre-release |
| `.github/agents/ops-runner.agent.md` | OPS | Scripts + evidence (no code) | MO-2 burn-in, paper trials, IBKR health checks |
| `.github/agents/research-reviewer.agent.md` | RSRCH | research/ only (no src/) | Experiment review, paper assessment, promotion gates |

### Currently Not-Started Step Assignments

| Step | Name | Agent | Status |
|---|---|---|---|
| 32 | LSTM baseline | Claude Opus (architecture) → Copilot (implementation) | Gated: Step 62 first |
| 46 | Paper trading daemon | Copilot | ✅ COMPLETED (Feb 25, 2026) |
| 49 | REST API scaffold | Copilot | ✅ COMPLETED (Feb 25, 2026) |
| 57 | BTC LSTM features | Claude Opus (design) → Copilot (implementation) | Ready for design |
| 59 | Class imbalance handling | Copilot | ✅ COMPLETED (Feb 25, 2026) |
| 60 | Data mining pre-registration | Copilot | ✅ COMPLETED (Feb 25, 2026) |
| 61 | Threshold target label | Copilot | ✅ COMPLETED (Feb 25, 2026) |
| 62 | MLP baseline | Claude Opus (architecture) → Copilot (implementation) | Ready for design |
| 63 | CoinbaseBroker | Copilot | ✅ COMPLETED (Feb 25, 2026) |
