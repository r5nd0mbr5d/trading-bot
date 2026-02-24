"""Unit tests for paper session summary exports."""

import csv
import json
import sqlite3

from src.audit.session_summary import export_paper_session_summary


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
                "2026-02-20T09:00:00+00:00",
                "SIGNAL",
                "AAPL",
                json.dumps({"symbol": "AAPL", "side": "buy", "strength": 0.8}),
            ),
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
                        "slippage_pct_vs_signal": 0.01,
                    }
                ),
            ),
            (
                "2026-02-20T09:03:00+00:00",
                "SIGNAL",
                "AAPL",
                json.dumps({"symbol": "AAPL", "side": "sell", "strength": 0.7}),
            ),
            (
                "2026-02-20T09:04:00+00:00",
                "ORDER_SUBMITTED",
                "AAPL",
                json.dumps({"symbol": "AAPL", "side": "sell", "qty": 10}),
            ),
            (
                "2026-02-20T09:05:00+00:00",
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
                        "slippage_pct_vs_signal": -0.005,
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


def _read_metric_csv(path: str) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["metric"]: row["value"] for row in rows}


def test_export_paper_session_summary_generates_metrics(tmp_path):
    db_path = str(tmp_path / "audit.db")
    out_dir = str(tmp_path / "reports")
    _seed_audit_db(db_path)

    result = export_paper_session_summary(
        db_path,
        out_dir,
        base_currency="GBP",
        fx_rates={"USD_GBP": 0.8},
    )

    summary = result["summary"]
    assert summary["signal_count"] == 2
    assert summary["order_attempt_count"] == 2
    assert summary["filled_order_count"] == 2
    assert summary["fill_rate"] == 1.0
    assert summary["closed_trade_count"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["fx_converted_fill_count"] == 2
    assert summary["fx_fallback_count"] == 0
    assert summary["fx_missing_pairs"] == []
    # PnL in GBP: proceeds(10*110*0.8 - 1*0.8) - cost(10*100*0.8 + 1*0.8) = 78.4
    assert summary["realized_pnl"] == 78.4

    with open(result["json_path"], encoding="utf-8") as f:
        json_payload = json.load(f)
    assert json_payload["realized_pnl"] == 78.4

    metrics = _read_metric_csv(result["csv_path"])
    assert metrics["signal_count"] == "2"
    assert metrics["fill_rate"] == "1.0"


def test_export_paper_session_summary_tracks_missing_fx_pairs(tmp_path):
    db_path = str(tmp_path / "audit.db")
    out_dir = str(tmp_path / "reports")
    _seed_audit_db(db_path)

    result = export_paper_session_summary(
        db_path,
        out_dir,
        base_currency="GBP",
        fx_rates={},
    )

    summary = result["summary"]
    assert summary["fx_converted_fill_count"] == 2
    assert summary["fx_fallback_count"] == 2
    assert summary["fx_missing_pairs"] == ["USD_GBP"]
