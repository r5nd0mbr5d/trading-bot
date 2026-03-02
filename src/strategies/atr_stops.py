"""ATR volatility-scaled trend strategy."""

from datetime import datetime, timezone
from typing import Optional

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.indicators.atr import atr_stop_loss, compute_atr
from src.strategies.base import BaseStrategy


class ATRStopsStrategy(BaseStrategy):
    """Generate long entries when trend is up and volatility is relatively low."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.atr_period = settings.atr.period
        self.fast_ma_period = settings.atr.fast_ma_period
        self.slow_ma_period = settings.atr.slow_ma_period
        self.low_vol_threshold_pct = settings.atr.low_vol_threshold_pct
        self.stop_multiplier = settings.atr.stop_multiplier

    def min_bars_required(self) -> int:
        return max(self.atr_period + 1, self.slow_ma_period + 1)

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        close = df["close"]
        fast_ma = close.rolling(self.fast_ma_period).mean()
        slow_ma = close.rolling(self.slow_ma_period).mean()

        atr_series = compute_atr(df, period=self.atr_period)
        atr_now = float(atr_series.iloc[-1])
        if atr_now <= 0:
            return None

        close_now = float(close.iloc[-1])
        atr_ratio = atr_now / close_now if close_now > 0 else 0.0

        trend_up_now = fast_ma.iloc[-1] > slow_ma.iloc[-1]
        trend_up_prev = fast_ma.iloc[-2] > slow_ma.iloc[-2]
        low_vol_now = atr_ratio <= self.low_vol_threshold_pct
        low_vol_prev = (
            float(atr_series.iloc[-2]) / float(close.iloc[-2])
        ) <= self.low_vol_threshold_pct

        if trend_up_now and low_vol_now and (not trend_up_prev or not low_vol_prev):
            stop_price = atr_stop_loss(close_now, atr_now, multiplier=self.stop_multiplier)
            strength = min(
                max(
                    (self.low_vol_threshold_pct - atr_ratio)
                    / max(self.low_vol_threshold_pct, 1e-9),
                    0.0,
                ),
                1.0,
            )
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "atr_value": round(atr_now, 6),
                    "stop_price": round(stop_price, 6),
                    "fast_ma": round(float(fast_ma.iloc[-1]), 6),
                    "slow_ma": round(float(slow_ma.iloc[-1]), 6),
                },
            )

        if not trend_up_now and trend_up_prev:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={
                    "atr_value": round(atr_now, 6),
                    "stop_price": round(
                        atr_stop_loss(close_now, atr_now, multiplier=self.stop_multiplier), 6
                    ),
                    "fast_ma": round(float(fast_ma.iloc[-1]), 6),
                    "slow_ma": round(float(slow_ma.iloc[-1]), 6),
                },
            )

        return None
