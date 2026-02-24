"""Unit tests for KillSwitch."""

import pytest

from src.risk.kill_switch import KillSwitch


@pytest.fixture
def ks(tmp_path):
    return KillSwitch(db_path=str(tmp_path / "ks.db"))


class TestKillSwitch:

    def test_initially_inactive(self, ks):
        assert ks.is_active() is False

    def test_trigger_activates(self, ks):
        ks.trigger("test_reason")
        assert ks.is_active() is True

    def test_reset_deactivates(self, ks):
        ks.trigger("test_reason")
        ks.reset("operator@test.com")
        assert ks.is_active() is False

    def test_check_and_raise_when_active(self, ks):
        ks.trigger("drawdown_limit")
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            ks.check_and_raise()

    def test_check_and_raise_when_inactive(self, ks):
        ks.check_and_raise()  # should not raise

    def test_trigger_is_idempotent(self, ks):
        ks.trigger("first")
        ks.trigger("second")
        assert ks.is_active() is True

    def test_reset_records_operator(self, ks):
        ks.trigger("test")
        ks.reset("alice@firm.com")
        s = ks.status()
        assert s["reset_by"] == "alice@firm.com"
        assert s["active"] == 0

    def test_trigger_stores_reason(self, ks):
        ks.trigger("max_drawdown_exceeded")
        s = ks.status()
        assert s["reason"] == "max_drawdown_exceeded"
        assert s["triggered_at"] is not None

    def test_status_returns_full_state(self, ks):
        s = ks.status()
        assert "id" in s
        assert "active" in s
        assert "reason" in s
        assert "triggered_at" in s
        assert "reset_by" in s
        assert "reset_at" in s

    def test_persists_across_instances(self, tmp_path):
        db = str(tmp_path / "persist.db")
        ks1 = KillSwitch(db_path=db)
        ks1.trigger("system_halt")
        # New instance reading same DB
        ks2 = KillSwitch(db_path=db)
        assert ks2.is_active() is True

    def test_error_message_contains_reason(self, ks):
        ks.trigger("VaR_limit_breached")
        with pytest.raises(RuntimeError, match="VaR_limit_breached"):
            ks.check_and_raise()
