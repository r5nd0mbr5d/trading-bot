import numpy as np
import pandas as pd
import json

from research.data.snapshots import save_snapshot
from research.experiments.xgboost_pipeline import run_xgboost_experiment


def _sample_bars(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="D", tz="UTC")
    base = np.arange(rows, dtype=float)
    oscillation = np.sin(base / 5.0) * 0.5
    close = pd.Series(np.round(100 + base * 0.1 + oscillation, 4), index=index)
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


def test_run_xgboost_experiment_with_stub_trainer(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot_id = "snap_test"
    save_snapshot(
        _sample_bars(),
        output_dir=str(snapshot_root),
        config={"symbol": "TEST"},
        snapshot_id=snapshot_id,
    )

    def trainer(**kwargs):
        _ = kwargs
        return {"weights": [1]}, {"val_accuracy": 0.55, "val_pos_rate": 0.4}

    result = run_xgboost_experiment(
        snapshot_dir=str(snapshot_root / snapshot_id),
        experiment_id="xgb_test",
        symbol="TEST",
        output_dir=str(tmp_path / "experiment"),
        trainer=trainer,
    )

    assert result.training_report_path.exists()
    assert result.experiment_report.aggregate_summary_path.exists()
    assert result.experiment_report.promotion_check_path.exists()
    assert result.training_report.metadata.artifact_hash
    assert (result.output_dir / "shap" / "fold_F1.json").exists()

    payload = json.loads(result.training_report_path.read_text(encoding="utf-8"))
    assert "scale_pos_weight_used" in payload
    assert "class_distribution" in payload
    assert payload["label_type"] in {"direction", "threshold"}


def test_run_xgboost_experiment_walk_forward(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot_id = "snap_test"
    save_snapshot(
        _sample_bars(rows=900),
        output_dir=str(snapshot_root),
        config={"symbol": "TEST"},
        snapshot_id=snapshot_id,
    )

    def trainer(**kwargs):
        _ = kwargs
        return {"weights": [1]}, {"val_accuracy": 0.55, "val_pos_rate": 0.4}

    result = run_xgboost_experiment(
        snapshot_dir=str(snapshot_root / snapshot_id),
        experiment_id="xgb_walk_forward",
        symbol="TEST",
        output_dir=str(tmp_path / "experiment"),
        trainer=trainer,
        walk_forward=True,
        train_months=6,
        val_months=3,
        test_months=3,
        step_months=3,
    )

    assert result.training_report_path.exists()
    assert result.experiment_report.aggregate_summary_path.exists()
    assert result.training_reports
    assert (result.output_dir / "shap").exists()
