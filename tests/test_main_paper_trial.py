"""Unit tests for paper trial orchestration command."""

from config.settings import Settings
from src.cli.runtime import cmd_paper_trial


def test_paper_trial_stops_when_health_check_fails(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("src.cli.runtime.cmd_uk_health_check", lambda *args, **kwargs: 1)
    monkeypatch.setattr(
        "src.cli.runtime.apply_symbol_universe_policy",
        lambda *args, **kwargs: {
            "allowed": True,
            "remediated": False,
            "selected_symbols": settings.data.symbols,
            "removed_symbols": [],
            "health_summary": {
                "availability_ratio": 1.0,
                "threshold_ratio": 0.8,
                "healthy_symbols": len(settings.data.symbols),
                "total_symbols": len(settings.data.symbols),
            },
            "reason": "threshold_met",
        },
    )

    called = {"paper": 0}

    async def fake_run(*args, **kwargs):
        called["paper"] += 1

    monkeypatch.setattr("src.cli.runtime._run_paper_for_duration", fake_run)

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

    monkeypatch.setattr("src.cli.runtime.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "src.cli.runtime.apply_symbol_universe_policy",
        lambda *args, **kwargs: {
            "allowed": True,
            "remediated": False,
            "selected_symbols": settings.data.symbols,
            "removed_symbols": [],
            "health_summary": {
                "availability_ratio": 1.0,
                "threshold_ratio": 0.8,
                "healthy_symbols": len(settings.data.symbols),
                "total_symbols": len(settings.data.symbols),
            },
            "reason": "threshold_met",
        },
    )
    monkeypatch.setattr(
        "src.cli.runtime.cmd_rotate_paper_db", lambda *args, **kwargs: {"rotated": False}
    )

    async def fake_run(*args, **kwargs):
        return None

    monkeypatch.setattr("src.cli.runtime._run_paper_for_duration", fake_run)
    monkeypatch.setattr(
        "src.cli.runtime.cmd_paper_session_summary", lambda *args, **kwargs: {"summary": {}}
    )
    monkeypatch.setattr(
        "src.cli.runtime.update_execution_trend", lambda *args, **kwargs: {"warnings": []}
    )
    monkeypatch.setattr("src.cli.runtime.cmd_paper_reconcile", lambda *args, **kwargs: 3)

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

    monkeypatch.setattr("src.cli.runtime.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "src.cli.runtime.apply_symbol_universe_policy",
        lambda *args, **kwargs: {
            "allowed": True,
            "remediated": False,
            "selected_symbols": settings.data.symbols,
            "removed_symbols": [],
            "health_summary": {
                "availability_ratio": 1.0,
                "threshold_ratio": 0.8,
                "healthy_symbols": len(settings.data.symbols),
                "total_symbols": len(settings.data.symbols),
            },
            "reason": "threshold_met",
        },
    )
    monkeypatch.setattr(
        "src.cli.runtime.cmd_rotate_paper_db", lambda *args, **kwargs: {"rotated": True}
    )

    calls = {"run": 0, "summary": 0, "reconcile": 0}

    async def fake_run(*args, **kwargs):
        calls["run"] += 1

    def fake_summary(*args, **kwargs):
        calls["summary"] += 1
        return {"summary": {"fill_rate": 0.0, "avg_slippage_pct": 0.0}}

    def fake_reconcile(*args, **kwargs):
        calls["reconcile"] += 1
        return 0

    monkeypatch.setattr("src.cli.runtime._run_paper_for_duration", fake_run)
    monkeypatch.setattr("src.cli.runtime.cmd_paper_session_summary", fake_summary)
    monkeypatch.setattr(
        "src.cli.runtime.update_execution_trend", lambda *args, **kwargs: {"warnings": []}
    )
    monkeypatch.setattr("src.cli.runtime.cmd_paper_reconcile", fake_reconcile)

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


def test_paper_trial_blocks_when_symbol_policy_disallows(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("src.cli.runtime.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "src.cli.runtime.apply_symbol_universe_policy",
        lambda *args, **kwargs: {
            "allowed": False,
            "remediated": False,
            "selected_symbols": settings.data.symbols,
            "removed_symbols": [],
            "health_summary": {
                "availability_ratio": 0.2,
                "threshold_ratio": 0.8,
                "healthy_symbols": 1,
                "total_symbols": 5,
            },
            "reason": "insufficient_availability",
        },
    )

    called = {"paper": 0}

    async def fake_run(*args, **kwargs):
        called["paper"] += 1

    monkeypatch.setattr("src.cli.runtime._run_paper_for_duration", fake_run)

    rc = cmd_paper_trial(
        settings,
        duration_seconds=5,
        db_path="trading_paper.db",
        output_dir="reports/session",
    )

    assert rc == 2
    assert called["paper"] == 0


def test_paper_trial_applies_symbol_remediation_and_audits(monkeypatch):
    settings = Settings()

    monkeypatch.setattr("src.cli.runtime.cmd_uk_health_check", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "src.cli.runtime.apply_symbol_universe_policy",
        lambda *args, **kwargs: {
            "allowed": True,
            "remediated": True,
            "selected_symbols": ["BARC.L", "BP.L"],
            "removed_symbols": ["HSBA.L", "VOD.L", "SHEL.L"],
            "health_summary": {
                "availability_ratio": 0.4,
                "threshold_ratio": 0.8,
                "healthy_symbols": 2,
                "total_symbols": 5,
            },
            "reason": "remediated_with_healthy_subset",
        },
    )
    monkeypatch.setattr(
        "src.cli.runtime.cmd_rotate_paper_db", lambda *args, **kwargs: {"rotated": False}
    )

    calls = {"audit": 0, "run": 0}

    def fake_audit(*args, **kwargs):
        calls["audit"] += 1

    async def fake_run(*args, **kwargs):
        calls["run"] += 1

    monkeypatch.setattr("src.cli.runtime._log_symbol_universe_remediation_event", fake_audit)
    monkeypatch.setattr("src.cli.runtime._run_paper_for_duration", fake_run)
    monkeypatch.setattr(
        "src.cli.runtime.cmd_paper_session_summary", lambda *args, **kwargs: {"summary": {}}
    )
    monkeypatch.setattr(
        "src.cli.runtime.update_execution_trend", lambda *args, **kwargs: {"warnings": []}
    )

    rc = cmd_paper_trial(
        settings,
        duration_seconds=5,
        db_path="trading_paper.db",
        output_dir="reports/session",
    )

    assert rc == 0
    assert settings.data.symbols == ["BARC.L", "BP.L"]
    assert calls["audit"] == 1
    assert calls["run"] == 1
