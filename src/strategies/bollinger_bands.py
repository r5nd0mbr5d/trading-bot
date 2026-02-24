"""Bollinger Bands Strategy.

Signal logic:
  BUY  — price closes at or below the lower band (mean-reversion entry).
  SELL — price crosses back above the middle band (20-day SMA).

Enterprise context:
  Bollinger Bands are a classic volatility-adjusted mean-reversion strategy.
  In practice they are combined with:
    - Volume confirmation (high volume on lower band touch)
    - RSI filter (enter only when RSI is simultaneously oversold)
    - Band width filter (skip signals when bands are very narrow / low vol)
  Those extensions can be added in generate_signal() without touching the engine.
"""

from datetime import datetime, timezone
from typing import Optional

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.period = settings.strategy.bb_period  # default: 20
        self.num_std = settings.strategy.bb_std  # default: 2.0

    def min_bars_required(self) -> int:
        # Need `period` bars for a valid rolling window + 1 bar for the
        # prev/curr comparison used by the SELL crossover condition.
        return self.period + 1

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        close = df["close"]
        middle = close.rolling(self.period).mean()
        std = close.rolling(self.period).std()
        lower = middle - self.num_std * std

        curr_std = std.iloc[-1]
        # No meaningful bands when there is zero (or invalid) volatility.
        if not (curr_std > 0):
            return None

        curr_close = close.iloc[-1]
        curr_middle = middle.iloc[-1]
        curr_lower = lower.iloc[-1]

        prev_close = close.iloc[-2]
        prev_middle = middle.iloc[-2]

        # BUY: price touches or breaks below the lower band (oversold).
        if curr_close <= curr_lower:
            band_width = curr_middle - curr_lower
            strength = min((curr_middle - curr_close) / band_width, 1.0)
            meta = {
                "close": round(curr_close, 4),
                "lower_band": round(curr_lower, 4),
                "middle_band": round(curr_middle, 4),
            }
            atr = self.get_atr(symbol, period=self.settings.strategy.atr_period)
            if atr is not None:
                meta["atr"] = round(atr, 4)
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata=meta,
            )

        # SELL: price crosses back above the middle band (mean reversion exit).
        if prev_close < prev_middle and curr_close >= curr_middle:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "close": round(curr_close, 4),
                    "middle_band": round(curr_middle, 4),
                },
            )

        return None
