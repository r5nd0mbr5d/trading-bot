# config/

This directory contains the **Python configuration module** for the trading bot.

| File | Purpose |
|------|---------|
| `settings.py` | Central `Settings` dataclass — all runtime parameters (broker, strategy, risk, data). Loaded at startup via `from config.settings import Settings`. |
| `test_baskets.json` | Symbol basket definitions used in tests and health checks. |
| `test_regimes.json` | Market-regime definitions for strategy validation tests. |
| `uk_correlations.json` | UK equity correlation matrix for the risk manager's correlation limiter. |

## Usage

```python
from config.settings import Settings

settings = Settings()           # loads from environment / defaults
settings.strategy.name          # e.g. "ma_crossover"
settings.data.symbols           # e.g. ["AAPL", "MSFT"]
```

> **Note:** This directory is the authoritative Python config. Do **not** add raw trial JSON
> manifests here — those live in `configs/`.
