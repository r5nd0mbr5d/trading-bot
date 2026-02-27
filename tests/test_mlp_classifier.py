import numpy as np
import pandas as pd
import pytest

from research.data.snapshots import save_snapshot
from research.experiments.xgboost_pipeline import run_xgboost_experiment
from research.models.mlp_classifier import train_mlp_model


def _sample_matrix(rows: int = 160, cols: int = 6) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    X = pd.DataFrame(rng.normal(size=(rows, cols)), columns=[f"f_{idx}" for idx in range(cols)])
    linear = X["f_0"] * 0.8 - X["f_1"] * 0.5 + X["f_2"] * 0.3
    probs = 1 / (1 + np.exp(-linear))
    y = pd.Series((probs > 0.5).astype(int))
    return X, y


def _sample_bars(rows: int = 320) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="D", tz="UTC")
    base = np.arange(rows, dtype=float)
    close = pd.Series(np.round(100 + base * 0.1 + np.sin(base / 5.0) * 0.5, 4), index=index)
    return pd.DataFrame(
        {
            "open": (close * 0.99).round(4),
            "high": (close * 1.01).round(4),
            "low": (close * 0.98).round(4),
            "close": close.round(4),
            "volume": 1000,
        },
        index=index,
    )


def test_train_mlp_model_outputs_probabilities_and_metrics():
    pytest.importorskip("torch")
    pytest.importorskip("skorch")

    X, y = _sample_matrix()
    train_rows = 120
    model, metrics = train_mlp_model(
        X.iloc[:train_rows],
        y.iloc[:train_rows],
        X.iloc[train_rows:],
        y.iloc[train_rows:],
        params={"max_epochs": 5, "batch_size": 32},
    )

    probs = model.predict_proba(X.iloc[train_rows:].to_numpy(dtype=np.float32))[:, 1]
    assert np.all(probs >= 0.0)
    assert np.all(probs <= 1.0)
    assert "val_pr_auc" in metrics
    assert "val_roc_auc" in metrics


def test_train_mlp_model_configures_lr_scheduler_callback():
    pytest.importorskip("torch")
    pytest.importorskip("skorch")

    X, y = _sample_matrix(rows=100)
    model, _ = train_mlp_model(
        X.iloc[:70],
        y.iloc[:70],
        X.iloc[70:],
        y.iloc[70:],
        params={"max_epochs": 4, "batch_size": 16},
    )

    net = model.named_steps["mlp"]
    callback_names = []
    for callback in net.callbacks:
        if isinstance(callback, tuple):
            callback_names.append(type(callback[1]).__name__)
        else:
            callback_names.append(type(callback).__name__)
    assert "LRScheduler" in callback_names


def test_mlp_trainer_runs_inside_research_pipeline(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("skorch")

    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot_id = "snap_mlp"
    save_snapshot(
        _sample_bars(),
        output_dir=str(snapshot_root),
        config={"symbol": "TEST"},
        snapshot_id=snapshot_id,
    )

    result = run_xgboost_experiment(
        snapshot_dir=str(snapshot_root / snapshot_id),
        experiment_id="mlp_pipeline_test",
        symbol="TEST",
        output_dir=str(tmp_path / "experiment"),
        model_type="mlp",
        trainer=train_mlp_model,
    )

    assert result.training_report_path.exists()
    assert result.experiment_report.aggregate_summary_path.exists()
