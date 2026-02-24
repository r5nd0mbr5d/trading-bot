# ML Baseline Stack Specification

**Prompt:** P7 | **Author:** Claude Opus | **Date:** 2026-02-23
**Status:** APPROVED — canonical model governance spec for the UK-first research track

---

## 1. Model Choice Rationale

### 1a. Primary Baseline: XGBoost Classifier

**Chosen as the baseline** for these reasons:

| Criterion | XGBoost | Alternative | Decision |
|-----------|---------|-------------|----------|
| Tabular data performance | Excellent (SOTA benchmark winner) | LSTM (sequential) | XGBoost wins for daily OHLCV features |
| Interpretability | Feature importance; SHAP values | LSTM: black box | XGBoost required for governance |
| Overfitting control | Built-in L1/L2 regularisation + early stopping | LSTM: more prone | XGBoost more conservative |
| Training speed | Minutes (CPU) | LSTM: hours (GPU preferred) | XGBoost faster iteration |
| Small-data performance | Good (works with 500+ samples) | LSTM: needs thousands | XGBoost better for MVU regime sizes |
| Hyperparameter sensitivity | Moderate; well-understood | LSTM: high | XGBoost more stable |

**Conclusion**: XGBoost is the safer, more auditable baseline. Use it to establish a performance floor before considering LSTM.

### 1b. Optional Extension: LSTM (Sequence Model)

Include **only** if:
- XGBoost baseline clears all promotion gates
- The hypothesis requires explicit sequence modelling (e.g. multi-day pattern recognition)
- Training compute budget allows ≥ 10 epochs with validation monitoring
- A GPU is available for viable training time

LSTM spec in this document is a scaffold only — it is not required for initial paper-trial promotion.

### 1c. What We Are Not Doing (and Why)

| Excluded | Reason |
|---------|--------|
| Deep neural networks (MLP / Transformer) | Overkill for 15-symbol daily data; explainability gap |
| Reinforcement learning | Requires much longer training horizon; unstable in low-data regimes |
| Online learning (incremental update) | Too complex for initial governance framework; batched retraining preferred |
| Ensemble voting across ML models | Introduce only after individual models are validated independently |

---

## 2. XGBoost Baseline Configuration

### 2a. Recommended Hyperparameters (starting point)

```python
xgb_params = {
    "objective": "binary:logistic",   # binary classification (H5 positive/negative)
    "n_estimators": 300,
    "max_depth": 4,                   # shallow trees → less overfitting
    "learning_rate": 0.05,
    "subsample": 0.8,                 # row subsampling
    "colsample_bytree": 0.8,          # feature subsampling per tree
    "min_child_weight": 10,           # min samples per leaf
    "reg_alpha": 0.1,                 # L1 regularisation
    "reg_lambda": 1.0,                # L2 regularisation
    "scale_pos_weight": 1.0,          # set to neg_count/pos_count if imbalanced
    "eval_metric": ["logloss", "auc"],
    "early_stopping_rounds": 30,
    "random_state": 42,
    "n_jobs": -1,
}
```

### 2b. Hyperparameter Tuning

Use `Optuna` (or manual grid) with the following search space on the **validation fold only**:

| Parameter | Search Range |
|-----------|-------------|
| `max_depth` | [3, 4, 5] |
| `learning_rate` | [0.01, 0.05, 0.1] |
| `n_estimators` | [100, 300, 500] |
| `subsample` | [0.7, 0.8, 0.9] |
| `min_child_weight` | [5, 10, 20] |

**Rule**: tune hyperparameters on the validation fold. Lock the best config and re-train on train+val before evaluating on the test fold. Never tune on the test fold.

### 2c. Feature Importance Governance

After each fold training, record top-20 features by SHAP value. Flag if:
- A single feature accounts for > 40% of SHAP importance (over-reliance)
- SHAP importance ranking changes substantially (> 5 positions in top 10) between consecutive folds (instability signal)

---

## 3. Calibration and Thresholding Policy

### 3a. Probability Calibration

XGBoost's raw `predict_proba` outputs are not guaranteed to be well-calibrated. Apply Platt scaling (sigmoid calibration) on the **validation fold**:

```python
from sklearn.calibration import CalibratedClassifierCV

calibrated_model = CalibratedClassifierCV(
    base_model,
    method="sigmoid",
    cv="prefit"   # use pre-fit XGBoost
)
calibrated_model.fit(X_val, y_val)
```

Evaluate calibration with a reliability diagram. If Brier score improvement > 0.02 on validation, apply calibration; otherwise skip (raw XGBoost may be adequate).

### 3b. Decision Threshold Policy

Default threshold is 0.5 (standard binary). Adjust **only** on the validation fold:

```python
from sklearn.metrics import precision_recall_curve

precision, recall, thresholds = precision_recall_curve(y_val, y_prob_val)
# Choose threshold that maximises F1 on validation set
optimal_threshold = thresholds[np.argmax(2 * precision * recall / (precision + recall))]
```

**Constraints on threshold adjustment:**
- Must not push precision below 0.45 (too many false positives → over-trading)
- Must not push recall below 0.30 (too few trades → insufficient sample size)
- Lock threshold at validation-fold optimum; apply unchanged to test fold

### 3c. Output Schema

Model output per bar is:

```python
@dataclass
class ModelPrediction:
    symbol: str
    date: pd.Timestamp
    raw_prob: float          # uncalibrated XGBoost output
    calibrated_prob: float   # post-Platt scaling
    predicted_class: int     # 0 or 1 after threshold
    confidence_band: str     # "high" (>0.65), "medium" (0.55-0.65), "low" (<0.55)
    model_version: str
    fold_id: str
```

---

## 4. Feature Stability / Drift Monitoring Requirements

### 4a. Population Stability Index (PSI)

Monitor feature distributions in live paper trading vs. training distribution using PSI:

```
PSI = Σ (actual_pct - expected_pct) × ln(actual_pct / expected_pct)
```

| PSI Value | Interpretation | Action |
|-----------|---------------|--------|
| < 0.10 | No drift | Continue |
| 0.10 – 0.25 | Moderate drift | Warn; review |
| > 0.25 | Significant drift | Flag for retraining review |

Compute PSI weekly during paper trial for the top-10 SHAP features. Store results in the audit log with event type `feature_drift_psi`.

### 4b. Prediction Distribution Monitoring

Track rolling distribution of `calibrated_prob` outputs over a 20-day window in paper trading:

- Expected mean ≈ 0.50 (efficient market prior)
- Expected standard deviation: typically 0.08–0.15 for a useful model

If rolling mean of calibrated_prob drifts to < 0.40 or > 0.60 over a 20-day window, emit `model_prediction_drift` event to audit log and trigger a manual review.

### 4c. Confidence Degradation Alert

If the 5-day rolling rate of `confidence_band == "low"` predictions exceeds 70%, emit `model_confidence_degraded` audit event. This indicates the model has low conviction and fill quality may suffer.

---

## 5. Fail-Safe Fallback Behavior

When model confidence degrades or monitoring alerts trigger, the system must fall back gracefully rather than continue trading on unreliable predictions.

### 5a. Fallback Levels

| Trigger | Fallback Action | Recovery Condition |
|---------|----------------|-------------------|
| `feature_drift_psi > 0.25` on any top-5 feature | Reduce position size by 50% | PSI returns to < 0.10 for 5 consecutive days |
| `model_confidence_degraded` event | Halt new entries from ML strategy; do not close existing positions | Manual reviewer approval required |
| `model_prediction_drift` event (mean < 0.40 or > 0.60) | Pause ML strategy; notify operator | Manual review + optional retraining |
| Any fold in online monitoring has OOS win rate < 0.45 over 20 trades | Trigger kill switch for ML strategy only | Must pass paper trial gates again after retraining |
| PSI > 0.50 on > 3 features simultaneously | Full strategy halt; emit `ml_strategy_emergency_halt` | Retraining required; new paper trial cycle |

### 5b. Fallback to Rule-Based Signal

If the ML strategy is halted, the runtime should:
1. Log the halt event with full context to audit log
2. Optionally activate the nearest rule-based strategy (`bollinger_bands` or `ma_crossover`) if approved for paper
3. Never automatically re-activate the ML strategy without operator confirmation

### 5c. No Silent Failures

Any fallback event must:
- Be logged to the audit log with event type and timestamp
- Appear in the next paper session summary report
- Require explicit operator acknowledgement before the ML strategy can resume

---

## 6. Evidence Required Before Candidate Promotion

A research ML candidate must provide all of the following before the promotion checklist is submitted:

### 6a. Required Evidence Bundle

| Item | File / Location | Required |
|------|----------------|---------|
| Walk-forward results (all folds) | `research/experiments/<id>/results/fold_F*.json` | Mandatory |
| Aggregate summary | `research/experiments/<id>/results/aggregate_summary.json` | Mandatory |
| Promotion gate check | `research/experiments/<id>/results/promotion_check.json` with `promotion_eligible: true` | Mandatory |
| Feature importance (SHAP) per fold | `research/experiments/<id>/shap/fold_F*.json` | Mandatory |
| Calibration curve | `research/experiments/<id>/calibration/` | Mandatory |
| Data snapshot ID | Referenced in experiment metadata | Mandatory |
| Reproducibility proof | Re-run with same seed produces identical metrics (script + log) | Mandatory |
| PSI baseline distribution | `research/experiments/<id>/feature_baselines.json` | Mandatory (for drift monitoring) |
| Overfitting score per fold | Present in fold_F*.json | Mandatory |
| Seed stability test | 3× runs with different seeds; stddev < 3pp win rate | Mandatory |
| LSTM results (if applicable) | Same structure as above | Optional |

### 6b. Paper Trial Thresholds (Higher Bar than Research Gates)

After walk-forward, the strategy enters a paper trial. Thresholds here are **stricter** than research gates because the strategy is now operating on live market data:

| Metric | Research Gate | Paper Trial Threshold |
|--------|-------------|----------------------|
| Win rate | ≥ 0.50 aggregate | ≥ 0.52 (20+ closed paper trades) |
| Profit factor | ≥ 1.10 | ≥ 1.15 |
| Fill rate | ≥ 0.90 | ≥ 0.93 |
| Avg slippage | ≤ 0.25% | ≤ 0.20% |
| Min closed trades | 100 OOS | 30 paper trades |

Paper trial thresholds are enforced by `paper_readiness_failures()` in `src/strategies/registry.py`.

---

## 7. LSTM Scaffold (Optional Extension)

If XGBoost passes all gates and an LSTM extension is warranted:

### 7a. Architecture

```python
class LSTMStrategy(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
```

### 7b. LSTM-Specific Governance Rules

- Sequence length: 20 bars (1 calendar month)
- No data normalisation across sequences (normalise within each sequence)
- Use Teacher Forcing only during training; never during inference
- Minimum training epochs: 20 with early stopping on val loss (patience=10)
- Artifact: save `.pt` weights + architecture config JSON; verify SHA256 on load (existing registry handles this)

---

## 8. Summary

| Parameter | Value |
|-----------|-------|
| Primary model | XGBoost classifier |
| Default horizon | H5 (5-day forward return) |
| Calibration | Platt scaling on validation fold |
| Threshold tuning | F1-optimal on validation fold; locked for test |
| Drift metric | PSI weekly on top-10 features |
| Fallback | Position size reduction → halt → kill switch |
| Evidence required | 11-item bundle (see §6a) |
| LSTM | Optional extension after XGBoost passes all gates |

---

**References:**
- `research/specs/FEATURE_LABEL_SPEC.md` — feature definitions
- `research/specs/VALIDATION_PROTOCOL.md` — walk-forward protocol
- `research/specs/RESEARCH_PROMOTION_POLICY.md` — promotion gates
- `src/strategies/registry.py` — `paper_readiness_failures()` and `promote()` with checklist gate
- `docs/PROMOTION_FRAMEWORK.md` — institutional promotion framework
- P8 prompt (`UK_STRATEGY_PROMPTS.md`) — training/eval pipeline implementation
