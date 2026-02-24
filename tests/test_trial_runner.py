"""Tests for trial batch runner aggregation and report generation."""

import json
from pathlib import Path

import pytest

from src.trial.manifest import TrialManifest
from src.trial.runner import TrialAndRunner


def test_trial_runner_generates_report_and_aggregates(tmp_path: Path) -> None:
    manifests = [
        TrialManifest(name="t1", profile="uk_paper", strategy="ma_crossover", duration_seconds=60),
        TrialManifest(name="t2", profile="uk_paper", strategy="rsi_momentum", duration_seconds=60),
    ]

    payloads = {
        "t1": {
            "exit_code": 0,
            "summary": {
                "fill_rate": 0.9,
                "win_rate": 0.6,
                "avg_slippage_pct": 0.01,
                "profit_factor": 1.2,
            },
        },
        "t2": {
            "exit_code": 0,
            "summary": {
                "fill_rate": 0.8,
                "win_rate": 0.7,
                "avg_slippage_pct": 0.02,
                "profit_factor": 1.4,
            },
        },
    }

    runner = TrialAndRunner(lambda manifest: payloads[manifest.name], parallel=False)
    report = runner.run(manifests, str(tmp_path))

    assert report["trial_count"] == 2
    assert report["successful_trials"] == 2
    assert report["failed_trials"] == 0
    assert report["overall_passed"] is True
    assert report["aggregate_metrics"]["win_rate"]["mean"] == pytest.approx(0.65)
    assert Path(report["report_path"]).exists()

    saved = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert saved["trial_count"] == 2


def test_trial_runner_marks_failed_threshold(tmp_path: Path) -> None:
    manifests = [
        TrialManifest(name="t1", profile="uk_paper", strategy="ma_crossover", duration_seconds=60),
        TrialManifest(name="t2", profile="uk_paper", strategy="rsi_momentum", duration_seconds=60),
    ]

    payloads = {
        "t1": {
            "exit_code": 0,
            "summary": {
                "fill_rate": 0.6,
                "win_rate": 0.4,
                "avg_slippage_pct": 0.01,
                "profit_factor": 0.9,
            },
        },
        "t2": {
            "exit_code": 0,
            "summary": {
                "fill_rate": 0.5,
                "win_rate": 0.45,
                "avg_slippage_pct": 0.01,
                "profit_factor": 1.0,
            },
        },
    }

    runner = TrialAndRunner(lambda manifest: payloads[manifest.name], parallel=False)
    report = runner.run(manifests, str(tmp_path / "batch"))

    assert report["overall_passed"] is False
    assert report["aggregate_metrics"]["profit_factor"]["mean"] < 1.10
