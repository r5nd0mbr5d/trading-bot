"""ADX filter wrapper strategy."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import Settings
from src.data.models import Bar, Signal
from src.indicators.adx import compute_adx
from src.strategies.base import BaseStrategy


class ADXFilterStrategy(BaseStrategy):
    """Wraps another strategy and suppresses signals when ADX is below threshold."""

    def __init__(self, settings: Settings, wrapped_strategy: BaseStrategy):
        super().__init__(settings)
        self.wrapped_strategy = wrapped_strategy
        self.adx_period = settings.strategy.adx_period
        self.adx_threshold = settings.strategy.adx_threshold
        self.name = f"{wrapped_strategy.name}+ADX"

    def min_bars_required(self) -> int:
        return max(self.wrapped_strategy.min_bars_required(), self.adx_period + 1)

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        if bar.symbol not in self._bar_history:
            self._bar_history[bar.symbol] = []
        self._bar_history[bar.symbol].append(bar)

        signal = self.wrapped_strategy.on_bar(bar)
        if signal is None:
            return None

        df = self.get_history_df(bar.symbol)
        if len(df) < self.adx_period + 1:
            return None

        adx_series = compute_adx(df, period=self.adx_period)
        adx_value = adx_series.iloc[-1]
        if pd.isna(adx_value) or float(adx_value) < float(self.adx_threshold):
            return None

        metadata = dict(signal.metadata or {})
        metadata["adx"] = round(float(adx_value), 4)
        metadata["adx_threshold"] = float(self.adx_threshold)
        signal.metadata = metadata
        signal.strategy_name = self.name
        return signal

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        return None
