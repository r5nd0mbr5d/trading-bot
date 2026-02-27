# BTC LSTM Feature Engineering Specification — Step 57

**Step**: 57
**Session**: ARCH-2026-02-26 (Claude Opus 4.6)
**ADR**: ADR-020
**Status**: APPROVED — Copilot-ready implementation contract

---

## 1. Inventory Table

| Item | Owner | Status | Blocker | Can Bundle |
|---|---|---|---|---|
| **Step 57** — BTC LSTM feature engineering | Copilot (feature eng) | NOT STARTED → **UNBLOCKED** (this decision) | None (feature engineering proceeds independently per deep-sequence governance §3) | Yes — self-contained |
| **Step 32** — LSTM baseline model | Opus (arch) → Copilot (impl) | NOT STARTED | Step 62 MLP performance gate (PR-AUC ≥ 0.55, Sharpe ≥ 0.8) + MO-7 + MO-8 evidence | No — separate gate |
| **MO-7** — R1/R2 research promotion evidence | Operator | ⏳ OPEN | Real walk-forward experiment results with dated artifact links | N/A — manual |
| **MO-8** — Production-run sign-off for FEATURE_LABEL_SPEC | Operator | ⏳ OPEN | Real experiment outputs + reviewer/date trace | N/A — manual |

**Conclusion**: Step 57 is unblocked for implementation. It produces feature engineering code and research configs only — no LSTM training integration. Step 32 remains separately gated.

---

## 2. Feature-Set Boundary Package

### 2a. Exact Timeframe Windows

All features operate on **daily OHLCV bars** (1D interval). Multi-timeframe is achieved via multiple lookback windows, not multiple bar intervals.

| Timeframe | Short | Medium | Long |
|---|---|---|---|
| Window (bars) | 5 | 20 | 60 |
| Calendar approx. | 1 week | 1 month | 3 months |
| Use case | Short-term momentum/reversal | Medium-term trend | Long-term regime |

**Rationale**: Daily bars avoid intraday noise (see ML_BASELINE_SPEC.md §1a: "XGBoost wins for daily OHLCV features"); multi-lookback windows capture the same indicator at different temporal scales, which is the core insight from zach1502's approach. Hourly/minute bars are explicitly out of scope for Step 57 — they require separate data pipeline work (see deep-sequence governance §2b: 6-month minimum for hourly bars).

### 2b. Exact Feature Families and Per-Family Rationale

**21 features total** across 7 families, computed at each of the 3 timeframes (short/medium/long) where applicable. Some features are computed once (not multi-timeframe).

#### Family 1: Trend (EMA-based) — 3 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `ema_{N}_pct` | `(close - EMA_N) / EMA_N` | 5, 20, 60 | Normalised distance from EMA; bounded; captures trend position at multiple scales |

**Why EMA over SMA**: EMA is more reactive to recent price action, important for crypto's fast regime shifts. Normalised to percentage of price for stationarity.

#### Family 2: Volatility (Bollinger + ATR) — 4 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `bb_pct_b_{N}` | Bollinger %B (period=N, std=2) | 20 | Mean-reversion signal; naturally bounded [0,1] with excursions |
| `atr_pct_{N}` | `ATR(N) / close × 100` | 5, 20, 60 | Volatility as % of price; bounded-range; key per Peng et al. 2022 |

**Why %B once only**: Bollinger %B at period 20 is the standard. Multi-timeframe ATR is more informative — short ATR vs long ATR reveals volatility acceleration.

#### Family 3: Momentum (RSI + Ultimate Oscillator) — 4 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `rsi_{N}` | RSI(period=N) | 5, 20 | Bounded [0,100]; standard momentum; two timeframes capture speed divergence |
| `uo_{7_14_28}` | Ultimate Oscillator(7,14,28) | once | Multi-period oscillator by design; already multi-timeframe internally |
| `roc_{N}` | `(close / close.shift(N) - 1) × 100` | 5, 20 | Rate of change; complements RSI with unbounded directional info |

**Why Ultimate Oscillator**: Built-in multi-period weighting (7/14/28) makes it naturally multi-timeframe. Reduces false signals vs single-period RSI per Larry Williams' design.

#### Family 4: Volume (OBV + A/D) — 3 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `obv_ratio_{N}` | `OBV / OBV.rolling(N).mean()` | 20, 60 | Normalised OBV trend; >1 = accumulation accelerating |
| `ad_ratio_{N}` | `A/D / A/D.rolling(N).mean()` | 20 | Accumulation/Distribution normalised; combines price position within bar with volume |

**Why normalised ratios**: Raw OBV/A/D are cumulative and non-stationary. Ratio to rolling mean creates a stationary, bounded signal.

#### Family 5: Money Flow (MFI + CMF) — 3 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `mfi_{N}` | Money Flow Index(period=N) | 14 | Bounded [0,100]; volume-weighted RSI; captures buying/selling pressure |
| `cmf_{N}` | Chaikin Money Flow(period=N) | 20, 60 | Zero-centered [-1,+1]; per Peng et al. 2022 recommendation; different indicator *category* reduces feature correlation |

**Why CMF added**: Peng et al. (2022, AishaRL) explicitly recommend CMF as a volume indicator alongside OBV, noting that different indicator categories (volatility, momentum, volume) minimise correlated features.

#### Family 6: Variance / Realised Vol — 2 features

| Feature | Formula | Timeframes | Rationale |
|---|---|---|---|
| `realised_vol_{N}` | `std(log_returns[-N:]) × sqrt(252)` | 5, 20 | Annualised realised volatility; two windows capture vol acceleration |

#### Family 7: Cross-Asset Context — 2 features (optional)

| Feature | Formula | Source | Rationale |
|---|---|---|---|
| `btc_vs_sp500_corr_20` | 20-day rolling correlation of BTC daily returns vs S&P 500 | External index | Regime indicator for "risk-on/risk-off" context |
| `btc_dominance_ratio` | BTC market cap / total crypto market cap (proxy: 20d EMA of BTC/ETH ratio) | BTC/ETH pair | Market-structure context |

**Note**: Family 7 features are optional and marked for later implementation (require additional data sources). Step 57 core scope is Families 1–6 (20 features).

### 2c. Summary

| Scope | Count | Note |
|---|---|---|
| Core features (Families 1–6) | **20** | Mandatory for Step 57 |
| Optional cross-asset (Family 7) | 2 | Deferred; needs additional data pipeline |
| **Total in step scope** | **20** | |

### 2d. Mandatory Normalization Policy

| Rule | Approach | Rationale |
|---|---|---|
| **All features** | Must be stationary or bounded-range | Non-stationary inputs degrade LSTM training stability |
| **Bounded indicators** (RSI, MFI, %B, CMF) | Use as-is (already bounded) | No additional normalization needed |
| **Percentage features** (EMA-pct, ATR-pct, ROC, realised-vol) | Clip at ±3σ training fold distribution | Prevents extreme outlier influence |
| **Ratio features** (OBV-ratio, A/D-ratio) | Clip at [0.5, 2.0] then min-max to [0,1] | Prevents extreme accumulation/distribution spikes |
| **Scaler fitting** | Fit ONLY on training fold; transform val/test with training stats | Per FEATURE_LABEL_SPEC §4 Trap 2 |
| **Missing data** | Drop rows with any NaN in required features; log count in manifest | Per FEATURE_LABEL_SPEC §7 null handling |

### 2e. Missing-Data Policy

| Scenario | Action |
|---|---|
| Insufficient bars for lookback (e.g., ATR_60 at bar 30) | Feature = `NaN`; row excluded from training; count logged |
| Volume = 0 on a bar | Set volume features to `NaN` for that bar; MFI/CMF undefined |
| Weekend/holiday gaps (crypto trades 24/7 but data may have gaps) | Forward-fill up to 3 bars max; if gap > 3 bars, set features to `NaN` |
| Exchange halt or data outage | Same as gap > 3 bars: `NaN` features for affected bars |

---

## 3. Leakage Control Package

### 3a. Prohibited Transformations

| Transformation | Why Prohibited |
|---|---|
| Future-looking indicators (e.g., centered MA, forward-fill from future data) | Directly uses future information |
| Full-dataset normalization (fit scaler on all data including test) | Leaks test distribution into training |
| Full-dataset threshold computation (percentiles on all returns) | Leaks test return distribution |
| Label-correlated feature construction (e.g., smoothed future return as "feature") | Direct target leakage |
| Lookahead-enriched regime tags (e.g., "this was a bear market" assigned post-hoc) | Hindsight bias |
| Cross-sectional features using symbols with survivorship issues | Survivorship leakage (per FEATURE_LABEL_SPEC §4 Trap 6) |

### 3b. Lookahead-Safe Construction Rules

1. **Feature timestamp rule**: Every feature at bar[t] uses ONLY data from bars [0…t]. No bar[t+1] or later data may enter any feature computation.

2. **Scaler rule**: `StandardScaler` (or any normalizer) must be fit ONLY on the training fold. Validation and test folds transform with the training fold's parameters.

3. **Threshold rule**: If any threshold is data-derived (e.g., clipping bounds), compute it from the training fold only.

4. **Sequence construction rule** (for later LSTM integration): If features are arranged into sequences of length L, the last timestamp in any sequence must be ≤ the decision point. `assert sequence[-1].timestamp <= label_decision_bar.timestamp`.

5. **Walk-forward gap rule**: Maintain a gap of ≥ `label_horizon` trading days between training end and validation start. For H5: gap ≥ 5 trading days.

6. **Crypto weekend rule**: Unlike equities, BTC trades continuously. Features computed over "5 trading days" for crypto should use 5 calendar days (or 5 actual bars if daily). Document the convention in the experiment config.

### 3c. Validation Checks to Enforce Leakage Guards

The following automated checks must be implemented in test code:

| Check ID | Description | Implementation |
|---|---|---|
| LG-01 | No feature computation accesses bar[t+1] or later | Unit test: mock OHLCV with known values; verify feature at bar N uses only bars [0…N] |
| LG-02 | Scaler fit isolation | Unit test: fit scaler on train, check that test data stats differ from scaler.mean_ |
| LG-03 | NaN handling audit | Unit test: introduce NaN at known positions; verify dropped row count matches expected |
| LG-04 | Feature count matches spec | Unit test: output DataFrame has exactly 20 columns (core features) |
| LG-05 | All timestamps UTC-aware | Unit test: assert `df.index.tz is not None` |
| LG-06 | No future data in sequence windows | Unit test (applies at LSTM integration, not Step 57): `max(sequence_timestamps) <= label_bar_timestamp` |
| LG-07 | Missing data forward-fill bounded | Unit test: insert 5-bar gap; verify bars 4-5 are NaN (max 3-bar ffill) |

---

## 4. Train/Validation Split Policy for Crypto Regime Shifts

### 4a. BTC Halving-Aware Splitting

Per Peng et al. 2022 recommendation: use **market-cycle-aware train/test splitting** at BTC halving dates rather than arbitrary date cutoffs.

| BTC Halving | Date | Block Reward After |
|---|---|---|
| 1st | 2012-11-28 | 25 BTC |
| 2nd | 2016-07-09 | 12.5 BTC |
| 3rd | 2020-05-11 | 6.25 BTC |
| 4th | 2024-04-19 | 3.125 BTC |

**Recommended walk-forward schedule for BTC research**:

| Fold | Train Start | Train End | Gap | Val Start | Val End | Test Start | Test End |
|---|---|---|---|---|---|---|---|
| F1 | 2017-01-01 | 2019-12-31 | 5d | 2020-01-08 | 2020-05-06 | 2020-05-12 | 2020-12-31 |
| F2 | 2017-01-01 | 2020-12-31 | 5d | 2021-01-08 | 2021-06-30 | 2021-07-08 | 2021-12-31 |
| F3 | 2017-01-01 | 2021-12-31 | 5d | 2022-01-07 | 2022-06-30 | 2022-07-08 | 2022-12-31 |
| F4 | 2017-01-01 | 2022-12-31 | 5d | 2023-01-07 | 2023-06-30 | 2023-07-08 | 2023-12-31 |
| F5 | 2017-01-01 | 2023-12-31 | 5d | 2024-01-07 | 2024-04-14 | 2024-04-20 | 2024-12-31 |

**Rationale**:
- Expanding window (not sliding) to maximise training data per deep-sequence governance §2b
- F1 test period straddles 3rd halving (2020-05-11) — validates pre/post-halving regime
- F5 test period straddles 4th halving (2024-04-19) — validates most recent regime shift
- 5-day gap between train/val boundaries (per FEATURE_LABEL_SPEC §6b, H5 horizon)
- Minimum 3 years training data in all folds (per deep-sequence governance §2b: 504+ trading days)

### 4b. Regime Tag Metadata

Each fold's `fold_F*.json` must include:

```json
{
  "regime_tags": {
    "train_spans_halving": false,
    "test_spans_halving": true,
    "dominant_market_regime": "bull|bear|sideways",
    "btc_price_range_usd": [9000, 29000]
  }
}
```

This metadata is informational only — not used in feature computation (would be leakage).

---

## 5. Output Schemas and Metadata for Step 32 Gating

### 5a. Feature Module Output Schema

`research/data/crypto_features.py` → `build_crypto_features(df: pd.DataFrame, config: dict) -> pd.DataFrame`

Output DataFrame columns:

```
ema_5_pct, ema_20_pct, ema_60_pct,
bb_pct_b_20, atr_pct_5, atr_pct_20, atr_pct_60,
rsi_5, rsi_20, uo_7_14_28, roc_5, roc_20,
obv_ratio_20, obv_ratio_60, ad_ratio_20,
mfi_14, cmf_20, cmf_60,
realised_vol_5, realised_vol_20
```

Index: UTC-aware DatetimeIndex (daily bars).

### 5b. Experiment Config Schema

`research/experiments/configs/btc_lstm_example.json`:

```json
{
  "experiment_id": "btc_lstm_features_v1",
  "model_type": "feature_engineering_only",
  "asset_class": "crypto",
  "symbols": ["BTC-GBP"],
  "feature_module": "research.data.crypto_features",
  "feature_config": {
    "short_window": 5,
    "medium_window": 20,
    "long_window": 60,
    "families": ["trend", "volatility", "momentum", "volume", "money_flow", "variance"],
    "max_ffill_bars": 3,
    "clip_sigma": 3.0
  },
  "split_policy": "btc_halving_aware",
  "horizon": "H5",
  "walk_forward_folds": 5,
  "gap_days": 5,
  "normalization": {
    "method": "train_fold_only",
    "clip_bounds": "training_fold_3sigma"
  }
}
```

### 5c. Metadata Required for Step 32 Gating

When Step 57 is COMPLETED, the following metadata must exist in the experiment output:

| Field | Location | Purpose |
|---|---|---|
| `feature_count` | `metadata.json` | Confirms exactly 20 features computed |
| `feature_names` | `metadata.json` | Explicit column list for downstream LSTM input dimension |
| `normalization_policy` | `metadata.json` | Documents scaler approach |
| `split_policy` | `metadata.json` | Documents BTC halving-aware split |
| `leakage_checks_passed` | `metadata.json` | Boolean; all LG-01 to LG-07 passed |
| `missing_data_report` | `metadata.json` | Counts of NaN rows dropped per fold |
| `fold_schedules` | `metadata.json` | Exact date ranges for each fold |

Step 32 implementation must read this metadata to set LSTM input dimension (`input_size = feature_count`) and validate that leakage checks passed before training.

---

## 6. Copilot Implementation Packet

### 6a. Files to Create

| File | Purpose |
|---|---|
| `research/data/crypto_features.py` | Core feature engineering module (20 indicators, multi-timeframe) |
| `research/experiments/configs/btc_lstm_example.json` | Experiment config for BTC LSTM feature engineering |
| `tests/test_crypto_features.py` | Feature engineering test suite |

### 6b. Files to Modify

| File | Change |
|---|---|
| `research/specs/FEATURE_LABEL_SPEC.md` | Add §3i "Crypto/BTC Feature Set" referencing this spec |
| `requirements.txt` | Verify `ta` library is present (already a dependency; no new deps needed for features) |

### 6c. Exact Tests to Add

In `tests/test_crypto_features.py`:

| Test | Description |
|---|---|
| `test_feature_count` | Output DataFrame has exactly 20 feature columns |
| `test_feature_names_match_spec` | Column names match §5a list exactly |
| `test_no_lookahead_ema` | EMA at bar N uses only data [0…N]; verified with hand-computed expected value |
| `test_no_lookahead_rsi` | RSI at bar N uses only close prices [0…N] |
| `test_no_lookahead_atr` | ATR at bar N uses only H/L/C [0…N] |
| `test_bounded_rsi` | RSI values in [0, 100] |
| `test_bounded_mfi` | MFI values in [0, 100] |
| `test_bounded_cmf` | CMF values in [-1, 1] |
| `test_nan_handling_insufficient_bars` | With 10 bars input, features requiring 60-bar lookback are NaN |
| `test_nan_rows_dropped_counted` | Drop count matches expected for given input size |
| `test_ffill_bounded_at_3` | Gap of 5 bars: bars 4-5 remain NaN after forward-fill |
| `test_utc_aware_index` | Output index has UTC timezone |
| `test_zero_volume_handling` | Volume=0 bars produce NaN for MFI/CMF/OBV features |
| `test_empty_dataframe_returns_empty` | Empty input returns empty output gracefully |

### 6d. Acceptance Criteria

1. `research/data/crypto_features.py` computes exactly 20 features per bar from daily OHLCV input
2. All features use only past/current data (no lookahead) — verified by LG-01 through LG-05 tests
3. Normalization is NOT applied in the feature module itself — raw (but bounded/clipped) features are output; scaler application is the harness's responsibility
4. Missing data follows policy: max 3-bar forward-fill, then NaN; dropped rows counted and reported
5. Experiment config `btc_lstm_example.json` is valid and parseable by existing config loader
6. `FEATURE_LABEL_SPEC.md` §3i references this spec and lists all 20 features
7. All 14 tests pass
8. No new runtime dependencies (all indicators via existing `ta` or `numpy`/`pandas`)
9. No imports from `src/` in `research/data/crypto_features.py`

### 6e. Non-Regression Checks

1. Existing feature tests (`tests/test_research_features.py` or equivalent) still pass — no changes to UK equity feature set
2. Full test suite (`python -m pytest tests/ -v`) passes with no new failures
3. `research/specs/FEATURE_LABEL_SPEC.md` §3a-§3h unchanged
4. No changes to `src/` directory
5. LPDD consistency gate passes

---

## 7. Blocker Register

| ID | Blocker | Blocks | Unblock Criteria |
|---|---|---|---|
| BLK-S57-01 | `ta` library must support all 7 feature families | Step 57 implementation | Verify: `ta.trend.EMAIndicator`, `ta.volatility.BollingerBands`, `ta.volatility.AverageTrueRange`, `ta.momentum.RSIIndicator`, `ta.momentum.UltimateOscillator`, `ta.volume.OnBalanceVolumeIndicator`, `ta.volume.AccDistIndexIndicator`, `ta.volume.MoneyFlowIndex`, `ta.volume.ChaikinMoneyFlowIndicator` — all exist in `ta>=0.10.0` |
| BLK-S57-02 | BTC daily OHLCV data availability via yfinance | Step 57 testing | Verify: `yfinance` can fetch `BTC-GBP` daily bars (or tests mock this) |
| BLK-S32-01 | Step 62 MLP performance gate not yet passed | Step 32 | MLP PR-AUC ≥ 0.55 AND Sharpe ≥ 0.8 on OOS folds |
| BLK-S32-02 | MO-7 evidence not committed | Step 32 | Operator commits R1/R2 residual evidence with dated artifact links |
| BLK-S32-03 | MO-8 evidence not committed | Step 32 | Operator commits production-run sign-off with reviewer/date trace |

---

## 8. Final Recommendation

**Proceed with Step 57 implementation using this specification — it is self-contained feature engineering work that produces a leakage-safe, bounded-range, multi-timeframe crypto feature set with full test coverage and explicit metadata for downstream LSTM gating, without modifying any runtime code or unblocking Step 32 prematurely.**

---

**Filed by**: Claude Opus 4.6 (ARCH session 2026-02-26)
**Effective**: Immediately — Step 57 moved to Copilot Immediately Actionable queue
