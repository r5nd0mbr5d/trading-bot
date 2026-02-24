"""Unit tests for UK health-check command."""

import json

from config.settings import Settings
from src.cli.runtime import apply_runtime_profile, cmd_uk_health_check


class _FakeIBKRBrokerOK:
    def __init__(self, settings):
        self.settings = settings

    def _connected(self):
        return True

    def get_primary_account(self):
        return "DU123456"

    def is_paper_account(self):
        return True

    def is_live_account(self):
        return False


class _FakeIBKRBrokerDown:
    def __init__(self, settings):
        self.settings = settings

    def _connected(self):
        return False

    def get_primary_account(self):
        return ""

    def is_paper_account(self):
        return False

    def is_live_account(self):
        return False


def test_cmd_uk_health_check_returns_zero_when_ready(monkeypatch):
    settings = Settings()
    apply_runtime_profile(settings, "uk_paper")

    monkeypatch.setattr("src.cli.runtime.IBKRBroker", _FakeIBKRBrokerOK)

    errors = cmd_uk_health_check(settings, with_data_check=False)
    assert errors == 0


def test_cmd_uk_health_check_reports_error_when_ibkr_down(monkeypatch):
    settings = Settings()
    apply_runtime_profile(settings, "uk_paper")

    monkeypatch.setattr("src.cli.runtime.IBKRBroker", _FakeIBKRBrokerDown)

    errors = cmd_uk_health_check(settings, with_data_check=False)
    assert errors >= 1


def test_cmd_uk_health_check_json_output(monkeypatch, capsys):
    settings = Settings()
    apply_runtime_profile(settings, "uk_paper")

    monkeypatch.setattr("src.cli.runtime.IBKRBroker", _FakeIBKRBrokerOK)

    errors = cmd_uk_health_check(settings, with_data_check=False, json_output=True)
    assert errors == 0

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["blocking_errors"] == 0
    assert payload["profile"] == "uk_paper"
    assert any(c["check"] == "ibkr_connection" for c in payload["checks"])
