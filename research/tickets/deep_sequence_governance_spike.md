# Deep-Sequence Model Governance Gate — Decision Memo

**Step**: 68
**Ticket**: (intake)
**Session**: ARCH-2026-02-26
**Decision**: ACCEPT — governance gate defined below

---

## 1. Summary

This document defines the minimum evidence and governance requirements for adding any sequence model architecture (CNN, LSTM, Transformer, or hybrid) beyond the current approved pipeline path (XGBoost → MLP → LSTM).

The existing Step 62 → Step 32 sequencing is **preserved and reinforced**. No new architecture may bypass the MLP gate. This gate applies to ALL model types not already in the backlog as of this date.

---

## 2. Minimum Evidence Requirements

Any proposal to add a new sequence model architecture must provide ALL of the following before implementation begins:

### 2a. Walk-Forward Validation Evidence

| Requirement | Threshold |
|---|---|
| Walk-forward folds | Minimum 5 folds, same configuration as XGBoost baseline |
| Out-of-sample PR-AUC | Must exceed current best model by ≥ 0.03 |
| Out-of-sample Sharpe | Must exceed current best model by ≥ 0.2 |
| Maximum drawdown | Must not exceed current best model's max DD by > 5% |
| Transaction cost inclusion | All evaluations must include 0.1% slippage + actual commission model |
| Stability across seeds | Results must be reproducible within ±0.02 PR-AUC across 3 random seeds |

### 2b. Data Volume Requirements

| Data Type | Minimum Volume |
|---|---|
| Daily bars | 2 years (≈504 trading days) per symbol |
| Hourly bars | 6 months (≈1,008 bars per symbol) — if model requires intraday features |
| Minimum symbols | 5 symbols from approved basket (config/test_baskets.json) |
| Train/test split | Walk-forward only; no single train/test split |

### 2c. Feature-Leakage Controls

1. **Sequence construction audit**: Verify that sequence windows do not include any future data points. Implement `assert sequence_end <= label_date - prediction_horizon`.
2. **Feature timestamp alignment**: All features must be stamped with the bar close time, not the bar open time.
3. **Target label isolation**: Target labels must be computed AFTER the prediction horizon with no overlap into the feature window.
4. **Cross-validation leakage**: Walk-forward folds must have non-overlapping train/val/test periods with gap equal to the sequence length.
5. **Automated leakage check**: Must pass `research/training/leakage_audit.py` (or equivalent) before any R2+ promotion claim.

### 2d. Compute Budget Constraints

| Constraint | Limit |
|---|---|
| Single-fold training time | ≤ 30 minutes on consumer GPU (RTX 3060 or equivalent) |
| Full walk-forward (5 folds) | ≤ 3 hours wall-clock |
| Maximum model parameters | 5M (prevents transformer scaling arms-race) |
| Memory footprint | ≤ 4 GB VRAM during training |
| Inference latency | ≤ 100ms per prediction (single symbol) |

### 2e. Promotion Thresholds Relative to Baselines

| Gate | XGBoost Baseline | MLP Baseline | New Model Requirement |
|---|---|---|---|
| R1 (hypothesis) | PR-AUC ≥ 0.55 | PR-AUC ≥ 0.55 | Must beat BOTH by ≥ 0.03 |
| R2 (walk-forward) | Sharpe ≥ 0.8 OOS | Sharpe ≥ 0.8 OOS | Must beat BOTH OOS Sharpe by ≥ 0.2 |
| R3 (paper trial) | 3 in-window sessions | 3 in-window sessions | Same requirement + side-by-side comparison with best baseline |
| R4 (live validation) | Human sign-off | Human sign-off | Same + additional risk review for model complexity |

---

## 3. Sequencing Decision

### Current approved pipeline path:

```
XGBoost (Step 25, completed)
  → MLP (Step 62, Opus-reviewed, Copilot-ready)
    → LSTM (Step 32, gated behind Step 62)
      → BTC LSTM Features (Step 57, gated behind Step 32)
```

### Recommendation on existing steps:

| Step | Status | Recommendation |
|---|---|---|
| Step 32 (LSTM) | NOT STARTED, gated | **KEEP** — preserve current gating behind Step 62 MLP |
| Step 57 (BTC LSTM features) | NOT STARTED | **KEEP** — feature engineering portion may proceed independently; training integration gated behind Step 32 |
| CNN track | Not in backlog | **NOT ADMITTED** — no evidence that CNN provides edge over LSTM for time-series financial data in this project's feature set |
| Transformer track | Not in backlog | **NOT ADMITTED** — parameter count and compute budget exceed §2d limits for consumer hardware; revisit only if Transformer-lite approach demonstrably fits within budget |
| Hybrid (e.g., CNN-LSTM) | Not in backlog | **NOT ADMITTED** — complexity not justified until single-architecture models exhaust improvement potential |

### New architecture admission process:

1. File a research ticket in `research/tickets/` with full evidence per §2a-§2e
2. Submit for Claude Opus review in an ARCH session
3. Receive explicit ADMIT/REJECT verdict with rationale
4. If ADMITTED: Create a backlog step following normal LPDD process
5. If REJECTED: Document rejection rationale; may re-apply with new evidence

---

## 4. Anti-Complexity Controls

1. **One active model track at a time**: Only one model architecture may be in active R2+ evaluation at any time. This prevents resource fragmentation and ensures proper comparison.
2. **Monotonic complexity**: New architectures must be evaluated against ALL simpler predecessors, not just the immediately prior one.
3. **Sunset clause**: If a model track fails to reach R2 within 90 days of admission, it is automatically suspended pending re-review.
4. **No ensemble before singles**: Multi-model ensembles (Step 32+ territory) may not be proposed until at least 2 individual models have independently reached R3.

---

## 5. References

- ADR-005: XGBoost before LSTM
- Step 62: MLP baseline specification (Opus-reviewed 2026-02-26)
- Step 32: LSTM baseline specification
- research/specs/ML_BASELINE_SPEC.md: Model governance specifications
- research/specs/RESEARCH_PROMOTION_POLICY.md: R1-R4 promotion path
- Step 65: Research claim-integrity gate

**Filed by**: Claude Opus (ARCH session 2026-02-26)
**Effective**: Immediately — applies to all new model architecture proposals
