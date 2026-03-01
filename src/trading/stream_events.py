"""Stream event callback builders for paper/live trading loops."""

from __future__ import annotations

from typing import Callable

from src.risk.kill_switch import KillSwitch


def build_stream_heartbeat_handler(
    enqueue_audit: Callable[..., None],
    strategy_name: str,
) -> Callable[[dict], None]:
    """Create heartbeat callback for market data stream.

    Args:
        enqueue_audit: Audit enqueue callback.
        strategy_name: Strategy name for event context.

    Returns:
        Callback that records heartbeat events.
    """

    def on_stream_heartbeat(payload: dict) -> None:
        enqueue_audit(
            payload.get("event", "STREAM_HEARTBEAT"),
            payload,
            strategy=strategy_name,
            severity="info",
        )

    return on_stream_heartbeat


def build_stream_error_handler(
    enqueue_audit: Callable[..., None],
    strategy_name: str,
    kill_switch: KillSwitch,
) -> Callable[[dict], None]:
    """Create error callback for market data stream.

    Args:
        enqueue_audit: Audit enqueue callback.
        strategy_name: Strategy name for event context.
        kill_switch: Kill-switch used for terminal stream failures.

    Returns:
        Callback that records stream errors and triggers kill-switch
        on failure-limit events.
    """

    def on_stream_error(payload: dict) -> None:
        event = payload.get("event", "STREAM_ERROR")
        severity = "warning"
        if event == "STREAM_FAILURE_LIMIT_REACHED":
            severity = "critical"
            kill_switch.trigger(
                "stream_failure_limit_reached: " f"{payload.get('consecutive_failure_cycles')}"
            )
        enqueue_audit(
            event,
            payload,
            strategy=strategy_name,
            severity=severity,
        )

    return on_stream_error
