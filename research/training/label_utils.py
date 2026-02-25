"""Label and class-imbalance utilities for research model training."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def compute_class_weights(y: pd.Series) -> dict[str, Any]:
    """Compute class-balance metadata and XGBoost positive-class weight.

    Parameters
    ----------
    y
        Binary label series where positive class is ``1`` and negative class is ``0``.

    Returns
    -------
    dict[str, Any]
        Dictionary containing class counts/distribution and ``scale_pos_weight``.
    """
    labels = pd.Series(y).dropna().astype(int)
    total = int(len(labels))
    if total == 0:
        return {
            "scale_pos_weight": 1.0,
            "class_distribution": {
                "positive": 0,
                "negative": 0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
            },
        }

    positive = int((labels == 1).sum())
    negative = int((labels == 0).sum())

    if positive <= 0:
        scale_pos_weight = 1.0
    else:
        scale_pos_weight = float(negative / positive)

    minority_ratio = min(positive, negative) / total if total else 0.0
    if minority_ratio < 0.40:
        logger.warning(
            "Class imbalance detected: minority class ratio %.3f below 0.40",
            minority_ratio,
        )

    return {
        "scale_pos_weight": scale_pos_weight,
        "class_distribution": {
            "positive": positive,
            "negative": negative,
            "positive_ratio": float(positive / total),
            "negative_ratio": float(negative / total),
        },
    }


def compute_threshold_label(returns_series: pd.Series, threshold_bps: float) -> pd.Series:
    """Build threshold-based profitability labels.

    Parameters
    ----------
    returns_series
        Forward return series expressed in decimal returns.
    threshold_bps
        Required minimum return in basis points to label a row positive.

    Returns
    -------
    pd.Series
        Binary label series where ``1`` indicates forward return exceeds threshold.
    """
    threshold = float(threshold_bps) / 10_000.0
    returns = pd.Series(returns_series).astype(float)
    return (returns > threshold).astype(int)
