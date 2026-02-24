"""RSI Momentum / Mean-Reversion Strategy.

Signal logic:
  BUY  — RSI crosses back above the oversold level (default 30)
  SELL — RSI crosses above the overbought level (default 70)

Enterprise context:
  RSI is one of the most widely used oscillators in systematic trading.
  Hedge funds typically use it as a mean-reversion filter:
    - Only buy when RSI < 30 AND price is above 200-day MA (trend filter)
    - Combine with volume to confirm breakouts
  Extensions to add: multi-timeframe RSI, RSI divergence, Stochastic RSI.
"""

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config.settings import Settings
from src.data.models import Signal, SignalType
from src.strategies.base import BaseStrategy


class RSIMomentumStrategy(BaseStrategy):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.period = settings.strategy.rsi_period  # default: 14
        self.oversold = settings.strategy.rsi_oversold  # default: 30.0
        self.overbought = settings.strategy.rsi_overbought  # default: 70.0

    def min_bars_required(self) -> int:
        return self.period + 2

    def _compute_rsi(self, closes: pd.Series) -> pd.Series:
        """Wilder's smoothed RSI (same as TradingView default)."""
        delta = closes.diff()
        gain = delta.clip(lower=0).ewm(span=self.period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(span=self.period, adjust=False).mean()
        rs = gain / loss.replace(0, float("inf"))
        return 100 - 100 / (1 + rs)

    def generate_signal(self, symbol: str) -> Optional[Signal]:
        df = self.get_history_df(symbol)
        if len(df) < self.min_bars_required():
            return None

        rsi = self._compute_rsi(df["close"])
        curr = rsi.iloc[-1]
        prev = rsi.iloc[-2]

        if prev < self.oversold <= curr:
            # RSI recovering from oversold — buy
            strength = min((curr - self.oversold) / (50 - self.oversold), 1.0)
            meta = {"rsi": round(curr, 2)}
            atr = self.get_atr(symbol, period=self.settings.strategy.atr_period)
            if atr is not None:
                meta["atr"] = round(atr, 4)
            return Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=max(strength, 0.0),
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata=meta,
            )

        if prev < self.overbought <= curr:
            # RSI hit overbought — exit
            return Signal(
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                strength=1.0,
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.name,
                metadata={"rsi": round(curr, 2)},
            )

        return None
