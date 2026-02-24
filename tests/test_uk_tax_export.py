"""Unit tests for UK tax audit exports."""

import csv
import json
import sqlite3

from src.audit.uk_tax_export import export_uk_tax_reports


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

        events = [
            (
                "2026-01-10T10:00:00+00:00",
                "FILL",
                "AAPL",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "buy",
                        "qty": 10,
                        "filled_price": 100,
                        "fee": 1.0,
                        "currency": "USD",
                    }
                ),
            ),
            (
                "2026-01-20T10:00:00+00:00",
                "FILL",
                "AAPL",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "sell",
                        "qty": 10,
                        "filled_price": 110,
                        "fee": 1.0,
                        "currency": "USD",
                    }
                ),
            ),
            (
                "2026-01-21T10:00:00+00:00",
                "FILL",
                "HSBA.L",
                json.dumps(
                    {"symbol": "HSBA.L", "side": "buy", "qty": 5, "filled_price": 200, "fee": 0.5}
                ),
            ),
        ]

        for ts, event_type, symbol, payload_json in events:
            conn.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, event_type, symbol, "test", "info", payload_json),
            )
        conn.commit()


def _read_csv_rows(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_export_uk_tax_reports_generates_expected_files(tmp_path):
    db_path = str(tmp_path / "audit.db")
    output_dir = str(tmp_path / "uk_reports")
    _seed_audit_db(db_path)

    paths = export_uk_tax_reports(
        db_path,
        output_dir,
        base_currency="GBP",
        fx_rates={"USD_GBP": 0.8},
    )

    assert "trade_ledger" in paths
    assert "realized_gains" in paths
    assert "fx_notes" in paths

    ledger_rows = _read_csv_rows(paths["trade_ledger"])
    realized_rows = _read_csv_rows(paths["realized_gains"])
    fx_rows = _read_csv_rows(paths["fx_notes"])

    assert len(ledger_rows) == 3
    # First buy: 10 * 100 USD * 0.8 = 800 GBP
    assert ledger_rows[0]["gross_value_gbp"] == "800.0"

    # Realized gain for AAPL round trip in GBP:
    # proceeds = 10*110*0.8 - 1*0.8 = 879.2
    # cost basis = 10*100*0.8 + 1*0.8 = 800.8
    # gain = 78.4
    assert len(realized_rows) == 1
    assert realized_rows[0]["symbol"] == "AAPL"
    assert realized_rows[0]["realized_gain_gbp"] == "78.4"

    # We traded USD and GBP instruments in GBP base, so USD_GBP should be documented.
    assert any(r["pair"] == "USD_GBP" for r in fx_rows)


def test_export_prefers_enriched_order_filled_fields(tmp_path):
    db_path = str(tmp_path / "audit_enriched.db")
    output_dir = str(tmp_path / "uk_reports_enriched")

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
        conn.execute(
            """
            INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-02-01T10:00:00+00:00",
                "ORDER_FILLED",
                "AAPL",
                "test",
                "info",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "buy",
                        "qty": 2,
                        "price": 100.0,
                        "price_reference": 99.5,
                        "filled_price": 101.0,
                        "fee": 0.4,
                        "commission": 99.0,
                        "slippage_pct_vs_signal": 0.01507538,
                        "currency": "USD",
                    }
                ),
            ),
        )
        conn.commit()

    paths = export_uk_tax_reports(
        db_path, output_dir, base_currency="GBP", fx_rates={"USD_GBP": 0.8}
    )
    ledger_rows = _read_csv_rows(paths["trade_ledger"])

    assert len(ledger_rows) == 1
    row = ledger_rows[0]
    assert row["price"] == "101.0"  # filled_price takes precedence over price
    assert row["price_reference"] == "99.5"
    assert row["slippage_pct_vs_signal"] == "0.01507538"
    assert row["fee"] == "0.4"  # fee takes precedence over commission


def test_fx_notes_flag_stale_timestamps(tmp_path):
    db_path = str(tmp_path / "audit.db")
    output_dir = str(tmp_path / "uk_reports")
    _seed_audit_db(db_path)

    paths = export_uk_tax_reports(
        db_path,
        output_dir,
        base_currency="GBP",
        fx_rates={"USD_GBP": 0.8},
        fx_rate_timestamps={"USD_GBP": "2000-01-01T00:00:00+00:00"},
        fx_rate_max_age_hours=24.0,
    )

    fx_rows = _read_csv_rows(paths["fx_notes"])
    usd_note = next(r["note"] for r in fx_rows if r["pair"] == "USD_GBP")
    assert "stale" in usd_note


def test_export_handles_missing_audit_table(tmp_path):
    db_path = str(tmp_path / "empty.db")
    output_dir = str(tmp_path / "uk_reports")

    with sqlite3.connect(db_path):
        pass

    paths = export_uk_tax_reports(db_path, output_dir, base_currency="GBP")

    ledger_rows = _read_csv_rows(paths["trade_ledger"])
    realized_rows = _read_csv_rows(paths["realized_gains"])
    fx_rows = _read_csv_rows(paths["fx_notes"])

    assert ledger_rows == []
    assert realized_rows == []
    assert fx_rows == []


def test_export_skips_unmatched_sell_realized_row(tmp_path):
    db_path = str(tmp_path / "audit_unmatched.db")
    output_dir = str(tmp_path / "uk_reports_unmatched")

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
        conn.execute(
            """
            INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-02-01T10:00:00+00:00",
                "FILL",
                "AAPL",
                "test",
                "info",
                json.dumps(
                    {
                        "symbol": "AAPL",
                        "side": "sell",
                        "qty": 3,
                        "filled_price": 101.0,
                        "fee": 0.3,
                        "currency": "USD",
                    }
                ),
            ),
        )
        conn.commit()

    paths = export_uk_tax_reports(
        db_path, output_dir, base_currency="GBP", fx_rates={"USD_GBP": 0.8}
    )
    realized_rows = _read_csv_rows(paths["realized_gains"])

    assert realized_rows == []
