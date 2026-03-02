"""Kill Switch — persistent, SQLite-backed trading halt.

When triggered, the kill switch blocks all new orders and survives process
restarts. It must be explicitly reset by an operator before trading resumes.

Typical trigger conditions:
  - Maximum drawdown circuit breaker
  - Data feed disconnection for > N seconds
  - N consecutive order rejections
  - Manual operator halt

Usage:
    ks = KillSwitch("trading.db")
    ks.check_and_raise()          # call before every order submission
    ks.trigger("drawdown_limit")  # automatic trigger
    ks.reset("operator@firm.com") # operator action only
"""

import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class KillSwitch:
    """
    Persistent kill switch backed by a single-row SQLite table.

    The singleton row (id=1) is created on first use and never deleted,
    so state survives process restarts.
    """

    def __init__(self, db_path: str = "trading.db"):
        self._db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kill_switch (
                    id           INTEGER PRIMARY KEY CHECK (id = 1),
                    active       INTEGER NOT NULL DEFAULT 0,
                    reason       TEXT,
                    triggered_at TEXT,
                    reset_by     TEXT,
                    reset_at     TEXT
                )
            """)
            conn.execute("INSERT OR IGNORE INTO kill_switch (id, active) VALUES (1, 0)")
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger(self, reason: str) -> None:
        """
        Activate the kill switch. Idempotent — safe to call multiple times.
        Subsequent calls update the reason and timestamp.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE kill_switch
                   SET active=1, reason=?, triggered_at=?, reset_by=NULL, reset_at=NULL
                   WHERE id=1""",
                (reason, now),
            )
            conn.commit()
        logger.critical(f"KILL SWITCH TRIGGERED: {reason}")

    def is_active(self) -> bool:
        """Return True if the kill switch is currently active."""
        with self._connect() as conn:
            row = conn.execute("SELECT active FROM kill_switch WHERE id=1").fetchone()
        return bool(row[0]) if row else False

    def reset(self, operator_id: str) -> None:
        """
        Deactivate the kill switch.
        Requires an operator_id for the audit trail.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE kill_switch
                   SET active=0, reset_by=?, reset_at=?
                   WHERE id=1""",
                (operator_id, now),
            )
            conn.commit()
        logger.warning(f"Kill switch RESET by operator: {operator_id}")

    def check_and_raise(self) -> None:
        """
        Raise RuntimeError if the kill switch is active.
        Call this at the top of every order-submission path.

        Because it only reads one SQLite row, this is near-instant and
        does not block the asyncio event loop in practice.
        """
        if self.is_active():
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT reason, triggered_at FROM kill_switch WHERE id=1"
                ).fetchone()
            reason = row[0] if row else "unknown"
            triggered_at = row[1] if row else "unknown"
            raise RuntimeError(f"Kill switch is active (triggered {triggered_at}): {reason}")

    def status(self) -> dict:
        """Return the full kill switch state as a plain dict."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM kill_switch WHERE id=1").fetchone()
        if row:
            return dict(row)
        return {
            "id": 1,
            "active": 0,
            "reason": None,
            "triggered_at": None,
            "reset_by": None,
            "reset_at": None,
        }
