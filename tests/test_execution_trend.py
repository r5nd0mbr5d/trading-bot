"""Tests for execution trend monitoring."""

from src.monitoring.execution_trend import update_execution_trend


def test_update_execution_trend_flags_monotonic_decline(tmp_path):
    trend_path = tmp_path / "trend.json"
    summaries = [
        {"fill_rate": 0.98, "avg_slippage_pct": 0.0010, "last_event_ts": "2026-02-20T10:00:00Z"},
        {"fill_rate": 0.95, "avg_slippage_pct": 0.0015, "last_event_ts": "2026-02-21T10:00:00Z"},
        {"fill_rate": 0.92, "avg_slippage_pct": 0.0021, "last_event_ts": "2026-02-22T10:00:00Z"},
    ]

    warnings = []
    for summary in summaries:
        result = update_execution_trend(summary, str(trend_path), window=5)
        warnings = result["warnings"]

    assert any("fill_rate declining" in w for w in warnings)
    assert any("avg_slippage rising" in w for w in warnings)


def test_update_execution_trend_handles_invalid_json(tmp_path):
    trend_path = tmp_path / "trend.json"
    trend_path.write_text("not-json", encoding="utf-8")

    result = update_execution_trend(
        {"fill_rate": 0.5, "avg_slippage_pct": 0.001, "last_event_ts": "2026-02-22T10:00:00Z"},
        str(trend_path),
    )

    assert result["history"]
