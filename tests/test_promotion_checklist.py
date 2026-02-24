"""Tests for promotion checklist generation/export."""

import json

from src.promotions.checklist import build_promotion_checklist, export_promotion_checklist


def test_build_promotion_checklist_with_summary_passes_metrics_gate():
    summary = {
        "closed_trade_count": 30,
        "win_rate": 0.55,
        "profit_factor": 1.30,
        "realized_pnl": 100.0,
        "fill_rate": 0.95,
        "avg_slippage_pct": 0.0015,
    }

    checklist = build_promotion_checklist("ma_crossover", summary=summary, base_currency="GBP")

    assert checklist["strategy"] == "ma_crossover"
    assert checklist["paper_readiness_failures"] == []
    metric_row = next(
        c for c in checklist["in_paper_checks"] if c["id"] == "paper_readiness_metrics"
    )
    assert metric_row["status"] == "pass"
    assert checklist["decision"] == "NOT_READY"


def test_export_promotion_checklist_writes_json(tmp_path):
    summary_path = tmp_path / "paper_session_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "closed_trade_count": 10,
                "win_rate": 0.40,
                "profit_factor": 0.90,
                "realized_pnl": -5.0,
                "fill_rate": 0.80,
                "avg_slippage_pct": 0.005,
            }
        ),
        encoding="utf-8",
    )

    result = export_promotion_checklist(
        str(tmp_path / "reports"),
        "rsi_momentum",
        summary_json_path=str(summary_path),
        base_currency="GBP",
    )

    assert result["output_path"].endswith("promotion_checklist.json")

    payload = json.loads(
        (tmp_path / "reports" / "promotion_checklist.json").read_text(encoding="utf-8")
    )
    assert payload["strategy"] == "rsi_momentum"
    assert payload["decision"] == "NOT_READY"
    assert len(payload["paper_readiness_failures"]) > 0
