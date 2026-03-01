"""Broker resilience layer — retry/backoff/circuit-breaker for fault tolerance.

Provides bounded retry logic with exponential backoff and jitter for transient
broker outages, with explicit circuit-breaker handoff to kill-switch on repeated
failures.
"""

import random
import time
from typing import Any, Callable

from config.settings import Settings
from src.risk.kill_switch import KillSwitch


def run_broker_operation(
    settings: Settings,
    operation_name: str,
    operation: Callable[[], Any],
    *,
    retry_state: dict[str, int],
    kill_switch: KillSwitch,
    enqueue_audit: Callable[..., None],
    symbol: str | None = None,
    strategy: str | None = None,
) -> Any:
    """Execute a broker operation with retry/backoff/circuit-breaker resilience.

    Args:
        settings: Application settings (broker outage configuration).
        operation_name: Human-readable name for audit logging (e.g., "submit_order").
        operation: Callable that performs the broker operation; raises on failure.
        retry_state: Mutable dict tracking consecutive_failures counter (shared across calls).
        kill_switch: KillSwitch instance to trigger on repeated broker failures.
        enqueue_audit: Callable to log audit events (BROKER_TRANSIENT_ERROR, etc.).
        symbol: Optional symbol for audit context (e.g., "AAPL").
        strategy: Optional strategy name for audit context.

    Returns:
        Result of operation() if successful.

    Raises:
        RuntimeError: After all retry attempts exhausted or circuit-breaker triggered.

    Resilience Behavior:
    - Retries: Configurable via settings.broker.outage_retry_attempts (default: 3)
    - Backoff: Exponential with base and max delays, jitter for randomization
    - Circuit-breaker: Triggers kill-switch when consecutive failures ≥ limit
    - Audit: Logs BROKER_TRANSIENT_ERROR, BROKER_RECOVERED, BROKER_TERMINAL_ERROR,
             BROKER_CIRCUIT_BREAKER_HALT events
    """
    attempts = max(int(getattr(settings.broker, "outage_retry_attempts", 3) or 1), 1)
    if bool(getattr(settings.broker, "outage_skip_retries", False)):
        attempts = 1
    base_delay = max(
        float(getattr(settings.broker, "outage_backoff_base_seconds", 0.25) or 0.0), 0.0
    )
    max_delay = max(float(getattr(settings.broker, "outage_backoff_max_seconds", 2.0) or 0.0), 0.0)
    jitter = max(float(getattr(settings.broker, "outage_backoff_jitter_seconds", 0.1) or 0.0), 0.0)
    failure_limit = max(
        int(getattr(settings.broker, "outage_consecutive_failure_limit", 3) or 1), 1
    )

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = operation()
            if attempt > 1:
                enqueue_audit(
                    "BROKER_RECOVERED",
                    {
                        "operation": operation_name,
                        "attempt": attempt,
                    },
                    symbol=symbol,
                    strategy=strategy,
                    severity="warning",
                )
            retry_state["consecutive_failures"] = 0
            return result
        except Exception as exc:
            last_exc = exc
            should_retry = attempt < attempts
            delay = 0.0
            if should_retry and base_delay > 0:
                delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                if jitter > 0:
                    delay += random.uniform(0.0, jitter)
                delay = max(delay, 0.0)

            enqueue_audit(
                "BROKER_TRANSIENT_ERROR" if should_retry else "BROKER_TERMINAL_ERROR",
                {
                    "operation": operation_name,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "retry_in_seconds": round(delay, 6),
                    "error": str(exc),
                },
                symbol=symbol,
                strategy=strategy,
                severity="error",
            )

            if should_retry and delay > 0:
                time.sleep(delay)

    retry_state["consecutive_failures"] = retry_state.get("consecutive_failures", 0) + 1
    consecutive_failures = retry_state["consecutive_failures"]
    if consecutive_failures >= failure_limit:
        reason = (
            f"broker_outage_resilience: operation={operation_name}, "
            f"consecutive_failures={consecutive_failures}, limit={failure_limit}"
        )
        kill_switch.trigger(reason)
        enqueue_audit(
            "BROKER_CIRCUIT_BREAKER_HALT",
            {
                "operation": operation_name,
                "consecutive_failures": consecutive_failures,
                "failure_limit": failure_limit,
                "last_error": str(last_exc) if last_exc else "unknown",
            },
            symbol=symbol,
            strategy=strategy,
            severity="critical",
        )

    raise RuntimeError(
        f"Broker operation failed after {attempts} attempt(s): {operation_name}: {last_exc}"
    )
