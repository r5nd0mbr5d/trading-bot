"""Abstract base class for all trading strategies.

To add a new strategy:
1. Subclass BaseStrategy
2. Implement generate_signal(symbol) -> Optional[Signal]
3. Register it in main.py STRATEGIES dict
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import Settings
from src.data.models import Bar, Signal
from src.indicators.atr import compute_atr


class BaseStrategy(ABC):
    """
    Strategies receive Bar objects via on_bar() and emit Signal objects.
    The engine calls on_bar() for every new price bar.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = self.__class__.__name__
        self._bar_history: Dict[str, List[Bar]] = {}
        self._context: Optional[Any] = None
        self._alternative_registry: Optional[Any] = None

    def set_context(self, context: Optional[Any]) -> None:
        """Set or clear strategy execution context."""
        self._context = context

    def set_alternative_registry(self, registry: Optional[Any]) -> None:
        """Attach or clear alternative data registry."""
        self._alternative_registry = registry

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Called by the engine/stream on each new bar. Do not override."""
        if bar.symbol not in self._bar_history:
            self._bar_history[bar.symbol] = []
        self._bar_history[bar.symbol].append(bar)
        return self.generate_signal(bar.symbol)

    def get_history_df(self, symbol: str) -> pd.DataFrame:
        """Convert stored bars to a DataFrame for indicator calculation."""
        bars = self._bar_history.get(symbol, [])
        if not bars:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "timestamp": b.timestamp,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ]
        ).set_index("timestamp")

    def get_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Return the current ATR for a symbol, or None if insufficient history.

        ATR requires at least (period + 1) bars: one extra bar for the
        True Range calculation which needs the previous close.

        Args:
            symbol: Ticker symbol.
            period: ATR smoothing period (default 14).

        Returns:
            Current ATR as a float, or None if < period+1 bars available.
        """
        df = self.get_history_df(symbol)
        if len(df) < period + 1:
            return None
        atr_series = compute_atr(df, period=period)
        val = atr_series.iloc[-1]
        if pd.isna(val) or val <= 0:
            return None
        return float(val)

    def get_alternative_features(self, symbol: str) -> pd.DataFrame:
        """Return alternative feature frame aligned to current symbol history."""
        history = self.get_history_df(symbol)
        if history.empty:
            return pd.DataFrame(index=history.index)
        if self._alternative_registry is None:
            return pd.DataFrame(index=history.index)

        as_of = getattr(self._context, "current_timestamp", None)
        return self._alternative_registry.get_features(
            symbol,
            history.index,
            as_of=as_of,
            start=history.index.min().to_pydatetime(),
            end=history.index.max().to_pydatetime(),
        )

    def load_history(self, symbol: str, df: pd.DataFrame) -> None:
        """Pre-load historical bars (used by BacktestEngine before replay)."""
        bars = []
        for ts, row in df.iterrows():
            dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                )
            )
        self._bar_history[symbol] = bars

    @abstractmethod
    def generate_signal(self, symbol: str) -> Optional[Signal]:
        """Produce a Signal (or None) from the current bar history."""
        ...

    def min_bars_required(self) -> int:
        """Minimum bars needed before this strategy can generate a signal."""
        return 1

    def required_symbols(self) -> list[str]:
        """Optional extra symbols required by strategy logic."""
        return []
