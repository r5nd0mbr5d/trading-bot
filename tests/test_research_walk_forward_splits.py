import pandas as pd

from research.data.splits import build_walk_forward_folds


def test_build_walk_forward_folds():
    folds = build_walk_forward_folds(
        start="2020-01-01",
        end="2021-12-31",
        train_months=6,
        val_months=3,
        test_months=3,
        step_months=3,
        gap_days=2,
    )

    assert len(folds) >= 1
    first = folds[0]
    assert first["train_start"] < first["train_end"]
    assert first["val_start"] > first["train_end"]
    assert first["test_start"] > first["val_end"]
