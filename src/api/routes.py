"""Read-only API routes backed by SQLite audit tables."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter

from src.api.schemas import (
    MetricsResponse,
    OrderResponse,
    PositionResponse,
    SignalResponse,
    StatusResponse,
)


def _decode_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload:
        try:
            loaded = json.loads(payload)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            return {}
    return {}


def _fetch_rows(db_path: str, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        return cur.fetchall()


def _table_exists(db_path: str, table: str) -> bool:
    rows = _fetch_rows(
        db_path,
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    return bool(rows)


def create_router(db_path: str) -> APIRouter:
    """Create read-only API router bound to a database path."""
    router = APIRouter()

    @router.get("/status", response_model=StatusResponse)
    def get_status() -> StatusResponse:
        kill_switch_active = False
        if _table_exists(db_path, "kill_switch"):
            rows = _fetch_rows(db_path, "SELECT COUNT(*) AS count FROM kill_switch")
            kill_switch_active = int(rows[0]["count"]) > 0 if rows else False

        last_heartbeat = None
        active_strategy = None
        if _table_exists(db_path, "audit_log"):
            heartbeat_rows = _fetch_rows(
                db_path,
                "SELECT timestamp, strategy FROM audit_log WHERE event_type = ? "
                "ORDER BY id DESC LIMIT 1",
                ("STREAM_HEARTBEAT",),
            )
            if heartbeat_rows:
                row = heartbeat_rows[0]
                last_heartbeat = row["timestamp"] if "timestamp" in row.keys() else None
                active_strategy = row["strategy"] if "strategy" in row.keys() else None

        return StatusResponse(
            kill_switch_active=kill_switch_active,
            last_heartbeat=last_heartbeat,
            active_strategy=active_strategy,
        )

    @router.get("/positions", response_model=list[PositionResponse])
    def get_positions() -> list[PositionResponse]:
        if not _table_exists(db_path, "audit_log"):
            return []

        rows = _fetch_rows(
            db_path,
            "SELECT symbol, event_type, payload FROM audit_log "
            "WHERE event_type IN ('ORDER_FILLED','ORDER_NOT_FILLED') ORDER BY id ASC",
        )

        positions: dict[str, dict[str, float]] = {}
        for row in rows:
            symbol = row["symbol"] or ""
            payload = _decode_payload(row["payload"])
            side = str(payload.get("side", "")).lower()
            qty = float(payload.get("qty", 0.0) or 0.0)
            price = float(payload.get("filled_price", payload.get("price_reference", 0.0)) or 0.0)
            if not symbol or qty <= 0:
                continue

            state = positions.setdefault(
                symbol,
                {"qty": 0.0, "avg_price": 0.0, "current_price": price},
            )

            if side == "buy":
                new_qty = state["qty"] + qty
                if new_qty > 0:
                    state["avg_price"] = (
                        (state["qty"] * state["avg_price"]) + (qty * price)
                    ) / new_qty
                    state["qty"] = new_qty
            elif side == "sell":
                state["qty"] = max(0.0, state["qty"] - qty)

            if price > 0:
                state["current_price"] = price

        output: list[PositionResponse] = []
        for symbol, state in positions.items():
            if state["qty"] <= 0:
                continue
            pnl = (state["current_price"] - state["avg_price"]) * state["qty"]
            output.append(
                PositionResponse(
                    symbol=symbol,
                    qty=state["qty"],
                    avg_price=state["avg_price"],
                    current_price=state["current_price"],
                    pnl=pnl,
                )
            )
        return output

    @router.get("/signals", response_model=list[SignalResponse])
    def get_signals(limit: int = 20) -> list[SignalResponse]:
        if not _table_exists(db_path, "audit_log"):
            return []
        rows = _fetch_rows(
            db_path,
            "SELECT timestamp, symbol, strategy, payload FROM audit_log "
            "WHERE event_type = ? ORDER BY id DESC LIMIT ?",
            ("SIGNAL", int(limit)),
        )
        return [
            SignalResponse(
                timestamp=row["timestamp"],
                symbol=row["symbol"],
                strategy=row["strategy"],
                signal_type=_decode_payload(row["payload"]).get("type"),
                strength=_decode_payload(row["payload"]).get("strength"),
            )
            for row in rows
        ]

    @router.get("/orders", response_model=list[OrderResponse])
    def get_orders(limit: int = 20) -> list[OrderResponse]:
        if not _table_exists(db_path, "audit_log"):
            return []
        rows = _fetch_rows(
            db_path,
            "SELECT timestamp, symbol, strategy, event_type, payload FROM audit_log "
            "WHERE event_type IN ('ORDER_SUBMITTED','ORDER_FILLED','ORDER_NOT_FILLED') "
            "ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        results: list[OrderResponse] = []
        for row in rows:
            payload = _decode_payload(row["payload"])
            event_type = row["event_type"]
            status = {
                "ORDER_SUBMITTED": "submitted",
                "ORDER_FILLED": "filled",
                "ORDER_NOT_FILLED": "not_filled",
            }.get(event_type, "unknown")
            results.append(
                OrderResponse(
                    timestamp=row["timestamp"],
                    symbol=row["symbol"],
                    strategy=row["strategy"],
                    side=payload.get("side"),
                    qty=payload.get("qty"),
                    status=status,
                )
            )
        return results

    @router.get("/metrics", response_model=MetricsResponse)
    def get_metrics() -> MetricsResponse:
        if not _table_exists(db_path, "audit_log"):
            return MetricsResponse(sharpe=0.0, return_pct=0.0, max_drawdown_pct=0.0)

        rows = _fetch_rows(
            db_path,
            "SELECT payload FROM audit_log WHERE event_type = ? ORDER BY id DESC LIMIT 1",
            ("PORTFOLIO",),
        )
        if not rows:
            return MetricsResponse(sharpe=0.0, return_pct=0.0, max_drawdown_pct=0.0)

        payload = _decode_payload(rows[0]["payload"])
        return MetricsResponse(
            sharpe=float(payload.get("sharpe", 0.0) or 0.0),
            return_pct=float(payload.get("return_pct", 0.0) or 0.0),
            max_drawdown_pct=float(payload.get("max_drawdown_pct", 0.0) or 0.0),
        )

    return router
