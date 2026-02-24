"""Label generation utilities for research datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class LabelRow:
    symbol: str
    date: pd.Timestamp
    horizon: str
    forward_return: float
    label_binary: int
    label_ternary: int
    label_threshold_pos: float
    label_threshold_neg: float
    fold_id: int


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


def compute_thresholds(train_returns: pd.Series) -> Dict[str, float]:
    """Compute leakage-safe thresholds from training fold returns only."""
    clean = train_returns.dropna()
    if clean.empty:
        return {"pos": 0.0, "neg": 0.0}
    pos = float(np.percentile(clean, 67))
    neg = float(np.percentile(clean, 33))
    return {"pos": pos, "neg": neg}


def compute_labels(
    df: pd.DataFrame,
    *,
    symbol: str,
    horizon_days: int,
    thresholds: Dict[str, float],
    fold_id: int,
    horizon_id: str,
) -> pd.DataFrame:
    """Compute forward-return labels using strictly future bars.

    thresholds must be computed from training-fold returns only.
    """
    df = _ensure_utc_index(df)
    if "close" not in df.columns:
        raise ValueError("DataFrame must include a 'close' column")

    close = df["close"].astype(float)
    forward_return = np.log(close.shift(-horizon_days) / close)

    label_binary = (forward_return > 0).astype(int)

    pos = float(thresholds.get("pos", 0.0))
    neg = float(thresholds.get("neg", 0.0))

    label_ternary = pd.Series(0, index=df.index, dtype=int)
    label_ternary = label_ternary.mask(forward_return > pos, 1)
    label_ternary = label_ternary.mask(forward_return < neg, -1)

    labels = pd.DataFrame(
        {
            "symbol": symbol,
            "date": df.index,
            "horizon": horizon_id,
            "forward_return": forward_return,
            "label_binary": label_binary,
            "label_ternary": label_ternary,
            "label_threshold_pos": pos,
            "label_threshold_neg": neg,
            "fold_id": int(fold_id),
        },
        index=df.index,
    )
    return labels
