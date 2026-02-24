"""Tests for main trial_batch command wrapper."""

import json
from pathlib import Path

from config.settings import Settings
from src.cli.runtime import cmd_trial_batch


def _write_manifest(path: Path, name: str, strategy: str, output_dir: str) -> None:
    payload = {
        "name": name,
        "profile": "uk_paper",
        "strategy": strategy,
        "duration_seconds": 1,
        "symbols": ["AAPL"],
        "capital": 100000.0,
        "expected_json": None,
        "tolerance_json": None,
        "output_dir": output_dir,
        "db_path": "trading_paper.db",
        "strict_reconcile": False,
        "skip_health_check": True,
        "skip_rotate": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cmd_trial_batch_runs_manifests_and_reports(tmp_path: Path, monkeypatch) -> None:
    m1 = tmp_path / "trial_a.json"
    m2 = tmp_path / "trial_b.json"
    out1 = tmp_path / "out_a"
    out2 = tmp_path / "out_b"
    _write_manifest(m1, "trial-a", "ma_crossover", str(out1))
    _write_manifest(m2, "trial-b", "rsi_momentum", str(out2))

    def fake_trial(*args, **kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "summary": {
                "fill_rate": 0.9,
                "win_rate": 0.6,
                "avg_slippage_pct": 0.01,
                "profit_factor": 1.3,
            }
        }
        (output_dir / "paper_session_summary.json").write_text(
            json.dumps(summary),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr("src.cli.runtime.cmd_paper_trial", fake_trial)

    report = cmd_trial_batch(
        Settings(),
        manifest_patterns=[str(tmp_path / "trial_*.json")],
        output_dir=str(tmp_path / "batch"),
        parallel=False,
    )

    assert report["trial_count"] == 2
    assert report["successful_trials"] == 2
    assert report["overall_passed"] is True
    assert Path(report["report_path"]).exists()


def test_cmd_trial_batch_no_match_raises(tmp_path: Path) -> None:
    try:
        cmd_trial_batch(
            Settings(),
            manifest_patterns=[str(tmp_path / "does_not_exist_*.json")],
            output_dir=str(tmp_path / "batch"),
            parallel=False,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "No trial manifests matched" in str(exc)
