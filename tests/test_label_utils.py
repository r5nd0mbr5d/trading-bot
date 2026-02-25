"""Tests for research training label utilities."""

import logging

import pandas as pd

from research.training.label_utils import compute_class_weights, compute_threshold_label


def test_compute_class_weights_for_80_20_split():
    labels = pd.Series([0] * 80 + [1] * 20)

    result = compute_class_weights(labels)

    assert result["scale_pos_weight"] == 4.0
    assert result["class_distribution"]["negative"] == 80
    assert result["class_distribution"]["positive"] == 20


def test_compute_class_weights_emits_warning_below_40_percent(caplog):
    labels = pd.Series([0] * 75 + [1] * 25)

    with caplog.at_level(logging.WARNING):
        _ = compute_class_weights(labels)

    assert "minority class ratio" in caplog.text


def test_compute_threshold_label_uses_bps_threshold():
    returns = pd.Series([0.0010, 0.0040, 0.0046, -0.0020])

    labels = compute_threshold_label(returns, threshold_bps=45.0)

    assert labels.tolist() == [0, 0, 1, 0]
