"""Unit tests for paper reconciliation reporting."""

import csv
import json
import sqlite3

from src.audit.reconciliation import build_reconciliation_report, export_paper_reconciliation


def _seed_audit_db(db_path: str) -> None:
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
                "2026-02-20T09:01:00+00:00",
                "ORDER_SUBMITTED",
                "AAPL",
                json.dumps({"symbol": "AAPL", "side": "buy", "qty": 10}),
            ),
            (
                "2026-02-20T09:02:00+00:00",
                "ORDER_FILLED",
                "AAPL",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "buy",
                        "qty": 10,
                        "filled_price": 100.0,
                        "fee": 1.0,
                        "currency": "USD",
                        "slippage_pct_vs_signal": 0.001,
                    }
                ),
            ),
            (
                "2026-02-20T09:03:00+00:00",
                "ORDER_SUBMITTED",
                "AAPL",
                json.dumps({"symbol": "AAPL", "side": "sell", "qty": 10}),
            ),
            (
                "2026-02-20T09:04:00+00:00",
                "ORDER_FILLED",
                "AAPL",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "sell",
                        "qty": 10,
                        "filled_price": 110.0,
                        "fee": 1.0,
                        "currency": "USD",
                        "slippage_pct_vs_signal": 0.001,
                    }
                ),
            ),
        ]

        for ts, event_type, symbol, payload in rows:
            conn.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, event_type, symbol, "test", "info", payload),
            )
        conn.commit()


def test_build_reconciliation_report_flags_drift():
    actual = {
        "fill_rate": 1.0,
        "win_rate": 1.0,
        "realized_pnl": 78.4,
    }
    expected = {
        "fill_rate": 0.98,
        "win_rate": 0.95,
        "realized_pnl": 400.0,
    }
    report = build_reconciliation_report(
        actual,
        expected,
        tolerances={"fill_rate": 0.05, "win_rate": 0.10, "realized_pnl": 50.0},
    )

    assert report["ok"] is False
    assert report["drift_flag_count"] == 1
    pnl_row = next(r for r in report["rows"] if r["metric"] == "realized_pnl")
    assert pnl_row["drift_flag"] is True


def test_export_paper_reconciliation_writes_json_and_csv(tmp_path):
    db_path = str(tmp_path / "audit.db")
    out_dir = str(tmp_path / "reports")
    _seed_audit_db(db_path)

    result = export_paper_reconciliation(
        db_path,
        out_dir,
        expected_metrics={
            "fill_rate": 1.0,
            "win_rate": 1.0,
            "realized_pnl": 78.4,
        },
        base_currency="GBP",
        fx_rates={"USD_GBP": 0.8},
        tolerances={
            "fill_rate": 0.01,
            "win_rate": 0.01,
            "realized_pnl": 0.1,
        },
    )

    assert result["report"]["ok"] is True

    with open(result["json_path"], encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["report"]["drift_flag_count"] == 0
    assert payload["actual_summary"]["fx_converted_fill_count"] == 2
    assert payload["actual_summary"]["fx_fallback_count"] == 0
    assert payload["actual_summary"]["fx_missing_pairs"] == []

    with open(result["csv_path"], newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3


def test_export_paper_reconciliation_handles_missing_audit_table(tmp_path):
    db_path = str(tmp_path / "empty.db")
    out_dir = str(tmp_path / "reports")

    with sqlite3.connect(db_path):
        pass

    result = export_paper_reconciliation(
        db_path,
        out_dir,
        expected_metrics={"fill_rate": 1.0},
    )

    assert result["report"]["ok"] is False
    assert result["report"]["metric_count"] == 1
    assert result["report"]["drift_flag_count"] == 1


def test_build_reconciliation_report_non_numeric_equal_values_do_not_drift():
    actual = {
        "base_currency": "GBP",
        "db_path": "trading_paper.db",
    }
    expected = {
        "base_currency": "GBP",
        "db_path": "trading_paper.db",
    }

    report = build_reconciliation_report(actual, expected)

    assert report["ok"] is True
    assert report["drift_flag_count"] == 0


def test_build_reconciliation_report_non_numeric_mismatch_flags_drift():
    actual = {
        "base_currency": "USD",
    }
    expected = {
        "base_currency": "GBP",
    }

    report = build_reconciliation_report(actual, expected)

    assert report["ok"] is False
    assert report["drift_flag_count"] == 1
    row = report["rows"][0]
    assert row["metric"] == "base_currency"
    assert row["drift_flag"] is True
    assert row["note"] == "non-numeric metric mismatch"
