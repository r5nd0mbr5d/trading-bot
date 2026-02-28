"""Pipeline event hook emitters for PAIOS integration.

Each ``make_*_event`` function produces a PAIOS-compatible event payload
dict that can be forwarded to an orchestrator, logged to the audit trail,
or consumed by downstream bridge consumers.

All events include a UTC ISO-8601 timestamp in the ``timestamp`` field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.bridge.paios_types import HandoffPacket


def make_bar_received_event(symbol: str, bar_data: dict[str, Any]) -> dict[str, Any]:
    """Build a ``bar.received`` event payload.

    Parameters
    ----------
    symbol : str
        Ticker symbol the bar belongs to.
    bar_data : dict[str, Any]
        Raw bar fields (open, high, low, close, volume, timestamp, …).

    Returns
    -------
    dict[str, Any]
        PAIOS-compatible event dict with ``event``, ``timestamp``,
        ``symbol``, and ``data`` keys.
    """
    return {
        "event": "bar.received",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "data": bar_data,
    }


def make_signal_generated_event(
    symbol: str, signal: str, confidence: float
) -> dict[str, Any]:
    """Build a ``signal.generated`` event payload.

    Parameters
    ----------
    symbol : str
        Ticker symbol the signal was generated for.
    signal : str
        Signal direction string (e.g. ``"buy"``, ``"sell"``, ``"hold"``).
    confidence : float
        Model or strategy confidence score in ``[0.0, 1.0]``.

    Returns
    -------
    dict[str, Any]
        PAIOS-compatible event dict.
    """
    return {
        "event": "signal.generated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
    }


def make_order_submitted_event(
    order_id: str, symbol: str, side: str, qty: float
) -> dict[str, Any]:
    """Build an ``order.submitted`` event payload.

    Parameters
    ----------
    order_id : str
        Broker-assigned or internally generated order identifier.
    symbol : str
        Ticker symbol the order is for.
    side : str
        Order side string (e.g. ``"buy"`` or ``"sell"``).
    qty : float
        Quantity of shares/contracts submitted.

    Returns
    -------
    dict[str, Any]
        PAIOS-compatible event dict.
    """
    return {
        "event": "order.submitted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
    }


def make_handoff_event(packet: HandoffPacket) -> dict[str, Any]:
    """Build a ``session.handoff`` event payload from a ``HandoffPacket``.

    Parameters
    ----------
    packet : HandoffPacket
        The structured handoff describing source/target session types and
        context files.

    Returns
    -------
    dict[str, Any]
        PAIOS-compatible event dict containing the serialized packet.
    """
    return {
        "event": "session.handoff",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "packet": packet.to_dict(),
    }
