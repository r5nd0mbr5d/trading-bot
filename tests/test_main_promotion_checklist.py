"""Unit test for main promotion checklist command wrapper."""

from config.settings import Settings
from src.cli.runtime import cmd_promotion_checklist


def test_cmd_promotion_checklist_invokes_export(monkeypatch):
    settings = Settings()
    captured = {}

    def fake_export(output_dir, strategy, summary_json_path, base_currency):
        captured["output_dir"] = output_dir
        captured["strategy"] = strategy
        captured["summary_json_path"] = summary_json_path
        captured["base_currency"] = base_currency
        return {
            "output_path": "reports/promotions/promotion_checklist.json",
            "decision": "NOT_READY",
        }

    monkeypatch.setattr("src.cli.runtime.export_promotion_checklist", fake_export)

    cmd_promotion_checklist(
        settings,
        strategy="ma_crossover",
        output_dir="reports/promotions",
        summary_json_path="reports/session/paper_session_summary.json",
    )

    assert captured["output_dir"] == "reports/promotions"
    assert captured["strategy"] == "ma_crossover"
    assert captured["summary_json_path"] == "reports/session/paper_session_summary.json"
    assert captured["base_currency"] == settings.base_currency


def test_cmd_promotion_checklist_emits_audit(monkeypatch):
    settings = Settings()
    captured = {"audit": 0}

    def fake_export(output_dir, strategy, summary_json_path, base_currency):
        return {"output_path": "reports/promotions/promotion_checklist.json", "decision": "READY"}

    def fake_log(db_path, strategy, decision, output_path):
        captured["audit"] += 1
        captured["db_path"] = db_path
        captured["strategy"] = strategy
        captured["decision"] = decision
        captured["output_path"] = output_path

    monkeypatch.setattr("src.cli.runtime.export_promotion_checklist", fake_export)
    monkeypatch.setattr("src.cli.runtime._log_promotion_checklist_event", fake_log)

    cmd_promotion_checklist(
        settings,
        strategy="ma_crossover",
        output_dir="reports/promotions",
        summary_json_path=None,
        audit_db_path="trading_paper.db",
    )

    assert captured["audit"] == 1
    assert captured["db_path"] == "trading_paper.db"
    assert captured["strategy"] == "ma_crossover"
    assert captured["decision"] == "READY"
    assert captured["output_path"] == "reports/promotions/promotion_checklist.json"
