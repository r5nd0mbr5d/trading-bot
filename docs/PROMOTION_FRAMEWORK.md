# Institutional-Grade Promotion Framework

> **Version:** 1.0.0
> **Date:** 2026-02-23
> **Owner:** Trading Operations
> **Status:** Active
> **Decision Rubric Schema:** `reports/promotions/decision_rubric.json`
> **Weekly Review Template:** `docs/WEEKLY_REVIEW_TEMPLATE.md`

---

## Overview

This document defines the objective, measurable criteria and process required to promote an algorithmic trading strategy from development through to live production trading. The framework is designed for a UK-based equities trading bot operating on LSE and US markets.

All promotion decisions must reference this document. Decisions not traceable to a completed rubric entry in `reports/promotions/` are invalid.

---

## Promotion Pathway

```
experimental
     │
     │  Gate A: Code Review + Backtest Validation
     ▼
approved_for_paper
     │
     │  Gate B: Paper Trading Validation (this framework)
     ▼
approved_for_live
     │
     │  Gate C: Live Production (funded account only)
     ▼
production
```

The `StrategyRegistry` (`src/strategies/registry.py`) enforces these state transitions programmatically. The `paper_readiness_failures()` function implements Gate B checks automatically.

---

## Gate A — Experimental to Paper-Approved

### Objective Criteria

| Category | Check | Threshold | Automated |
|----------|-------|-----------|-----------|
| **Code Quality** | All unit tests pass | 100% pass rate | Yes (`pytest`) |
| **Backtest Performance** | Sharpe ratio (3-year) | ≥ 0.5 | Yes (`BacktestResults`) |
| **Backtest Performance** | Max drawdown (3-year) | ≤ 30% | Yes (`BacktestResults`) |
| **Backtest Performance** | Win rate | ≥ 45% | Yes (`BacktestResults`) |
| **Backtest Performance** | Profit factor | ≥ 1.05 | Yes (`BacktestResults`) |
| **Lookahead** | `generate_signal()` returns None when `len(df) < min_bars_required()` | 0 violations | Yes (test coverage) |
| **Signal Integrity** | Signal strength in [0.0, 1.0] | 0 violations | Yes (assertions) |
| **Risk Routing** | All orders flow through `RiskManager.approve_signal()` | 0 direct orders | Code review |
| **Walk-Forward** | Out-of-sample Sharpe ≥ in-sample × 0.6 | Not degraded >40% | Yes (walk_forward.py) |

### Process

1. Developer opens a PR and runs `python -m pytest tests/ -v`
2. Code reviewer checks the Risk Routing invariant manually
3. `python main.py walk_forward --start 2021-01-01 --end 2024-01-01` output is reviewed
4. Registry entry is created at `experimental` status:
   ```bash
   # Registered via registry.save("strategy_name", "1.0.0", "rule", parameters)
   ```
5. If all Gate A criteria pass, registry is promoted to `approved_for_paper`:
   ```bash
   # registry.promote("strategy_name", "1.0.0", "approved_for_paper")
   ```

---

## Gate B — Paper-Approved to Live-Approved

### Minimum Paper Trading Duration

| Market | Minimum Duration | Minimum Trades |
|--------|-----------------|----------------|
| US equities (Alpaca) | 10 trading days | 30 closed trades |
| UK equities (IBKR LSE) | 10 trading days | 20 closed trades |
| Combined (multi-market) | 15 trading days | 40 closed trades |

### Objective Thresholds (Gate B)

These are enforced by `paper_readiness_failures()` in `src/strategies/registry.py`.

#### Category 1 — Risk

| Metric | Threshold | Severity | Notes |
|--------|-----------|----------|-------|
| Max drawdown (paper) | ≤ 15% | P0 — blocks promotion | Intraday peak-to-trough |
| Daily loss limit breach | 0 circuit-breaker trips | P0 — blocks promotion | Via `RiskManager` |
| Kill switch activations | 0 | P0 — blocks promotion | `src/risk/kill_switch.py` |
| VaR breach events | 0 | P1 — requires explanation | 95% 1-day VaR > 5% |
| Consecutive loss halts | ≤ 1 | P1 — requires explanation | Triggers on 5 consecutive losses |
| Position concentration | ≤ 40% in any single position | P1 — requires explanation | Tracked via `PortfolioTracker` |

#### Category 2 — Execution Quality

| Metric | Threshold | Severity | Notes |
|--------|-----------|----------|-------|
| Fill rate | ≥ 90% | P0 — blocks promotion | Orders filled / orders submitted |
| Average slippage | ≤ 0.25% | P0 — blocks promotion | Avg of `(fill_price - signal_price) / signal_price` |
| Reject rate | ≤ 10% | P1 — requires explanation | Broker-level order rejects |
| Order latency (p95) | ≤ 2 seconds | P2 — informational | Measured submission-to-fill |
| Commission per trade | ≤ 0.10% of notional | P2 — informational | For cost modelling |

#### Category 3 — Statistical Significance

| Metric | Threshold | Severity | Notes |
|--------|-----------|----------|-------|
| Closed trade count | ≥ 20 (UK) / ≥ 30 (US) | P0 — blocks promotion | Minimum sample for statistical validity |
| Win rate | ≥ 50% | P0 — blocks promotion | Closed profitable trades / total closed |
| Profit factor | ≥ 1.10 | P0 — blocks promotion | Gross profit / gross loss |
| Realized P&L | ≥ £0 / $0 | P0 — blocks promotion | Net of commissions and slippage |
| Sharpe ratio (paper) | ≥ 0.3 | P1 — requires explanation | Annualized on paper returns |

#### Category 4 — Data Integrity

| Metric | Threshold | Severity | Notes |
|--------|-----------|----------|-------|
| Audit log completeness | 100% events recorded | P0 — blocks promotion | No gaps in `AuditLogger` |
| Market data gaps | 0 unhandled gaps during session | P1 — requires explanation | Via `MarketDataFeed` |
| Bar timestamp ordering | 100% chronological | P0 — blocks promotion | Checked in `BacktestEngine` |
| Reconciliation drift | < 5% on all KPIs | P1 — requires explanation | Via `src/audit/reconciliation.py` |

#### Category 5 — Stability

| Metric | Threshold | Severity | Notes |
|--------|-----------|----------|-------|
| Unhandled exceptions | 0 | P0 — blocks promotion | In audit log `severity=CRITICAL` |
| Process restarts | ≤ 1 | P1 — requires explanation | Unexpected crashes |
| Memory growth (leak) | < 50 MB / hour | P2 — informational | Only if running > 4 hours |
| Signal generation latency | ≤ 500ms per bar | P2 — informational | End-to-end per symbol |

---

## Multi-Level Promotion Path

### Level 1 — Paper (Alpaca Sandbox)

- **Requirement:** Gate A passed
- **Environment:** Alpaca paper trading (no real money)
- **Duration:** Minimum 10 trading days
- **Oversight:** Daily automated KPI check via `paper_session_summary`

### Level 2 — Paper-Ready

- **Requirement:** Gate B passed (all P0 metrics within threshold)
- **Environment:** IBKR demo account (LSE symbols in GBP)
- **Duration:** Minimum 5 additional trading days on UK market
- **Oversight:** Weekly review using `docs/WEEKLY_REVIEW_TEMPLATE.md`

### Level 3 — Approved-for-Live

- **Requirement:** Gate B fully passed + Level 2 complete + manual review sign-off
- **Environment:** IBKR live with minimum funded account
- **Capital:** Start with ≤ 10% of intended allocation ("shadow mode")
- **Oversight:** Daily automated reporting + weekly human review

### Level 4 — Full Production

- **Requirement:** 20 trading days at Level 3 with no P0 incidents
- **Environment:** Full allocation as per strategy design parameters
- **Oversight:** Weekly review + monthly external audit

---

## Severity Definitions

| Severity | Definition | Action |
|----------|------------|--------|
| **P0 — Blocking** | Hard stop: strategy cannot be promoted until resolved | Fail promotion; create remediation ticket |
| **P1 — Urgent** | Must have written explanation and sign-off from two reviewers | Document reason in rubric; proceed with approval |
| **P2 — Nice-to-have** | Informational only; logged but does not affect promotion | Record in rubric notes field |

---

## Decision Rubric

All promotion decisions must be recorded in `reports/promotions/` as a JSON file conforming to `reports/promotions/decision_rubric.json` schema.

### File Naming Convention

```
reports/promotions/<strategy_name>_<version>_<yyyymmdd>_<level>.json
```

Example: `reports/promotions/ma_crossover_1.0.0_20260223_paper_to_live.json`

### Rubric Fields

See `reports/promotions/decision_rubric.json` for the full JSON schema. Key fields:

- `strategy_id` — `name:version` (matches `StrategyRegistry` ID)
- `promotion_level` — e.g., `"experimental_to_paper"`, `"paper_to_live"`
- `decision` — `"APPROVED"`, `"REJECTED"`, `"DEFERRED"`
- `decision_date` — ISO 8601 UTC timestamp
- `reviewer_ids` — At least one required; two required for P1 overrides
- `metrics` — All Gate B metric values with pass/fail
- `p0_failures` — List of blocking failures (must be empty for APPROVED)
- `p1_overrides` — P1 metrics that failed threshold with written justification
- `notes` — Free-text notes for context
- `rubric_version` — Version of this framework document used

---

## Automated Promotion Check

Run the following to perform a Gate B automated check:

```bash
# Generate paper session summary
python main.py paper_session_summary trading_paper.db reports/session

# Check promotion readiness (uses paper_readiness_failures())
python -c "
from src.strategies.registry import paper_readiness_failures
import json

with open('reports/session/paper_session_summary.json') as f:
    summary = json.load(f)

failures = paper_readiness_failures(summary)
if failures:
    print('GATE B FAILED:')
    for f in failures:
        print(' -', f)
else:
    print('GATE B PASSED — strategy eligible for promotion to approved_for_live')
"
```

For a full promotion:

```bash
python -c "
from src.strategies.registry import StrategyRegistry
import json

reg = StrategyRegistry('trading.db')
with open('reports/session/paper_session_summary.json') as f:
    summary = json.load(f)

reg.promote('ma_crossover', '1.0.0', 'approved_for_live', paper_summary=summary)
print('Promoted to approved_for_live')
"
```

---

## Communication Template

When a strategy is promoted to `approved_for_live`, send this summary to stakeholders:

```
Subject: Strategy Promotion — [Strategy Name] v[Version] → Approved for Live

Summary:
  Strategy:       [name:version]
  Promotion To:   approved_for_live
  Decision Date:  [date]
  Reviewers:      [reviewer IDs]

Gate B Results:
  Fill Rate:      [value] (threshold: 90%)
  Win Rate:       [value] (threshold: 50%)
  Profit Factor:  [value] (threshold: 1.10)
  Max Drawdown:   [value] (threshold: 15%)
  Closed Trades:  [count] (minimum: 20)
  Avg Slippage:   [value] (threshold: 0.25%)
  Realized P&L:   [value] (minimum: 0)

P1 Overrides:     [list any, or "None"]
P0 Failures:      None (required for approval)

Decision Rubric:  reports/promotions/[rubric_filename].json
Framework Ref:    docs/PROMOTION_FRAMEWORK.md v1.0.0
```

---

## Immutability Requirements

Once a decision rubric JSON is written to `reports/promotions/`:

1. It must never be overwritten or deleted
2. The file must be committed to git with a signed commit
3. The rubric file's SHA256 must be logged as an audit event:
   ```
   event_type: "promotion_decision"
   payload: { rubric_file, rubric_sha256, decision, strategy_id }
   ```

This creates an immutable audit trail for regulatory and compliance purposes.

---

## Change Control

This document may only be updated:
1. With agreement from at least two senior reviewers
2. By incrementing the version number in the header
3. With a `rubric_version` field update in the JSON schema
4. With a changelog entry below

### Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-02-23 | System | Initial version — covers 4 strategy types, 5 metric categories, 4 promotion levels |
