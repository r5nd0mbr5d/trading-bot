"""Unit tests for paper trial orchestration command."""

from config.settings import Settings
from main import cmd_paper_trial


def test_paper_trial_stops_when_health_check_fails(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("main.cmd_uk_health_check", lambda *args, **kwargs: 1)

    called = {"paper": 0}

    async def fake_run(*args, **kwargs):
        called["paper"] += 1

    monkeypatch.setattr("main._run_paper_for_duration", fake_run)

    rc = cmd_paper_trial(
        settings,
        duration_seconds=5,
        db_path="trading_paper.db",
        output_dir="reports/session",
    )

    assert rc == 2
    assert called["paper"] == 0


def test_paper_trial_strict_reconcile_returns_one_on_drift(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("main.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr("main.cmd_rotate_paper_db", lambda *args, **kwargs: {"rotated": False})

    async def fake_run(*args, **kwargs):
        return None

    monkeypatch.setattr("main._run_paper_for_duration", fake_run)
    monkeypatch.setattr("main.cmd_paper_session_summary", lambda *args, **kwargs: {"summary": {}})
    monkeypatch.setattr("main.update_execution_trend", lambda *args, **kwargs: {"warnings": []})
    monkeypatch.setattr("main.cmd_paper_reconcile", lambda *args, **kwargs: 3)

    rc = cmd_paper_trial(
        settings,
        duration_seconds=5,
        db_path="trading_paper.db",
        output_dir="reports/session",
        expected_json_path="reports/session/expected_kpis.json",
        strict_reconcile=True,
    )

    assert rc == 1


def test_paper_trial_happy_path(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("main.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr("main.cmd_rotate_paper_db", lambda *args, **kwargs: {"rotated": True})

    calls = {"run": 0, "summary": 0, "reconcile": 0}

    async def fake_run(*args, **kwargs):
        calls["run"] += 1

    def fake_summary(*args, **kwargs):
        calls["summary"] += 1
        return {"summary": {"fill_rate": 0.0, "avg_slippage_pct": 0.0}}

    def fake_reconcile(*args, **kwargs):
        calls["reconcile"] += 1
        return 0

    monkeypatch.setattr("main._run_paper_for_duration", fake_run)
    monkeypatch.setattr("main.cmd_paper_session_summary", fake_summary)
    monkeypatch.setattr("main.update_execution_trend", lambda *args, **kwargs: {"warnings": []})
    monkeypatch.setattr("main.cmd_paper_reconcile", fake_reconcile)

    rc = cmd_paper_trial(
        settings,
        duration_seconds=5,
        db_path="trading_paper.db",
        output_dir="reports/session",
        expected_json_path="reports/session/expected_kpis.json",
        strict_reconcile=True,
    )

    assert rc == 0
    assert calls["run"] == 1
    assert calls["summary"] == 1
    assert calls["reconcile"] == 1
