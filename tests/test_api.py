"""Integration tests for read-only dashboard API endpoints."""

import json
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app


def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE kill_switch (id INTEGER PRIMARY KEY AUTOINCREMENT, reason TEXT)")
    conn.execute(
        "CREATE TABLE audit_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "timestamp TEXT, "
        "event_type TEXT, "
        "payload TEXT, "
        "symbol TEXT, "
        "strategy TEXT"
        ")"
    )
    conn.execute("INSERT INTO kill_switch (reason) VALUES ('manual_test')")
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, payload, symbol, strategy) VALUES (?, ?, ?, ?, ?)",
        (
            "2026-02-25T09:00:00Z",
            "STREAM_HEARTBEAT",
            json.dumps({"event": "STREAM_HEARTBEAT"}),
            "",
            "ma_crossover",
        ),
    )
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, payload, symbol, strategy) VALUES (?, ?, ?, ?, ?)",
        (
            "2026-02-25T09:01:00Z",
            "SIGNAL",
            json.dumps({"type": "long", "strength": 0.8}),
            "HSBA.L",
            "ma_crossover",
        ),
    )
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, payload, symbol, strategy) VALUES (?, ?, ?, ?, ?)",
        (
            "2026-02-25T09:02:00Z",
            "ORDER_FILLED",
            json.dumps({"side": "buy", "qty": 1.0, "filled_price": 100.0}),
            "HSBA.L",
            "ma_crossover",
        ),
    )
    conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, payload, symbol, strategy) VALUES (?, ?, ?, ?, ?)",
        (
            "2026-02-25T16:05:00Z",
            "PORTFOLIO",
            json.dumps({"sharpe": 1.1, "return_pct": 0.02, "max_drawdown_pct": 0.01}),
            "",
            "ma_crossover",
        ),
    )
    conn.commit()
    conn.close()


def test_api_endpoints_return_expected_shapes(tmp_path):
    db_path = str(tmp_path / "api_test.db")
    _seed_db(db_path)

    app = create_app(db_path)
    client = TestClient(app)

    status = client.get("/status")
    assert status.status_code == 200
    assert status.json()["kill_switch_active"] is True

    positions = client.get("/positions")
    assert positions.status_code == 200
    assert isinstance(positions.json(), list)

    signals = client.get("/signals?limit=5")
    assert signals.status_code == 200
    assert len(signals.json()) >= 1

    orders = client.get("/orders?limit=5")
    assert orders.status_code == 200
    assert len(orders.json()) >= 1

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["sharpe"] == 1.1
