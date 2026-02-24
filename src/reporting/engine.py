"""Shared reporting data-access engine for SQLite-backed reports."""

from __future__ import annotations

import sqlite3
from typing import Optional


class ReportingEngine:
    """Centralized SQLite query helper used by reporting/audit exporters."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def fetch_audit_events(self) -> list[sqlite3.Row]:
        """Return audit events sorted by timestamp, or empty when table missing."""
        with self._connect() as conn:
            try:
                return conn.execute(
                    """
                    SELECT timestamp, event_type, symbol, payload_json
                    FROM audit_log
                    ORDER BY timestamp ASC
                    """
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower() and "audit_log" in str(exc).lower():
                    return []
                raise

    def fetch_market_bars(self) -> list[sqlite3.Row]:
        """Return market bars sorted by symbol/timestamp, or empty when table missing."""
        with self._connect() as conn:
            try:
                return conn.execute(
                    """
                    SELECT symbol, timestamp, open, high, low, close
                    FROM market_bars
                    ORDER BY symbol ASC, timestamp ASC
                    """
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower() and "market_bars" in str(exc).lower():
                    return []
                raise

    def fetch_one(self, query: str, params: Optional[tuple] = None) -> sqlite3.Row | None:
        """Execute a read-only query and return one row (utility method)."""
        with self._connect() as conn:
            return conn.execute(query, params or ()).fetchone()
