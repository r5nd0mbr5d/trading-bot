# UK-Focused Paper Test Plan

> **Version:** 1.0.0
> **Date:** 2026-02-23
> **Scope:** UK equities (LSE) paper trading validation
> **Symbol Baskets:** `config/test_baskets.json`
> **Market Regimes:** `config/test_regimes.json`
> **Applies To:** All strategies under `approved_for_paper` status on IBKR paper account

---

## 1. Purpose

This document defines a statistically rigorous paper test plan for validating algorithmic trading strategies against UK equities traded on the London Stock Exchange (LSE). It specifies:

- **Market regimes** to test across (bull, bear, sideways, volatile, crisis)
- **Symbol baskets** by market cap and sector
- **Session timing** rules for GMT/BST transitions
- **Statistical significance** requirements before conclusions can be drawn
- **Pass/fail thresholds** per regime and basket

The plan is directly runnable using the existing `paper_trial` + manifest system. See section 7 for CLI commands.

---

## 2. UK Market Context

### 2.1 Exchange Details

| Parameter | Value |
|-----------|-------|
| Exchange | London Stock Exchange (LSE) |
| Trading Hours | 08:00–16:30 GMT (winter) / BST (summer) |
| Pre-market / After-hours | Not available for retail LSE paper trading |
| Symbol suffix | `.L` (e.g., `BARC.L`, `SHEL.L`) |
| Settlement | T+2 |
| Base Currency | GBP (£) |
| UK market hours code | `LSE` (see `src/execution/market_hours.py`) |

### 2.2 GMT vs BST Transition Risk

The UK observes British Summer Time (BST = UTC+1) from the last Sunday of March to the last Sunday of October:

| Period | Offset | LSE Open | LSE Close |
|--------|--------|----------|-----------|
| BST (summer) | UTC+1 | 07:00 UTC | 15:30 UTC |
| GMT (winter) | UTC+0 | 08:00 UTC | 16:30 UTC |

**Risk:** Strategies that hardcode session windows in UTC will trade at incorrect times during DST transitions. All session timing must use `market_hours.py` `is_market_open()` which handles this automatically.

**Test requirement:** Run at least one trial that straddles a GMT↔BST boundary (last Sunday of March or October). Relevant regime periods are flagged in `config/test_regimes.json`.

### 2.3 US Market Overlap

| Period | Times (GMT) | Notes |
|--------|------------|-------|
| LSE only | 08:00–13:00 | Lower liquidity for US-cross instruments |
| Overlap (LSE + NYSE) | 13:00–16:30 | Highest liquidity; US news can move UK indices |
| US only (after LSE close) | 14:30–21:00 | No LSE trading; hold-overnight risk |

**Recommendation:** Run at least two trials — one covering LSE-only hours and one covering the overlap window — to measure strategy performance difference.

---

## 3. Symbol Baskets

Full basket definitions are in `config/test_baskets.json`. Summary:

### 3.1 Blue-Chip Basket (FTSE 100)

**Purpose:** Highest liquidity, tightest spreads, most institutional coverage. Ideal for initial strategy validation.

**Minimum size for statistical validity:** 10 symbols

| Symbol | Company | Sector |
|--------|---------|--------|
| SHEL.L | Shell plc | Energy |
| AZN.L | AstraZeneca | Pharma |
| HSBA.L | HSBC Holdings | Banking |
| ULVR.L | Unilever | Consumer |
| BP.L | BP | Energy |
| GSK.L | GSK plc | Pharma |
| RIO.L | Rio Tinto | Mining |
| DGE.L | Diageo | Beverages |
| BARC.L | Barclays | Banking |
| LSEG.L | LSEG (London Stock Exchange Group) | Financial Services |

**Expected characteristics:**
- Spread: 1–5 bps
- ADV (average daily volume): >£50m
- Fill rate target: ≥ 95%

### 3.2 Mid-Cap Basket (FTSE 250)

**Purpose:** Higher alpha potential, wider spreads, more volatile. Use after blue-chip validation.

| Symbol | Company | Sector |
|--------|---------|--------|
| IMB.L | Imperial Brands | Tobacco |
| SDR.L | Schroders | Asset Management |
| MKS.L | Marks & Spencer | Retail |
| SMDS.L | DS Smith | Packaging |
| JDW.L | JD Wetherspoon | Hospitality |
| RWS.L | RWS Holdings | Translation/IP |
| JET2.L | Jet2 | Travel |
| HFD.L | Halfords | Retail Automotive |
| NWG.L | NatWest Group | Banking |
| TW.L | Taylor Wimpey | Housebuilding |

**Expected characteristics:**
- Spread: 5–30 bps
- ADV: £5m–£50m
- Fill rate target: ≥ 88%

### 3.3 AIM Basket (High-Growth, Small-Cap)

**Purpose:** Highest volatility, widest spreads, liquidity risk. Test only after mid-cap validation. Risk controls must be tighter for AIM stocks.

| Symbol | Company | Sector |
|--------|---------|--------|
| BOIL.L | Boil Energy | Energy |
| ASLR.L | Asler Mining | Mining |
| GGP.L | Greatland Gold | Mining |
| AFC.L | AFC Energy | Clean Energy |
| AMFI.L | Amigo Holdings | Financial |

**Expected characteristics:**
- Spread: 50–200 bps
- ADV: <£5m
- Fill rate target: ≥ 75% (lower due to liquidity)
- **Additional risk control:** Reduce max position size to 5% for AIM stocks

**Warning:** AIM stocks are unsuitable for initial paper testing. Use only after blue-chip and mid-cap validation is complete.

### 3.4 Sector Baskets

**Purpose:** Sector-rotation strategy validation; correlation analysis.

| Basket | Symbols | Key Risk |
|--------|---------|----------|
| `uk_energy` | SHEL.L, BP.L, TLW.L | Oil price correlated; treat as one risk factor |
| `uk_banking` | HSBA.L, BARC.L, NWG.L, LLOY.L | BoE rate cycle; correlated on stress events |
| `uk_pharma` | AZN.L, GSK.L, HIK.L | FDA/MHRA approval binary risk |
| `uk_retail` | TSCO.L, MKS.L, SBRY.L | Consumer sentiment and CPI correlated |
| `uk_mining` | RIO.L, AAL.L, BHP.L | Commodity price and CNY sentiment |

**Concentration rule:** When testing sector baskets, enforce a sector concentration limit: no single sector > 40% of open positions (modify `RiskManager` config if needed).

---

## 4. Market Regimes

Full regime date-ranges are in `config/test_regimes.json`. Summary:

### 4.1 Regime Definitions

| Regime | Definition | Key Characteristics |
|--------|-----------|---------------------|
| **Bull** | FTSE 100 up >15% over 12 months, low VIX | Trend-following strategies should outperform |
| **Bear** | FTSE 100 down >15% over 12 months | Mean-reversion strategies may suffer; stops are critical |
| **Sideways** | FTSE 100 ±5% over 12 months | Bollinger Bands and mean-reversion preferred |
| **Volatile** | FTSE 100 ±5% over 12 months but VIX-equivalent >25 | ATR-scaled stops most important; reduce position sizing |
| **Crisis** | Rapid market dislocation >20% drawdown in <6 months | Tests circuit breakers and kill switch; do not use real capital |

### 4.2 Historical Regime Periods (LSE)

| Regime | Period | FTSE 100 Return | Key Events |
|--------|--------|----------------|------------|
| **Pre-COVID Bull** | 2018-01-01 to 2019-12-31 | +4% | Trade tensions; modest recovery |
| **COVID Crisis** | 2020-02-01 to 2020-04-30 | -34% peak draw | Black swan; BoE intervention |
| **Post-COVID Bull** | 2020-11-01 to 2021-12-31 | +29% | Vaccine rally; reopening trades |
| **2022 Bear / Stagflation** | 2022-01-01 to 2022-12-31 | -4.5% (LSE held better than others) | Russia/Ukraine; energy crisis; BoE hiking |
| **2023 Bull** | 2023-01-01 to 2023-12-31 | +4.8% | Disinflation recovery |
| **2024 Sideways** | 2024-01-01 to 2024-09-30 | +8.5% (mixed) | UK election; BoE cuts begin |
| **2025 Volatile** | 2025-01-01 to 2025-09-30 | Variable | Global macro uncertainty; AI cycle |

---

## 5. Statistical Significance Requirements

### 5.1 Minimum Sample Sizes

Statistical significance is assessed using a one-sample z-test on the win rate (H₀: win_rate = 0.50).

| Confidence Level | Min Closed Trades (per strategy, per regime) |
|-----------------|----------------------------------------------|
| 80% (screening) | 24 trades |
| 90% (soft threshold) | 43 trades |
| **95% (standard, required)** | **68 trades** |
| 99% (high-stakes live promotion) | 122 trades |

**Derivation:** Using the formula n = (z²·p·(1-p)) / E² where:
- z = 1.96 (95% confidence), p = 0.5 (null hypothesis), E = 0.12 (12% margin of error)
- Result: n ≈ 67.1 → rounded to 68

**For production promotion (Gate B):** A minimum of 68 closed trades is recommended for statistically valid conclusions. The current Gate B threshold of 20 trades is a minimum floor; the 68-trade threshold is recommended before live promotion.

### 5.2 Power Analysis

Statistical power measures the ability to detect a real effect (e.g., win rate of 0.55 vs the null of 0.50).

| Win Rate to Detect | Min Trades (80% power, α=0.05) |
|-------------------|-------------------------------|
| 0.52 (small effect) | 1,537 trades |
| 0.55 (medium effect) | 385 trades |
| 0.60 (large effect) | 97 trades |
| 0.65 (very large) | 43 trades |

**Practical implication:** Detecting a small (2%) edge requires thousands of trades. For initial paper validation, target strategies with demonstrably larger edges (≥ 0.60 win rate) to reach significance faster.

### 5.3 Confidence Rules

| Rule | Description |
|------|-------------|
| **Minimum trades** | No conclusions drawn below 20 closed trades (Gate B floor) |
| **Recommended minimum** | 68 trades for 95% confidence |
| **Cross-regime consistency** | Strategy must pass ≥ 3 of 5 regime tests to be considered robust |
| **Out-of-sample requirement** | Walk-forward out-of-sample Sharpe ≥ in-sample × 0.6 |
| **No cherry-picking** | Results must be reported for ALL regimes tested, not just favourable ones |

---

## 6. Session Timing Rules

### 6.1 Standard Trading Windows

| Window | Times (GMT/UTC) | Recommended For |
|--------|----------------|-----------------|
| **Full LSE session** | 08:00–16:30 GMT | Standard paper trials |
| **LSE morning** | 08:00–12:00 GMT | First hour: typically higher volatility and spread |
| **Overlap only** | 13:00–16:30 GMT | US-influenced instruments |
| **Avoid** | 08:00–08:15 GMT | Auction period — erratic prices |
| **Avoid** | 16:25–16:35 GMT | Closing auction — high slippage risk |

### 6.2 Calendar Exclusions

The following dates should be excluded from all paper trial result analysis (may be included in the data fetch but trades should not be analysed from these windows):

| Exclusion | Reason |
|-----------|--------|
| UK bank holidays | No LSE trading |
| Christmas Eve (afternoon) | Thin markets, wide spreads |
| First trading day of year | Erratic repositioning |
| Budget/Autumn Statement days | Binary macro event risk |
| BoE MPC meeting days (announcement 12:00 noon) | Rate decisions cause sharp moves |
| US FOMC meeting days (19:00–20:00 UTC) | US-cross instruments can move sharply post-market |

### 6.3 DST Transition Handling

The `is_market_open()` function in `src/execution/market_hours.py` uses `pytz` or `zoneinfo` for correct DST handling. Verify this works during transitions:

```bash
# Test that market hours correctly handle BST transition
python -c "
from src.execution.market_hours import is_market_open
from datetime import datetime
import pytz

# Last Sunday of March 2025 (BST begins): 2025-03-30 at 01:00 UTC
# LSE should NOT be open at 07:30 UTC on 2025-03-29 (GMT, before open)
# LSE SHOULD be open at 07:30 UTC on 2025-03-30 (BST = 08:30 local)
for ts_str in ['2025-03-29T07:30:00+00:00', '2025-03-30T07:30:00+00:00']:
    ts = datetime.fromisoformat(ts_str)
    open_ = is_market_open('BARC.L', ts)
    print(f'{ts_str}: open={open_}')
"
```

---

## 7. Test Plan Execution

### 7.1 Trial Structure

Each test plan run = **one manifest per regime per basket**. A full test plan covers:

- 5 regimes × 3 baskets (blue-chip, mid-cap, sector) = 15 trial configurations
- Each trial: minimum 5 consecutive trading days
- Total: 75 trading-day-equivalents of paper data

### 7.2 Phased Execution

**Phase 1 — Blue-chip validation** (recommended first)
```bash
# Run full paper trial on blue-chip basket in 2023 bull regime
python main.py paper_trial configs/trial_standard.json
# Override symbols and regime dates in manifest before running:
# symbols: ["SHEL.L","AZN.L","HSBA.L","ULVR.L","BP.L","GSK.L","RIO.L","DGE.L","BARC.L","LSEG.L"]
# regime: "2023_bull" (dates: 2023-01-01 to 2023-12-31)
```

**Phase 2 — Cross-regime validation** (after blue-chip passes Phase 1)
```bash
# Test all 5 regimes on blue-chip basket
# One manifest per regime; run sequentially or in a batch
```

**Phase 3 — Mid-cap validation** (after Phase 2 passes)
```bash
# Same 5 regimes on mid-cap basket
```

**Phase 4 — Sector rotation** (after Phase 3)
```bash
# Sector baskets for correlation analysis
```

**Phase 5 — AIM stocks** (final, only after all prior phases pass)
```bash
# AIM basket with tighter position sizing (max_position_pct=0.05)
```

### 7.3 Manifest Templates

Pre-built manifest templates for common test combinations are in `configs/`:

| File | Basket | Regime | Duration |
|------|--------|--------|----------|
| `trial_standard.json` | Default symbols | Default dates | 900s (15 min) |
| `trial_conservative.json` | Default symbols | Default dates | 900s (conservative risk) |
| `trial_aggressive.json` | Default symbols | Default dates | 900s (aggressive risk) |

For UK-specific trials, override the manifest fields:
```json
{
  "profile": "uk_paper",
  "symbols": ["SHEL.L", "AZN.L", "HSBA.L"],
  "paper_duration_seconds": 28800
}
```

### 7.4 Batch Trial Runner (Planned)

When `src/trial/runner.py` (Step 4) is implemented, batch all 15 configurations:

```bash
python main.py trial_batch \
  --manifests configs/uk_trials/trial_*.json \
  --output reports/uk_test_plan/ \
  --sequential
```

---

## 8. Pass/Fail Thresholds by Regime

Strategies should not be held to the same pass threshold across all regimes. Expected performance varies by market condition.

| Regime | Min Win Rate | Min Profit Factor | Max Drawdown | Min Fill Rate |
|--------|-------------|------------------|--------------|---------------|
| Bull | 0.52 | 1.15 | 12% | 92% |
| Bear | 0.45 | 1.00 | 18% | 90% |
| Sideways | 0.50 | 1.10 | 10% | 92% |
| Volatile | 0.48 | 1.05 | 20% | 88% |
| Crisis | 0.40 | 0.90 | 30% | 80% |

**Interpretation:**
- A strategy failing **crisis** thresholds is expected for trend-following strategies (acceptable if crisis is not a target regime).
- A strategy failing **bull** thresholds suggests a fundamental strategy flaw.
- A strategy must pass at least **3 of 5** regime threshold sets to be considered robust.

---

## 9. Reporting Requirements

After completing each trial phase, generate:

```bash
# Session KPI summary
python main.py paper_session_summary trading_paper.db reports/uk_test_plan/

# Reconcile vs expected KPIs
python main.py paper_reconcile trading_paper.db reports/uk_test_plan/ \
  reports/session/presets/expected_kpis_standard.json \
  --tolerances reports/session/presets/tolerances_standard.json

# UK tax export (to confirm GBP trade ledger is correct)
python main.py uk_tax_export trading_paper.db reports/uk_test_plan/
```

Completed test plan results must be filed in `reports/uk_test_plan/` with the following naming:
```
<strategy>_<basket>_<regime>_<yyyymmdd>.json
```
Example: `ma_crossover_blue_chip_2023_bull_20260223.json`

---

## 10. Acceptance Criteria for Phase Completion

| Phase | Criteria |
|-------|----------|
| Phase 1 done | ≥ 68 closed trades on blue-chip basket in any single regime; win rate ≥ 50% |
| Phase 2 done | Strategy passes threshold in ≥ 3 of 5 regimes on blue-chip |
| Phase 3 done | Strategy passes threshold in ≥ 3 of 5 regimes on mid-cap |
| Phase 4 done | No single sector constitutes > 60% of total trades; correlation review done |
| Phase 5 done | AIM fill rate ≥ 75%; no kill switch activations |
| Full plan done | All 5 phases complete; promotion rubric filed per `docs/PROMOTION_FRAMEWORK.md` |

---

## 11. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| yfinance LSE data quality | Some gaps and delayed data for small caps | Use only blue-chip + mid-cap for backtesting; AIM requires premium data |
| Paper broker (PaperBroker) fills at simulated prices | Slippage model may not match real LSE spreads | Use IBKR paper for UK validation (real order book simulation) |
| No Level 2 data | Spread not modelled | Add 1–3 bps manually to slippage estimate for realistic mid-cap/AIM testing |
| DST transitions | 2x/year session timing risk | Use `market_hours.py` consistently; include DST-boundary trials |
| Historical regime selection bias | Selected regimes may not represent future regimes | Include at least one crisis and one sideways regime always |

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-02-23 | Initial version — covers 5 regimes, 4 basket types, power analysis, session timing |
