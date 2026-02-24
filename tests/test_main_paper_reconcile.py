"""Unit test for main paper reconciliation command wrapper."""

import json

from config.settings import Settings
from src.cli.runtime import cmd_paper_reconcile


def test_cmd_paper_reconcile_invokes_export(tmp_path, monkeypatch):
    settings = Settings()
    settings.base_currency = "GBP"
    settings.fx_rates = {"USD_GBP": 0.8}
    settings.db_url_paper = "sqlite:///db.sqlite"

    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps({"win_rate": 0.5}), encoding="utf-8")

    tolerance_path = tmp_path / "tol.json"
    tolerance_path.write_text(json.dumps({"win_rate": 0.1}), encoding="utf-8")

    captured = {}

    def fake_export(db_path, output_dir, expected_metrics, base_currency, fx_rates, **kwargs):
        captured["db_path"] = db_path
        captured["output_dir"] = output_dir
        captured["expected_metrics"] = expected_metrics
        captured["base_currency"] = base_currency
        captured["fx_rates"] = fx_rates
        captured["kwargs"] = kwargs
        return {
            "json_path": "reports/paper_reconciliation.json",
            "csv_path": "reports/paper_reconciliation.csv",
            "report": {
                "metric_count": 1,
                "drift_flag_count": 0,
                "ok": True,
            },
        }

    monkeypatch.setattr("src.cli.runtime.export_paper_reconciliation", fake_export)

    drift_count = cmd_paper_reconcile(
        settings,
        "db.sqlite",
        "reports/reconcile",
        str(expected_path),
        str(tolerance_path),
    )

    assert drift_count == 0
    assert captured["db_path"] == "db.sqlite"
    assert captured["output_dir"] == "reports/reconcile"
    assert captured["expected_metrics"]["win_rate"] == 0.5
    assert captured["base_currency"] == "GBP"
    assert captured["fx_rates"]["USD_GBP"] == 0.8
    assert captured["kwargs"]["tolerances"]["win_rate"] == 0.1
    assert "fx_rate_timestamps" in captured["kwargs"]
    assert "fx_rate_max_age_hours" in captured["kwargs"]


def test_cmd_paper_reconcile_unwraps_summary_payload(tmp_path, monkeypatch):
    settings = Settings()
    settings.base_currency = "GBP"
    settings.db_url_paper = "sqlite:///db.sqlite"

    expected_path = tmp_path / "expected_summary.json"
    expected_path.write_text(
        json.dumps({"summary": {"win_rate": 0.55, "fill_rate": 0.8}}),
        encoding="utf-8",
    )

    captured = {}

    def fake_export(db_path, output_dir, expected_metrics, base_currency, fx_rates, **kwargs):
        captured["expected_metrics"] = expected_metrics
        return {
            "json_path": "reports/paper_reconciliation.json",
            "csv_path": "reports/paper_reconciliation.csv",
            "report": {
                "metric_count": 2,
                "drift_flag_count": 0,
                "ok": True,
            },
        }

    monkeypatch.setattr("src.cli.runtime.export_paper_reconciliation", fake_export)

    drift_count = cmd_paper_reconcile(
        settings,
        "db.sqlite",
        "reports/reconcile",
        str(expected_path),
        None,
    )

    assert drift_count == 0
    assert captured["expected_metrics"] == {"win_rate": 0.55, "fill_rate": 0.8}
