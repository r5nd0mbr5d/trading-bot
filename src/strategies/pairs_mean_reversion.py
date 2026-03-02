"""Pairs mean-reversion benchmark strategy.

This strategy computes a rolling z-score for the spread between two symbols and
emits long-only entry/exit signals on the configured primary symbol.
"""

from datetime import datetime, timezone
from typing import Optional

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class PairsMeanReversionStrategy(BaseStrategy):
    """Rolling z-score spread strategy for a two-symbol pair.

    Notes
    -----
    - Long-only benchmark in current runtime (`SignalType.SHORT` is not used).
    - Signals are emitted only for the configured primary symbol.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings)
        symbols = settings.data.symbols
        if len(symbols) < 2:
            raise ValueError("PairsMeanReversionStrategy requires at least 2 configured symbols")

        self.primary_symbol = settings.strategy.pair_primary_symbol or symbols[0]
        self.secondary_symbol = settings.strategy.pair_secondary_symbol or symbols[1]
        self.lookback = settings.strategy.pair_lookback
        self.entry_zscore = settings.strategy.pair_entry_zscore
        self.exit_zscore = settings.strategy.pair_exit_zscore
        self.max_holding_bars = settings.strategy.pair_max_holding_bars
        self.hedge_ratio = settings.strategy.pair_hedge_ratio

        self._position_open = False
        self._bars_since_entry = 0

    def min_bars_required(self) -> int:
        return self.lookback

    def _compute_zscore(self) -> Optional[float]:
        primary_df = self.get_history_df(self.primary_symbol)
        secondary_df = self.get_history_df(self.secondary_symbol)

        if (
            len(primary_df) < self.min_bars_required()
            or len(secondary_df) < self.min_bars_required()
        ):
            return None

        lookback = min(self.lookback, len(primary_df), len(secondary_df))
        primary_close = primary_df["close"].iloc[-lookback:].reset_index(drop=True)
        secondary_close = secondary_df["close"].iloc[-lookback:].reset_index(drop=True)

        spread = primary_close - (self.hedge_ratio * secondary_close)
        spread_std = float(spread.std())
        if spread_std <= 0.0:
            return None

        zscore = float((spread.iloc[-1] - spread.mean()) / spread_std)
        return zscore

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        if symbol != self.primary_symbol:
            return None

        zscore = self._compute_zscore()
        if zscore is None:
            return None

        if self._position_open:
            self._bars_since_entry += 1
            should_exit_by_reversion = abs(zscore) <= self.exit_zscore
            should_exit_by_timeout = self._bars_since_entry >= self.max_holding_bars

            if should_exit_by_reversion or should_exit_by_timeout:
                self._position_open = False
                self._bars_since_entry = 0
                return Signal(
                    symbol=self.primary_symbol,
                    signal_type=SignalType.CLOSE,
                    strength=1.0,
                    timestamp=datetime.now(timezone.utc),
                    strategy_name=self.name,
                    metadata={
                        "zscore": round(zscore, 4),
                        "entry_threshold": self.entry_zscore,
                        "exit_threshold": self.exit_zscore,
                        "bars_held": self._bars_since_entry,
                    },
                )
            return None

        if zscore <= -self.entry_zscore:
            self._position_open = True
            self._bars_since_entry = 0
            strength = min(abs(zscore) / max(self.entry_zscore, 1e-6), 1.0)
            return Signal(
                symbol=self.primary_symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "zscore": round(zscore, 4),
                    "entry_threshold": self.entry_zscore,
                    "exit_threshold": self.exit_zscore,
                    "pair": f"{self.primary_symbol}/{self.secondary_symbol}",
                },
            )

        return None
