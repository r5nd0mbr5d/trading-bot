# Tick Data Specification (Research)

**Owner:** Copilot  
**Date:** 2026-02-23  
**Status:** DRAFT

---

## 1. Purpose

Define a lightweight tick data format for offline testing and model validation. This is not a live feed integration; it is a reproducible ingestion contract for research and fixtures.

---

## 2. Required Columns

Tick CSV files must include:

- `timestamp` (ISO-8601, timezone-aware)
- `price` (float, > 0)
- `size` (float, >= 0)
- `bid` (float, <= price)
- `ask` (float, >= price)
- `symbol` (string, optional if provided at load time)

---

## 3. Ordering Rules

- Ticks must be non-decreasing in time per symbol.
- Multiple symbols may interleave, but each symbol must remain ordered.

---

## 4. Validation Rules

- All timestamps must be UTC-aware.
- `bid <= price <= ask` for every row.
- Negative prices or sizes are rejected.

---

## 5. Aggregation Contract

Aggregations to bars use:

- Price: `open`, `high`, `low`, `close`
- Volume: sum of `size`
- Default frequency: `1min`

See `research/data/ticks.py` for implementation reference.

---

## 6. Fixture Example

Sample CSV fixture: `tests/fixtures/ticks_sample.csv`

```
timestamp,price,size,bid,ask,symbol
2026-02-20T10:00:00Z,100.0,50,99.9,100.1,TEST
2026-02-20T10:00:01Z,100.2,30,100.1,100.3,TEST
```

## 7. Historical Tick Data Sources (download)

Preferred sources for historical tick downloads (verify licensing):

- Massive (Polygon.io) — primary; REST `/v3/trades/{ticker}` and S3 flat files
- AlgoSeek
- QuantQuote
- Nasdaq Data Link (formerly Quandl)
- Kaggle datasets (quality varies)

Download helper CLI (Polygon):

```bash
python main.py research_download_ticks \
	--tick-provider polygon \
	--symbols AAPL \
	--tick-date 2026-02-20 \
	--tick-api-key <POLYGON_API_KEY> \
	--tick-output-dir research/data/ticks
```

This writes both raw JSON and canonical CSV (`symbol,timestamp,price,size,bid,ask`) for testing.

Date-range backlog download:

```bash
python main.py research_download_ticks \
	--tick-provider polygon \
	--symbols AAPL \
	--tick-start-date 2026-02-20 \
	--tick-end-date 2026-02-22 \
	--tick-api-key <POLYGON_API_KEY> \
	--tick-output-dir research/data/ticks \
	--tick-build-manifest
```

Manifest output defaults to `research/data/ticks/tick_backlog_manifest.json` and includes file hashes, row counts, and timestamp ranges.

Manifest-driven dataset loading for tests:

- Load backlog slice by symbol/date range via `research.data.tick_dataset.load_ticks_from_manifest(...)`
- Split loaded ticks into train/val/test via `research.data.tick_dataset.split_ticks_by_date(...)`
