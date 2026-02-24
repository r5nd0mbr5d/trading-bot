"""Tests for research walk-forward experiment harness outputs (R2)."""

import json

from research.experiments.harness import run_experiment


def test_harness_emits_fold_and_aggregate_outputs(tmp_path):
    folds = [
        {"win_rate": 0.55, "profit_factor": 1.2, "fill_rate": 0.95, "passed": True},
        {"win_rate": 0.52, "profit_factor": 1.1, "fill_rate": 0.94, "passed": True},
        {"win_rate": 0.49, "profit_factor": 1.05, "fill_rate": 0.93, "passed": False},
    ]

    report = run_experiment(
        experiment_id="xgb_h5_test",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={"snapshot_id": "snap_1", "seed": 42},
    )

    assert report.aggregate_summary_path.exists()
    assert report.promotion_check_path.exists()
    assert len(report.fold_paths) == 3

    payload = json.loads(report.aggregate_summary_path.read_text(encoding="utf-8"))
    assert payload["experiment_id"] == "xgb_h5_test"
    assert payload["aggregate_metrics"]["fold_count"] == 3
    assert "metadata" in payload


def test_harness_promotion_check_is_machine_readable(tmp_path):
    folds = [
        {"win_rate": 0.60, "profit_factor": 1.3, "fill_rate": 0.96, "passed": True},
        {"win_rate": 0.58, "profit_factor": 1.2, "fill_rate": 0.95, "passed": True},
        {"win_rate": 0.56, "profit_factor": 1.15, "fill_rate": 0.94, "passed": True},
        {"win_rate": 0.54, "profit_factor": 1.12, "fill_rate": 0.93, "passed": True},
    ]

    report = run_experiment(
        experiment_id="lstm_h5_test",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={"snapshot_id": "snap_2", "seed": 7},
    )

    promotion = json.loads(report.promotion_check_path.read_text(encoding="utf-8"))
    assert isinstance(promotion["promotion_eligible"], bool)
    assert isinstance(promotion["gates"], list)
    assert all("gate" in g and "passed" in g for g in promotion["gates"])
