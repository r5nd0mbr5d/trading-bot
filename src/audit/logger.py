"""Audit Logger — non-blocking, asyncio.Queue + SQLite writer.

Every critical trading event (signals, orders, fills, circuit breakers,
kill-switch state changes) should be logged here for an immutable audit trail.

Design (Q11 research answer):
  - asyncio.Queue separates the fast event-loop path from slow SQLite I/O.
  - A background asyncio.Task drains the queue and writes to SQLite.
  - queue.join() in flush() provides back-pressure-safe shutdown.
  - Schema: normalized columns for common fields + JSON payload for details.
  - Three indexed columns: timestamp, event_type, symbol — fast for reporting.

Usage:
    audit = AuditLogger("trading.db")
    await audit.start()

    await audit.log_event(
        "SIGNAL",
        {"type": "LONG", "strength": 0.8},
        symbol="AAPL",
        strategy="bollinger_bands",
        severity="info",
    )

    await audit.flush()   # wait for all events to hit SQLite
    await audit.stop()

    # Synchronous query (call after flush for consistency)
    rows = audit.query_events(event_type="SIGNAL", symbol="AAPL")
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_VALID_SEVERITIES = ("info", "warning", "error", "critical")


class AuditLogger:
    """
    Non-blocking asyncio audit logger with SQLite persistence.

    Events are enqueued via log_event() (fire-and-forget) and written to
    SQLite by a background task.  Call flush() before querying or shutting
    down to ensure all events have been committed.
    """

    def __init__(self, db_path: str = "trading.db"):
        self._db_path = db_path
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    TEXT NOT NULL,
                    event_type   TEXT NOT NULL,
                    symbol       TEXT,
                    strategy     TEXT,
                    severity     TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp " "ON audit_log(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_event_type " "ON audit_log(event_type)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_symbol " "ON audit_log(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_strategy " "ON audit_log(strategy)")
            conn.commit()

    async def _writer_loop(self) -> None:
        """Background task: consume the queue and write events to SQLite."""
        while True:
            event = await self._queue.get()
            try:
                with self._connect() as conn:
                    conn.execute(
                        """INSERT INTO audit_log
                           (timestamp, event_type, symbol, strategy,
                            severity, payload_json)
                           VALUES (:timestamp, :event_type, :symbol, :strategy,
                                   :severity, :payload_json)""",
                        event,
                    )
                    conn.commit()
            except Exception as exc:
                logger.error(f"AuditLogger write failed: {exc}")
            finally:
                self._queue.task_done()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background SQLite writer task."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._writer_loop())
        logger.debug("AuditLogger background writer started")

    async def stop(self) -> None:
        """Flush pending events then cancel the writer task."""
        await self.flush()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.debug("AuditLogger stopped")

    async def log_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        severity: str = "info",
    ) -> None:
        """
        Enqueue an audit event. Non-blocking — returns immediately.

        Args:
            event_type: Category label (e.g., "SIGNAL", "ORDER_SUBMITTED",
                        "FILL", "KILL_SWITCH", "RISK_VIOLATION", "ERROR").
            payload:    Event-specific dict; serialised to JSON automatically.
            symbol:     Instrument symbol (nullable — omit for system events).
            strategy:   Strategy name (nullable).
            severity:   "info" | "warning" | "error" | "critical".
        """
        await self._queue.put(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "symbol": symbol,
                "strategy": strategy,
                "severity": severity,
                "payload_json": json.dumps(payload, default=str),
            }
        )

    async def flush(self) -> None:
        """
        Block until all queued events have been written to SQLite.
        Call before querying or shutting down.
        """
        await self._queue.join()

    def query_events(
        self,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Synchronous query against the audit_log table.
        Call flush() first to ensure all in-flight events are committed.

        Args:
            event_type: Optional exact-match filter.
            symbol:     Optional exact-match filter.
            strategy:   Optional exact-match filter.
            limit:      Maximum rows returned (newest first).

        Returns:
            List of dicts with payload_json decoded to a dict.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM audit_log {where} " f"ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            try:
                d["payload_json"] = json.loads(d["payload_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(d)
        return result
