# YFinance Local Store Feasibility (Step 73)

**Date:** 2026-02-25  
**Status:** Draft feasibility memo (implementation-scoped)  
**Related:** Step 73, RFC-005, TD-018

## Purpose

Estimate storage footprint and operational feasibility of a local yfinance-backed store for UK-first symbols, with practical retention assumptions for:
- `1m` intraday bars
- `5m` intraday bars
- `1d` daily bars

## Sizing Assumptions

- Active symbol universe: 20 UK symbols (conservative extension over current 5-symbol core)
- Trading days per month: 22
- LSE session minutes/day used in cache: ~480 (08:00–16:00 UTC)
- Bars per symbol/month:
  - `1m`: `480 * 22 = 10,560`
  - `5m`: `96 * 22 = 2,112`
  - `1d`: `22`
- SQLite row payload (OHLCV + timestamp + symbol + overhead): ~120–220 bytes/row practical range

## Approximate Monthly Growth

Using 20 symbols:

- `1m`: `10,560 * 20 = 211,200` rows/month
  - Size range: ~24 MB to ~46 MB/month
- `5m`: `2,112 * 20 = 42,240` rows/month
  - Size range: ~5 MB to ~9 MB/month
- `1d`: `22 * 20 = 440` rows/month
  - Size range: negligible (< 1 MB/month)

**Combined estimate:** ~29 MB to ~55 MB/month for 20 symbols.

## 12-Month Projection

- 20 symbols combined: ~0.35 GB to ~0.66 GB/year
- 50 symbols combined (scaled linearly): ~0.9 GB to ~1.65 GB/year

These figures are operationally small for local SSD-backed development and paper-trial workflows.

## Feasibility Assessment

**Feasible:** Yes.

Rationale:
- Current hybrid cache approach (SQLite + optional parquet snapshots) already exists.
- Projected growth is modest relative to typical developer machine storage.
- Local store materially reduces sensitivity to transient yfinance call failures and repeated remote fetches.

## Recommended Phased Rollout

1. **Phase A (now):** Keep current cache as source-of-truth for repeated reads; add yfinance request retries (Step 73 code path).
2. **Phase B:** Add simple cache retention policy by interval (e.g., keep `1m` for 60–90 days, `5m` for 6–12 months).
3. **Phase C:** Add cache health metrics (row counts by symbol/interval/day, freshness, gap-rate) to operational reports.

## Operational Trade-Offs

- Pros:
  - Better resilience against transient provider errors
  - Lower repeated network dependence
  - Faster preflight checks and repeated test cycles
- Risks:
  - Potential stale-data reliance if freshness checks are weak
  - SQLite write contention under heavy concurrent writers (limited in current single-runtime setup)
- Mitigation:
  - Enforce timestamp freshness checks in preflight/stream paths
  - Keep write path single-process for paper runs

## Recommendation

Proceed with local-store usage as the default paper-trial cache layer and add explicit retention/freshness controls incrementally. No architectural blocker is identified for UK-first paper operations at current or near-term scale.
