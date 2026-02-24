"""Unit test for main UK tax export command wrapper."""

from config.settings import Settings
from src.cli.runtime import cmd_uk_tax_export


def test_cmd_uk_tax_export_invokes_export(monkeypatch, caplog):
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
            "trade_ledger": "x/trade_ledger.csv",
            "realized_gains": "x/realized_gains.csv",
            "fx_notes": "x/fx_notes.csv",
        }

    monkeypatch.setattr("src.cli.runtime.export_uk_tax_reports", fake_export)

    cmd_uk_tax_export(settings, "db.sqlite", "reports/uk_tax")

    assert captured["db_path"] == "db.sqlite"
    assert captured["output_dir"] == "reports/uk_tax"
    assert captured["base_currency"] == "GBP"
    assert captured["fx_rates"]["USD_GBP"] == 0.8
    assert "fx_rate_timestamps" in captured["kwargs"]
    assert "fx_rate_max_age_hours" in captured["kwargs"]
