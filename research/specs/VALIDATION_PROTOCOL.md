# Walk-Forward + Regime Validation Protocol

**Prompt:** P5 + R4b | **Author:** Claude Opus | **Date:** 2026-02-23
**Status:** APPROVED — canonical validation protocol for all strategy research in this track

---

## 1. Purpose

This protocol defines the statistical standards that a research strategy must meet before being considered for paper-trial promotion. It is designed to:

1. Detect overfitting through temporal out-of-sample validation
2. Ensure robustness across multiple market regimes
3. Produce machine-readable pass/fail outputs that feed automated promotion checks
4. Provide confidence intervals rather than point estimates

---

## 2. Walk-Forward Windowing Schedule

### 2a. Fold Structure

Use an **expanding-window** walk-forward with a fixed test window. Each fold has three non-overlapping periods:

| Period | Purpose | Data Usage |
|--------|---------|------------|
| Train | Model fitting + scaler/threshold calibration | All past data up to fold cutoff |
| Validation | Hyperparameter tuning and threshold adjustment | Immediately after train; not used in model fit |
| Test (OOS) | Final performance measurement | Never used in any fitting step |

**Gap rule**: insert a gap of ≥ `label_horizon` trading days between train end and val start, and between val end and test start (see `FEATURE_LABEL_SPEC.md` §6c).

### 2b. Standard Fold Schedule (H5 horizon, MVU universe)

| Fold | Train Start | Train End | Val Start | Val End | Test Start | Test End |
|------|------------|-----------|-----------|---------|------------|----------|
| F1 | 2018-01-01 | 2020-06-30 | 2020-07-08 | 2020-12-31 | 2021-01-08 | 2021-06-30 |
| F2 | 2018-01-01 | 2020-12-31 | 2021-01-08 | 2021-06-30 | 2021-07-08 | 2021-12-31 |
| F3 | 2018-01-01 | 2021-06-30 | 2021-07-08 | 2021-12-31 | 2022-01-07 | 2022-06-30 |
| F4 | 2018-01-01 | 2021-12-31 | 2022-01-07 | 2022-06-30 | 2022-07-08 | 2022-12-30 |
| F5 | 2018-01-01 | 2022-06-30 | 2022-07-08 | 2022-12-30 | 2023-01-06 | 2023-06-30 |
| F6 | 2018-01-01 | 2022-12-30 | 2023-01-06 | 2023-06-30 | 2023-07-07 | 2023-12-29 |
| F7 | 2018-01-01 | 2023-06-30 | 2023-07-07 | 2023-12-29 | 2024-01-05 | 2024-06-28 |
| F8 | 2018-01-01 | 2023-12-29 | 2024-01-05 | 2024-06-28 | 2024-07-05 | 2024-12-31 |

**Notes:**
- 8 folds × 6-month test windows = 4 years of OOS coverage (2021–2024)
- Each test window is approximately 130 trading days
- The expanding train window ensures models see progressively more regime data
- Minimum train period (F1): 2.5 years; ensures ≥ 600 trading days for stable parameter estimation

### 2c. Minimum Signal Count per Fold

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| Min training samples | 200 | Below this, ML models are statistically unreliable |
| Min test trades | 20 | Below this, win rate confidence interval is too wide |
| Min OOS closed trades (aggregate) | 100 | For aggregate promotion decision |

If a fold produces fewer than 20 test trades, mark it `insufficient_data` rather than pass/fail. A strategy with > 3 `insufficient_data` folds is ineligible for promotion regardless of other metrics.

---

## 3. Regime-Split Validation

In addition to the time-ordered walk-forward, validate performance separately by regime type.

### 3a. Regime Mapping

Use the regime date ranges from `config/test_regimes.json`. Each OOS bar is tagged with its regime:

| Regime Tag | Date Range | Characteristic |
|-----------|-----------|----------------|
| `bull_pre_covid` | 2018-01 → 2020-02 | Low vol trend |
| `crisis` | 2020-02 → 2020-05 | Extreme vol |
| `bull_post_covid` | 2020-05 → 2021-12 | Growth momentum |
| `bear_stagflation` | 2022-01 → 2022-12 | Rising rates, negative returns |
| `bull_recovery` | 2023-01 → 2024-06 | Selective momentum |
| `sideways_volatile` | 2024-07 → present | Mixed signals |

### 3b. Regime Aggregation

For each regime tag, aggregate OOS predictions across all folds where test bars fall in that regime:

```
regime_win_rate[regime] = sum(winning_trades in regime) / sum(all_closed_trades in regime)
```

### 3c. Required Regime Coverage for Promotion

A strategy cannot be promoted to paper trial unless it has OOS coverage in at least:

| Requirement | Minimum |
|-------------|---------|
| Bull regime coverage | ≥ 50 closed OOS trades |
| Bear/crisis regime coverage | ≥ 30 closed OOS trades |
| Sideways regime coverage | ≥ 20 closed OOS trades |

If bull or bear coverage is below threshold, the strategy is classified as **regime-undertested** and cannot be promoted.

---

## 4. Confidence Reporting Requirements

Every strategy evaluation must report confidence intervals, not just point estimates.

### 4a. Confidence Interval Method

Use the **Wilson score interval** for win rate (proportion), which handles small samples better than normal approximation:

```python
from scipy.stats import norm

def wilson_ci(wins: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    z = norm.ppf(1 - (1 - confidence) / 2)
    p_hat = wins / n
    denominator = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denominator
    margin = (z * (p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denominator
    return centre - margin, centre + margin
```

### 4b. Required Report Fields

Every fold must emit:

```json
{
  "fold_id": "F3",
  "test_start": "2022-01-07",
  "test_end": "2022-06-30",
  "regime_tags": ["bear_stagflation"],
  "n_closed_trades": 47,
  "win_rate": 0.532,
  "win_rate_ci_95": [0.389, 0.671],
  "profit_factor": 1.18,
  "sharpe_ratio": 0.74,
  "max_drawdown_pct": 8.3,
  "fill_rate": 0.96,
  "avg_slippage_pct": 0.0018,
  "model_version": "xgb_v1.0.0",
  "feature_snapshot_id": "snap_20220101",
  "status": "pass"
}
```

### 4c. Aggregate Summary

After all folds complete:

```json
{
  "strategy_id": "xgb_h5_v1.0.0",
  "n_folds": 8,
  "n_folds_pass": 6,
  "n_folds_fail": 1,
  "n_folds_insufficient_data": 1,
  "aggregate_win_rate": 0.548,
  "aggregate_win_rate_ci_95": [0.512, 0.584],
  "aggregate_profit_factor": 1.22,
  "aggregate_sharpe_ratio": 0.91,
  "aggregate_max_drawdown_pct": 12.1,
  "regime_coverage": {
    "bull_pre_covid": {"n_trades": 120, "win_rate": 0.58},
    "bear_stagflation": {"n_trades": 47, "win_rate": 0.53},
    "sideways_volatile": {"n_trades": 38, "win_rate": 0.49}
  },
  "promotion_eligible": true
}
```

---

## 5. Pass/Fail Thresholds for Promotion to Paper Trial

### 5a. Per-Fold Gates (minimum to avoid fold failure)

| Metric | Minimum to Pass Fold | Severity |
|--------|---------------------|----------|
| OOS win rate | ≥ 0.50 | P0 |
| OOS profit factor | ≥ 1.05 | P0 |
| OOS max drawdown | ≤ 20% | P0 |
| OOS fill rate | ≥ 0.90 | P1 |
| OOS avg slippage | ≤ 0.25% | P1 |

A fold is `fail` if **any P0 metric** is below threshold. A fold with P1 failures only is `warn`.

### 5b. Aggregate Promotion Gate (all folds combined)

| Requirement | Threshold | Applies To |
|-------------|-----------|-----------|
| Fold pass rate | ≥ 6/8 folds pass (or N-2/N for N folds) | Aggregate |
| Aggregate win rate lower CI bound | ≥ 0.48 | 95% Wilson CI |
| Aggregate profit factor | ≥ 1.10 | Aggregate |
| Aggregate Sharpe ratio | ≥ 0.50 | Aggregate |
| Aggregate max drawdown | ≤ 15% | Aggregate |
| Regime coverage (bull) | ≥ 50 OOS trades | Regime |
| Regime coverage (bear) | ≥ 30 OOS trades | Regime |
| No fold with `insufficient_data` > 3 | — | Count check |
| Strategy has NOT been re-trained after seeing test data | — | Process check |

**All gates must pass** for `promotion_eligible: true`. Any single P0 gate failure → `promotion_eligible: false`.

---

## 6. Overfitting Diagnostics and Rejection Criteria

### 6a. Train vs. OOS Performance Gap

Compute for each fold:

```
overfitting_score = (train_win_rate - oos_win_rate) / train_win_rate
```

| Overfitting Score | Classification | Action |
|-------------------|---------------|--------|
| < 0.10 | Low | Pass |
| 0.10 – 0.20 | Moderate | Warn; continue but flag |
| > 0.20 | High | Fail fold; investigate feature set |

If **aggregate** overfitting score > 0.15 across all folds, the strategy is **rejected** regardless of OOS metrics.

### 6b. Walk-Forward Degradation

Check whether OOS performance degrades monotonically as folds advance (a sign of concept drift or regime mismatch):

```python
fold_win_rates = [fold["win_rate"] for fold in sorted_folds]
degradation = fold_win_rates[0] - fold_win_rates[-1]
```

If `degradation > 0.15` (15 percentage point decline from first to last fold), flag as **drift suspect**. Requires explicit investigation before promotion.

### 6c. Hyperparameter Sensitivity

For XGBoost baseline: vary `max_depth` by ±1 and `n_estimators` by ±20% from optimal. If OOS win rate changes by > 5 percentage points, the model is **hyperparameter-sensitive** → reduce complexity.

### 6d. Random Seed Stability

Run the full walk-forward 3× with different random seeds (for any random components). If standard deviation of aggregate win rate across seeds > 3 percentage points, the result is **seed-unstable** → investigate feature randomness or re-examine purging logic.

---

## 7. Automated Protocol (Machine-Readable)

The experiment harness (P6 — Copilot task) must:

1. Run all 8 folds sequentially, emitting per-fold JSON as each completes
2. Compute aggregate summary with all metrics and `promotion_eligible` flag
3. Save outputs to `research/experiments/<experiment_id>/results/`:
   - `fold_F1.json` through `fold_F8.json`
   - `aggregate_summary.json`
   - `promotion_check.json` (boolean pass/fail per gate with reasoning)
4. Exit code 0 if `promotion_eligible: true`, exit code 1 otherwise

### 7a. promotion_check.json Schema

```json
{
  "experiment_id": "xgb_h5_v1_20240201",
  "evaluated_at": "2024-02-01T10:30:00Z",
  "promotion_eligible": false,
  "gates": [
    {"gate": "fold_pass_rate", "threshold": "6/8", "actual": "5/8", "passed": false},
    {"gate": "aggregate_win_rate_ci_lower", "threshold": 0.48, "actual": 0.461, "passed": false},
    {"gate": "aggregate_profit_factor", "threshold": 1.10, "actual": 1.08, "passed": false},
    {"gate": "regime_coverage_bear", "threshold": 30, "actual": 47, "passed": true}
  ],
  "rejection_reasons": [
    "fold_pass_rate: only 5/8 folds passed",
    "aggregate_win_rate_ci_lower: 0.461 < 0.48"
  ]
}
```

---

## 8. Protocol Summary

| Step | Action | Output |
|------|--------|--------|
| 1 | Define universe + date range | UK_UNIVERSE.md §2 |
| 2 | Generate features + labels per fold (no leakage) | features.parquet, labels.parquet per fold |
| 3 | Run expanding-window walk-forward (8 folds) | fold_F*.json |
| 4 | Check per-fold gates | pass/warn/fail per fold |
| 5 | Compute aggregate metrics + confidence intervals | aggregate_summary.json |
| 6 | Check overfitting + degradation diagnostics | overfitting_score per fold |
| 7 | Generate promotion_check.json | promotion_eligible: true/false |
| 8 | If eligible → create paper trial manifest | TRIAL_MANIFEST.md |

---

**References:**
- `research/specs/UK_UNIVERSE.md` — tradable universe
- `research/specs/FEATURE_LABEL_SPEC.md` — feature/label leakage-safe spec
- `config/test_regimes.json` — regime date ranges
- `docs/PROMOTION_FRAMEWORK.md` — Gate B (paper→live) criteria
- P6 prompt (`UK_STRATEGY_PROMPTS.md`) — experiment harness implementation
