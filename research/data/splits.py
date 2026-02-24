"""Train/validation/test split utilities for research datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class ScalingStats:
    mean: pd.Series
    std: pd.Series


def _ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    return df


def build_walk_forward_folds(
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    train_months: int,
    val_months: int,
    test_months: int,
    step_months: int,
    gap_days: int = 0,
) -> List[dict]:
    """Build expanding-window walk-forward fold boundaries.

    Returns list of dicts with train/val/test date ranges.
    """
    if train_months <= 0 or val_months <= 0 or test_months <= 0 or step_months <= 0:
        raise ValueError("train_months, val_months, test_months and step_months must be > 0")
    if gap_days < 0:
        raise ValueError("gap_days must be >= 0")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    if start_ts >= end_ts:
        return []

    folds: List[dict] = []
    cursor = start_ts
    fold_idx = 1

    while True:
        train_start = cursor
        train_end = train_start + pd.DateOffset(months=train_months) - pd.Timedelta(days=1)

        val_start = train_end + pd.Timedelta(days=1 + gap_days)
        val_end = val_start + pd.DateOffset(months=val_months) - pd.Timedelta(days=1)

        test_start = val_end + pd.Timedelta(days=1 + gap_days)
        test_end = test_start + pd.DateOffset(months=test_months) - pd.Timedelta(days=1)

        if test_end > end_ts:
            break

        folds.append(
            {
                "fold_id": f"F{fold_idx}",
                "train_start": train_start,
                "train_end": train_end,
                "val_start": val_start,
                "val_end": val_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )

        fold_idx += 1
        cursor = cursor + pd.DateOffset(months=step_months)

    return folds


def apply_gap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    *,
    gap_days: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Enforce a minimum day gap between train/val/test boundaries.

    Drops validation rows that fall within `gap_days` of the training end,
    and test rows that fall within `gap_days` of the validation end.
    """
    if gap_days <= 0:
        return train_df, val_df, test_df

    train_df = _ensure_dt_index(train_df)
    val_df = _ensure_dt_index(val_df)
    test_df = _ensure_dt_index(test_df)

    if not train_df.empty and not val_df.empty:
        train_end = train_df.index.max()
        cutoff = train_end + pd.Timedelta(days=gap_days)
        val_df = val_df[val_df.index > cutoff]

    if not val_df.empty and not test_df.empty:
        val_end = val_df.index.max()
        cutoff = val_end + pd.Timedelta(days=gap_days)
        test_df = test_df[test_df.index > cutoff]

    return train_df, val_df, test_df


def fit_scaler(train_df: pd.DataFrame, feature_cols: Iterable[str]) -> ScalingStats:
    """Fit z-score scaling stats using training data only."""
    feature_cols = list(feature_cols)
    mean = train_df[feature_cols].mean()
    std = train_df[feature_cols].std(ddof=0).replace(0, np.nan).fillna(1.0)
    return ScalingStats(mean=mean, std=std)


def apply_scaler(
    df: pd.DataFrame,
    stats: ScalingStats,
    feature_cols: Iterable[str],
) -> pd.DataFrame:
    """Apply z-score scaling using precomputed training stats."""
    feature_cols = list(feature_cols)
    scaled = df.copy()
    scaled[feature_cols] = (scaled[feature_cols] - stats.mean) / stats.std
    return scaled
