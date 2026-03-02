"""Tests for daily P&L report generation."""

import json
import sqlite3
from datetime import datetime, timezone

from config.settings import Settings
from src.audit.daily_report import DailyReportGenerator
from src.cli.runtime import cmd_daily_report


def _init_audit_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                symbol TEXT,
                strategy TEXT,
                severity TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """)
        conn.commit()


def test_daily_report_generator_build_report_aggregates_metrics(tmp_path):
    db_path = str(tmp_path / "daily_report.db")
    _init_audit_db(db_path)

    report_date = datetime.now(timezone.utc).date().isoformat()
    now_ts = datetime.now(timezone.utc).isoformat()

    rows = [
        (now_ts, "FILL", "AAPL", "ma_crossover", "info", json.dumps({"pnl": 12.5})),
        (now_ts, "FILL", "AAPL", "ma_crossover", "info", json.dumps({"realized_pnl": -2.0})),
        (
            now_ts,
            "PORTFOLIO_SNAPSHOT",
            None,
            "ma_crossover",
            "info",
            json.dumps({"positions": [{"symbol": "AAPL"}], "drawdown": 0.04, "sharpe": 1.1}),
        ),
        (
            now_ts,
            "PAPER_GUARDRAIL_BLOCK",
            "AAPL",
            "ma_crossover",
            "warning",
            json.dumps({"reason": "daily limit"}),
        ),
    ]

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    generator = DailyReportGenerator(db_path)
    report = generator.build_report(report_date=report_date)

    assert report["report_date"] == report_date
    assert report["fills"] == 2
    assert report["pnl_proxy_mark_to_close"] == 10.5
    assert report["open_positions"] == 1
    assert report["sharpe_running"] == 1.1
    assert report["max_intraday_drawdown"] == 0.04
    assert report["guardrail_firings"] == 1


def test_daily_report_generator_write_report_creates_json(tmp_path):
    db_path = str(tmp_path / "daily_report_write.db")
    _init_audit_db(db_path)

    generator = DailyReportGenerator(db_path)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_date": "2026-02-25",
        "fills": 0,
        "pnl_proxy_mark_to_close": 0.0,
        "open_positions": 0,
        "sharpe_running": None,
        "max_intraday_drawdown": None,
        "guardrail_firings": 0,
        "db_path": db_path,
    }

    output_path = generator.write_report(report, output_dir=str(tmp_path / "reports" / "daily"))
    assert output_path.endswith("2026-02-25.json")

    payload = json.loads(
        (tmp_path / "reports" / "daily" / "2026-02-25.json").read_text(encoding="utf-8")
    )
    assert payload["report_date"] == "2026-02-25"


def test_cmd_daily_report_uses_runtime_handler(tmp_path):
    settings = Settings()
    db_path = str(tmp_path / "daily_cmd.db")
    _init_audit_db(db_path)

    result = cmd_daily_report(
        settings,
        db_path,
        output_dir=str(tmp_path / "reports" / "daily"),
        report_date="2026-02-25",
        notify_email=None,
    )

    assert "report" in result
    assert result["report"]["report_date"] == "2026-02-25"
