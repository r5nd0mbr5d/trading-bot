# Project Review TODOs (UK-Focused) — ARCHIVED

**⚠️ ARCHIVED on Feb 23, 2026**

**Note:** This file contains task items from the Feb 23 review. Many items have been completed or consolidated into [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) for centralized tracking.

**For current outstanding tasks, blockers, and prompts, see:** [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)

This file is kept for historical reference only.

---

## Historical Record — Critical Issues (Fix First)

- [ ] **Timezone invariant breach in market data feed**
  - `src/data/feeds.py` currently strips timezone with `tz_localize(None)`, producing naive timestamps.
  - Project invariant says all timestamps must be timezone-aware UTC.
  - **Action:** Keep source tz, convert to UTC explicitly, and ensure all `Bar.timestamp` values are UTC-aware.

- [ ] **No automated tests for IBKR broker path**
  - `src/execution/ibkr_broker.py` exists but has no coverage in `tests/`.
  - **Action:** Add unit tests for connection fallback, status mapping, order rejection path, and position/account parsing.

- [ ] **Status/roadmap drift vs implemented code**
  - `PROJECT_STATUS.md` still lists ATR, walk-forward, and IBKR adapter as "not yet started" while code exists.
  - **Action:** Update project docs to reflect current state and prevent planning errors.

## UK Paper Trading Platform (Required)

- [ ] **Add explicit UK paper-trading profile (MVP)**
  - **Action:** Add a `uk_paper` runtime preset (or equivalent config profile) that defaults to:
    - broker: `ibkr`
    - paper endpoint/port: `7497`
    - timezone: `Europe/London`
    - starter symbols: UK-compatible tickers (e.g., `.L` suffix).

- [ ] **IBKR paper/live safety guardrails**
  - Current `live` confirmation flow is Alpaca-oriented and does not enforce IBKR account safety.
  - **Action:** Add explicit guardrails for IBKR:
    - block run if connected account is live while in paper mode,
    - require explicit confirmation for IBKR live,
    - log account type on startup.

- [ ] **UK market session awareness**
  - Polling loop is time-agnostic; no session calendar enforcement.
  - **Action:** Add exchange/session checks for LSE and US markets using `Europe/London` handling (GMT/BST aware) to avoid off-session execution.

## UK Trading Readiness Gaps

- [ ] **Instrument contract localization for UK equities**
  - IBKR contract creation is currently fixed to `SMART` + `USD` stock contract.
  - **Action:** Add contract mapping config (exchange/currency per symbol) so UK symbols can route as `GBP`/LSE when needed.

- [ ] **FX and base-currency risk tracking**
  - Portfolio/risk currently assumes a single currency path.
  - **Action:** Add FX normalization for valuation and risk (GBP base option), with clear reporting of P&L in base and instrument currency.

- [ ] **UK tax/audit export support**
  - Audit logging exists, but no UK tax-oriented export flow.
  - **Action:** Add export reports suitable for UK record-keeping (trade ledger, realized gains, fees, FX conversion notes).

## Data & Execution Enhancements (High Value Next)

- [ ] **Multi-provider data abstraction**
  - `DataConfig.source` advertises multiple sources, but implementation is yfinance-only in `src/data/feeds.py`.
  - **Action:** Implement provider adapters with failover and schema-normalized output.

- [ ] **Production-grade streaming mode**
  - Current stream is polling-based simulation.
  - **Action:** Add broker/data websocket streaming mode with reconnect/backoff and heartbeat checks.

- [ ] **Order lifecycle reconciliation**
  - **Action:** Add robust pending/partial/cancel reconciliation loop (especially for IBKR) to align broker state with internal portfolio state.

## Suggested Execution Order

1. Timezone invariant fix + tests
2. IBKR broker tests
3. UK paper profile + IBKR guardrails
4. Session calendar (Europe/London aware)
5. UK contract/currency mapping
6. FX-normalized risk/reporting
7. Doc/status alignment updates
