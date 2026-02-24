"""Tests for shared reporting SQLite query engine."""

import sqlite3
from pathlib import Path

from src.reporting.engine import ReportingEngine


def _create_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            timestamp TEXT,
            event_type TEXT,
            symbol TEXT,
            payload_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_bars (
            symbol TEXT,
            timestamp TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL
        )
        """
    )
    conn.commit()
    conn.close()


def test_fetch_audit_events_returns_sorted_rows(tmp_path):
    db_path = tmp_path / "reporting.db"
    _create_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, symbol, payload_json) VALUES (?, ?, ?, ?)",
        ("2026-02-24T10:01:00+00:00", "ORDER_FILLED", "AAPL", "{}"),
    )
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, symbol, payload_json) VALUES (?, ?, ?, ?)",
        ("2026-02-24T10:00:00+00:00", "ORDER_SUBMITTED", "AAPL", "{}"),
    )
    conn.commit()
    conn.close()

    engine = ReportingEngine(str(db_path))
    rows = engine.fetch_audit_events()

    assert len(rows) == 2
    assert rows[0]["event_type"] == "ORDER_SUBMITTED"
    assert rows[1]["event_type"] == "ORDER_FILLED"


def test_fetch_market_bars_returns_rows(tmp_path):
    db_path = tmp_path / "reporting.db"
    _create_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO market_bars (symbol, timestamp, open, high, low, close) VALUES (?, ?, ?, ?, ?, ?)",
        ("AAPL", "2026-02-24T10:00:00+00:00", 1.0, 1.1, 0.9, 1.0),
    )
    conn.commit()
    conn.close()

    engine = ReportingEngine(str(db_path))
    rows = engine.fetch_market_bars()

    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"


def test_missing_tables_return_empty_lists(tmp_path):
    db_path = tmp_path / "empty.db"
    sqlite3.connect(db_path).close()

    engine = ReportingEngine(str(db_path))

    assert engine.fetch_audit_events() == []
    assert engine.fetch_market_bars() == []
