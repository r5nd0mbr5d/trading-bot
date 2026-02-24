# Massive API Reference (formerly Polygon.io)

**Source**: https://massive.com/docs | **LLMs index**: https://massive.com/docs/llms.txt
**Rebrand**: Polygon.io → Massive (October 30, 2025). Same company, same APIs.
**Last reviewed**: 2026-02-24

---

## 1. Quick Facts

| Item | Value |
|------|-------|
| Legacy domain | `polygon.io` (still resolves; redirects to `massive.com`) |
| REST base URL | `https://api.polygon.io` (legacy, extended support) / `https://api.massive.com` (new) |
| WebSocket base URL | `wss://socket.polygon.io` (legacy) / `wss://socket.massive.com` (new) |
| Flat Files | Daily S3 downloads (bucket details provided in dashboard) |
| Auth — REST | `Authorization: Bearer YOUR_API_KEY` header **or** `?apiKey=YOUR_API_KEY` query param |
| Auth — WebSocket | Send `{"action":"auth","params":"YOUR_API_KEY"}` immediately after connect |
| Auth — Flat Files | AWS credentials provided via dashboard; use standard AWS SDK / `aws s3 cp` |
| Env var (this project) | `POLYGON_API_KEY` in `.env` — used by `src/data/providers.py` |

> **Note for LLMs**: Authentication headers are not shown in the public markdown docs pages. The above
> is confirmed behaviour inherited from Polygon.io's documented auth pattern (unchanged in rebrand).
> Always use `Authorization: Bearer <key>` for REST. Never log or commit the key.

---

## 2. REST API

### 2a. Base Endpoints — Stocks (Primary Use Case for This Project)

All paths are relative to `https://api.polygon.io` (or `https://api.massive.com`).

#### Aggregates (OHLC)

| Endpoint | Method | Path | Notes |
|----------|--------|------|-------|
| Custom Bars | GET | `/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}` | Primary fetch for historical OHLCV |
| Daily Market Summary | GET | `/v2/aggs/grouped/locale/us/market/stocks/{date}` | All US stocks for one date |
| Daily Ticker Summary | GET | `/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}` | Single ticker, single day |
| Previous Day Bar | GET | `/v2/aggs/ticker/{ticker}/prev` | Last trading day OHLC |

**Custom Bars — Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | Yes | Case-sensitive (e.g. `AAPL`, `HSBA.L`) |
| `multiplier` | int | Yes | Timespan multiplier (e.g. `1`, `5`, `60`) |
| `timespan` | string | Yes | `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year` |
| `from` | string | Yes | Start date `YYYY-MM-DD` or Unix ms |
| `to` | string | Yes | End date `YYYY-MM-DD` or Unix ms |
| `adjusted` | bool | No | Split-adjusted (default: `true`) |
| `sort` | string | No | `asc` or `desc` (default: `asc`) |
| `limit` | int | No | Max results per page (max: `50000`, default: `5000`) |

**Custom Bars — Response**:

```json
{
  "ticker": "AAPL",
  "adjusted": true,
  "queryCount": 2,
  "resultsCount": 2,
  "status": "OK",
  "results": [
    {
      "o": 180.05,
      "h": 182.34,
      "l": 179.80,
      "c": 181.50,
      "v": 55432100,
      "vw": 181.12,
      "t": 1704153600000,
      "n": 412345
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `o` | Open |
| `h` | High |
| `l` | Low |
| `c` | Close |
| `v` | Volume |
| `vw` | VWAP (volume-weighted average price) |
| `t` | Unix timestamp (milliseconds) |
| `n` | Number of transactions in the window |

---

#### Trades & Quotes

| Endpoint | Method | Path |
|----------|--------|------|
| Last Trade | GET | `/v2/last/trade/{ticker}` |
| Last Quote (NBBO) | GET | `/v2/last/nbbo/{ticker}` |
| Trades (historical) | GET | `/v3/trades/{ticker}` |
| Quotes (historical NBBO) | GET | `/v3/quotes/{ticker}` |

**Last Quote (NBBO) — Response Fields**:

| Field | Description |
|-------|-------------|
| `results.P` | Ask price |
| `results.p` | Bid price |
| `results.S` | Ask size (shares) |
| `results.s` | Bid size (shares) |
| `results.T` | Exchange symbol |
| `results.X` / `results.x` | Ask / Bid exchange ID |
| `results.t` | SIP timestamp (nanoseconds) |
| `results.y` | Exchange timestamp (nanoseconds) |
| `results.z` | Tape (1=NYSE, 2=NYSE ARCA/AMEX, 3=NASDAQ) |
| `results.c` | Condition codes array |
| `results.q` | Sequence number |

---

#### Snapshots

| Endpoint | Method | Path | Notes |
|----------|--------|------|-------|
| Single Ticker Snapshot | GET | `/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}` | Latest data for one ticker |
| Full Market Snapshot | GET | `/v2/snapshot/locale/us/markets/stocks/tickers` | All US stocks |
| Top Movers (Gainers) | GET | `/v2/snapshot/locale/us/markets/stocks/gainers` | Top 20 |
| Top Movers (Losers) | GET | `/v2/snapshot/locale/us/markets/stocks/losers` | Top 20 |
| Unified Snapshot | GET | `/v3/snapshot` | Cross-asset-class snapshot |

---

#### Technical Indicators (Server-Side)

| Indicator | Method | Path |
|-----------|--------|------|
| SMA | GET | `/v1/indicators/sma/{ticker}` |
| EMA | GET | `/v1/indicators/ema/{ticker}` |
| MACD | GET | `/v1/indicators/macd/{ticker}` |
| RSI | GET | `/v1/indicators/rsi/{ticker}` |

All accept: `timespan`, `adjusted`, `window`, `series_type` (`close`/`open`/`high`/`low`), `order`, `limit`.

---

#### Tickers & Reference

| Endpoint | Method | Path |
|----------|--------|------|
| All Tickers | GET | `/v3/reference/tickers` |
| Ticker Overview | GET | `/v3/reference/tickers/{ticker}` |
| Ticker Types | GET | `/v3/reference/tickers/types` |
| Related Tickers | GET | `/v1/related-companies/{ticker}` |

**All Tickers — Key Params**: `ticker`, `type`, `market`, `exchange`, `search`, `date` (point-in-time), `limit` (max 1000), `sort`, `order`.
**Pagination**: Follow `next_url` in the response for subsequent pages.

---

#### Corporate Actions

| Endpoint | Method | Path |
|----------|--------|------|
| Splits | GET | `/v3/reference/splits` |
| Dividends | GET | `/v3/reference/dividends` |
| IPOs | GET | `/vX/reference/ipos` |
| Ticker Events | GET | `/vX/reference/tickers/{ticker}/events` |

---

#### Fundamentals

| Endpoint | Method | Path |
|----------|--------|------|
| Income Statements | GET | `/vX/reference/financials` |
| Balance Sheets | GET | `/vX/reference/financials` (with `type=balance_sheet`) |
| Cash Flow Statements | GET | `/vX/reference/financials` (with `type=cash_flow_statement`) |
| Ratios | GET | `/vX/reference/financials/ratios` |
| Short Interest | GET | `/vX/reference/short-interest/{ticker}` |
| Short Volume | GET | `/vX/reference/short-volume/{ticker}` |
| Float | GET | `/vX/reference/float` |

---

#### Market Operations

| Endpoint | Method | Path |
|----------|--------|------|
| Market Status | GET | `/v1/marketstatus/now` |
| Market Holidays | GET | `/v1/marketstatus/upcoming` |
| Exchanges | GET | `/v3/reference/exchanges` |
| Condition Codes | GET | `/v3/reference/conditions` |

---

#### SEC Filings (Stocks)

| Endpoint | Method | Path |
|----------|--------|------|
| 10-K Sections | GET | `/vX/reference/sec/filings/{filing_id}/sections` |
| Risk Factors | GET | `/vX/reference/sec/filings/{filing_id}/risk-factors` |
| Risk Categories | GET | `/vX/reference/sec/risk-categories` |

---

### 2b. Other Asset Classes (Summary)

| Asset Class | Aggregates Path | Trades Path | Snapshots Path |
|-------------|-----------------|-------------|----------------|
| **Options** | `/v2/aggs/ticker/{ticker}/range/...` | `/v3/trades/{ticker}` | `/v3/snapshot/options/{underlying}` |
| **Forex** | `/v2/aggs/ticker/{forex_ticker}/range/...` | N/A | `/v2/snapshot/locale/global/markets/forex/tickers` |
| **Crypto** | `/v2/aggs/ticker/{crypto_ticker}/range/...` | `/v3/trades/{ticker}` | `/v2/snapshot/locale/global/markets/crypto/tickers` |
| **Indices** | `/v2/aggs/ticker/{index_ticker}/range/...` | N/A | `/v3/snapshot/indices` |
| **Futures** | `/vX/markets/futures/aggs/{ticker}/range/...` | `/vX/markets/futures/trades` | `/vX/markets/futures/snapshots` |

---

### 2c. Partner Data (Add-On)

| Partner | Data | Endpoint Prefix |
|---------|------|----------------|
| **Benzinga** | News, analyst ratings, earnings, guidance, consensus | `/vX/reference/partners/benzinga/...` |
| **ETF Global** | ETF constituents, fund flows, analytics, profiles | `/vX/reference/partners/etf-global/...` |
| **TMX / Wall Street Horizon** | Corporate events calendar | `/vX/reference/partners/tmx/...` |

---

### 2d. Economy

| Endpoint | Method | Path |
|----------|--------|------|
| Treasury Yields | GET | `/vX/reference/treasury-yields` |
| Inflation | GET | `/vX/reference/inflation` |
| Inflation Expectations | GET | `/vX/reference/inflation-expectations` |
| Labor Market | GET | `/vX/reference/labor-market` |

---

### 2e. Rate Limits & Pagination

- Rate limits are **plan-dependent** (see dashboard). Free tier: 5 calls/min. Paid tiers: higher.
- All list endpoints support cursor-based pagination via `next_url` in the response body.
- Set `limit` up to the documented maximum per endpoint (typically 1000–50000).
- On 429 (rate limit exceeded): back off exponentially; `Retry-After` header may be present.

---

## 3. WebSocket API

### 3a. Connection & Authentication

```
WSS endpoint (stocks):  wss://socket.polygon.io/stocks
WSS endpoint (options): wss://socket.polygon.io/options
WSS endpoint (forex):   wss://socket.polygon.io/forex
WSS endpoint (crypto):  wss://socket.polygon.io/crypto
WSS endpoint (indices): wss://socket.polygon.io/indices
```

**Handshake sequence**:
1. Connect → server sends `[{"ev":"status","status":"connected","message":"Connected Successfully"}]`
2. Authenticate → send `{"action":"auth","params":"YOUR_API_KEY"}`
3. Server confirms → `[{"ev":"status","status":"auth_success","message":"authenticated"}]`
4. Subscribe → send `{"action":"subscribe","params":"AM.AAPL,AM.MSFT"}` (see event prefixes below)

**Unsubscribe**: `{"action":"unsubscribe","params":"AM.AAPL"}`
**Wildcard**: Use `*` for all tickers (e.g. `"params":"AM.*"`)

---

### 3b. Stocks — Event Types & Prefixes

| Prefix | Event | `ev` Field | Description |
|--------|-------|-----------|-------------|
| `AM` | Agg/Minute | `AM` | Per-minute OHLCV bar |
| `A` | Agg/Second | `A` | Per-second OHLCV bar |
| `T` | Trade | `T` | Tick-level trade |
| `Q` | Quote (NBBO) | `Q` | Best bid/offer update |
| `FMV` | Fair Market Value | `FMV` | Real-time FMV |
| `NOI` | Net Order Imbalance | `NOI` | Pre/post-market imbalance |
| `LULD` | Limit Up-Limit Down | `LULD` | Circuit breaker bands |

---

### 3c. Stocks — Message Schemas

#### Aggregate Per Minute (`AM`)

```json
{
  "ev":  "AM",
  "sym": "AAPL",
  "v":   4110,
  "av":  9470157,
  "op":  182.50,
  "vw":  182.88,
  "o":   182.85,
  "c":   182.90,
  "h":   182.95,
  "l":   182.80,
  "a":   182.45,
  "z":   685,
  "s":   1610144640000,
  "e":   1610144700000
}
```

| Field | Description |
|-------|-------------|
| `ev` | Event type (`AM`) |
| `sym` | Ticker |
| `v` | Tick volume (this bar) |
| `av` | Accumulated volume today |
| `op` | Today's official opening price |
| `vw` | VWAP for this bar |
| `o`/`c`/`h`/`l` | Open/Close/High/Low |
| `a` | Today's VWAP (accumulated) |
| `z` | Average trade size |
| `s` / `e` | Bar start / end timestamp (Unix ms) |

#### Trade (`T`)

```json
{
  "ev": "T",
  "sym": "AAPL",
  "x": 4,
  "i": "12345",
  "z": 3,
  "p": 114.125,
  "s": 100,
  "c": [14, 41],
  "t": 1610144700123,
  "q": 880982
}
```

| Field | Description |
|-------|-------------|
| `sym` | Ticker |
| `x` | Exchange ID |
| `p` | Price |
| `s` | Trade size (shares) |
| `c` | Condition codes array |
| `t` | Timestamp (Unix ms) |
| `q` | Sequence number |
| `z` | Tape (1=NYSE, 2=ARCA/AMEX, 3=NASDAQ) |

#### Quote (`Q` — NBBO)

| Field | Description |
|-------|-------------|
| `bx` | Bid exchange ID |
| `ax` | Ask exchange ID |
| `bp` | Bid price |
| `ap` | Ask price |
| `bs` | Bid size |
| `as` | Ask size |
| `t` | Timestamp (Unix ms) |
| `c` | Condition codes |
| `z` | Tape |

---

### 3d. Other Asset Class WebSocket Prefixes

| Asset | Prefix | Events Available |
|-------|--------|-----------------|
| Options | `AM`, `A`, `T`, `Q`, `FMV` | Aggregates, trades, quotes, FMV |
| Forex | `AM`, `A`, `C`, `FMV` | Aggregates, currency conversions, FMV |
| Crypto | `AM`, `A`, `XT`, `XQ`, `FMV` | Aggregates, trades, quotes, FMV |
| Indices | `AM`, `A`, `V` | Aggregates, index value |
| Futures | `AM`, `A`, `T`, `Q` | Aggregates, trades, quotes |

---

## 4. Flat Files (Bulk S3 Downloads)

### 4a. Overview

Flat files are daily bulk data files delivered via S3. They are the most cost-effective way to ingest
large historical datasets. Files are generated once per day (typically available by 06:00 ET).

**Access**: Credentials (AWS Access Key + Secret) are provisioned via the Massive dashboard.
**Download**: Standard AWS SDK (`boto3`) or AWS CLI (`aws s3 cp`).

### 4b. Available File Types

| Asset | File Type | Granularity | Description |
|-------|-----------|-------------|-------------|
| **Stocks** | Day Aggregates | Daily OHLCV | All US equities, one bar per symbol per day |
| **Stocks** | Minute Aggregates | Per-minute OHLCV | All US equities, all market-hours minutes |
| **Stocks** | Trades | Tick-level | Nanosecond-timestamped trades, all US exchanges |
| **Stocks** | Quotes | Tick-level | NBBO quotes, nanosecond timestamps |
| **Options** | Day Aggregates | Daily OHLCV | All US options contracts |
| **Options** | Minute Aggregates | Per-minute OHLCV | All US options contracts |
| **Options** | Trades | Tick-level | Nanosecond trades |
| **Options** | Quotes | Tick-level | Nanosecond NBBO quotes |
| **Forex** | Day Aggregates | Daily OHLCV | 1,750+ currency pairs |
| **Forex** | Minute Aggregates | Per-minute OHLCV | 1,750+ currency pairs |
| **Forex** | Quotes | Tick-level | BBO quotes from major institutions |
| **Crypto** | Day Aggregates | Daily OHLCV | Expansive crypto pairings |
| **Crypto** | Minute Aggregates | Per-minute OHLCV | Expansive crypto pairings |
| **Crypto** | Trades | Tick-level | Nanosecond trades |
| **Indices** | Day Aggregates | Daily OHLCV | S&P, NASDAQ, Dow Jones, and more |
| **Indices** | Minute Aggregates | Per-minute OHLCV | Same index set |
| **Indices** | Values | Tick-level | Tick-by-tick index values |

### 4c. S3 Path Convention

Bucket and exact path are provided in the Massive dashboard after subscription. The general pattern
(inherited from Polygon.io) is:

```
s3://flatfiles.polygon.io/{asset_class}/{file_type}/{date}.csv.gz
```

Example paths:
```
s3://flatfiles.polygon.io/us_stocks_sip/day_aggs_v1/2025-01-02.csv.gz
s3://flatfiles.polygon.io/us_stocks_sip/minute_aggs_v1/2025-01-02.csv.gz
s3://flatfiles.polygon.io/us_stocks_sip/trades_v1/2025-01-02.csv.gz
```

> **Note for LLMs**: Confirm exact bucket and path structure from the user's dashboard or by checking
> the Massive docs once authenticated, as the bucket name may have changed during the rebrand.

### 4d. File Schema — Day Aggregates (Stocks)

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | string | Ticker symbol |
| `volume` | int64 | Total shares traded |
| `open` | float64 | Opening price |
| `close` | float64 | Closing price |
| `high` | float64 | Session high |
| `low` | float64 | Session low |
| `window_start` | int64 | Bar start (Unix nanoseconds) |
| `transactions` | int64 | Number of trades in session |
| `vwap` | float64 | Volume-weighted average price (optional, where available) |

### 4e. Typical Access Pattern (Python / boto3)

```python
import boto3
import pandas as pd

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["MASSIVE_AWS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["MASSIVE_AWS_SECRET_KEY"],
)

obj = s3.get_object(
    Bucket="flatfiles.polygon.io",          # confirm bucket name from dashboard
    Key="us_stocks_sip/day_aggs_v1/2025-01-02.csv.gz",
)
df = pd.read_csv(obj["Body"], compression="gzip")
```

---

## 5. Project-Specific Notes

### 5a. Env Variables (`.env`)

```
POLYGON_API_KEY=<your_key>          # used by src/data/providers.py
MASSIVE_AWS_ACCESS_KEY=<key>        # flat file access (if subscribed)
MASSIVE_AWS_SECRET_KEY=<secret>     # flat file access (if subscribed)
```

The legacy name `POLYGON_API_KEY` is correct — the Massive API still accepts the same key format.
No rename needed.

### 5b. Provider Integration in This Project

The `HistoricalDataProvider` protocol (`src/data/providers.py`) defines the adapter interface.
`YFinanceProvider` is implemented. The Massive/Polygon provider (`MassiveProvider`) is planned in
Step 24 of the backlog.

Relevant REST endpoints for the `MassiveProvider` implementation:

| Use Case | Endpoint |
|----------|----------|
| Historical OHLCV (backtest) | `GET /v2/aggs/ticker/{ticker}/range/{mult}/{span}/{from}/{to}` |
| Real-time bar (paper streaming) | WebSocket `AM` event |
| Market status check | `GET /v1/marketstatus/now` |
| Splits/dividends (corp actions) | `GET /v3/reference/splits`, `/v3/reference/dividends` |
| Ticker validation | `GET /v3/reference/tickers/{ticker}` |

### 5c. UK LSE Symbol Format

For UK symbols, Massive uses the `.` suffix convention identical to yfinance:
- `HSBA.L`, `VOD.L`, `BP.L`, `BARC.L`, `SHEL.L`

Confirm UK symbol availability and exchange coverage in your plan before implementing the provider.

### 5d. Step 24 Backlog Item

The `MassiveProvider` adapter should:
1. Implement `HistoricalDataProvider` protocol
2. Use `Authorization: Bearer` header (read from `POLYGON_API_KEY` env var)
3. Map `timespan` parameter to Massive's values (`day`, `minute`, `hour`, etc.)
4. Handle pagination via `next_url`
5. Normalise response to the project's `Bar` dataclass (`src/data/models.py`)
6. Respect rate limits with exponential backoff on 429

---

## 6. Key Links

| Resource | URL |
|----------|-----|
| Main docs | https://massive.com/docs |
| LLMs index (full endpoint list) | https://massive.com/docs/llms.txt |
| Dashboard / API keys | https://massive.com/dashboard |
| Status page | https://status.massive.com |
| Blog (rebrand announcement) | https://massive.com/blog/polygon-is-now-massive |
| Legacy domain (still works) | https://polygon.io |
| Legacy API base (still works) | https://api.polygon.io |
