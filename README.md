# Trading Bot

Enterprise-grade algorithmic trading platform operated from the UK, trading global equities (UK LSE, US NYSE/NASDAQ, European, Asian, and other IBKR-accessible exchanges), crypto (BTC/GBP via Coinbase/Binance), and planned forex — powered by EODHD market data (70+ exchanges).

## Features

- **10 trading strategies** — MA Crossover, RSI Momentum, MACD, Bollinger Bands, ATR Stops, ADX Filter, OBV Momentum, Stochastic Oscillator, Pairs Mean Reversion, ML Strategy Wrapper (XGBoost/MLP)
- **Multi-broker execution** — Alpaca (paper), Interactive Brokers (live, 150+ global exchanges), Coinbase (crypto primary), Binance (crypto fallback), PaperBroker (backtest)
- **EODHD primary data** — OHLCV, fundamentals, corporate actions, forex across 70+ global exchanges; yfinance as zero-cost fallback
- **Backtesting engine** — zero-lookahead event-driven bar replay with configurable slippage and commissions
- **Walk-forward validation** — rolling window out-of-sample testing to detect overfitting
- **Risk management** — VaR gates, position limits, daily loss circuit breaker, correlation limits, crypto risk overlay
- **ML/research pipeline** — XGBoost (walk-forward, SHAP explanations) + MLP baseline (skorch/PyTorch), 4-stage promotion gate (R1→R4)
- **Audit trail** — immutable async logging of every signal, order, and fill to SQLite
- **UK operations** — GBP base currency, FX normalisation, UK tax export, LSE session guardrails
- **657 tests passing** — comprehensive unit test coverage across all modules

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd trading-bot
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# Copy environment template and add your API keys
cp .env.example .env
# Edit .env — EODHD_API_KEY required for primary data; broker keys optional for backtesting

# Run a backtest (no broker keys needed; uses yfinance fallback if no EODHD key)
python main.py backtest --start 2022-01-01 --end 2024-01-01

# Run with a specific strategy and symbols
python main.py backtest --strategy rsi_momentum --symbols AAPL NVDA MSFT

# UK equities backtest
python main.py backtest --strategy ma_crossover --symbols SHEL.L AZN.L HSBA.L

# Simulated live replay (full trading pipeline, any interval)
python main.py sim_live --start 2024-01-01 --end 2024-06-01 --interval 1h --strategy ma_crossover

# Paper trade (requires Alpaca or IBKR keys in .env)
python main.py paper

# Run tests
python -m pytest tests/ -v
```

## Architecture

```
main.py                          CLI entry point (17 lines, thin wiring only)
├── src/cli/                     Argument parsing & mode dispatch
├── config/settings.py           All configuration parameters
├── src/data/
│   ├── feeds.py                 OHLCV data fetching (EODHD primary, yfinance fallback)
│   ├── providers.py             EODHDProvider, YFinanceProvider, PolygonProvider, AlphaVantageProvider
│   ├── models.py                Bar, Signal, Order, Position, AssetClass dataclasses
│   ├── symbol_utils.py          Per-exchange symbol normalisation
│   ├── corporate_actions.py     Splits, dividends via EODHD Corporate Actions API
│   └── data_context.py          Pull-based data bus (DataContext + DataSourceProvider)
├── src/strategies/              One file per strategy, all inherit BaseStrategy
│   ├── base.py                  Abstract base with DataContext integration
│   ├── ma_crossover.py          Canonical example strategy
│   └── ...                      9 more strategies
├── src/risk/manager.py          Signal → Order gate (VaR, guardrails, limits)
├── src/execution/
│   ├── broker.py                Alpaca, Coinbase, Binance, PaperBroker
│   └── ibkr_broker.py           Interactive Brokers live (global exchange routing)
├── src/trading/loop.py          Real-time bar processing loop + broker factory
├── src/portfolio/tracker.py     P&L, position tracking, multi-currency FX conversion (GBP base)
├── src/audit/logger.py          Immutable async event logging
├── backtest/
│   ├── engine.py                Daily bar replay engine
│   ├── walk_forward.py          Walk-forward validation harness
│   └── replay_engine.py         Multi-interval historical replay (sim_live)
└── research/                    ML model training, experiments, & promotion governance
```

### Key Design Principles

- **RiskManager.approve_signal()** is the only path from Signal to Order — strategies never submit orders directly
- **BacktestEngine** uses PaperBroker exclusively — never a real broker
- **generate_signal()** returns None when insufficient data — prevents lookahead bias
- All timestamps are UTC-aware (`pd.to_datetime(..., utc=True)`)
- Configuration lives in `config/settings.py` — no hardcoded symbols or dates
- `research/` layer must not import from `src/` at module level — only via `research/bridge/`

## Data Providers

The platform uses a 4-tier data provider stack (ADR-022):

| Tier | Provider | Use | Coverage | Status |
|------|----------|-----|----------|--------|
| **1 (Primary)** | **EODHD** | OHLCV, fundamentals, corporate actions, forex | 70+ global exchanges | ✅ Implemented |
| 2 (Fallback) | yfinance | Fallback OHLCV when EODHD unavailable | Global (unofficial) | ✅ Implemented |
| 3 | Massive (Polygon.io) | Tick data, WebSocket, partner APIs | US primarily | ✅ Implemented |
| 4 | Alpha Vantage | Server-side indicators | US primarily | Scaffolded |

**EODHD exchange coverage includes:** LSE (UK), NYSE/NASDAQ (US), Euronext (EU), XETRA (DE), SIX (CH), TSE (JP), ASX (AU), HKEX (HK), and 60+ more.

## Brokers

| Broker | Asset Class | Use | Global Access |
|--------|-------------|-----|---------------|
| **Alpaca** | Equities | Paper trading (free) | US equities |
| **IBKR** | Equities | Live trading | 150+ exchanges globally |
| **Coinbase** | Crypto | Primary crypto (sandbox) | BTC/GBP, ETH/GBP |
| **Binance** | Crypto | Fallback crypto (testnet) | BTC/USDT |
| **PaperBroker** | All | Backtest simulation only | N/A |

## Available Commands

| Command | Description |
|---------|-------------|
| `python main.py backtest` | Run backtest with daily bars |
| `python main.py sim_live` | Historical replay with full trading pipeline |
| `python main.py paper` | Live paper trading (requires broker keys) |
| `python main.py paper_trial` | Automated paper trial from manifest config |
| `python main.py uk_health_check` | Verify broker connectivity and data quality |
| `python main.py research_train_xgboost` | Train XGBoost model from experiment config |
| `python main.py research_download_ticks` | Download historical tick data (Polygon) |
| `python main.py research_build_tick_splits` | Build reproducible train/val/test data splits |

## Strategies

All strategies inherit from `BaseStrategy` and implement `generate_signal(symbol) -> Optional[Signal]`.

| Strategy | Type | Description |
|----------|------|-------------|
| MA Crossover | Trend | Golden/death cross (configurable fast/slow SMA) |
| RSI Momentum | Mean Reversion | Overbought/oversold detection |
| MACD Crossover | Momentum | MACD line/signal line crossover |
| Bollinger Bands | Mean Reversion | Price vs. 2σ bands |
| ATR Stops | Volatility | ATR-scaled trailing stops |
| ADX Filter | Trend Filter | Trend strength gating (avoid choppy markets) |
| OBV Momentum | Volume | On-balance volume accumulation |
| Stochastic Oscillator | Mean Reversion | %K/%D crossover |
| Pairs Mean Reversion | Statistical Arb | Cointegrated pair spread trading |
| ML Strategy Wrapper | ML-Backed | XGBoost/MLP model signal generation |

### Adding a New Strategy

1. Create `src/strategies/<name>.py` subclassing `BaseStrategy`
2. Implement `generate_signal(symbol)` and `min_bars_required()`
3. Register in `src/cli/runtime.py` strategy map
4. Add tests in `tests/test_strategies.py`

See `src/strategies/ma_crossover.py` as the canonical example.

## ML / Research Pipeline

The research track supports offline strategy development with a 4-stage promotion gate:

| Stage | Name | Requirement |
|-------|------|-------------|
| R1 | Experimental | Reproducible experiment with metadata |
| R2 | Validated | Walk-forward + out-of-sample evidence |
| R3 | Paper-Qualified | Passes paper trial with fills |
| R4 | Production-Approved | Live gate criteria met |

**Current ML models:**
- **XGBoost** — Walk-forward validated with SHAP feature importance (✅ Implemented)
- **MLP** — Feedforward neural net baseline via skorch/PyTorch (✅ Implemented)
- **LSTM** — Deep sequence model (planned, gated behind MLP performance)

```bash
# Run XGBoost pipeline
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json

# Inspect config or list presets
python main.py research_train_xgboost --config research/experiments/configs/xgboost_example.json --dry-run
python main.py research_train_xgboost --print-presets
```

## Testing

```bash
python -m pytest tests/ -v          # Run all tests
python -m pytest tests/ -v -k rsi   # Run specific tests
```

Current baseline: **657 tests passing**. All tests must pass before any change is committed.

## Configuration

All parameters live in `config/settings.py`. Key settings:

- **Data source** — `DataConfig.source = "eodhd"` (primary), `fallback_sources = ["yfinance"]`
- **Symbols** — which tickers to trade (supports any EODHD/IBKR-accessible exchange)
- **Strategy parameters** — lookback periods, thresholds
- **Risk limits** — max position size, daily loss limit, VaR threshold
- **Broker config** — API keys loaded from `.env`, sandbox/testnet flags

Paper trial presets are in `configs/` (conservative, standard, aggressive).

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `EODHD_API_KEY` | Yes (for primary data) | EODHD market data API key |
| `ALPACA_API_KEY` | For paper trading | Alpaca paper trading key |
| `ALPACA_SECRET_KEY` | For paper trading | Alpaca paper trading secret |
| `IBKR_HOST` | For live trading | IBKR TWS/Gateway host |
| `COINBASE_API_KEY` | For crypto | Coinbase Advanced Trade key |
| `BINANCE_API_KEY` | For crypto fallback | Binance API key |

## Project Scope

**Operated from the UK**, trading any equity market accessible via IBKR and EODHD (ADR-023):

- **UK** — LSE (FTSE 100/250, ETFs)
- **US** — NYSE, NASDAQ
- **Europe** — Euronext, XETRA, SIX
- **Asia-Pacific** — TSE, ASX, HKEX
- **Crypto** — BTC/GBP via Coinbase (primary), Binance (fallback)
- **Forex** — Planned via EODHD forex endpoints

Base currency: **GBP**. UK tax export, FX normalisation, and session guardrails are built in. Research baseline uses UK equities (FTSE 100/250); global equities available for expanded analysis.

## Documentation

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](CLAUDE.md) | Full architecture context, invariants, how-to guides |
| [PROJECT_DESIGN.md](PROJECT_DESIGN.md) | Design authority — ADRs, RFCs, technical debt, evolution log |
| [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) | Task queue and progress tracking |
| [EXECUTION_FLOW.md](EXECUTION_FLOW.md) | Detailed startup/runtime flow diagrams per mode |
| [DATA_MODELS.md](DATA_MODELS.md) | Data type and schema reference |
| [.python-style-guide.md](.python-style-guide.md) | Code style standards and enforcement |
| [UK_OPERATIONS.md](UK_OPERATIONS.md) | UK paper trading operational runbook |
| [TRIAL_MANIFEST.md](TRIAL_MANIFEST.md) | Paper trial configuration framework |
| [docs/DATA_PROVIDERS_REFERENCE.md](docs/DATA_PROVIDERS_REFERENCE.md) | External data provider API reference |
| [docs/PROMOTION_FRAMEWORK.md](docs/PROMOTION_FRAMEWORK.md) | Strategy promotion gates and criteria |
| [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md) | Risk gap analysis and remediation |
| [research/README.md](research/README.md) | Research pipeline governance |

## Tech Stack

- **Python 3.10+** — Core runtime
- **EODHD API** — Primary market data (OHLCV, fundamentals, corporate actions, forex)
- **pandas / numpy** — Data manipulation
- **ta** — Technical indicators
- **alpaca-py / ib_insync** — Equity broker integrations
- **coinbase-advanced-py / python-binance** — Crypto broker integrations
- **XGBoost** — Gradient boosting ML models
- **PyTorch / skorch** — Neural network models (MLP, planned LSTM)
- **scikit-learn** — Calibration, metrics, preprocessing
- **SQLite** — Operational data (audit log, registry, kill switch)
- **Parquet** — Research data (historical OHLCV snapshots, feature cache)
- **pytest** — Testing (657 tests)
- **black / pylint / pre-commit** — Code quality enforcement

## Project Status

- **91 implementation steps completed** out of 107 total
- **10 strategies** implemented and tested
- **5 brokers** integrated (Alpaca, IBKR, Coinbase, Binance, PaperBroker)
- **EODHD** as primary data provider covering 70+ global exchanges
- **657 tests** passing
- Paper trading pipeline operational
- Research pipeline with XGBoost/MLP training and walk-forward validation
- **Next up:** EODHD fundamentals pipeline, cross-dataset correlational analysis, forex integration

See [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) for current progress and the full task queue.

## License

Private project — not for redistribution.
