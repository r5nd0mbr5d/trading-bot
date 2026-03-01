"""Offline paper-trial harness for reports and reconciliation."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import Settings  # noqa: E402
from src.cli.runtime import (  # noqa: E402
    apply_runtime_profile,
    cmd_paper_reconcile,
    cmd_paper_session_summary,
    cmd_uk_tax_export,
    resolve_runtime_db_path,
)


def _ensure_db(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                symbol TEXT,
                strategy TEXT,
                severity TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_symbol ON audit_log(symbol)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_strategy ON audit_log(strategy)"
        )
        conn.commit()


def _has_events(db_path: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM audit_log")
        return cur.fetchone()[0] > 0


def _seed_minimal_round_trip(
    db_path: str,
    *,
    symbol: str,
    strategy: str,
    qty: float,
    buy_price: float,
    sell_price: float,
    currency: str,
) -> None:
    now = datetime.now(timezone.utc)
    events = [
        (
            "SIGNAL",
            symbol,
            strategy,
            "info",
            {
                "symbol": symbol,
                "side": "buy",
                "strength": 0.8,
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
            },
        ),
        (
            "ORDER_SUBMITTED",
            symbol,
            strategy,
            "info",
            {"symbol": symbol, "side": "buy", "qty": qty, "price_reference": buy_price},
        ),
        (
            "ORDER_FILLED",
            symbol,
            strategy,
            "info",
            {
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "filled_price": buy_price,
                "fee": 1.0,
                "currency": currency,
                "slippage_pct_vs_signal": 0.0,
            },
        ),
        (
            "SIGNAL",
            symbol,
            strategy,
            "info",
            {
                "symbol": symbol,
                "side": "sell",
                "strength": 0.7,
                "timestamp": (now - timedelta(minutes=2)).isoformat(),
            },
        ),
        (
            "ORDER_SUBMITTED",
            symbol,
            strategy,
            "info",
            {"symbol": symbol, "side": "sell", "qty": qty, "price_reference": sell_price},
        ),
        (
            "ORDER_FILLED",
            symbol,
            strategy,
            "info",
            {
                "symbol": symbol,
                "side": "sell",
                "qty": qty,
                "filled_price": sell_price,
                "fee": 1.0,
                "currency": currency,
                "slippage_pct_vs_signal": 0.0,
            },
        ),
    ]

    with sqlite3.connect(db_path) as conn:
        for i, (event_type, sym, strat, severity, payload) in enumerate(events):
            ts = (now + timedelta(seconds=i)).isoformat()
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, symbol, strategy, severity, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, event_type, sym, strat, severity, json.dumps(payload)),
            )
        conn.commit()


def run() -> int:
    parser = argparse.ArgumentParser(description="Offline report harness")
    parser.add_argument(
        "--confirm-harness",
        action="store_true",
        help="Explicit confirmation that this is a test harness run",
    )
    parser.add_argument("--profile", default="default", choices=["default", "uk_paper"])
    parser.add_argument("--db-path", default="reports/uk_tax/harness_paper.db")
    parser.add_argument("--output-dir", default="reports/uk_tax")
    parser.add_argument("--expected-json", default=None)
    parser.add_argument("--tolerance-json", default=None)
    parser.add_argument("--strict-reconcile", action="store_true")
    parser.add_argument("--seed-empty", action="store_true", help="Seed a minimal round-trip if DB is empty")
    parser.add_argument("--seed-symbol", default="AAPL")
    parser.add_argument("--seed-strategy", default="ma_crossover")
    parser.add_argument("--seed-qty", type=float, default=10.0)
    parser.add_argument("--seed-buy-price", type=float, default=150.0)
    parser.add_argument("--seed-sell-price", type=float, default=152.0)
    parser.add_argument("--seed-currency", default="USD")
    parser.add_argument(
        "--expected-from-summary",
        action="store_true",
        help="Write expected metrics from summary (numeric only) and reconcile against it",
    )
    parser.add_argument("--expected-out", default=None)
    args = parser.parse_args()

    if not args.confirm_harness:
        print("ERROR: --confirm-harness is required for offline harness runs.")
        return 2

    settings = Settings()
    apply_runtime_profile(settings, args.profile)

    db_path = args.db_path
    paper_db = resolve_runtime_db_path(settings, "paper")
    live_db = resolve_runtime_db_path(settings, "live")
    test_db = resolve_runtime_db_path(settings, "test")
    if db_path in {paper_db, live_db, test_db}:
        print(
            "ERROR: Harness DB must be isolated from runtime DBs. "
            f"Got {db_path}."
        )
        return 2
    _ensure_db(db_path)
    if args.seed_empty and not _has_events(db_path):
        _seed_minimal_round_trip(
            db_path,
            symbol=args.seed_symbol,
            strategy=args.seed_strategy,
            qty=args.seed_qty,
            buy_price=args.seed_buy_price,
            sell_price=args.seed_sell_price,
            currency=args.seed_currency,
        )

    summary_result = cmd_paper_session_summary(
        settings,
        db_path,
        args.output_dir,
        enforce_mode=False,
    )
    expected_json = args.expected_json or summary_result["json_path"]
    if args.expected_from_summary:
        summary = summary_result["summary"]
        numeric_expected = {
            key: value
            for key, value in summary.items()
            if isinstance(value, (int, float))
        }
        expected_path = Path(args.expected_out) if args.expected_out else Path(args.output_dir) / "expected_metrics.json"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(json.dumps(numeric_expected, indent=2), encoding="utf-8")
        expected_json = str(expected_path)

    drift_count = cmd_paper_reconcile(
        settings,
        db_path,
        args.output_dir,
        expected_json,
        args.tolerance_json,
        enforce_mode=False,
    )

    cmd_uk_tax_export(settings, db_path, args.output_dir, enforce_mode=False)

    if args.strict_reconcile and drift_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
