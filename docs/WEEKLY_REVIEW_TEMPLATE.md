# Weekly Strategy Review Template

> **Framework Reference:** `docs/PROMOTION_FRAMEWORK.md`
> **Rubric Schema:** `reports/promotions/decision_rubric.json`
> **Usage:** Complete this checklist every Monday morning covering the prior trading week.
> **Storage:** Save completed reviews to `reports/promotions/weekly_review_<yyyymmdd>.md`

---

## Review Metadata

| Field | Value |
|-------|-------|
| **Review Period** | YYYY-MM-DD to YYYY-MM-DD |
| **Reviewer Name** | |
| **Review Date** | YYYY-MM-DD |
| **Strategy** | e.g., `ma_crossover:1.0.0` |
| **Environment** | Paper / Paper-Ready / Shadow-Live |
| **Market** | US (Alpaca) / UK-LSE (IBKR) / Both |
| **Base Currency** | USD / GBP |

---

## Section 1 — System Health

### 1.1 Process Stability

- [ ] Bot ran without unhandled exceptions this week
- [ ] No unexpected process restarts (check OS logs / supervisor)
- [ ] Audit log has no CRITICAL severity events
- [ ] Kill switch was NOT activated during the week

If kill switch WAS activated, document here:
```
Kill switch trigger:
Activation time:
Resolution:
```

### 1.2 Data Feed Quality

- [ ] Market data arrived on time for all trading days
- [ ] No gaps detected in OHLCV data (check `MarketDataFeed` logs)
- [ ] Timestamps are UTC-aligned (no clock drift detected)
- [ ] Corporate action adjustments applied where relevant (splits, dividends)

Data feed issues noted:
```
[None / describe issues]
```

### 1.3 Audit Log Completeness

Run audit log completeness check:
```bash
python main.py paper_session_summary trading_paper.db reports/session
```

- [ ] All orders have a corresponding fill or reject event
- [ ] Audit event count matches expected order count
- [ ] No orphaned events (fill without order, signal without fill logic)

Audit completeness result:
```
Total events:
Order count:
Fill count:
Reject count:
Missing events:
```

---

## Section 2 — Execution Quality

Generate the session summary:
```bash
python main.py paper_session_summary trading_paper.db reports/session
```

### 2.1 Core Execution Metrics

| Metric | This Week | Threshold | Status |
|--------|-----------|-----------|--------|
| Fill Rate | | ≥ 90% | ☐ Pass / ☐ Fail |
| Avg Slippage | | ≤ 0.25% | ☐ Pass / ☐ Fail |
| Reject Rate | | ≤ 10% | ☐ Pass / ☐ Fail |
| Avg Commission per Trade | | ≤ 0.10% notional | ☐ Pass / ☐ Fail |
| Orders Submitted | | ≥ 5 | ☐ Pass / ☐ Fail |

### 2.2 Execution Trend (vs Prior Week)

| Metric | Prior Week | This Week | Trend |
|--------|-----------|-----------|-------|
| Fill Rate | | | ↑ / ↓ / → |
| Avg Slippage | | | ↑ / ↓ / → |
| Reject Rate | | | ↑ / ↓ / → |

Execution quality narrative (3–5 sentences):
```
[Describe what changed and why — e.g., "Higher reject rate attributable to
pre-market orders submitted before LSE open. Will adjust session window."]
```

---

## Section 3 — P&L and Statistical Performance

### 3.1 Weekly P&L

| Metric | This Week | Threshold | Status |
|--------|-----------|-----------|--------|
| Realized P&L | | ≥ 0 | ☐ Pass / ☐ Fail |
| Win Rate | | ≥ 50% | ☐ Pass / ☐ Fail |
| Profit Factor | | ≥ 1.10 | ☐ Pass / ☐ Fail |
| Closed Trade Count | | ≥ 4/week | ☐ Pass / ☐ Fail |

### 3.2 Cumulative P&L (since paper start)

| Metric | Cumulative | Threshold | Status |
|--------|------------|-----------|--------|
| Total Realized P&L | | ≥ 0 | ☐ Pass / ☐ Fail |
| Cumulative Win Rate | | ≥ 50% | ☐ Pass / ☐ Fail |
| Cumulative Profit Factor | | ≥ 1.10 | ☐ Pass / ☐ Fail |
| Total Closed Trades | | ≥ 20 (Gate B min) | ☐ Pass / ☐ Fail |

### 3.3 Drawdown Monitoring

| Metric | This Week | Threshold | Status |
|--------|-----------|-----------|--------|
| Max Intraday Drawdown | | ≤ 15% | ☐ Pass / ☐ Fail |
| Current Drawdown from Peak | | ≤ 10% | ☐ Pass / ☐ Fail |
| Circuit Breaker Trips | | 0 | ☐ Pass / ☐ Fail |

Drawdown narrative:
```
[Describe any significant drawdown events. Was drawdown caused by market
conditions or strategy issues? Any parameter adjustment needed?]
```

---

## Section 4 — Risk Control Verification

### 4.1 Position Limits

- [ ] No single position exceeded 10% of portfolio (`max_position_pct`)
- [ ] Maximum open positions at any time was ≤ `max_open_positions` (10)
- [ ] No symbol appeared in both a BUY and SHORT signal on the same day

Position limit check:
```
Max position size seen:
Max open positions seen:
```

### 4.2 VaR Check

- [ ] 1-day VaR (95%) remained below 5% (`max_var_pct`) throughout the week
- [ ] No VaR-triggered order blocks occurred

VaR readings:
```
Monday VaR:
Wednesday VaR:
Friday VaR:
```

### 4.3 Risk Manager Routing

- [ ] Confirm all orders routed through `RiskManager.approve_signal()` (no direct order submission)
- [ ] ATR-derived stops were used (not fixed % fallback) for all eligible signals

---

## Section 5 — Broker Reconciliation

Run reconciliation:
```bash
python main.py paper_reconcile trading_paper.db reports/reconcile \
  reports/session/expected_kpis_standard.json \
  --tolerances reports/session/tolerances_standard.json
```

### 5.1 KPI Reconciliation Results

| KPI | Expected | Actual | Drift | Within Tolerance |
|-----|----------|--------|-------|-----------------|
| fill_rate | | | | ☐ Yes / ☐ No |
| win_rate | | | | ☐ Yes / ☐ No |
| profit_factor | | | | ☐ Yes / ☐ No |
| avg_slippage_pct | | | | ☐ Yes / ☐ No |
| realized_pnl | | | | ☐ Yes / ☐ No |

Overall reconciliation: ☐ All within tolerance / ☐ Drift detected

If drift detected, document explanation:
```
[Metric that drifted]: [Reason for drift]
[Action taken or planned]:
```

---

## Section 6 — Strategy Signal Quality

### 6.1 Signal Distribution

| Signal Type | Count This Week | % of Total |
|-------------|----------------|------------|
| LONG | | |
| SHORT | | |
| CLOSE | | |
| HOLD (no signal) | | |

- [ ] No HOLD-only sessions (strategy is generating signals)
- [ ] Signal strength distribution is reasonable (not all at 0.0 or 1.0)

### 6.2 Strategy Parameter Stability

- [ ] Strategy parameters unchanged from registered version
- [ ] No ad-hoc parameter overrides applied this week
- [ ] Min bars required check passing (no premature signals)

If parameters were changed:
```
Old parameters:
New parameters:
Reason:
Registry update required: ☐ Yes / ☐ No
```

---

## Section 7 — Promotion Readiness Assessment

### 7.1 Gate B Automated Check

Run the Gate B check:
```bash
python -c "
from src.strategies.registry import paper_readiness_failures
import json
with open('reports/session/paper_session_summary.json') as f:
    summary = json.load(f)
failures = paper_readiness_failures(summary)
print('GATE B FAILURES:', failures if failures else 'None — ELIGIBLE')
"
```

Gate B result: ☐ All pass / ☐ Failures present

Failures (if any):
```
[List failures or "None"]
```

### 7.2 Promotion Decision

Based on this review, the strategy promotion status is:

- [ ] **Continue paper trading** — Not yet at minimum thresholds (specify):
  ```
  Missing: [e.g., "Need 8 more closed trades to reach minimum 20"]
  ```
- [ ] **Ready for promotion** — All Gate B criteria met; submit rubric to `reports/promotions/`
- [ ] **Hold — investigation needed** — P0 or multiple P1 failures require investigation (specify):
  ```
  Issue: [describe blocking issue]
  Owner: [who will investigate]
  ETA:   [expected resolution date]
  ```
- [ ] **Demote** — Strategy is underperforming; return to `approved_for_paper` or `experimental`

---

## Section 8 — Action Items

| # | Action | Owner | Priority | Due Date | Status |
|---|--------|-------|----------|----------|--------|
| 1 | | | HIGH/MED/LOW | | Open |
| 2 | | | | | |
| 3 | | | | | |

---

## Section 9 — Sign-Off

| Role | Name | Date | Signature/Initials |
|------|------|------|-------------------|
| Primary Reviewer | | | |
| Secondary Reviewer (required for P1 override) | | | |
| Decision Rubric Filed | | | `reports/promotions/[filename]` |

---

## Appendix — Commands Reference

```bash
# Generate session summary
python main.py paper_session_summary trading_paper.db reports/session

# Reconcile vs expected KPIs
python main.py paper_reconcile trading_paper.db reports/reconcile \
  reports/session/presets/expected_kpis_standard.json \
  --tolerances reports/session/presets/tolerances_standard.json

# UK tax export (for UK operations)
python main.py uk_tax_export trading_paper.db reports/tax

# UK health check
python main.py uk_health_check trading_paper.db

# Run full paper trial (using manifest)
python main.py paper_trial configs/trial_standard.json

# Walk-forward for out-of-sample validation
python main.py walk_forward --start 2022-01-01 --end 2024-01-01 \
  --train-months 6 --test-months 2 --step-months 1

# Gate B check
python -c "
from src.strategies.registry import paper_readiness_failures
import json
with open('reports/session/paper_session_summary.json') as f:
    summary = json.load(f)
failures = paper_readiness_failures(summary)
print('Gate B:', 'PASS' if not failures else 'FAIL — ' + str(failures))
"
```
