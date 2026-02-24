"""Unit tests for data quality report export."""

import json
import sqlite3
from datetime import datetime, timezone

from src.reporting.data_quality_report import export_data_quality_report


def _seed_market_bars(db_path: str, rows: list[tuple]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE market_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL
            )
            """)
        for symbol, ts, open_, high, low, close in rows:
            conn.execute(
                """
                INSERT INTO market_bars (symbol, timestamp, open, high, low, close)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (symbol, ts, open_, high, low, close),
            )
        conn.commit()


def test_data_quality_report_handles_empty_db(tmp_path):
    db_path = str(tmp_path / "empty.db")
    output = str(tmp_path / "reports" / "data_quality.json")
    dashboard = str(tmp_path / "reports" / "execution_dashboard.html")

    with sqlite3.connect(db_path):
        pass

    result = export_data_quality_report(db_path, output, dashboard_path=dashboard)

    assert result["report"]["symbols_checked"] == 0
    assert (tmp_path / "reports" / "data_quality.json").exists()
    assert (tmp_path / "reports" / "execution_dashboard.html").exists()


def test_data_quality_report_flags_stale_data(tmp_path):
    db_path = str(tmp_path / "stale.db")
    output = str(tmp_path / "data_quality.json")

    _seed_market_bars(
        db_path,
        [
            ("TEST", "2026-01-01T00:00:00+00:00", 100.0, 101.0, 99.0, 100.5),
        ],
    )

    now = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    result = export_data_quality_report(
        db_path,
        output,
        max_staleness_seconds=1800,
        now_utc=now,
    )

    row = result["report"]["symbols"][0]
    assert row["symbol"] == "TEST"
    assert row["stale"] is True


def test_data_quality_report_detects_gaps_and_ohlc_violations(tmp_path):
    db_path = str(tmp_path / "gaps.db")
    output = str(tmp_path / "data_quality.json")

    _seed_market_bars(
        db_path,
        [
            ("AAA", "2026-01-01T00:00:00+00:00", 100.0, 101.0, 99.0, 100.2),
            ("AAA", "2026-01-01T00:05:00+00:00", 100.2, 101.2, 99.2, 100.4),
            ("AAA", "2026-01-01T00:30:00+00:00", 100.4, 99.0, 100.5, 100.3),
        ],
    )

    result = export_data_quality_report(
        db_path,
        output,
        expected_gap_seconds=600,
        now_utc=datetime(2026, 1, 1, 0, 40, tzinfo=timezone.utc),
    )

    row = result["report"]["symbols"][0]
    assert row["gap_count"] == 1
    assert row["ohlc_violation_count"] == 1

    payload = json.loads((tmp_path / "data_quality.json").read_text(encoding="utf-8"))
    assert payload["symbols_checked"] == 1
