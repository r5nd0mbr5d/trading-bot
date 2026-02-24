"""Feature engineering for research datasets (leakage-safe)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class FeatureRow:
    symbol: str
    date: pd.Timestamp
    log_return_1d: float
    log_return_5d: float
    log_return_21d: float
    price_vs_ma20: float
    price_vs_ma50: float
    price_vs_ma200: float
    bb_pct_b: float
    high_low_range: float
    gap_up: float
    volume_ratio_20d: float
    obv_normalised: float
    atr_pct: float
    realised_vol_5d: float
    realised_vol_21d: float
    vol_regime: float
    adx: float
    rsi_14: float
    macd_hist: float
    stoch_k: float
    roc_5: float
    roc_21: float
    market_return_5d: Optional[float]
    market_return_21d: Optional[float]
    beta_20d: Optional[float]


def _ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize("UTC")
    else:
        df = df.copy()
        df.index = df.index.tz_convert("UTC")
    return df


def _log_returns(close: pd.Series, periods: int) -> pd.Series:
    shifted = close.shift(periods)
    return np.log(close / shifted)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.inf)
    return 100 - 100 / (1 + rs)


def _macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def _stoch_k(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    return ((close - lowest_low) / denom) * 100


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0.0)
    return (direction * volume).cumsum()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(span=period, min_periods=period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(span=period, adjust=False).mean() / atr
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(span=period, min_periods=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = df["close"].astype(float).shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, min_periods=period, adjust=False).mean()


def compute_features(
    df: pd.DataFrame,
    *,
    symbol: str,
    market_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Compute leakage-safe feature frame using only bar[t] and earlier data."""
    df = _ensure_utc_index(df)
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    volume = df["volume"].astype(float)

    log_return_1d = _log_returns(close, 1)
    log_return_5d = _log_returns(close, 5)
    log_return_21d = _log_returns(close, 21)

    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()
    ma200 = close.rolling(window=200).mean()

    price_vs_ma20 = (close - ma20) / ma20
    price_vs_ma50 = (close - ma50) / ma50
    price_vs_ma200 = (close - ma200) / ma200

    bb_mid = ma20
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_pct_b = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    high_low_range = (high - low) / close.replace(0, np.nan)
    gap_up = (open_ - close.shift(1)) / close.shift(1).replace(0, np.nan)

    volume_ratio_20d = volume / volume.rolling(window=20).mean()
    obv = _obv(close, volume)
    obv_normalised = obv / obv.rolling(window=50).mean()

    atr = _atr(df, period=14)
    atr_pct = (atr / close.replace(0, np.nan)) * 100

    log_returns = close.pct_change().replace([np.inf, -np.inf], np.nan)
    realised_vol_5d = log_returns.rolling(window=5).std() * np.sqrt(252)
    realised_vol_21d = log_returns.rolling(window=21).std() * np.sqrt(252)
    vol_regime = realised_vol_5d / realised_vol_21d.replace(0, np.nan)

    adx = _adx(high, low, close, period=14)
    rsi_14 = _rsi(close, period=14)
    macd_hist = _macd_hist(close)
    stoch_k = _stoch_k(high, low, close, period=14)
    roc_5 = (close / close.shift(5) - 1) * 100
    roc_21 = (close / close.shift(21) - 1) * 100

    market_return_5d = None
    market_return_21d = None
    beta_20d = None
    if market_df is not None:
        market_df = _ensure_utc_index(market_df)
        if "close" not in market_df.columns:
            raise ValueError("market_df must include a 'close' column")
        market_close = market_df["close"].astype(float).reindex(df.index)
        market_ret = market_close.pct_change().replace([np.inf, -np.inf], np.nan)
        market_return_5d = _log_returns(market_close, 5)
        market_return_21d = _log_returns(market_close, 21)
        rolling_cov = log_returns.rolling(window=20).cov(market_ret)
        rolling_var = market_ret.rolling(window=20).var()
        beta_20d = rolling_cov / rolling_var.replace(0, np.nan)

    features = pd.DataFrame(
        {
            "symbol": symbol,
            "date": df.index,
            "log_return_1d": log_return_1d,
            "log_return_5d": log_return_5d,
            "log_return_21d": log_return_21d,
            "price_vs_ma20": price_vs_ma20,
            "price_vs_ma50": price_vs_ma50,
            "price_vs_ma200": price_vs_ma200,
            "bb_pct_b": bb_pct_b,
            "high_low_range": high_low_range,
            "gap_up": gap_up,
            "volume_ratio_20d": volume_ratio_20d,
            "obv_normalised": obv_normalised,
            "atr_pct": atr_pct,
            "realised_vol_5d": realised_vol_5d,
            "realised_vol_21d": realised_vol_21d,
            "vol_regime": vol_regime,
            "adx": adx,
            "rsi_14": rsi_14,
            "macd_hist": macd_hist,
            "stoch_k": stoch_k,
            "roc_5": roc_5,
            "roc_21": roc_21,
            "market_return_5d": market_return_5d,
            "market_return_21d": market_return_21d,
            "beta_20d": beta_20d,
        },
        index=df.index,
    )

    return features


def drop_nan_rows(features: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Drop rows with any NaN in required feature columns.

    Returns cleaned DataFrame and count of dropped rows.
    """
    feature_cols = [
        "log_return_1d",
        "log_return_5d",
        "log_return_21d",
        "price_vs_ma20",
        "price_vs_ma50",
        "price_vs_ma200",
        "bb_pct_b",
        "high_low_range",
        "gap_up",
        "volume_ratio_20d",
        "obv_normalised",
        "atr_pct",
        "realised_vol_5d",
        "realised_vol_21d",
        "vol_regime",
        "adx",
        "rsi_14",
        "macd_hist",
        "stoch_k",
        "roc_5",
        "roc_21",
    ]
    required = features[feature_cols]
    mask = required.notna().all(axis=1)
    cleaned = features.loc[mask].copy()
    dropped = int((~mask).sum())
    return cleaned, dropped


def build_drop_manifest(dropped_rows: int, total_rows: int) -> Dict[str, float]:
    """Return manifest metadata for NaN drops."""
    if total_rows <= 0:
        ratio = 0.0
    else:
        ratio = dropped_rows / total_rows
    return {
        "nan_dropped_rows": int(dropped_rows),
        "nan_drop_ratio": round(float(ratio), 6),
        "nan_total_rows": int(total_rows),
    }


def add_cross_sectional_features(
    features: pd.DataFrame,
    *,
    date_col: str = "date",
) -> pd.DataFrame:
    """Add cross-sectional ranks for return/vol/RSI per date."""
    required = {"log_return_5d", "realised_vol_21d", "rsi_14", date_col}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    ranked = features.copy()
    group = ranked.groupby(date_col, sort=False)

    ranked["cs_rank_return_5d"] = group["log_return_5d"].rank(pct=True)
    ranked["cs_rank_vol"] = group["realised_vol_21d"].rank(pct=True)
    ranked["cs_rank_rsi"] = group["rsi_14"].rank(pct=True)
    return ranked
