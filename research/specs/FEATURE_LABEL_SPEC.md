# Feature & Label Specification — Leakage-Safe Design

**Prompt:** P3 + R4a | **Author:** Claude Opus | **Date:** 2026-02-23
**Status:** APPROVED — canonical spec for all feature/label engineering in this research track

---

## 1. Core Design Principle

**No future information may enter any feature or label used in training.**

Leakage is the single largest source of inflated backtest performance. This specification enforces a strict temporal boundary at every step: features are computed from data available at the decision bar's **close**; labels are computed from data available only **after** the decision bar.

---

## 2. Horizon Definitions

### 2a. Classification Horizons

| Horizon ID | Forward Period | Use Case | Label Definition |
|------------|---------------|----------|-----------------|
| H1 | 1 trading day | Day-trading / overnight signal | Return > 0 → class 1; Return ≤ 0 → class 0 |
| H5 | 5 trading days (1 week) | Swing trading | Return > threshold → 1; Return < -threshold → -1; else 0 |
| H21 | 21 trading days (1 month) | Position trading | Return > threshold → 1; Return < -threshold → -1; else 0 |

**Default horizon for UK baseline**: H5 (5-day forward return). Matches LSE settlement cycle and typical swing-trade holding period.

### 2b. Regression Horizons

| Horizon ID | Forward Period | Target Variable |
|------------|---------------|-----------------|
| R1 | 1 day | Log return: log(close[t+1] / close[t]) |
| R5 | 5 days | Cumulative log return: log(close[t+5] / close[t]) |

### 2c. Threshold Selection

For multi-class classification (H5, H21), threshold is set per-symbol at the **training fold's** 33rd and 67th percentile of absolute returns to avoid look-ahead in threshold selection:

```
positive_threshold = np.percentile(train_fold_returns, 67)
negative_threshold = np.percentile(train_fold_returns, 33)
```

**Do not** use the full dataset's percentiles — that leaks test-period distribution into training labels.

### 2d. ThresholdLabel (Cost-Aware Binary Target)

For cost-aware binary classification experiments, use:

```
label = 1 if forward_return_bps > (round_trip_cost_bps + target_return_bps) else 0
```

Where:
- `round_trip_cost_bps` captures spread + commission assumptions for the venue
- `target_return_bps` captures minimum post-cost alpha requirement
- `threshold_bps = round_trip_cost_bps + target_return_bps`

Default threshold for baseline UK paper assumptions: `45 bps` (25 bps costs + 20 bps target).

---

## 3. Feature Families

All features are computed as of the **bar[t] close** using only data from bars [0 … t].

### 3a. Price Features

| Feature | Formula | Lookback | Notes |
|---------|---------|----------|-------|
| log_return_1d | log(close[t] / close[t-1]) | 1 | Winsorise at ±5σ |
| log_return_5d | log(close[t] / close[t-5]) | 5 | — |
| log_return_21d | log(close[t] / close[t-21]) | 21 | — |
| price_vs_ma20 | (close[t] - MA20[t]) / MA20[t] | 20 | Normalised |
| price_vs_ma50 | (close[t] - MA50[t]) / MA50[t] | 50 | Normalised |
| price_vs_ma200 | (close[t] - MA200[t]) / MA200[t] | 200 | Normalised |
| bb_pct_b | Bollinger %B position | 20, 2σ | In [0,1] naturally |
| high_low_range | (high - low) / close | 1 | Daily range normalised |
| gap_up | (open[t] - close[t-1]) / close[t-1] | 1 | Overnight gap |

### 3b. Volume Features

| Feature | Formula | Lookback | Notes |
|---------|---------|----------|-------|
| volume_ratio_20d | volume[t] / MA_volume_20[t] | 20 | >1 = above-average activity |
| obv_normalised | OBV[t] / MA_OBV_50[t] | 50 | On-Balance Volume trend |
| volume_price_trend | VPT normalised | 14 | Price×Volume directional |

### 3c. Volatility Features

| Feature | Formula | Lookback | Notes |
|---------|---------|----------|-------|
| atr_pct | ATR[t] / close[t] × 100 | 14 | Volatility as % of price |
| realised_vol_5d | std(log_returns[-5:]) × √252 | 5 | Annualised short-term vol |
| realised_vol_21d | std(log_returns[-21:]) × √252 | 21 | Annualised medium-term vol |
| vol_regime | realised_vol_5d / realised_vol_21d | — | Volatility acceleration ratio |
| adx | ADX[t] | 14 | Trend strength (no direction) |

### 3d. Momentum / Oscillator Features

| Feature | Formula | Lookback | Notes |
|---------|---------|----------|-------|
| rsi_14 | RSI[t] | 14 | In [0,100] |
| macd_hist | MACD histogram[t] | 12/26/9 | Normalise by price |
| stoch_k | Stochastic %K[t] | 14, 3 | In [0,100] |
| cci_20 | CCI[t] | 20 | Normalise by 100σ convention |
| roc_5 | (close[t] / close[t-5] - 1) × 100 | 5 | Rate of change % |
| roc_21 | (close[t] / close[t-21] - 1) × 100 | 21 | — |

### 3e. Regime Features

| Feature | Formula | Source | Notes |
|---------|---------|--------|-------|
| market_return_5d | Log return of ISF.L over 5 days | Index ETF | Market trend context |
| market_return_21d | Log return of ISF.L over 21 days | Index ETF | — |
| beta_20d | Rolling 20-day beta vs ISF.L | Regression | Market sensitivity |
| sector_return_5d | Sector ETF 5-day return | Sector basket | Sector momentum |
| vix_proxy | 21-day realised vol of ISF.L | Index vol | Market fear proxy |

### 3f. Cross-Sectional Features (Expanded Universe Only)

| Feature | Formula | Notes |
|---------|---------|-------|
| cs_rank_return_5d | Percentile rank of 5d return within universe | Z-score or rank [0,1] |
| cs_rank_vol | Percentile rank of realised vol within universe | — |
| cs_rank_rsi | Percentile rank of RSI within universe | — |

**Cross-sectional features require** simultaneous computation across all universe symbols. They introduce a subtle leakage risk if any symbol in the cross-section has survivorship issues. Document carefully.

### 3g. News/Sentiment Features

| Feature | Type | Definition | Notes |
|---------|------|------------|-------|
| sentiment_score | float | Mean sentiment for symbol/day using Polygon `insights[].sentiment` mapped as `positive=+1`, `neutral=0`, `negative=-1` | `NaN` when no news articles for that symbol/day |
| article_count | int | Count of all news articles for symbol/day across all publishers | `0` when no articles |
| benzinga_count | int | Count of symbol/day articles where `publisher.name == "Benzinga"` | `0` when no Benzinga articles |
| earnings_proximity | bool | `True` when the date is within ±3 calendar days of any article containing the token `"earnings"` in title/description in the fetched window | `False` otherwise |

**Join key and index contract**
- Output frame index is a UTC-aware `DatetimeIndex` with date-only granularity (`00:00:00+00:00`).
- Feature family joins to the main feature table by `(symbol, date)`; `date` must align with bar-close date index.
- Source endpoint: `GET /v2/reference/news` (Polygon/Massive free tier) with Bearer auth.

### 3h. Optional UK Sentiment Validation Note (Step 69)

- Step 69 evaluates sentiment utility as an **offline research ticket only**.
- Candidate paths:
  1. Massive/Polygon news sentiment features (existing integration path)
  2. Free/low-cost RSS headline ingestion + deterministic lexicon scoring
- Promotion criteria for enabling sentiment in baseline research flow:
  - PR-AUC improvement of at least `+0.02` versus baseline
  - max drawdown deterioration not worse than `5%` versus baseline
- No runtime (`src/`) feature additions are allowed under Step 69 without a follow-on approved ticket.

### 3i. Crypto/BTC Feature Set (Step 57 — ADR-020)

| Feature | Family | Formula | Lookback | Bounded Range |
|---------|--------|---------|----------|---------------|
| `ema_5_pct` | Trend | `(close - EMA_5) / EMA_5` | 5 | ±few % |
| `ema_20_pct` | Trend | `(close - EMA_20) / EMA_20` | 20 | ±few % |
| `ema_60_pct` | Trend | `(close - EMA_60) / EMA_60` | 60 | ±few % |
| `bb_pct_b_20` | Volatility | Bollinger %B(20, 2σ) | 20 | [0,1] with excursions |
| `atr_pct_5` | Volatility | `ATR(5) / close × 100` | 5 | % |
| `atr_pct_20` | Volatility | `ATR(20) / close × 100` | 20 | % |
| `atr_pct_60` | Volatility | `ATR(60) / close × 100` | 60 | % |
| `rsi_5` | Momentum | RSI(5) | 5 | [0,100] |
| `rsi_20` | Momentum | RSI(20) | 20 | [0,100] |
| `uo_7_14_28` | Momentum | Ultimate Oscillator(7,14,28) | 28 | [0,100] |
| `roc_5` | Momentum | `(close/close.shift(5) - 1) × 100` | 5 | % |
| `roc_20` | Momentum | `(close/close.shift(20) - 1) × 100` | 20 | % |
| `obv_ratio_20` | Volume | `OBV / OBV.rolling(20).mean()` | 20 | ratio |
| `obv_ratio_60` | Volume | `OBV / OBV.rolling(60).mean()` | 60 | ratio |
| `ad_ratio_20` | Volume | `A/D / A/D.rolling(20).mean()` | 20 | ratio |
| `mfi_14` | Money Flow | MFI(14) | 14 | [0,100] |
| `cmf_20` | Money Flow | CMF(20) | 20 | [-1,+1] |
| `cmf_60` | Money Flow | CMF(60) | 60 | [-1,+1] |
| `realised_vol_5` | Variance | `std(log_returns[-5:]) × √252` | 5 | annualised % |
| `realised_vol_20` | Variance | `std(log_returns[-20:]) × √252` | 20 | annualised % |

**Full specification**: `research/specs/BTC_LSTM_FEATURE_SPEC.md`
**ADR**: ADR-020
**Leakage controls**: 7 automated checks (LG-01 to LG-07); see spec §3
**Split policy**: BTC halving-aware expanding-window walk-forward (5 folds)
**Normalization**: Bounded indicators as-is; %-based features clip at ±3σ training fold; scaler fit on training fold only

---

## 4. Leakage Traps and Mitigation Rules

### Trap 1: Label computed using close[t]
**Problem**: if H1 label = sign(close[t+1] - close[t]) and close[t] is also a feature, the model sees the last price used in its own target.
**Mitigation**: labels use **strictly future** bars. For H1, label = sign(close[t+1] - close[t]). Feature `log_return_1d` uses close[t-1] → close[t]. These are distinct bars.

### Trap 2: Scaling / normalisation fitted on full dataset
**Problem**: StandardScaler fitted on full dataset leaks test mean/std into training features.
**Mitigation**: fit scaler **only on training fold**, transform validation and test folds with training statistics. Re-fit scaler for each walk-forward fold.

### Trap 3: Threshold percentiles computed on full dataset
**Problem**: computing classification threshold on full return series leaks future distribution.
**Mitigation**: compute thresholds on training fold only (see Section 2c).

### Trap 4: Rolling windows crossing train/test boundary
**Problem**: a 200-day MA at the first test bar uses the last 200 training bars — valid. But if the test bar is bar[201], the 200-day MA includes bar[1]…bar[200] which are training bars only — no leak.
**Clarification**: rolling features computed from historical data only are **not** leakage. The boundary is the label horizon, not the feature lookback.

### Trap 5: Point-in-time data issues
**Problem**: using total-return adjusted prices recalculated after the fact (e.g., subsequent splits applied retroactively).
**Mitigation**: use yfinance `auto_adjust=True` which applies adjustments forward. Document adjustment convention in snapshot metadata. Validate that adjusted prices are monotonically consistent.

### Trap 6: Survivorship bias in universe construction
**Problem**: backtesting on today's FTSE 100 constituents for 2018 data excludes companies that were delisted between 2018 and today.
**Mitigation**: acknowledge this limitation explicitly in all research reports. For the MVU, the core 10 FTSE 100 symbols are stable names with continuous listing. Flag any symbol that was added to FTSE 100 after 2018.

### Trap 7: Cross-sectional ranking with missing data
**Problem**: if some symbols have missing bars, ranking at time t uses only available symbols — this is fine operationally but must be handled consistently.
**Mitigation**: require all cross-sectional features to use a fixed symbol set per fold. Drop a symbol from a fold's cross-section if it has missing data.

---

## 5. Class Imbalance Handling

### 5a. Expected Imbalance

For H5 classification with thresholds at 33rd/67th percentile:
- Class +1 (up): ~33% of bars
- Class 0 (neutral): ~34% of bars
- Class -1 (down): ~33% of bars

For binary classification (H1):
- Class 1 (positive return): ~50% of bars (efficient market prior; may shift in trending regimes)

### 5b. Handling Strategies

| Strategy | When to Use | Implementation |
|----------|-------------|----------------|
| Class weights (`class_weight='balanced'`) | Default for XGBoost/sklearn | Passes `scale_pos_weight` or `class_weight` |
| Oversampling (SMOTE) | Only if class ratio > 3:1 | Apply only within training fold; never to validation/test |
| Threshold adjustment | Always | Tune decision threshold on validation fold, not test |
| No undersampling | Never by default | Removes potentially valuable data |

**Rule**: oversample or reweight **only on training fold**. Apply resulting model to validation/test without resampling.

### 5c. Neutral Class Handling

For 3-class problems, the neutral class (0) is the hardest to learn. Options:
1. **Keep 3 classes**: train a 3-class classifier; accept low accuracy on class 0.
2. **Reduce to 2 classes**: label only top/bottom tertile; exclude neutral bars from training (but include in test for fair evaluation).

**Default**: option 2 (binary, exclude neutral from training) for the baseline model. Document this choice in experiment metadata.

---

## 6. Validation Split Strategy

Compatible with the walk-forward protocol defined in `research/specs/VALIDATION_PROTOCOL.md`.

### 6a. Forbidden Patterns

| Pattern | Why Forbidden |
|---------|---------------|
| Random shuffle + train/test split | Future bars in train; temporal dependency broken |
| K-fold cross-validation without time ordering | Same as above |
| Gap between train and test < label horizon | Test labels overlap with train |

### 6b. Required Pattern: Expanding Window Walk-Forward

```
Fold 1: Train [2018-01 → 2020-12] | Val [2021-01 → 2021-06] | Test [2021-07 → 2021-12]
Fold 2: Train [2018-01 → 2021-06] | Val [2021-07 → 2021-12] | Test [2022-01 → 2022-06]
...
```

**Gap rule**: there must be a gap of **≥ label_horizon** days between train end and val start to prevent label leakage at the boundary.

For H5 (5-day horizon): min gap = 5 trading days.

### 6c. Purging and Embargo

| Concept | Rule |
|---------|------|
| Purge | Remove training samples within `label_horizon` days of the train/val boundary |
| Embargo | Do not use validation samples within `label_horizon` days of the val/test boundary as training data in the next fold |

---

## 7. Feature Schema (Implementation-Ready)

Output of `research/data/features.py` must conform to this schema:

```python
@dataclass
class FeatureRow:
    symbol: str           # e.g. "SHEL.L"
    date: pd.Timestamp    # bar close date, UTC-aware
    # Price features
    log_return_1d: float
    log_return_5d: float
    log_return_21d: float
    price_vs_ma20: float
    price_vs_ma50: float
    price_vs_ma200: float
    bb_pct_b: float
    high_low_range: float
    gap_up: float
    # Volume features
    volume_ratio_20d: float
    obv_normalised: float
    # Volatility features
    atr_pct: float
    realised_vol_5d: float
    realised_vol_21d: float
    vol_regime: float
    adx: float
    # Momentum features
    rsi_14: float
    macd_hist: float
    stoch_k: float
    roc_5: float
    roc_21: float
    # Regime features (optional; None if index data unavailable)
    market_return_5d: Optional[float]
    market_return_21d: Optional[float]
    beta_20d: Optional[float]
```

**Null handling**: features requiring more bars than available (e.g. MA200 on day 50) must be `NaN`. Rows with any required feature as NaN are dropped from training but **recorded** in the snapshot manifest so the drop is auditable.

---

## 8. Label Schema

Output of `research/data/labels.py` must conform to this schema:

```python
@dataclass
class LabelRow:
    symbol: str
    date: pd.Timestamp    # decision date (bar[t] close)
    horizon: str          # "H1", "H5", "H21"
    forward_return: float # raw log return over horizon
    label_binary: int     # 0 or 1 (H1 default)
    label_ternary: int    # -1, 0, or 1 (H5/H21 default)
    label_threshold_pos: float  # threshold used for positive class
    label_threshold_neg: float  # threshold used for negative class
    fold_id: int          # which walk-forward fold generated this label
```

**Critical**: `label_binary` and `label_ternary` must be generated **after** train/val/test split, using only the training fold's distribution for threshold computation. Never pre-compute labels on the full dataset.

---

## 9. Implementation Checklist

When implementing `features.py` and `labels.py` (P4 — Copilot task), verify:

- [x] All features use only data available at or before bar[t] close
- [x] Labels use only data from bars strictly after bar[t]
- [x] Scaler is fit only on training fold; transforms applied to val/test without refitting
- [x] Thresholds computed only on training fold returns
- [x] Gap of ≥ `label_horizon` days enforced between train and val/test boundaries
- [x] NaN rows dropped and logged; count available in snapshot manifest
- [x] `symbol` + `date` form a unique key per row (no duplicates)
- [x] All timestamps UTC-aware (consistent with runtime data model)
- [x] Feature computation seeds set for reproducibility where randomness applies
  - Policy: all deterministic transforms (MA, RSI, ATR, etc.) need no seed. Stochastic operations (SMOTE oversampling, bootstrap confidence intervals, cross-sectional tie-breaking) use `RANDOM_SEED = 42` passed explicitly via config. Validated: current `features.py` and `labels.py` implementations are fully deterministic; no SMOTE is applied at the feature stage.
- [x] Cross-sectional features recomputed per fold with fixed symbol set

---

**References:**
- `research/specs/VALIDATION_PROTOCOL.md` — walk-forward schedule
- `research/specs/UK_UNIVERSE.md` — tradable universe definition
- `config/test_regimes.json` — historical regime date ranges for fold selection
- P4 prompt (`UK_STRATEGY_PROMPTS.md`) — feature/label module implementation
