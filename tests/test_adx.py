"""Tests for ADX indicator and ADX signal filter."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config.settings import Settings
from src.data.models import Bar, Signal, SignalType
from src.indicators.adx import compute_adx
from src.strategies.adx_filter import ADXFilterStrategy
from src.strategies.base import BaseStrategy


class _AlwaysLongStrategy(BaseStrategy):
    def min_bars_required(self) -> int:
        return 2

    def generate_signal(self, symbol: str):
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None
        return Signal(
            symbol=symbol,
            signal_type=SignalType.LONG,
            strength=0.6,
            timestamp=datetime.now(timezone.utc),
            strategy_name=self.name,
            metadata={"source": "always_long"},
        )


def _bar(symbol: str, close: float, i: int, spread: float = 1.0) -> Bar:
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
    return Bar(
        symbol=symbol,
        timestamp=ts,
        open=close,
        high=close + spread,
        low=close - spread,
        close=close,
        volume=1000.0,
    )


def test_compute_adx_matches_ta_reference():
    ta = __import__("ta")
    _ = ta

    idx = pd.date_range("2025-01-01", periods=120, freq="D", tz="UTC")
    close = pd.Series(
        100 + np.linspace(0, 20, len(idx)) + np.sin(np.arange(len(idx)) / 4.0), index=idx
    )
    frame = pd.DataFrame(
        {
            "high": close + 1.2,
            "low": close - 1.2,
            "close": close,
        },
        index=idx,
    )

    ours = compute_adx(frame, period=14)

    from ta.trend import ADXIndicator

    ref = ADXIndicator(frame["high"], frame["low"], frame["close"], window=14, fillna=False).adx()
    aligned = pd.concat([ours, ref], axis=1).dropna()

    max_abs_err = (aligned.iloc[:, 0] - aligned.iloc[:, 1]).abs().max()
    assert float(max_abs_err) < 1e-6


def test_adx_filter_blocks_low_trend_sideways_market():
    settings = Settings()
    settings.strategy.adx_period = 14
    settings.strategy.adx_threshold = 25.0

    wrapped = _AlwaysLongStrategy(settings)
    strategy = ADXFilterStrategy(settings, wrapped)

    prices = [100.0 + (0.2 if i % 2 == 0 else -0.2) for i in range(40)]
    signal_count = 0
    for i, price in enumerate(prices):
        signal = strategy.on_bar(_bar("TEST", price, i, spread=0.3))
        if signal is not None:
            signal_count += 1

    assert signal_count == 0
