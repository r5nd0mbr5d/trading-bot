"""Unit tests for main data_quality_report wrapper."""

from config.settings import Settings
from src.cli.runtime import cmd_data_quality_report


def test_cmd_data_quality_report_invokes_export(monkeypatch):
    settings = Settings()
    captured = {}

    def fake_export(db_path, output_path, dashboard_path):
        captured["db_path"] = db_path
        captured["output_path"] = output_path
        captured["dashboard_path"] = dashboard_path
        return {
            "output_path": output_path,
            "dashboard_path": dashboard_path,
            "report": {"symbols_checked": 2},
        }

    monkeypatch.setattr("src.cli.runtime.export_data_quality_report", fake_export)

    cmd_data_quality_report(
        settings,
        "trading_paper.db",
        "reports/data_quality.json",
        dashboard_path="reports/execution_dashboard.html",
    )

    assert captured["db_path"] == "trading_paper.db"
    assert captured["output_path"] == "reports/data_quality.json"
    assert captured["dashboard_path"] == "reports/execution_dashboard.html"
