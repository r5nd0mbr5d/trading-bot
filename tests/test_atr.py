"""Unit tests for ATR indicator helpers."""

import pandas as pd

from src.indicators.atr import atr_stop_loss, atr_take_profit, compute_atr


def test_compute_atr_matches_expected_wilder_ewm():
    df = pd.DataFrame(
        {
            "high": [12.0, 13.0, 15.0, 16.0, 17.0],
            "low": [10.0, 11.0, 12.0, 14.0, 15.0],
            "close": [11.0, 12.0, 14.0, 15.0, 16.0],
        }
    )
    atr = compute_atr(df, period=3)

    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    expected = tr.ewm(span=3, min_periods=3, adjust=False).mean()

    pd.testing.assert_series_equal(atr, expected)


def test_compute_atr_requires_min_periods():
    df = pd.DataFrame(
        {
            "high": [11.0, 12.0, 13.0],
            "low": [10.0, 11.0, 12.0],
            "close": [10.5, 11.5, 12.5],
        }
    )
    atr = compute_atr(df, period=3)
    assert atr.iloc[0] != atr.iloc[0]
    assert atr.iloc[1] != atr.iloc[1]
    assert atr.iloc[2] > 0


def test_atr_stop_loss_and_take_profit_default_multipliers():
    entry = 100.0
    atr_value = 2.5

    stop = atr_stop_loss(entry, atr_value)
    take_profit = atr_take_profit(entry, atr_value)

    assert stop == 95.0
    assert take_profit == 110.0


def test_atr_stop_loss_is_floored_to_positive_value():
    stop = atr_stop_loss(entry_price=1.0, atr=10.0, multiplier=5.0)
    assert stop == 0.0001
