"""Average True Range (ATR) indicator.

ATR measures market volatility by decomposing the full price range for a bar,
including gaps from the previous close.  It is used for:

  - Volatility-scaled stop-loss placement (e.g. entry − 2×ATR)
  - Dynamic take-profit targets        (e.g. entry + 4×ATR  →  2:1 R/R)
  - Position sizing based on current volatility
  - Regime detection (high ATR = expanding vol, low ATR = consolidation)

Formula (Wilder, 1978):
  True Range[t] = max(
      High[t] − Low[t],
      |High[t] − Close[t-1]|,
      |Low[t]  − Close[t-1]|,
  )
  ATR[t] = EWM(True Range, span=period, adjust=False)   ← Wilder smoothing
"""

import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Wilder's exponentially-smoothed ATR.

    Args:
        df:      DataFrame with 'high', 'low', 'close' columns.
        period:  Smoothing window (default 14 — Wilder's original).

    Returns:
        pd.Series of ATR values aligned to df.index.
        First (period − 1) values are NaN (insufficient history).

    Example:
        >>> atr = compute_atr(df, period=14)
        >>> current_atr = atr.iloc[-1]   # e.g. 3.45 for a $150 stock ≈ 2.3%
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(span=period, min_periods=period, adjust=False).mean()


def atr_stop_loss(entry_price: float, atr: float, multiplier: float = 2.0) -> float:
    """
    Return a volatility-adjusted stop-loss price.

    Stop = entry − multiplier × ATR

    A 2× multiplier keeps the stop outside normal daily noise for most stocks.
    Wider multipliers (2.5–3×) suit trending strategies; tighter (1.5×) suit
    mean-reversion strategies with higher win rates.

    Args:
        entry_price: Fill price of the buy order.
        atr:         Current ATR for the symbol.
        multiplier:  Number of ATR units below entry (default 2.0).

    Returns:
        Stop price, floored at 0.0001 (can't be negative).
    """
    return round(max(entry_price - multiplier * atr, 0.0001), 4)


def atr_take_profit(entry_price: float, atr: float, multiplier: float = 4.0) -> float:
    """
    Return a volatility-adjusted take-profit price.

    Target = entry + multiplier × ATR

    With stop at entry − 2×ATR and target at entry + 4×ATR, the reward:risk
    ratio is 2:1 — the standard institutional minimum.

    Args:
        entry_price: Fill price of the buy order.
        atr:         Current ATR for the symbol.
        multiplier:  Number of ATR units above entry (default 4.0 → 2:1 R/R).

    Returns:
        Take-profit price.
    """
    return round(entry_price + multiplier * atr, 4)
