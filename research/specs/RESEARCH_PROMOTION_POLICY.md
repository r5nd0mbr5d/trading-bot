# Research-to-Runtime Promotion Policy

**Prompt:** P9 + R4c | **Author:** Claude Opus | **Date:** 2026-02-23
**Status:** APPROVED — canonical governance policy for promoting research strategies into runtime

---

## 1. Purpose and Scope

This policy governs the path from a research strategy candidate to a runtime-registered strategy. It is the **bridge** between the offline research track (`research/`) and the production registry (`src/strategies/registry.py`).

It applies to:
- ML-based strategies (XGBoost, LSTM)
- Rule-based strategies developed and evaluated through the research track
- Any strategy that was not hand-coded and directly tested within the main test suite

It does **not** apply to:
- Hotfixes to existing approved strategies (governed by the standard PROMOTION_FRAMEWORK.md Gate A/B process)
- Configuration-only changes (e.g. changing a moving average window length in an already-approved strategy)

---

## 2. Four-Stage Promotion Path

```
[Research Candidate]
       │
       │  Stage R1: Internal Research Gate
       ▼
[Research-Validated]
       │
       │  Stage R2: Runtime Integration Gate
       ▼
[Integrated (experimental)]
       │
       │  Stage R3: Paper Trial Gate
       ▼
[approved_for_paper]
       │
       │  Stage R4: Live Promotion Gate
       ▼
[approved_for_live]
```

Each stage has hard exit criteria. A candidate that fails any gate is returned to the previous stage (not terminated, unless a no-go criterion is met).

---

## 3. Required Evidence Bundle

The following must be assembled **before** submitting for Stage R2 review. Missing items are automatic blockers.

### 3a. Mandatory Evidence (all required)

| # | Item | Description | File Location |
|---|------|-------------|---------------|
| E1 | Data snapshot ID | Unique ID of the data snapshot used for training and OOS | `research/experiments/<id>/metadata.json` → `snapshot_id` |
| E2 | Snapshot reproducibility proof | Re-run of snapshot generation produces identical hash | `research/experiments/<id>/reproducibility.log` |
| E3 | Walk-forward results (all folds) | Per-fold JSON with metrics, regime tags, confidence intervals | `research/experiments/<id>/results/fold_F*.json` |
| E4 | Aggregate OOS summary | Combined metrics across all folds | `research/experiments/<id>/results/aggregate_summary.json` |
| E5 | Promotion gate check | `promotion_eligible: true` | `research/experiments/<id>/results/promotion_check.json` |
| E6 | Feature importance (SHAP) | Top-20 features per fold; no single feature > 40% | `research/experiments/<id>/shap/fold_F*.json` |
| E7 | Calibration curve | Reliability diagram for probability calibration | `research/experiments/<id>/calibration/` |
| E8 | Overfitting scores | Per-fold train vs OOS gap; aggregate < 0.15 | Within fold_F*.json |
| E9 | Seed stability test | 3× runs with different seeds; win rate stddev < 3pp | `research/experiments/<id>/seed_stability.json` |
| E10 | PSI feature baselines | Distribution snapshots for drift monitoring | `research/experiments/<id>/feature_baselines.json` |
| E11 | Model artifact + metadata | `.pt` or XGBoost model file + SHA256 + training config | `research/experiments/<id>/artifacts/` |

### 3b. Optional Evidence (required if applicable)

| Item | Required When |
|------|--------------|
| Regime coverage gap explanation | If any regime category has < minimum OOS trades (see VALIDATION_PROTOCOL.md §3c) |
| LSTM benchmark comparison | If LSTM was run alongside XGBoost |
| Data staleness documentation | If any training data is > 6 months old at submission time |
| Corporate action adjustment log | If any training symbol had splits/dividends during the training window |

---

## 4. Stage R1: Internal Research Gate

**Owner**: Researcher (single reviewer)
**Input**: raw experiment results
**Output**: `research_validated` flag in experiment metadata

### R1 Pass Criteria

All of the following must be true:

- [ ] E1–E11 evidence bundle is complete
- [ ] `promotion_check.json` → `promotion_eligible: true`
- [ ] Overfitting aggregate score < 0.15
- [ ] No fold with walk-forward degradation > 0.15 (see VALIDATION_PROTOCOL.md §6b)
- [ ] Seed stability: win rate stddev across 3 seeds < 3 percentage points
- [ ] Feature concentration: no feature > 40% SHAP importance in any fold
- [ ] Mean PR-AUC across OOS folds ≥ 0.55

### Multiple-Testing Adjustment (Bonferroni)

When multiple variants are tested on the same dataset, report:

```
adjusted_alpha = 0.05 / (n_prior_tests + 1)
```

`n_prior_tests` must be recorded in experiment metadata and propagated to `training_report.json` and `promotion_check.json`.

### R1 Output

Commit `research/experiments/<id>/research_gate.json`:

```json
{
  "experiment_id": "xgb_h5_v1_20240201",
  "stage": "R1",
  "decision": "PASS",
  "reviewer": "researcher_name",
  "reviewed_at": "2024-02-01T14:00:00Z",
  "evidence_items_checked": ["E1","E2","E3","E4","E5","E6","E7","E8","E9","E10","E11"],
  "notes": ""
}
```

---

## 5. Stage R2: Runtime Integration Gate

**Owner**: Developer + second reviewer
**Input**: `research_gate.json` (Stage R1 PASS)
**Output**: strategy registered in registry with `status=experimental`

### R2 Tasks

1. Implement the strategy factory bridge (P10 — Copilot task):
   - Map research config/model to runtime `BaseStrategy` interface
   - Enforce mandatory metadata validation on load
   - Reject candidates missing required evidence items
2. Register in `StrategyRegistry` with `status=experimental`
3. Pass all existing test suite assertions (`pytest tests/ -v` — 100% pass)
4. Add integration test covering the research→runtime bridge for this strategy

### R2 Pass Criteria

- [x] Strategy passes `pytest tests/ -v` with 100% pass rate
- [x] New integration test covers the strategy factory bridge
- [ ] Strategy registered with `status=experimental` in `trading.db`
- [ ] SHA256 of model artifact matches `E11` evidence entry
- [ ] Second reviewer has reviewed the integration code

Current status note (2026-02-23): bridge implementation + tests are complete, and real R1/R2 gate artifacts now exist; remaining open items are SHA256 verification for NN artifacts and second-reviewer sign-off, plus R3 paper-trial evidence.

Demo artifacts (validated command path):
- `research/experiments/rule_r2_demo_20260223/research_gate.json`
- `research/experiments/rule_r2_demo_20260223/integration_gate.json`
- `trading.db` entry: `uk_rule_alpha_demo:0.1.0` (`status=experimental`)

Real candidate artifacts (Feb 23, 2026):
- `research/experiments/rule_r2_real_20260223/research_gate.json`
- `research/experiments/rule_r2_real_20260223/integration_gate.json`
- `trading.db` entry: `ma_crossover_research:0.1.0` (`status=experimental`)

Operational command (R2 artifact path):

```bash
python main.py research_register_candidate \
  --candidate-dir research/experiments/<experiment_id> \
  --registry-db-path trading.db \
  --artifacts-dir strategies \
  --output-dir research/experiments/<experiment_id>
```

This command registers the candidate as `experimental` and writes `integration_gate.json` for Stage R2 evidence.

### R2 Output

Registry entry + commit `research/experiments/<id>/integration_gate.json`:

```json
{
  "experiment_id": "xgb_h5_v1_20240201",
  "stage": "R2",
  "decision": "PASS",
  "strategy_registry_id": "xgb_h5:1.0.0",
  "registry_status": "experimental",
  "test_count_before": 317,
  "test_count_after": 325,
  "reviewer_1": "developer_name",
  "reviewer_2": "second_reviewer_name",
  "reviewed_at": "2024-02-05T09:00:00Z"
}
```

---

## 6. Stage R3: Paper Trial Gate

**Owner**: Operator
**Input**: `integration_gate.json` (Stage R2 PASS)
**Output**: `status=approved_for_paper` in registry

### R3 Paper Trial Requirements

The paper trial must be run using the manifest framework (`TRIAL_MANIFEST.md`):

```bash
python main.py paper_trial \
  --manifest configs/trial_standard.json \
  --profile uk_paper \
  --output-dir reports/paper_trials/<experiment_id>
```

### R3 Pass Criteria (enforced by `paper_readiness_failures()`)

| Metric | Threshold |
|--------|-----------|
| Closed trade count | ≥ 30 paper trades |
| Win rate | ≥ 0.52 |
| Profit factor | ≥ 1.15 |
| Fill rate | ≥ 0.93 |
| Avg slippage | ≤ 0.20% |
| Reconciliation drift | ≤ 5% vs expected KPIs |

Additionally (not in `paper_readiness_failures`, checked manually):
- [ ] No `feature_drift_psi > 0.25` events in audit log during trial
- [ ] No `model_confidence_degraded` events during trial
- [ ] No UK health check failures during trial
- [ ] LSE session enforcement verified (no orders placed outside 08:15–16:25)

### R3 Promotion CLI

```bash
python main.py promotion_checklist \
  --strategy xgb_h5 \
  --output-dir reports/promotions \
  --summary-json reports/paper_trials/<experiment_id>/paper_session_summary.json
```

The resulting `promotion_checklist.json` must have `decision=READY`.

Then promote:

```python
registry.promote(
    "xgb_h5", "1.0.0",
    new_status="approved_for_paper",
)
```

---

## 7. Stage R4: Live Promotion Gate

Governed by the full institutional framework in `docs/PROMOTION_FRAMEWORK.md` Gate B. A research-track strategy must pass the same Gate B criteria as any other strategy.

Additional requirement specific to research-track strategies:
- The full R1–R3 evidence bundle must be present in `reports/promotions/<strategy_id>/`
- A dedicated decision rubric JSON must reference the `experiment_id` from the research track

---

## 8. Rollback Conditions and Monitoring Triggers

### 8a. Automatic Rollback Triggers

The following trigger an automatic strategy halt (kill switch for the strategy, not system-wide):

| Event | Audit Event Type | Action |
|-------|-----------------|--------|
| PSI > 0.50 on ≥ 3 features | `ml_strategy_emergency_halt` | Immediate halt; operator alert |
| Win rate < 0.45 over ≥ 20 live trades | `live_win_rate_below_threshold` | Halt new entries; operator alert |
| Drawdown > 10% in live | `live_drawdown_circuit_breaker` | Halt; requires manual reset |
| Model prediction drift (mean prob < 0.40 or > 0.60) | `model_prediction_drift` | Pause entries; operator review |
| Audit log shows broker fill rate < 0.85 over 20 trades | `live_fill_rate_below_threshold` | Reduce position size 50%; operator alert |

### 8b. Rollback Procedure

1. Operator triggers `StrategyRegistry.promote(name, version, "approved_for_paper")` to downgrade status (requires manual rollback — registry does not auto-downgrade)
2. Open positions are managed to their existing stop-loss / take-profit levels (no forced immediate exit)
3. Record rollback in `reports/promotions/<strategy_id>/rollback.json` with timestamp, trigger event, and operator name

### 8c. Reactivation Procedure

After rollback, the strategy must complete a fresh paper trial cycle (Stage R3) with at least 30 new trades before live re-promotion is considered.

---

## 9. Explicit No-Go Criteria

A research candidate is **permanently rejected** (cannot re-enter the promotion pipeline without a full retraining cycle) if any of the following are found:

| No-Go Criterion | Rationale |
|----------------|-----------|
| Leakage confirmed: OOS metrics collapse to ~50% win rate after leakage fix | Model learned from future data; results are invalid |
| Model was retrained after seeing test-fold data | Contamination; OOS estimates are unreliable |
| Seed stability fails (stddev > 10pp across seeds) | Results are not reproducible; model is unstable |
| Overfitting aggregate score > 0.30 | Excessive overfitting; not safe for live capital |
| Fabricated or modified evidence bundle detected | Trust violation; zero tolerance |
| Strategy was run live (even with paper capital) before completing R1–R3 | Governance bypass |

A permanently rejected candidate must have its registry entry set to `experimental` (blocked from paper/live) and a note added to the decision record explaining the rejection reason.

---

## 10. Policy Change Control

This policy may be updated only through a pull request with:
- Written rationale for the change
- At least one reviewer who was not the author
- Update to `DOCUMENTATION_INDEX.md` if new files are introduced

All changes must be backward-compatible with existing promotion evidence bundles or existing approved strategies must be re-evaluated under the new policy.

---

## 11. Quick Reference Checklist

**Current candidate**: `ma_crossover_research:0.1.0` (rule-based demo) and `uk_rule_alpha_demo:0.1.0`
**Evidence root**: `research/experiments/rule_r2_real_20260223/` and `rule_r2_demo_20260223/`

```
STAGE R1 — Research Validated
  [ ] E1-E11 evidence bundle complete         ← BLOCKER: requires real walk-forward experiment run
  [ ] promotion_check.json → promotion_eligible: true  ← BLOCKER: requires walk-forward harness (R2 ticket)
  [ ] overfitting aggregate < 0.15            ← BLOCKER: requires OOS fold data
  [ ] seed stability: stddev < 3pp            ← BLOCKER: requires 3× experiment runs
  [ ] feature concentration: no feature > 40% SHAP  ← BLOCKER: requires XGBoost training
  NOTE: R1 gate applies to ML candidates. Rule-based candidates skip to R2 directly.

STAGE R2 — Runtime Integration
  [x] strategy factory bridge implemented and tested  (research/bridge/strategy_bridge.py)
  [x] registered as experimental in registry  (ma_crossover_research:0.1.0 in trading.db)
  [x] pytest 100% pass                        (339+ passing as of Feb 24)
  [ ] SHA256 verified                         ← MANUAL: applies to NN model artifacts only;
                                                  rule-based demo has no .pt artifact to verify
  [ ] second reviewer sign-off                ← MANUAL OPERATOR: MO-6 item; requires human sign-off

STAGE R3 — Paper Trial (approved_for_paper)
  [ ] ≥ 30 closed paper trades                ← BLOCKED by Step 1/1A in-window run (MO-1/MO-2)
  [ ] win rate ≥ 0.52                         ← BLOCKED
  [ ] profit factor ≥ 1.15                    ← BLOCKED
  [ ] fill rate ≥ 0.93                        ← BLOCKED
  [ ] avg slippage ≤ 0.20%                    ← BLOCKED
  [ ] no feature drift or confidence degradation events  ← BLOCKED
  [ ] promotion_checklist.json → decision=READY  ← BLOCKED by above

STAGE R4 — Live (approved_for_live)
  [ ] PROMOTION_FRAMEWORK.md Gate B criteria  ← BLOCKED by R3
  [ ] full evidence bundle in reports/promotions/  ← BLOCKED
  [ ] decision rubric references experiment_id    ← BLOCKED
```

**Stage R1 note (rule-based candidates)**: Rule-based strategies (`type=rule`) do not require walk-forward ML evidence (E3–E10). They enter at Stage R2 directly, with the following substitutes for the E1-E11 bundle:
- E1/E2: Backtest snapshot ID + reproducibility (same-config backtest produces same metrics)
- E3/E4: Walk-forward backtest fold results and aggregate summary (via `backtest/engine.py`)
- E5: Aggregate win rate ≥ 0.50, profit factor ≥ 1.10 over OOS window
- E6–E10: N/A for rule-based (no SHAP, no calibration curve, no PSI baseline)
- E11: No artifact (rule-based strategies have `type=rule`, no `.pt` file)

**Unblocking path**:
1. Complete Step 1 in-window paper session (MO-1) → provides R3 evidence
2. Run offline walk-forward harness (R2 ticket, Copilot) → provides R1 evidence for ML candidates
3. Obtain second-reviewer sign-off (MO-6) for final R2 closure

---

**References:**
- `docs/PROMOTION_FRAMEWORK.md` — institutional Gate B framework
- `src/strategies/registry.py` — `promote()` with checklist gate enforcement
- `docs/PROMOTION_CHECKLIST.md` — operational checklist
- `research/specs/VALIDATION_PROTOCOL.md` — walk-forward requirements
- `research/specs/ML_BASELINE_SPEC.md` — evidence bundle specification
- P10 prompt (`UK_STRATEGY_PROMPTS.md`) — runtime strategy bridge implementation
