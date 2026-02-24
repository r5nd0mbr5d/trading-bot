"""Average Directional Index (ADX) indicator."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ADX using `ta` library when available, else Wilder-style fallback."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    try:
        from ta.trend import ADXIndicator

        indicator = ADXIndicator(high=high, low=low, close=close, window=period, fillna=False)
        return indicator.adx()
    except Exception:
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(span=period, min_periods=period, adjust=False).mean()
        plus_di = (
            100 * pd.Series(plus_dm, index=high.index).ewm(span=period, adjust=False).mean() / atr
        )
        minus_di = (
            100 * pd.Series(minus_dm, index=high.index).ewm(span=period, adjust=False).mean() / atr
        )

        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        return dx.ewm(span=period, min_periods=period, adjust=False).mean()
