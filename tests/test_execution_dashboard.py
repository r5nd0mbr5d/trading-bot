"""Unit tests for execution telemetry dashboard export."""

import sqlite3

from src.reporting.execution_dashboard import export_execution_dashboard


def _seed_dashboard_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                symbol TEXT,
                strategy TEXT,
                severity TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """)

        rows = [
            (
                "2026-02-20T08:00:00+00:00",
                "ORDER_SUBMITTED",
                "HSBA.L",
                '{"symbol":"HSBA.L","order_id":"1"}',
            ),
            (
                "2026-02-20T08:00:03+00:00",
                "ORDER_FILLED",
                "HSBA.L",
                '{"symbol":"HSBA.L","order_id":"1","slippage_pct_vs_signal":0.0012}',
            ),
            (
                "2026-02-20T08:10:00+00:00",
                "ORDER_SUBMITTED",
                "VOD.L",
                '{"symbol":"VOD.L","order_id":"2"}',
            ),
            (
                "2026-02-20T08:10:05+00:00",
                "ORDER_REJECTED",
                "VOD.L",
                '{"symbol":"VOD.L","order_id":"2"}',
            ),
        ]

        for ts, event_type, symbol, payload_json in rows:
            conn.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, event_type, symbol, "test", "info", payload_json),
            )
        conn.commit()


def test_export_execution_dashboard_writes_html(tmp_path):
    db_path = str(tmp_path / "audit.db")
    output_path = str(tmp_path / "reports" / "execution_dashboard.html")
    _seed_dashboard_db(db_path)

    result = export_execution_dashboard(db_path, output_path, refresh_seconds=30)

    assert result["output_path"].endswith("execution_dashboard.html")
    assert result["metrics"]["event_count"] == 4
    assert len(result["metrics"]["reject_rate_by_symbol"]) == 2

    html = (tmp_path / "reports" / "execution_dashboard.html").read_text(encoding="utf-8")
    assert "Execution Dashboard" in html
    assert "Auto-refresh every 30s" in html


def test_export_execution_dashboard_handles_missing_table(tmp_path):
    db_path = str(tmp_path / "empty.db")
    output_path = str(tmp_path / "dashboard.html")

    with sqlite3.connect(db_path):
        pass

    result = export_execution_dashboard(db_path, output_path)

    assert result["metrics"]["event_count"] == 0
    assert (tmp_path / "dashboard.html").exists()
