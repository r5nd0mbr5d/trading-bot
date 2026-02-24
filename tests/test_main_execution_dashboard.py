"""Unit test for main execution dashboard command wrapper."""

from config.settings import Settings
from src.cli.runtime import cmd_execution_dashboard


def test_cmd_execution_dashboard_invokes_export(monkeypatch):
    settings = Settings()

    captured = {}

    def fake_export(db_path, output_path, refresh_seconds):
        captured["db_path"] = db_path
        captured["output_path"] = output_path
        captured["refresh_seconds"] = refresh_seconds
        return {
            "output_path": output_path,
            "metrics": {
                "event_count": 12,
                "reject_rate_by_symbol": [{"symbol": "HSBA.L"}],
            },
        }

    monkeypatch.setattr("src.cli.runtime.export_execution_dashboard", fake_export)

    cmd_execution_dashboard(
        settings,
        "trading_paper.db",
        "reports/execution_dashboard.html",
        refresh_seconds=45,
    )

    assert captured["db_path"] == "trading_paper.db"
    assert captured["output_path"] == "reports/execution_dashboard.html"
    assert captured["refresh_seconds"] == 45
