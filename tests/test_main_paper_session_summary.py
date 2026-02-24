"""Unit test for main paper session summary command wrapper."""

from config.settings import Settings
from src.cli.runtime import cmd_paper_session_summary


def test_cmd_paper_session_summary_invokes_export(monkeypatch):
    settings = Settings()
    settings.base_currency = "GBP"
    settings.fx_rates = {"USD_GBP": 0.8}
    settings.db_url_paper = "sqlite:///db.sqlite"

    captured = {}

    def fake_export(db_path, output_dir, base_currency, fx_rates, **kwargs):
        captured["db_path"] = db_path
        captured["output_dir"] = output_dir
        captured["base_currency"] = base_currency
        captured["fx_rates"] = fx_rates
        captured["kwargs"] = kwargs
        return {
            "summary": {
                "filled_order_count": 3,
                "order_attempt_count": 5,
                "fill_rate": 0.6,
                "win_rate": 0.5,
                "realized_pnl": 12.34,
            },
            "json_path": "reports/paper_session_summary.json",
            "csv_path": "reports/paper_session_summary.csv",
        }

    monkeypatch.setattr("src.cli.runtime.export_paper_session_summary", fake_export)

    cmd_paper_session_summary(settings, "db.sqlite", "reports/session")

    assert captured["db_path"] == "db.sqlite"
    assert captured["output_dir"] == "reports/session"
    assert captured["base_currency"] == "GBP"
    assert captured["fx_rates"]["USD_GBP"] == 0.8
    assert "fx_rate_timestamps" in captured["kwargs"]
    assert "fx_rate_max_age_hours" in captured["kwargs"]
