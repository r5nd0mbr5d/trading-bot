"""MACD Crossover Strategy.

Signal logic:
  BUY  — MACD line crosses above the signal line (histogram goes from negative to non-negative)
  SELL — MACD line crosses below the signal line (histogram goes from positive to non-positive)

Enterprise context:
  MACD (Moving Average Convergence Divergence) is a momentum indicator that shows the
  relationship between two EMAs of a security's price. The MACD line crossing the signal
  line is widely used as a buy/sell trigger. In practice it is combined with:
    - Volume confirmation (only trade if volume > N-day average)
    - Trend filters (only take MACD longs in an uptrend via 200-day SMA)
    - Divergence analysis (price vs MACD divergence for early reversal detection)
  Those extensions can be added in generate_signal() without touching the engine.
"""

from datetime import datetime, timezone
from typing import Optional

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class MACDCrossoverStrategy(BaseStrategy):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9

    def min_bars_required(self) -> int:
        return 36

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        close = df["close"]

        # Calculate MACD line = EMA(12) - EMA(26)
        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow

        # Calculate signal line = EMA(9) of MACD line
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

        # Histogram = MACD - Signal
        histogram = macd_line - signal_line

        curr_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2]

        curr_macd = macd_line.iloc[-1]
        curr_signal = signal_line.iloc[-1]

        # BUY: MACD crosses above signal line (histogram goes negative -> non-negative)
        if prev_hist < 0 and curr_hist >= 0:
            meta = {
                "macd": round(curr_macd, 4),
                "signal_line": round(curr_signal, 4),
                "histogram": round(curr_hist, 4),
            }
            atr = self.get_atr(symbol, period=self.settings.strategy.atr_period)
            if atr is not None:
                meta["atr"] = round(atr, 4)
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=min(abs(curr_hist) / 0.5, 1.0),
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata=meta,
            )

        # SELL: MACD crosses below signal line (histogram goes positive -> non-positive)
        if prev_hist > 0 and curr_hist <= 0:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=min(abs(curr_hist) / 0.5, 1.0),
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "macd": round(curr_macd, 4),
                    "signal_line": round(curr_signal, 4),
                    "histogram": round(curr_hist, 4),
                },
            )

        return None
