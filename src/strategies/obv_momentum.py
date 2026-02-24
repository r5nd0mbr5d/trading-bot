"""On-Balance Volume momentum strategy."""

from datetime import datetime, timezone
from typing import Optional

from ta.volume import OnBalanceVolumeIndicator

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class OBVMomentumStrategy(BaseStrategy):
    """Generate signals from OBV fast/slow crossover momentum."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.fast_period = settings.obv.fast_period
        self.slow_period = settings.obv.slow_period

    def min_bars_required(self) -> int:
        return self.slow_period + 2

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        obv = OnBalanceVolumeIndicator(close=df["close"], volume=df["volume"]).on_balance_volume()
        obv_fast = obv.rolling(self.fast_period).mean()
        obv_slow = obv.rolling(self.slow_period).mean()

        curr_above = obv_fast.iloc[-1] > obv_slow.iloc[-1]
        prev_above = obv_fast.iloc[-2] > obv_slow.iloc[-2]

        if curr_above and not prev_above:
            denominator = max(abs(float(obv_slow.iloc[-1])), 1.0)
            spread = abs(float(obv_fast.iloc[-1] - obv_slow.iloc[-1])) / denominator
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=min(spread, 1.0),
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "obv": round(float(obv.iloc[-1]), 4),
                    "obv_fast": round(float(obv_fast.iloc[-1]), 4),
                    "obv_slow": round(float(obv_slow.iloc[-1]), 4),
                },
            )

        if not curr_above and prev_above:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "obv": round(float(obv.iloc[-1]), 4),
                    "obv_fast": round(float(obv_fast.iloc[-1]), 4),
                    "obv_slow": round(float(obv_slow.iloc[-1]), 4),
                },
            )

        return None
