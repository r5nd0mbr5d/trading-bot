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


def test_harness_adds_preregistration_caution_when_not_registered(tmp_path):
    folds = [
        {"win_rate": 0.60, "profit_factor": 1.3, "fill_rate": 0.96, "pr_auc": 0.61, "passed": True},
    ]

    report = run_experiment(
        experiment_id="xgb_hypothesis_test",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={
            "snapshot_id": "snap_3",
            "hypothesis": {
                "n_prior_tests": 5,
                "adjusted_alpha": 0.05 / 6,
                "registered_before_test": False,
            },
        },
    )

    promotion = json.loads(report.promotion_check_path.read_text(encoding="utf-8"))
    assert promotion["registered_before_test"] is False
    assert promotion["n_prior_tests"] == 5
    assert "caution" in promotion


def test_harness_adds_claim_integrity_caution_when_fields_missing(tmp_path):
    folds = [
        {
            "win_rate": 0.60,
            "profit_factor": 1.3,
            "fill_rate": 0.96,
            "pr_auc": 0.61,
            "annualized_return_pct": 42.0,
            "passed": True,
        },
    ]

    report = run_experiment(
        experiment_id="xgb_claim_integrity_missing",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={"snapshot_id": "snap_ci_1"},
    )

    promotion = json.loads(report.promotion_check_path.read_text(encoding="utf-8"))
    assert promotion["claim_integrity"]["is_complete"] is False
    assert "claim_integrity_fields_missing" in promotion["caution_flags"]
    assert "claim_integrity_caution" in promotion


def test_harness_flags_high_return_claim_unverified(tmp_path):
    folds = [
        {
            "win_rate": 0.60,
            "profit_factor": 1.3,
            "fill_rate": 0.96,
            "pr_auc": 0.61,
            "annualized_return_pct": 140.0,
            "passed": True,
        },
    ]

    report = run_experiment(
        experiment_id="xgb_high_return_unverified",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={"snapshot_id": "snap_ci_2"},
    )

    promotion = json.loads(report.promotion_check_path.read_text(encoding="utf-8"))
    assert "high_return_claim_unverified" in promotion["caution_flags"]


def test_harness_clean_claim_integrity_has_no_claim_caution(tmp_path):
    folds = [
        {
            "win_rate": 0.60,
            "profit_factor": 1.3,
            "fill_rate": 0.96,
            "pr_auc": 0.61,
            "annualized_return_pct": 60.0,
            "passed": True,
        },
    ]

    report = run_experiment(
        experiment_id="xgb_claim_integrity_clean",
        fold_results=folds,
        output_dir=str(tmp_path),
        metadata={
            "snapshot_id": "snap_ci_3",
            "claim_integrity": {
                "out_of_sample_period": "2024-01-01 to 2024-12-31",
                "transaction_costs_slippage_assumptions": "IBKR realistic preset",
                "max_drawdown": 0.11,
                "turnover": 2.5,
                "tested_variants": 4,
            },
        },
    )

    promotion = json.loads(report.promotion_check_path.read_text(encoding="utf-8"))
    assert promotion["claim_integrity"]["is_complete"] is True
    assert promotion["caution_flags"] == []
    assert "claim_integrity_caution" not in promotion
