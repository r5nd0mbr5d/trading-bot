# Data Providers Reference

**Purpose**: LLM-optimised reference for all external data and execution providers used in this project.
**Audience**: Claude Code, Copilot, any LLM agent working on the codebase.
**Last reviewed**: 2026-03-01

---

## 1. Provider Summary Table

| # | Provider | Type | Status | Auth Env Var | Cost |
|---|----------|------|--------|-------------|------|
| 1 | **EODHD (EOD Historical Data)** | **Primary: OHLCV + Fundamentals + Corporate Actions + Forex** | ✅ **Primary** (ADR-022) | `EODHD_API_KEY` | API key required (free 20 req/day; paid tiers) |
| 2 | **yfinance (Yahoo Finance)** | Historical OHLCV (fallback) | ✅ Fallback | None | Free |
| 3 | **Massive (formerly Polygon.io)** | Historical + Tick + Real-time | ✅ Implemented | `POLYGON_API_KEY` | Paid |
| 4 | **Alpha Vantage** | Historical OHLCV (fallback) | ⚠️ Scaffolded | `ALPHA_VANTAGE_API_KEY` | Free / Paid |
| 5 | ~~**IEX Cloud**~~ | ~~Historical + Fundamentals~~ | ❌ Removed — shut down April 2025 | N/A | N/A |
| 6 | **Alpaca (Data API)** | Real-time streaming | ⚠️ Scaffolded | `ALPACA_API_KEY` | Paid |
| 7 | **Alpaca (Broker)** | Paper trading execution | ✅ Implemented | `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Free (paper) |
| 8 | **Interactive Brokers (IBKR)** | Paper + Live execution | ✅ Implemented | `IBKR_HOST` / `IBKR_PORT` / `IBKR_CLIENT_ID` | Free (paper) |
| 9 | **Benzinga** | News + Analyst ratings | ⚠️ Available via Massive | `POLYGON_API_KEY` | Free (news via `/v2/reference/news`); Massive tier for partner endpoints |
| 10 | **ETF Global** | ETF analytics + constituents | ⚠️ Available via Massive | `POLYGON_API_KEY` | Massive tier |
| 11 | **TMX / Wall Street Horizon** | Corporate events calendar | ⚠️ Available via Massive | `POLYGON_API_KEY` | Massive tier |

---

## 2. Provider Detail

---

### 2.0 EODHD — EOD Historical Data (PRIMARY)

**Full name**: EOD Historical Data
**Site**: https://eodhd.com
**Docs**: https://eodhd.com/financial-apis
**Library**: Direct REST via `requests` (no SDK needed)

**Role**: **Primary data provider** — EODHD is the default data source for all OHLCV, fundamentals, corporate actions, and planned forex data. (ADR-022, supersedes ADR-004.)

**Current use (implemented)**:
- Daily OHLCV adjusted bars via `/api/eod/{ticker}?api_token=...&fmt=json`
- Corporate actions (dividends, splits) via `EODHDCorporateActionsProvider` in `src/data/corporate_actions.py`
- UK LSE equities: `.LSE` suffix (e.g. `HSBA.LSE`, `BARC.LSE`)
- Symbol mapping: yfinance `.L` suffix → EODHD `.LSE` suffix (handled in `EODHDProvider._resolve_eodhd_symbol()`)

**Planned use (not yet implemented)**:
- Fundamental data via `/api/fundamentals/{ticker}` — earnings, financials, balance sheet, ratios
- Forex via `/api/eod/{pair}.FOREX` — GBP/USD, EUR/GBP, etc.
- Bulk daily data via `/api/eod-bulk-last-day/{exchange}` — efficient cache backfill
- Live/delayed prices via `/api/real-time/{ticker}`

**Implementation**: `EODHDProvider` in [src/data/providers.py](../src/data/providers.py)
**Config key**: `data.source = "eodhd"` (default in `config/settings.py`)
**Fallback**: `data.fallback_sources = ["yfinance"]`
**Auth env var**: `EODHD_API_KEY`
**Cost**: Free tier = 20 API calls/day; paid tiers from $19.99/month (see https://eodhd.com/pricing)
**Rate limit (free)**: 20 calls/day total
**Rate limit (paid)**: 100,000 calls/day (All World tier)

**Key endpoints**:
| Endpoint | Description | Status |
|---|---|---|
| `GET /api/eod/{ticker}` | Daily OHLCV adjusted bars | ✅ Implemented |
| `GET /api/div/{ticker}` | Dividend history | ✅ Implemented (corporate actions) |
| `GET /api/splits/{ticker}` | Stock split history | ✅ Implemented (corporate actions) |
| `GET /api/fundamentals/{ticker}` | Earnings, financials, ratios | 🔲 Planned |
| `GET /api/eod-bulk-last-day/{exchange}` | Bulk daily bars per exchange | 🔲 Planned |
| `GET /api/eod/{pair}.FOREX` | Forex OHLCV (e.g. `GBPUSD.FOREX`) | 🔲 Planned |
| `GET /api/real-time/{ticker}` | Live/delayed prices | 🔲 Planned |
| `GET /api/calendar/earnings` | Earnings calendar | 🔲 Planned |

**Symbol format**:
- UK: `HSBA.LSE`, `BARC.LSE`, `AZN.LSE`
- US: `AAPL.US`, `MSFT.US`
- Forex: `GBPUSD.FOREX`, `EURGBP.FOREX`
- Crypto: `BTC-USD.CC`

---

### 2.1 yfinance — Yahoo Finance (FALLBACK)

**Full name**: Yahoo Finance (via the `yfinance` Python library)
**Site**: https://finance.yahoo.com | https://pypi.org/project/yfinance/
**Library**: `pip install yfinance`

**Proposed use**:
- Fallback provider for historical OHLCV when EODHD is unavailable
- UK LSE equities (`.L` suffix — e.g. `HSBA.L`, `BARC.L`)
- Backtesting and offline research data when no EODHD API key is set
- No API key required; free forever
- Automatic split/dividend adjustment via `auto_adjust=True`

**Limitations**:
- 1-minute LSE bars are 15–30 minutes delayed (yfinance data latency)
- Not suitable for real-time paper trading signals
- Rate limits apply (unofficial; no SLA)
- No tick-level data

**Implementation**: `YFinanceProvider` in [src/data/providers.py](../src/data/providers.py)
**Config key**: `data.source = "yfinance"` in `config/settings.py`
**Auth**: None required

---

### 2.2 Massive (formerly Polygon.io)

**Full name**: Massive (rebranded from Polygon.io, October 30, 2025)
**Site**: https://massive.com | Legacy: https://polygon.io
**Docs**: https://massive.com/docs | LLM index: https://massive.com/docs/llms.txt
**Full API reference**: [docs/MASSIVE_API_REFERENCE.md](MASSIVE_API_REFERENCE.md)

**Proposed use**:
- Production-grade historical OHLCV (daily, hourly, minute bars)
- Tick-level trade and quote data for ML/NN research feature engineering
- Real-time WebSocket streaming (minute agg, trades, NBBO quotes)
- Bulk S3 flat-file downloads for training data pipelines
- Corporate actions (splits, dividends) for clean adjusted prices
- Market status / holiday calendars
- UK equities via `.L` suffix (LSE coverage confirmed)

**REST base URL**: `https://api.polygon.io` (legacy, extended support) or `https://api.massive.com`
**WebSocket**: `wss://socket.polygon.io/stocks` (legacy) or `wss://socket.massive.com/stocks`
**Flat Files**: Daily S3 bulk — `s3://flatfiles.polygon.io/{asset_class}/{file_type}/{date}.csv.gz`

**Implementation**: `PolygonProvider` in [src/data/providers.py](../src/data/providers.py)
**Config key**: `data.source = "polygon"`
**Auth env var**: `POLYGON_API_KEY` (Bearer token; set in `.env`)
**Flat file env vars**: `MASSIVE_AWS_ACCESS_KEY`, `MASSIVE_AWS_SECRET_KEY`
**Cost**: Starter ~$29/month; free tier = 5 req/min (insufficient for research)

**Key REST endpoints for this project**:

| Use case | Endpoint |
|----------|----------|
| Historical OHLCV (backtest / research) | `GET /v2/aggs/ticker/{ticker}/range/{mult}/{span}/{from}/{to}` |
| Daily all-market summary | `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` |
| Last NBBO quote | `GET /v2/last/nbbo/{ticker}` |
| Tick trades (research) | `GET /v3/trades/{ticker}` |
| Splits | `GET /v3/reference/splits` |
| Dividends | `GET /v3/reference/dividends` |
| Market status | `GET /v1/marketstatus/now` |
| Ticker validation | `GET /v3/reference/tickers/{ticker}` |

**WebSocket subscription** (real-time paper trading upgrade):
```json
{"action": "auth",      "params": "YOUR_API_KEY"}
{"action": "subscribe", "params": "AM.AAPL,AM.HSBA.L"}
```
Response events: `AM` (minute agg), `T` (trade), `Q` (NBBO quote)

**Tick download CLI** (research data pipeline):
```bash
python main.py research_download_ticks \
  --tick-provider polygon \
  --symbols AAPL HSBA.L \
  --tick-start-date 2025-01-01 \
  --tick-end-date 2025-12-31 \
  --tick-api-key $POLYGON_API_KEY \
  --tick-build-manifest
```

---

### 2.3 Alpha Vantage

**Full name**: Alpha Vantage Inc.
**Site**: https://www.alphavantage.co
**Docs**: https://www.alphavantage.co/documentation/
**Library**: `pip install alpha-vantage`

**Proposed use**:
- Tier 3 fallback for US equity OHLCV when yfinance and Massive are unavailable
- Server-side technical indicators (SMA, EMA, MACD, RSI, Bollinger, ADX, etc.)
- Intraday bars (1min, 5min, 15min, 30min, 60min)
- Forex and crypto OHLCV

**Current status**: Scaffolded — `NotImplementedProvider("alpha_vantage")` returned by factory
**Backlog item**: Step 26 (Alpha Vantage adapter) — not yet scheduled; deferred
**Config key**: `data.source = "alpha_vantage"`
**Auth env var**: `ALPHA_VANTAGE_API_KEY` (to be added to `.env`)
**Cost**: Free = 25 req/day (very limited); Premium = 75–1200 req/min ($50–$250/month)
**Rate limit (free)**: 5 req/min, 500 req/day

**Implementation**: Add `AlphaVantageProvider` class to [src/data/providers.py](../src/data/providers.py)
following the `HistoricalDataProvider` protocol.

---

### 2.4 ~~IEX Cloud~~ — REMOVED

**Status**: ❌ **Shut down April 2025 — do not implement**

IEX Cloud (iexcloud.io) ceased operations in April 2025. The registration and login pages no longer
load. The service is confirmed non-operational. `"iex"` has been removed from the provider factory.
The `.env` key `IEX_CLOUD_API_KEY` has been deleted.

**Replacement coverage**:
- OHLCV data → already covered by yfinance (free) and Massive/Polygon.io (paid)
- News sentiment → Benzinga articles via free `/v2/reference/news` (§2.8); paid partner API for earnings/ratings
- Tick data → Massive REST + flat files

No replacement provider registration is required — existing providers cover all prior IEX use cases.

---

### 2.5 Alpaca (Data API)

**Full name**: Alpaca Markets Data API
**Site**: https://alpaca.markets
**Docs**: https://docs.alpaca.markets/reference/stockbars
**Library**: `alpaca-py` (already installed for broker use)

**Proposed use**:
- Real-time streaming bars as an alternative to yfinance for paper trading
- US equity historical OHLCV (alternative to yfinance)
- WebSocket streaming compatible with existing `AlpacaBroker` credentials

**Current status**: Scaffolded — `NotImplementedProvider("alpaca")` returned by factory
**Backlog item**: Not scheduled; natural follow-on if Alpaca broker is primary
**Config key**: `data.source = "alpaca"`
**Auth env vars**: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (already in `.env` for broker)
**Cost**: Free with paper trading account; market data subscription for full real-time

**Note**: If you use Alpaca as broker, using the Alpaca Data API avoids a second vendor dependency.

---

### 2.6 Alpaca (Broker — Paper Trading)

**Full name**: Alpaca Markets
**Site**: https://alpaca.markets
**Docs**: https://docs.alpaca.markets
**Library**: `alpaca-py`

**Proposed use**:
- Paper trading (no real money) for US equities
- Order submission, management, and cancellation
- Position and portfolio tracking
- Account balance and buying power

**Implementation**: `AlpacaBroker` in [src/execution/broker.py](../src/execution/broker.py)
**Auth env vars**: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`
**Config**: `broker.provider = "alpaca"`, `broker.paper_trading = True`
**Cost**: Free for paper trading

---

### 2.7 Interactive Brokers (IBKR)

**Full name**: Interactive Brokers LLC
**Site**: https://www.interactivebrokers.com
**Docs**: https://interactivebrokers.github.io/tws-api/
**Library**: `ib_insync` (async wrapper around TWS API)

**Proposed use**:
- Paper trading for UK LSE equities (primary current use)
- Live trading with real capital (when enabled)
- Contract resolution for non-US symbols (exchange, currency, primary exchange)
- Real-time portfolio snapshots and cash balance
- Order lifecycle management (submit, modify, cancel)

**Implementation**: `IBKRBroker` in [src/execution/ibkr_broker.py](../src/execution/ibkr_broker.py)
**Auth env vars**: `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`
**Config**:
- `broker.provider = "ibkr"`
- `broker.ibkr_port = 7497` (paper) / `7496` (live)
- `broker.paper_trading = True/False`
- `broker.ibkr_symbol_overrides` — per-symbol contract routing for LSE

**Requires**: TWS (Trader Workstation) or IB Gateway running locally
**Cost**: Free paper account; live requires funded account + commissions

---

### 2.8 Benzinga (via Massive Partner API OR Free News Endpoint)

**Full name**: Benzinga
**Site**: https://www.benzinga.com | API via https://massive.com
**API prefix (paid)**: `/vX/reference/partners/benzinga/`
**API prefix (free)**: `/v2/reference/news` ✅ available on free Polygon tier

> **Step 33 uses the free endpoint** — `GET /v2/reference/news?ticker={symbol}` returns
> articles from all publishers including Benzinga, with pre-computed `insights[].sentiment`
> labels ("positive" / "negative" / "neutral") per ticker. No paid subscription required.
> Rate limit: 5 calls/min. See `docs/MASSIVE_API_REFERENCE.md` §2a for full details.

**Proposed use**:
- Real-time and historical financial news with ticker tagging
- Analyst ratings, price target changes, rating actions (paid tier only)
- Earnings announcements — actual vs. estimate EPS and revenue (paid tier only)
- Corporate guidance data (paid tier only)
- Sentiment signal for ML feature engineering ✅ **available on free tier**

**Access**:
- `/v2/reference/news` — Free Polygon tier (5 calls/min)
- `/vX/reference/partners/benzinga/...` — Requires paid Massive subscription tier

**Auth env var**: `POLYGON_API_KEY` (same key for both tiers)
**Current status**: Available but not integrated into this project
**Key endpoints**:
- `GET /v2/reference/news?ticker={symbol}` — news with sentiment (FREE) ✅
- `GET /vX/reference/partners/benzinga/news` — real-time news (paid)
- `GET /vX/reference/partners/benzinga/analyst-ratings` — ratings history (paid)
- `GET /vX/reference/partners/benzinga/earnings` — EPS/revenue actuals (paid)
- `GET /vX/reference/partners/benzinga/consensus-ratings` — aggregated consensus (paid)

---

### 2.9 ETF Global (via Massive Partner API)

**Full name**: ETF Global
**Site**: https://www.etfg.com | API via https://massive.com
**API prefix**: `/vX/reference/partners/etf-global/`

**Proposed use**:
- ETF constituent lookups (e.g. ISF.L FTSE 100 ETF holdings)
- Fund flow tracking (institutional inflow/outflow signals)
- Sector/industry exposure data for regime feature engineering
- ETF analytics (performance, risk metrics)

**Access**: Via Massive subscription
**Auth env var**: `POLYGON_API_KEY`
**Current status**: Available but not integrated
**Key endpoints**:
- `GET /vX/reference/partners/etf-global/constituents` — ETF holdings
- `GET /vX/reference/partners/etf-global/fundflows` — capital flows
- `GET /vX/reference/partners/etf-global/analytics` — performance metrics

---

### 2.10 TMX / Wall Street Horizon (via Massive Partner API)

**Full name**: TMX Data Services / Wall Street Horizon (now part of TMX)
**Site**: https://wallstreethorizon.com | API via https://massive.com
**API prefix**: `/vX/reference/partners/tmx/`

**Proposed use**:
- Corporate events calendar: earnings dates, ex-dividend dates, investor conferences
- Stock split announcements and merger/acquisition timelines
- Event-driven alpha signals for ML feature engineering
- Pre-earnings volatility regime detection

**Access**: Via Massive subscription
**Auth env var**: `POLYGON_API_KEY`
**Current status**: Available but not integrated
**Key endpoint**:
- `GET /vX/reference/partners/tmx/corporate-events` — full event calendar

---

## 3. Historical Data in Strategy Development & ML/NN Training

### 3a. How Historical Data Is Used (Current Architecture)

```
Data Provider (EODHD primary / yfinance fallback / Massive)
        │
        ▼
MarketDataFeed (src/data/feeds.py)
  — fetch_bars(symbol, start, end, interval)
  — returns pd.DataFrame [open, high, low, close, volume]
        │
   ┌────┴────────────────────────┐
   ▼                             ▼
BacktestEngine              Research Track
(backtest/engine.py)        (research/)
   │                             │
   ▼                             ▼
Strategy.generate_signal()   feature engineering
RiskManager.approve()        walk-forward training
PaperBroker.submit()         XGBoost / MLP / LSTM
BacktestResults              Promotion Pipeline
```

### 3b. Research Data Pipeline (Offline)

The research track (`research/`) uses historical data for three purposes:

**1. Snapshot creation** — reproducible fixed datasets for training
```bash
# Download tick data (Massive API)
python main.py research_download_ticks \
  --tick-provider polygon --symbols AAPL HSBA.L \
  --tick-start-date 2023-01-01 --tick-end-date 2025-12-31 \
  --tick-api-key $POLYGON_API_KEY --tick-build-manifest

# Split into train/val/test
python main.py research_build_tick_splits \
  --tick-input-manifest research/data/ticks/tick_backlog_manifest.json \
  --tick-train-end 2024-06-30 --tick-val-end 2024-12-31 \
  --tick-split-output-dir research/data/ticks/splits
```

**2. Feature engineering** — leakage-safe features from OHLCV + volume
(See [research/specs/FEATURE_LABEL_SPEC.md](../research/specs/FEATURE_LABEL_SPEC.md))
- 30+ features across: price, volume, volatility, momentum, regime, cross-sectional
- Labels: H5 (5-day forward return), binary or ternary classification
- All computed strictly from data available at bar[t] close — no lookahead

**3. Walk-forward training and evaluation**
(See [research/specs/VALIDATION_PROTOCOL.md](../research/specs/VALIDATION_PROTOCOL.md))
- 8-fold expanding-window schedule (2018–2024)
- Per-fold: train → Platt-calibrate → threshold-optimize → OOS evaluate
- Aggregate gate: ≥ 6/8 folds pass; Sharpe ≥ 0.50; CI lower bound ≥ 0.48

### 3c. XGBoost Pipeline (Implemented)

```bash
# Run full XGBoost pipeline with config
python main.py research_train_xgboost \
  --config research/experiments/configs/xgboost_example.json

# End-to-end demo (generates snapshot + runs pipeline)
python research/experiments/examples/end_to_end_xgb_demo.py
```

**Outputs**:
- `research/experiments/<id>/results/fold_F*.json` — per-fold metrics
- `research/experiments/<id>/results/aggregate_summary.json` — combined OOS metrics
- `research/experiments/<id>/results/promotion_check.json` — `promotion_eligible: true/false`
- `research/experiments/<id>/shap/fold_F*.json` — SHAP top-20 feature importance
- `research/experiments/<id>/artifacts/<model_id>/model.bin` — serialised model
- `research/experiments/<id>/artifacts/<model_id>/metadata.json` — SHA256 + training config
- `research/experiments/<id>/training_report.json` — full training report

### 3d. LSTM / Neural Net (Planned)

LSTM is deferred as an optional extension after XGBoost passes all gates.
See [research/specs/ML_BASELINE_SPEC.md](../research/specs/ML_BASELINE_SPEC.md) §3.
The same data pipeline, feature set, and validation protocol applies.

---

## 4. Backlog Tasks Related to Providers & Historical Data

### Completed

| Step | Title | Notes |
|------|-------|-------|
| Step 12 | Multi-provider data adapter scaffold | `HistoricalDataProvider` protocol + factory |
| Step 24 | Polygon.io / Massive provider adapter | `PolygonProvider` implemented in `src/data/providers.py` |
| Step 25 | XGBoost training pipeline | Per-fold SHAP, artifact SHA256, `promotion_check.json` |
| Step 26 | Research isolation CI guard | Research imports cannot leak into runtime |
| Step 28 | Data quality monitoring report | Staleness, gap count, OHLC ordering violations |

### Outstanding / Planned

| Step | Title | Priority | Estimated Effort | Notes |
|------|-------|----------|-----------------|-------|
| **Step 34** | **Persistent Market Data Cache (SQLite + Parquet)** | **CRITICAL** | 6–10 hrs | ⭐ Do first — blocks Steps 29–31; eliminates redundant API calls |
| Step 29 | Alpha Vantage Provider | MEDIUM | 4–6 hrs | Needs Step 34 first; 25 req/day free tier unusable without cache |
| Step 30 | Real-time WebSocket Feed | HIGH | 10–16 hrs | Replace yfinance polling; cache used for warm-up |
| Step 31 | Flat File Bulk Ingestion | HIGH | 8–16 hrs | S3 → Parquet; feeds the cache |
| Step 32 | LSTM/NN Baseline | HIGH | 16–32 hrs | After XGBoost passes R3 |
| Step 33 | News Sentiment Integration | MEDIUM | 4–6 hrs | ✅ Free tier (`/v2/reference/news`) — no paid sub needed |
| **New** | **Alpaca Data API Provider** | LOW | 3–5 hrs | Natural pairing if Alpaca is primary broker |
| MO-2 | Step 1A burn-in (3 sessions) | CRITICAL | Manual | Live in-window paper sessions with fills |

**Free tier constraints that make Step 34 critical**:
| Provider | Free Limit | Impact without cache |
|----------|-----------|---------------------|
| Alpha Vantage | **25 req/day** | 5 symbols = daily quota gone in 1 backtest |
| Massive/Polygon | **5 req/min** | Repeated research runs hit limit instantly |
| yfinance | Unofficial (no SLA) | Can be blocked; cache provides resilience |

---

## 5. Prompts & Agents Required

### 5a. Prompt Pack (Copilot Implementation Tasks)

These are ready-to-execute prompts for each outstanding provider/data task:

---

**P-ALPHA: Alpha Vantage Provider Adapter**
> **Model**: Copilot
> Implement `AlphaVantageProvider` in `src/data/providers.py` following the `HistoricalDataProvider`
> protocol. Use `requests` (not a third-party SDK) to call `https://www.alphavantage.co/query` with
> `function=TIME_SERIES_DAILY_ADJUSTED`, `symbol`, `outputsize=full`, `apikey=ALPHA_VANTAGE_API_KEY`.
> Parse the response into a `pd.DataFrame` with UTC-aware DatetimeIndex and columns
> `[open, high, low, close, volume]`. Add exponential backoff on 429/503 (max 3 retries).
> Register in the provider factory under `"alpha_vantage"`. Add focused pytest tests covering:
> successful fetch, 429 retry, empty response, malformed JSON.

---

**P-LSTM: LSTM/NN Baseline**
> **Model**: Claude Opus / Copilot
> Implement an LSTM baseline in `research/models/train_lstm.py` following the same interface as
> `research/models/train_xgboost.py`. Use PyTorch. Architecture: 2-layer LSTM (hidden=64),
> dropout=0.2, linear output head. Input: sequence of 20 bars × feature_dim. Target: H5 binary label.
> Training: Adam (lr=1e-3), early stopping (patience=10 epochs), batch_size=64.
> Calibration: Platt scaling on validation fold (same as XGBoost). Output artifacts:
> `model.pt`, `metadata.json` (SHA256, architecture, training config). Integrate into
> `research/experiments/xgboost_pipeline.py` as an optional `--model-type lstm` flag.
> The same walk-forward folds, SHAP-equivalent (permutation importance), and `promotion_check.json`
> schema apply. Tests: training loop runs to completion, artifacts saved correctly, SHA256 verifiable.

---

**P-WS: Real-Time WebSocket Data Feed**
> **Model**: Copilot
> Replace the yfinance polling loop in `src/data/feeds.py` with a `MassiveWebSocketFeed` class that
> subscribes to `wss://socket.polygon.io/stocks` using the `websockets` library. Auth:
> `{"action":"auth","params":POLYGON_API_KEY}`. Subscribe: `{"action":"subscribe","params":"AM.{symbol}"}`.
> Parse `AM` events into the existing `Bar` dataclass (`src/data/models.py`). Implement reconnect with
> exponential backoff (max 5 retries, base 2s). Expose the same `on_bar(callback)` interface as the
> current polling feed. Activate when `data.source = "polygon"` and `broker.provider = "ibkr"` and
> paper trading is True. Tests: mock WebSocket messages, reconnect handling, callback invocation.

---

**P-FLAT: Flat File Bulk Ingestion Pipeline**
> **Model**: Copilot
> Implement `research/data/flat_file_ingestion.py` to download and cache Massive flat files from S3.
> Use `boto3` with `MASSIVE_AWS_ACCESS_KEY` + `MASSIVE_AWS_SECRET_KEY`. Download target:
> `s3://flatfiles.polygon.io/us_stocks_sip/day_aggs_v1/{date}.csv.gz`.
> Parse into Parquet files stored at `research/data/snapshots/{symbol}/{date}.parquet`.
> Support: date-range backfill, incremental updates (skip existing files), symbol filtering.
> Generate a manifest JSON per batch with: file list, row counts, date range, SHA256 hashes.
> CLI: `python main.py research_ingest_flat_files --symbols AAPL HSBA.L --start 2020-01-01 --end 2025-12-31`
> Tests: mock S3 client, verify Parquet output schema, manifest generation.

---

**P-BENZ: News Sentiment Integration (Step 33)**
> **Model**: Copilot
> Implement `research/data/news_features.py` to fetch news via the free Polygon endpoint
> (`GET /v2/reference/news?ticker={symbol}&published_utc.gte={from}&limit=50`,
> `Authorization: Bearer $POLYGON_API_KEY`). Use the pre-computed `insights[].sentiment`
> labels ("positive" / "negative" / "neutral") — no manual NLP scoring needed.
> Compute: daily sentiment score (mean of +1/0/−1 per article), daily article count,
> and earnings-proximity flag (within 3 days of any earnings-tagged article).
> Optionally filter to Benzinga articles via `publisher.name == "Benzinga"`.
> Output a per-symbol per-day DataFrame joinable to the main feature set by date.
> Add to `research/specs/FEATURE_LABEL_SPEC.md` §3 as "News/Sentiment Features" family.
> Rate limit: 5 calls/min — use `time.sleep(12)` between tickers or MarketDataStore cache.
> Tests: mock `insights` list, sentiment aggregation, date alignment, empty-response guard.

---

### 5b. Agent Assignments

| Task | Recommended Agent | Reason |
|------|------------------|--------|
| Alpha Vantage adapter | Copilot | Straightforward REST adapter; well-defined interface |
| LSTM/NN baseline | Claude Opus + Copilot | Architecture decisions need Opus; code gen by Copilot |
| WebSocket real-time feed | Copilot | Async WebSocket + reconnect logic; clear spec |
| Flat file S3 ingestion | Copilot | boto3 + Parquet; follows existing tick-download pattern |
| News sentiment integration | Copilot | REST fetch + `insights[]` labels from free endpoint; straightforward |
| Walk-forward LSTM evaluation | Claude Opus | Evaluation strategy decisions need reasoning |
| Provider strategy review | Claude Opus | Trade-off analysis across providers / cost / reliability |

### 5c. Research Governance Agents

For any new ML strategy following the research track, the standard agent sequence is:

```
1. Claude Opus  → Design feature set + label spec (adds to FEATURE_LABEL_SPEC.md)
2. Copilot      → Implement features.py and labels.py
3. Copilot      → Implement or extend training pipeline
4. Claude Opus  → Review walk-forward results + gate decision (R1 research gate)
5. Copilot      → R2 runtime integration bridge
6. Manual (MO)  → R3 paper trial (30+ closed trades)
7. Claude Opus  → R4 live promotion review
```

---

## 6. Environment Variables Reference

All variables read from `.env` at project root:

```bash
# --- Data Providers ---
EODHD_API_KEY=            # EODHD (PRIMARY) — OHLCV, fundamentals, corporate actions, forex
POLYGON_API_KEY=          # Massive / Polygon.io REST + WebSocket + Partner APIs
ALPHA_VANTAGE_API_KEY=    # Alpha Vantage (not yet wired; add when implementing Step 29)
# IEX Cloud removed — service shut down April 2025

# --- Flat Files (Massive S3) ---
MASSIVE_AWS_ACCESS_KEY=   # AWS access key for S3 flat file downloads
MASSIVE_AWS_SECRET_KEY=   # AWS secret key for S3 flat file downloads

# --- Alpaca (Broker + Data API) ---
ALPACA_API_KEY=           # Alpaca paper/live broker + optional data API
ALPACA_SECRET_KEY=        # Alpaca secret key

# --- Interactive Brokers ---
IBKR_HOST=127.0.0.1       # TWS / IB Gateway host
IBKR_PORT=7497            # 7497 = paper, 7496 = live
IBKR_CLIENT_ID=1          # Unique per process; increment if collision

# --- Databases ---
DATABASE_URL=sqlite:///trading.db
DATABASE_URL_PAPER=sqlite:///trading_paper.db
DATABASE_URL_LIVE=sqlite:///trading_live.db
```

---

## 7. Key Files

| File | Purpose |
|------|---------|
| [src/data/providers.py](../src/data/providers.py) | `HistoricalDataProvider` protocol + all provider implementations |
| [src/data/feeds.py](../src/data/feeds.py) | `MarketDataFeed` — fetches bars using the active provider |
| [src/execution/broker.py](../src/execution/broker.py) | `AlpacaBroker` + `PaperBroker` |
| [src/execution/ibkr_broker.py](../src/execution/ibkr_broker.py) | `IBKRBroker` |
| [config/settings.py](../config/settings.py) | `DataConfig`, `BrokerConfig`, provider selection |
| [research/data/tick_download.py](../research/data/tick_download.py) | Polygon tick data download utilities |
| [research/models/train_xgboost.py](../research/models/train_xgboost.py) | XGBoost training pipeline |
| [docs/MASSIVE_API_REFERENCE.md](MASSIVE_API_REFERENCE.md) | Full Massive REST/WebSocket/FlatFile reference |
| [research/specs/FEATURE_LABEL_SPEC.md](../research/specs/FEATURE_LABEL_SPEC.md) | Feature/label leakage-safe design |
| [research/specs/VALIDATION_PROTOCOL.md](../research/specs/VALIDATION_PROTOCOL.md) | Walk-forward validation protocol |
| [research/specs/ML_BASELINE_SPEC.md](../research/specs/ML_BASELINE_SPEC.md) | XGBoost + LSTM governance spec |
| [research/specs/RESEARCH_PROMOTION_POLICY.md](../research/specs/RESEARCH_PROMOTION_POLICY.md) | R1→R4 promotion gates |
| [IMPLEMENTATION_BACKLOG.md](../IMPLEMENTATION_BACKLOG.md) | Full task backlog with status |
