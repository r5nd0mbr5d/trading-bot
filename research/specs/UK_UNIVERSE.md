# UK-First Tradable Universe Specification

**Prompt:** P1 | **Author:** Claude Opus | **Date:** 2026-02-23
**Status:** APPROVED — use as canonical universe definition for all research work

---

## 1. Design Principles

1. **Liquidity first**: every symbol must meet minimum daily volume and spread thresholds to survive realistic paper-trial and live execution costs.
2. **Regime coverage**: the final universe must produce enough signal history to span at least three distinct market regimes (bull, bear, sideways).
3. **Data availability**: all symbols must have ≥ 3 years of clean daily OHLCV history in Yahoo Finance (`yfinance`) — the current primary data source.
4. **Operational simplicity**: IBKR paper-trial routing works on `.L`-suffix symbols with GBP base currency; no exotic derivatives.
5. **Research/runtime parity**: the same symbol universe drives both offline research and live paper trials to avoid distribution shift.

---

## 2. Minimum Viable Universe (MVU)

The MVU is the smallest set that remains statistically meaningful and operationally viable. Use this when compute or time is constrained.

### 2a. Core FTSE 100 Blue-Chip Basket (10 symbols)

| Symbol | Company | Sector | Approx. Market Cap | Min ADV Target |
|--------|---------|--------|-------------------|----------------|
| SHEL.L | Shell | Energy | Large | £200M |
| AZN.L | AstraZeneca | Pharma | Large | £150M |
| HSBA.L | HSBC Holdings | Banking | Large | £200M |
| ULVR.L | Unilever | Consumer Staples | Large | £100M |
| BP.L | BP | Energy | Large | £150M |
| RIO.L | Rio Tinto | Mining | Large | £100M |
| GSK.L | GSK | Pharma | Large | £100M |
| BATS.L | British American Tobacco | Consumer Staples | Large | £80M |
| VOD.L | Vodafone | Telecom | Large | £80M |
| LLOY.L | Lloyds Banking Group | Banking | Large | £100M |

**Selection rationale**: highest UK ADV; broad sector diversity; most liquid names on LSE; all available in `yfinance` with multi-year history.

### 2b. Supplementary FTSE 250 Mid-Cap Basket (5 symbols)

| Symbol | Company | Sector | Min ADV Target |
|--------|---------|--------|----------------|
| IMB.L | Imperial Brands | Consumer Staples | £30M |
| WTB.L | Whitbread | Consumer Discretionary | £20M |
| MNDI.L | Mondi | Materials | £15M |
| JDW.L | J D Wetherspoon | Consumer Discretionary | £10M |
| TW.L | Taylor Wimpey | Real Estate | £20M |

**Use for**: sector diversification testing; mid-cap regime behaviour differs from large-cap.
**Risk**: wider spreads; exclude if daily ADV < threshold for a given date range.

### 2c. MVU Summary

- **Total symbols**: 15 (10 FTSE 100 + 5 FTSE 250)
- **Date range minimum**: 2018-01-01 to present (covers 5 regimes)
- **Expected regime coverage**: pre-COVID bull, COVID crisis, post-COVID bull, 2022 bear, 2023+ recovery

---

## 3. Expanded Universe

Use the expanded universe for cross-sectional strategies, factor research, or when MVU produces insufficient signal count.

### 3a. Full FTSE 100 Basket (additions beyond MVU)

Add remaining liquid FTSE 100 names with ADV ≥ £40M daily:

```
REL.L   (RELX)
DGE.L   (Diageo)
LSEG.L  (London Stock Exchange Group)
NG.L    (National Grid)
TSCO.L  (Tesco)
NWG.L   (NatWest Group)
BA.L    (BAE Systems)
CPG.L   (Compass Group)
STAN.L  (Standard Chartered)
PRU.L   (Prudential)
```

### 3b. UK-Listed ETFs

For index-level exposure, regime calibration, and factor hedging:

| Symbol | Description | Provider |
|--------|-------------|----------|
| ISF.L | iShares Core FTSE 100 ETF | BlackRock |
| VMID.L | Vanguard FTSE 250 ETF | Vanguard |
| VUKE.L | Vanguard FTSE 100 ETF | Vanguard |

**Use for**: regime signal construction; cross-sectional beta calculation; not for individual strategy alpha measurement.

### 3c. Optional Non-UK Expansion

Include US/EU symbols **only** when:
- The research hypothesis explicitly requires cross-market signals (e.g. lead-lag from US tech to UK telecom)
- ADV and spread filters are met on the non-UK exchange
- FX risk is explicitly modelled or hedged in the research design
- The paper-trial broker (IBKR) can route orders to the relevant exchange

| Non-UK Category | Example Symbols | Include When |
|----------------|----------------|--------------|
| US mega-cap (as sentiment proxy) | SPY, QQQ, GLD | Cross-market signal hypothesis |
| EU blue-chip (post-Brexit correlation) | DAX ETF via LSE | EU correlation research only |
| US sector ETFs | XLE, XLF, XLK | Sector rotation cross-market |

**Default**: exclude non-UK symbols from baseline research. Add only with explicit hypothesis.

---

## 4. Liquidity & Spread Filters

All symbols must pass these filters **per date range** before inclusion in any training fold. Filters are evaluated on daily OHLCV data.

### 4a. Offline Research Filters

| Filter | Threshold | Rationale |
|--------|-----------|-----------|
| Average Daily Volume (ADV, 20-day) | ≥ 500,000 shares | Ensures model isn't trained on thin days |
| Average Daily Value Traded (ADVT) | ≥ £5M/day | Absolute liquidity floor |
| Max consecutive missing-bar days | ≤ 3 days | Corporate actions / halts exceeding this → exclude period |
| OHLC sanity | High ≥ Open ≥ Close; Low ≤ all; Close > 0 | Basic data integrity |
| Split/dividend adjusted | Required | Use adjusted close for all return calculations |

### 4b. Paper-Trial Execution Filters

Applied before live paper orders to avoid IBKR routing failures:

| Filter | Threshold |
|--------|-----------|
| LSE session | 08:15–16:25 GMT/BST only (avoid opening auction 08:00–08:15 and closing auction 16:25–16:35) |
| Real-time bid-ask spread | ≤ 0.3% of mid-price (IBKR L1 data) |
| Min order size | £500 per trade (IBKR minimum viable lot) |
| Max slippage tolerance | 0.25% per fill before order flagged for review |

### 4c. Exclusion Triggers

Exclude a symbol from a date range if:
- Suspended trading period detected (volume = 0 for ≥ 5 consecutive trading days)
- Major corporate action (merger, delisting announcement) within the test window
- Adjusted-close price ≤ 10p (penny stock regime; spread/commissions distort results)

---

## 5. Regime Coverage Requirements

Research results are only valid if they span all three regime types below. A study failing to cover all three is classified as **regime-overfit** and cannot be promoted.

| Regime | Date Range | Characteristic | FTSE 100 Approx Return |
|--------|-----------|----------------|------------------------|
| Bull (pre-COVID) | 2017-01 to 2020-02 | Low vol, trend-following | +20% |
| Crisis | 2020-02 to 2020-05 | Extreme vol, mean-reversion | -35% then +30% |
| Post-COVID bull | 2020-05 to 2021-12 | Growth/momentum | +40% |
| Bear/stagflation | 2022-01 to 2022-12 | High inflation, rising rates | -15% |
| Recovery/bull | 2023-01 to 2024-06 | Rate-sensitive, selective momentum | +10% |
| Sideways/volatile | 2024-07 to present | Mixed signals, macro uncertainty | ±5% |

**Minimum required coverage**: at least one bull period, one bear/crisis period, and one sideways period. A walk-forward test that covers only 2022–2024 fails regime coverage.

---

## 6. Minimum Viable Universe vs Expanded Universe — Trade-offs

| Dimension | MVU (15 symbols) | Expanded (30–40 symbols) |
|-----------|-----------------|--------------------------|
| Data pull time | ~30s | ~2–3 min |
| Regime coverage | Sufficient | Richer cross-sectional |
| Overfitting risk | Lower | Higher (more degrees of freedom) |
| Cross-sectional signal | Limited | Full factor model viable |
| IBKR paper routing | All green | May include less-liquid mid-caps |
| Default for baseline research | **Yes** | No |
| Recommended for factor models | No | **Yes** |

**Recommendation**: start with MVU for all baseline strategy research. Graduate to expanded universe only when the hypothesis requires cross-sectional ranking or factor exposure.

---

## 7. Symbol Validation Procedure

Before starting any research study:

```python
# Pseudocode — implement in research/data/universe.py
def validate_universe(symbols: list[str], start: str, end: str) -> dict:
    """
    For each symbol: download OHLCV, check ADV, check OHLC sanity,
    count missing bars. Returns dict of {symbol: pass|fail|reason}.
    """
    ...
```

Expected output:
```json
{
  "SHEL.L": "pass",
  "LLOY.L": "pass",
  "SOME_ILLIQUID.L": "fail: ADV=120000 < threshold=500000"
}
```

Log validation result in the snapshot metadata JSON (see P2 — Snapshot pipeline).

---

## 8. Summary

| Parameter | Value |
|-----------|-------|
| Default universe | MVU: 15 UK symbols (10 FTSE 100 + 5 FTSE 250) |
| Expanded universe | 30–40 symbols + optional ETFs |
| Non-UK expansion | Opt-in with explicit hypothesis |
| Min data history | 3 years (ideally 8 years for regime coverage) |
| ADV filter (offline) | ≥ 500,000 shares / £5M daily |
| Spread filter (paper) | ≤ 0.3% of mid |
| Regime coverage | Must span bull + bear + sideways |
| Primary data source | yfinance (adjusted OHLCV) |
| Base currency | GBP |

---

**References:**
- `config/test_baskets.json` — symbol basket definitions for paper trials
- `config/test_regimes.json` — historical regime date ranges
- `docs/UK_TEST_PLAN.md` — paper trial execution plan
- P2 prompt (`UK_STRATEGY_PROMPTS.md`) — data snapshot pipeline implementation
