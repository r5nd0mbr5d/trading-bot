"""Centralised configuration — all settings flow from here.

Add new parameters here rather than scattering magic numbers through the code.
Override any value via environment variables or by passing a custom Settings
object to each component.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DataConfig:
    source: str = "yfinance"           # yfinance | alpaca | polygon
    fallback_sources: List[str] = field(default_factory=list)
    symbols: List[str] = field(
        default_factory=lambda: ["HSBA.L", "LLOY.L", "BP.L", "RIO.L", "GLEN.L"]  # UK LSE symbols
    )
    timeframe: str = "1d"              # 1m | 5m | 15m | 1h | 1d
    lookback_days: int = 365
    cache_dir: str = "data/cache"
    cache_enabled: bool = True


@dataclass
class StrategyConfig:
    name: str = "ma_crossover"         # ma_crossover | rsi_momentum
    # Moving Average Crossover
    fast_period: int = 20
    slow_period: int = 50
    # RSI Momentum
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    # Bollinger Bands
    bb_period: int = 20
    bb_std: float = 2.0
    # ATR (shared across all strategies for volatility-scaled stops)
    atr_period: int = 14               # Wilder's default
    # ADX trend filter (optional gate for any strategy)
    use_adx_filter: bool = False
    adx_period: int = 14
    adx_threshold: float = 25.0


@dataclass
class DataQualityConfig:
    """Guards against stale bars and large session gaps."""
    max_bar_age_seconds: int = 1200    # 20 min for paper/yfinance (1-min bars often delay 10-15 min)
    max_bar_gap_seconds: int = 3600
    max_consecutive_stale: int = 3
    session_gap_skip_bars: int = 1
    enable_stale_check: bool = True    # Disable for paper trading with yfinance (known latency issue)


@dataclass
class RiskConfig:
    # Position sizing
    max_position_pct: float = 0.10     # Max 10% of portfolio in one position
    max_portfolio_risk_pct: float = 0.02  # Risk max 2% of portfolio per trade
    stop_loss_pct: float = 0.05        # 5% stop-loss from entry
    take_profit_pct: float = 0.15      # 15% take-profit from entry
    # Portfolio limits
    max_open_positions: int = 10
    max_drawdown_pct: float = 0.20     # Circuit breaker: halt at 20% drawdown
    # Additional circuit breakers
    max_intraday_loss_pct: float = 0.02   # Halt if portfolio drops >2% intraday
    consecutive_loss_limit: int = 5       # Halt after 5 consecutive losing trades
    # Portfolio VaR gate
    max_var_pct: float = 0.05             # Block new trades if 1-day VaR > 5%
    var_window: int = 252                 # Rolling window for VaR (trading days)
    # ATR-based stop / take-profit (used when strategy emits metadata["atr"])
    use_atr_stops: bool = True            # Prefer ATR stops over fixed %; falls back if ATR absent
    atr_multiplier: float = 2.0          # Stop = entry − atr_multiplier × ATR
    atr_tp_multiplier: float = 4.0       # TP   = entry + atr_tp_multiplier × ATR (2:1 R/R)
    # Sector concentration gate
    max_sector_concentration_pct: float = 0.40
    sector_map_path: str = "config/test_baskets.json"
    skip_sector_concentration: bool = False


@dataclass
class PaperGuardrailsConfig:
    """Paper-trading-only runtime safeguards (disabled in backtest)."""
    enabled: bool = True
    # Daily order limits
    max_orders_per_day: int = 50           # Halt after 50 orders today
    # Rejection rate limits
    max_rejects_per_hour: int = 5          # Halt if 5+ rejects in 1 hour
    # Per-symbol cooldown after reject
    reject_cooldown_seconds: int = 300     # 5-minute cooldown per symbol after reject
    # Session window constraints
    session_start_hour: int = 8            # Stop trading before 8 AM (UTC)
    session_end_hour: int = 16             # Stop trading after 4 PM (UTC)
    session_timezone: str = "UTC"         # Interpret session hours in this timezone (e.g., Europe/London)
    # Auto-stop conditions
    max_consecutive_rejects: int = 3       # Halt after 3 consecutive rejects
    consecutive_reject_reset_minutes: int = 60  # Reset counter if 60 min passes without reject
    # Disable individual checks for testing
    skip_daily_limit: bool = False
    skip_reject_rate: bool = False
    skip_cooldown: bool = False
    skip_session_window: bool = False
    skip_auto_stop: bool = False


@dataclass
class ReconciliationConfig:
    """Broker-vs-internal reconciliation tolerances."""
    enabled: bool = True
    # Position tolerance: allow ±N shares difference per symbol
    position_tolerance_shares: float = 1.0
    # Cash tolerance: allow ±N dollars difference
    cash_tolerance_dollars: float = 0.01
    # Portfolio value tolerance: allow ±N% difference
    value_tolerance_pct: float = 0.5
    # Reconciliation frequency: every N fills
    reconcile_every_n_fills: int = 10
    # Skip individual checks for testing
    skip_position_check: bool = False
    skip_cash_check: bool = False
    skip_value_check: bool = False


@dataclass
class BrokerConfig:
    provider: str = field(default_factory=lambda: os.getenv("BROKER_PROVIDER", "ibkr"))  # alpaca | ibkr
    api_key: str = field(
        default_factory=lambda: os.getenv("ALPACA_API_KEY", "")
    )
    secret_key: str = field(
        default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", "")
    )
    paper_trading: bool = True
    base_url: str = "https://paper-api.alpaca.markets"
    # Transaction cost model (used by BacktestEngine)
    slippage_pct: float = 0.0005         # 0.05% slippage per fill
    commission_per_share: float = 0.005  # $0.005 per share commission
    # Interactive Brokers (UK live trading alternative — requires TWS or IB Gateway)
    ibkr_host: str = field(default_factory=lambda: os.getenv("IBKR_HOST", "127.0.0.1"))
    ibkr_port: int = field(default_factory=lambda: int(os.getenv("IBKR_PORT", "7497")))
    ibkr_client_id: int = field(default_factory=lambda: int(os.getenv("IBKR_CLIENT_ID", "1")))
    outage_retry_attempts: int = field(default_factory=lambda: int(os.getenv("BROKER_OUTAGE_RETRY_ATTEMPTS", "3")))
    outage_backoff_base_seconds: float = field(default_factory=lambda: float(os.getenv("BROKER_OUTAGE_BACKOFF_BASE_SECONDS", "0.25")))
    outage_backoff_max_seconds: float = field(default_factory=lambda: float(os.getenv("BROKER_OUTAGE_BACKOFF_MAX_SECONDS", "2.0")))
    outage_backoff_jitter_seconds: float = field(default_factory=lambda: float(os.getenv("BROKER_OUTAGE_BACKOFF_JITTER_SECONDS", "0.1")))
    outage_consecutive_failure_limit: int = field(default_factory=lambda: int(os.getenv("BROKER_OUTAGE_CONSECUTIVE_FAILURE_LIMIT", "3")))
    outage_skip_retries: bool = field(default_factory=lambda: os.getenv("BROKER_OUTAGE_SKIP_RETRIES", "false").strip().lower() in {"1", "true", "yes", "on"})
    # Optional per-symbol contract routing overrides, e.g.
    # {"HSBA.L": {"ib_symbol": "HSBA", "exchange": "SMART", "currency": "GBP", "primary_exchange": "LSE"}}
    ibkr_symbol_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class Settings:
    data: DataConfig = field(default_factory=DataConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    paper_guardrails: PaperGuardrailsConfig = field(default_factory=PaperGuardrailsConfig)
    reconciliation: ReconciliationConfig = field(default_factory=ReconciliationConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    initial_capital: float = 100_000.0
    base_currency: str = field(default_factory=lambda: os.getenv("BASE_CURRENCY", "GBP"))  # GBP for UK, USD for US
    # FX rates keyed as "FROM_TO", e.g. {"USD_GBP": 0.79, "GBP_USD": 1.2658}
    fx_rates: Dict[str, float] = field(default_factory=dict)
    # FX rate timestamps keyed by pair, ISO-8601 strings (UTC recommended)
    fx_rate_timestamps: Dict[str, str] = field(default_factory=dict)
    fx_rate_max_age_hours: float = 24.0
    risk_free_rate: float = 0.0        # Annualised, used in Sharpe ratio calculation
    market_timezone: str = field(default_factory=lambda: os.getenv("MARKET_TIMEZONE", "Europe/London"))
    enforce_market_hours: bool = True
    log_dir: Path = Path("logs")
    db_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///trading.db")
    )
    db_url_paper: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL_PAPER", "sqlite:///trading_paper.db")
    )
    db_url_live: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL_LIVE", "sqlite:///trading_live.db")
    )
    db_url_test: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL_TEST", "sqlite:///trading_test.db")
    )
    strict_db_isolation: bool = field(
        default_factory=lambda: os.getenv("STRICT_DB_ISOLATION", "true").strip().lower() in {"1", "true", "yes", "on"}
    )
    auto_rotate_paper_db: bool = field(
        default_factory=lambda: os.getenv("AUTO_ROTATE_PAPER_DB", "false").strip().lower() in {"1", "true", "yes", "on"}
    )
    paper_db_archive_dir: str = field(
        default_factory=lambda: os.getenv("PAPER_DB_ARCHIVE_DIR", "archives/db")
    )
