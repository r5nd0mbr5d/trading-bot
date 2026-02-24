"""Stochastic oscillator mean-reversion strategy."""

from datetime import datetime, timezone
from typing import Optional

from ta.momentum import StochasticOscillator

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class StochasticOscillatorStrategy(BaseStrategy):
    """Generate signals from %K/%D crossovers in overbought/oversold regions."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.k_period = settings.stochastic.k_period
        self.d_period = settings.stochastic.d_period
        self.smooth_window = settings.stochastic.smooth_window
        self.oversold = settings.stochastic.oversold
        self.overbought = settings.stochastic.overbought

    def min_bars_required(self) -> int:
        return self.k_period + self.smooth_window + self.d_period

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        indicator = StochasticOscillator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=self.k_period,
            smooth_window=self.smooth_window,
        )
        k_line = indicator.stoch()
        d_line = k_line.rolling(self.d_period).mean()

        curr_k = float(k_line.iloc[-1])
        prev_k = float(k_line.iloc[-2])
        curr_d = float(d_line.iloc[-1])
        prev_d = float(d_line.iloc[-2])

        if prev_k < prev_d and curr_k > curr_d and curr_k <= self.oversold:
            strength = min(max((self.oversold - curr_k) / max(self.oversold, 1.0), 0.0), 1.0)
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "stoch_k": round(curr_k, 2),
                    "stoch_d": round(curr_d, 2),
                },
            )

        if prev_k > prev_d and curr_k < curr_d and curr_k >= self.overbought:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "stoch_k": round(curr_k, 2),
                    "stoch_d": round(curr_d, 2),
                },
            )

        return None
