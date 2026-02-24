"""Moving Average Crossover Strategy.

Signal logic:
  BUY  — fast MA crosses above slow MA (golden cross)
  SELL — fast MA crosses below slow MA (death cross)

Enterprise context:
  MA crossover is the canonical baseline strategy. Most quant shops use it as
  a benchmark to beat. In practice it is combined with:
    - Volume confirmation (only trade if volume > N-day average)
    - Volatility filter (ATR threshold to avoid choppy markets)
    - Trend strength (ADX > 25 filter)
  Those extensions can be added in generate_signal() without touching the engine.
"""

from datetime import datetime, timezone
from typing import Optional

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class MACrossoverStrategy(BaseStrategy):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.fast = settings.strategy.fast_period  # default: 20
        self.slow = settings.strategy.slow_period  # default: 50

    def min_bars_required(self) -> int:
        return self.slow + 1

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        close = df["close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()

        curr_above = fast_ma.iloc[-1] > slow_ma.iloc[-1]
        prev_above = fast_ma.iloc[-2] > slow_ma.iloc[-2]

        if curr_above and not prev_above:
            # Golden cross: fast crossed above slow
            spread = (fast_ma.iloc[-1] - slow_ma.iloc[-1]) / slow_ma.iloc[-1]
            meta = {
                "fast_ma": round(fast_ma.iloc[-1], 4),
                "slow_ma": round(slow_ma.iloc[-1], 4),
            }
            atr = self.get_atr(symbol, period=self.settings.strategy.atr_period)
            if atr is not None:
                meta["atr"] = round(atr, 4)
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=min(abs(spread) * 10, 1.0),  # normalise to 0-1
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata=meta,
            )

        if not curr_above and prev_above:
            # Death cross: fast crossed below slow
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "fast_ma": round(fast_ma.iloc[-1], 4),
                    "slow_ma": round(slow_ma.iloc[-1], 4),
                },
            )

        return None
