"""Pydantic schemas for read-only dashboard API responses."""

from __future__ import annotations

from pydantic import BaseModel


class StatusResponse(BaseModel):
    kill_switch_active: bool
    last_heartbeat: str | None
    active_strategy: str | None


class PositionResponse(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    current_price: float
    pnl: float


class SignalResponse(BaseModel):
    timestamp: str | None
    symbol: str | None
    strategy: str | None
    signal_type: str | None
    strength: float | None


class OrderResponse(BaseModel):
    timestamp: str | None
    symbol: str | None
    strategy: str | None
    side: str | None
    qty: float | None
    status: str


class MetricsResponse(BaseModel):
    sharpe: float
    return_pct: float
    max_drawdown_pct: float
