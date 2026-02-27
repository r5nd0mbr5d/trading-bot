"""BTC crypto feature engineering utilities for Step 57.

This module computes leakage-safe, daily-bar features for BTC research experiments.
All features are calculated using data available at or before bar[t].
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from ta.momentum import ROCIndicator, RSIIndicator, UltimateOscillator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import (
    AccDistIndexIndicator,
    ChaikinMoneyFlowIndicator,
    MFIIndicator,
    OnBalanceVolumeIndicator,
)

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
DEFAULT_FEATURE_CONFIG: Dict[str, Any] = {
    "short_window": 5,
    "medium_window": 20,
    "long_window": 60,
    "max_ffill_bars": 3,
    "clip_sigma": 3.0,
}

FEATURE_COLUMNS = [
    "ema_5_pct",
    "ema_20_pct",
    "ema_60_pct",
    "bb_pct_b_20",
    "atr_pct_5",
    "atr_pct_20",
    "atr_pct_60",
    "rsi_5",
    "rsi_20",
    "uo_7_14_28",
    "roc_5",
    "roc_20",
    "obv_ratio_20",
    "obv_ratio_60",
    "ad_ratio_20",
    "mfi_14",
    "cmf_20",
    "cmf_60",
    "realised_vol_5",
    "realised_vol_20",
]


def _ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with UTC-aware DatetimeIndex.

    Parameters
    ----------
    df : pd.DataFrame
        Input frame with DatetimeIndex.

    Returns
    -------
    pd.DataFrame
        Copy of input frame with UTC-aware index.

    Raises
    ------
    ValueError
        If index is not a DatetimeIndex.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")

    utc_df = df.copy()
    if utc_df.index.tz is None:
        utc_df.index = utc_df.index.tz_localize("UTC")
    else:
        utc_df.index = utc_df.index.tz_convert("UTC")
    return utc_df.sort_index()


def _merge_feature_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge user config onto module defaults."""
    merged = DEFAULT_FEATURE_CONFIG.copy()
    if config:
        merged.update(config)
    return merged


def _prepare_daily_frame(df: pd.DataFrame, max_ffill_bars: int) -> pd.DataFrame:
    """Reindex to daily bars and bounded forward-fill missing gaps.

    Parameters
    ----------
    df : pd.DataFrame
        UTC OHLCV input frame.
    max_ffill_bars : int
        Maximum consecutive bars to forward-fill.

    Returns
    -------
    pd.DataFrame
        Daily-indexed frame with bounded forward-fill.
    """
    daily = df.asfreq("D")
    return daily.ffill(limit=max_ffill_bars)


def _clip_by_sigma(series: pd.Series, sigma: float) -> pd.Series:
    """Clip a numeric series to mean ± sigma*std.

    Parameters
    ----------
    series : pd.Series
        Input series.
    sigma : float
        Sigma multiplier.

    Returns
    -------
    pd.Series
        Clipped series.
    """
    mean_value = float(series.mean(skipna=True))
    std_value = float(series.std(skipna=True))
    if np.isnan(std_value) or std_value == 0.0:
        return series

    lower = mean_value - sigma * std_value
    upper = mean_value + sigma * std_value
    return series.clip(lower=lower, upper=upper)


def _ratio_to_unit_interval(series: pd.Series) -> pd.Series:
    """Clip ratio features to [0.5, 2.0] and scale to [0, 1]."""
    clipped = series.clip(lower=0.5, upper=2.0)
    return (clipped - 0.5) / 1.5


def _nan_series(index: pd.Index) -> pd.Series:
    """Return a NaN-valued series for the provided index."""
    return pd.Series(np.nan, index=index, dtype=float)


def _safe_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
) -> pd.Series:
    """Compute ATR or return NaNs when window exceeds available data."""
    if len(close) < window:
        return _nan_series(close.index)

    return AverageTrueRange(high, low, close, window=window, fillna=False).average_true_range()


def get_feature_columns() -> List[str]:
    """Return ordered feature column names for crypto features.

    Returns
    -------
    List[str]
        Ordered list of feature names.
    """
    return FEATURE_COLUMNS.copy()


def build_crypto_features(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Build BTC daily-bar crypto features defined by ADR-020.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data indexed by timestamp with required columns:
        ``open``, ``high``, ``low``, ``close``, ``volume``.
    config : Optional[Dict[str, Any]], optional
        Feature configuration overrides. Supported keys:
        ``short_window``, ``medium_window``, ``long_window``,
        ``max_ffill_bars``, and ``clip_sigma``.

    Returns
    -------
    pd.DataFrame
        Feature DataFrame with UTC-aware daily index and 20 feature columns.

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    merged_config = _merge_feature_config(config)
    source = _ensure_utc_index(df)

    missing_columns = set(REQUIRED_COLUMNS) - set(source.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing_text}")

    prepared = _prepare_daily_frame(source[list(REQUIRED_COLUMNS)], merged_config["max_ffill_bars"])

    if prepared.empty:
        return pd.DataFrame(columns=get_feature_columns(), index=prepared.index)

    close = prepared["close"].astype(float)
    high = prepared["high"].astype(float)
    low = prepared["low"].astype(float)
    volume = prepared["volume"].astype(float)

    short_window = int(merged_config["short_window"])
    medium_window = int(merged_config["medium_window"])
    long_window = int(merged_config["long_window"])
    clip_sigma = float(merged_config["clip_sigma"])

    ema_5 = EMAIndicator(close, window=short_window, fillna=False).ema_indicator()
    ema_20 = EMAIndicator(close, window=medium_window, fillna=False).ema_indicator()
    ema_60 = EMAIndicator(close, window=long_window, fillna=False).ema_indicator()

    bb_20 = BollingerBands(close=close, window=medium_window, window_dev=2, fillna=False)
    bb_pct_b_20 = bb_20.bollinger_pband()

    atr_5 = _safe_atr(high, low, close, window=short_window)
    atr_20 = _safe_atr(high, low, close, window=medium_window)
    atr_60 = _safe_atr(high, low, close, window=long_window)

    rsi_5 = RSIIndicator(close, window=short_window, fillna=False).rsi()
    rsi_20 = RSIIndicator(close, window=medium_window, fillna=False).rsi()
    uo_7_14_28 = UltimateOscillator(high, low, close, window1=7, window2=14, window3=28).ultimate_oscillator()

    roc_5 = ROCIndicator(close, window=short_window, fillna=False).roc()
    roc_20 = ROCIndicator(close, window=medium_window, fillna=False).roc()

    obv = OnBalanceVolumeIndicator(close=close, volume=volume, fillna=False).on_balance_volume()
    obv_ratio_20 = obv / obv.rolling(window=medium_window).mean()
    obv_ratio_60 = obv / obv.rolling(window=long_window).mean()

    ad = AccDistIndexIndicator(high=high, low=low, close=close, volume=volume, fillna=False)
    ad_value = ad.acc_dist_index()
    ad_ratio_20 = ad_value / ad_value.rolling(window=medium_window).mean()

    mfi_14 = MFIIndicator(high, low, close, volume, window=14, fillna=False).money_flow_index()
    cmf_20 = ChaikinMoneyFlowIndicator(high, low, close, volume, window=medium_window, fillna=False).chaikin_money_flow()
    cmf_60 = ChaikinMoneyFlowIndicator(high, low, close, volume, window=long_window, fillna=False).chaikin_money_flow()

    log_returns = np.log(close / close.shift(1))
    realised_vol_5 = log_returns.rolling(window=short_window).std() * np.sqrt(252)
    realised_vol_20 = log_returns.rolling(window=medium_window).std() * np.sqrt(252)

    features = pd.DataFrame(
        {
            "ema_5_pct": (close - ema_5) / ema_5,
            "ema_20_pct": (close - ema_20) / ema_20,
            "ema_60_pct": (close - ema_60) / ema_60,
            "bb_pct_b_20": bb_pct_b_20,
            "atr_pct_5": (atr_5 / close) * 100,
            "atr_pct_20": (atr_20 / close) * 100,
            "atr_pct_60": (atr_60 / close) * 100,
            "rsi_5": rsi_5,
            "rsi_20": rsi_20,
            "uo_7_14_28": uo_7_14_28,
            "roc_5": roc_5,
            "roc_20": roc_20,
            "obv_ratio_20": obv_ratio_20,
            "obv_ratio_60": obv_ratio_60,
            "ad_ratio_20": ad_ratio_20,
            "mfi_14": mfi_14,
            "cmf_20": cmf_20,
            "cmf_60": cmf_60,
            "realised_vol_5": realised_vol_5,
            "realised_vol_20": realised_vol_20,
        },
        index=prepared.index,
    )

    sigma_clip_columns = [
        "ema_5_pct",
        "ema_20_pct",
        "ema_60_pct",
        "atr_pct_5",
        "atr_pct_20",
        "atr_pct_60",
        "roc_5",
        "roc_20",
        "realised_vol_5",
        "realised_vol_20",
    ]
    for column_name in sigma_clip_columns:
        features[column_name] = _clip_by_sigma(features[column_name], clip_sigma)

    features["obv_ratio_20"] = _ratio_to_unit_interval(features["obv_ratio_20"])
    features["obv_ratio_60"] = _ratio_to_unit_interval(features["obv_ratio_60"])
    features["ad_ratio_20"] = _ratio_to_unit_interval(features["ad_ratio_20"])

    zero_volume_mask = volume <= 0
    volume_columns = ["obv_ratio_20", "obv_ratio_60", "ad_ratio_20", "mfi_14", "cmf_20", "cmf_60"]
    features.loc[zero_volume_mask, volume_columns] = np.nan

    return features[get_feature_columns()]


def drop_nan_feature_rows(features: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Drop rows with NaN values in any required feature column.

    Parameters
    ----------
    features : pd.DataFrame
        Feature frame produced by :func:`build_crypto_features`.

    Returns
    -------
    Tuple[pd.DataFrame, int]
        Cleaned frame and dropped-row count.
    """
    required = features[get_feature_columns()]
    valid_mask = required.notna().all(axis=1)
    cleaned = features.loc[valid_mask].copy()
    dropped_count = int((~valid_mask).sum())
    return cleaned, dropped_count
