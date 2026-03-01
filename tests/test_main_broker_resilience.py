"""Unit tests for broker outage resilience helper logic in main runtime."""

import pytest

from config.settings import Settings
from src.execution.resilience import run_broker_operation
from src.risk.kill_switch import KillSwitch


def _event_collector(events):
    def _enqueue(event_type, payload, **kwargs):
        events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "kwargs": kwargs,
            }
        )

    return _enqueue


def test_broker_operation_retries_then_recovers(monkeypatch, tmp_path):
    settings = Settings()
    settings.broker.outage_retry_attempts = 3
    settings.broker.outage_backoff_base_seconds = 0.1
    settings.broker.outage_backoff_max_seconds = 1.0
    settings.broker.outage_backoff_jitter_seconds = 0.0
    settings.broker.outage_consecutive_failure_limit = 3

    sleeps = []
    monkeypatch.setattr(
        "src.execution.resilience.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    state = {"consecutive_failures": 2}
    events = []
    kill_switch = KillSwitch(str(tmp_path / "ks_recover.db"))

    call_counter = {"n": 0}

    def flaky_op():
        call_counter["n"] += 1
        if call_counter["n"] < 3:
            raise RuntimeError("transient outage")
        return {"ok": True}

    result = run_broker_operation(
        settings,
        "get_positions",
        flaky_op,
        retry_state=state,
        kill_switch=kill_switch,
        enqueue_audit=_event_collector(events),
        symbol="AAPL",
        strategy="ma_crossover",
    )

    assert result == {"ok": True}
    assert state["consecutive_failures"] == 0
    assert kill_switch.is_active() is False
    assert sleeps == [0.1, 0.2]

    transient = [e for e in events if e["event_type"] == "BROKER_TRANSIENT_ERROR"]
    recovered = [e for e in events if e["event_type"] == "BROKER_RECOVERED"]
    assert len(transient) == 2
    assert len(recovered) == 1


def test_broker_operation_terminal_failure_triggers_halt(tmp_path):
    settings = Settings()
    settings.broker.outage_retry_attempts = 2
    settings.broker.outage_backoff_base_seconds = 0.0
    settings.broker.outage_backoff_max_seconds = 0.0
    settings.broker.outage_backoff_jitter_seconds = 0.0
    settings.broker.outage_consecutive_failure_limit = 1

    state = {"consecutive_failures": 0}
    events = []
    kill_switch = KillSwitch(str(tmp_path / "ks_halt.db"))

    def always_fail():
        raise RuntimeError("broker down")

    with pytest.raises(RuntimeError, match="Broker operation failed"):
        run_broker_operation(
            settings,
            "submit_order",
            always_fail,
            retry_state=state,
            kill_switch=kill_switch,
            enqueue_audit=_event_collector(events),
            symbol="MSFT",
            strategy="ma_crossover",
        )

    assert state["consecutive_failures"] == 1
    assert kill_switch.is_active() is True
    terminal = [e for e in events if e["event_type"] == "BROKER_TERMINAL_ERROR"]
    halt = [e for e in events if e["event_type"] == "BROKER_CIRCUIT_BREAKER_HALT"]
    assert len(terminal) == 1
    assert len(halt) == 1


def test_broker_operation_halts_after_consecutive_failures(tmp_path):
    settings = Settings()
    settings.broker.outage_retry_attempts = 1
    settings.broker.outage_backoff_base_seconds = 0.0
    settings.broker.outage_backoff_jitter_seconds = 0.0
    settings.broker.outage_consecutive_failure_limit = 2

    state = {"consecutive_failures": 0}
    events = []
    kill_switch = KillSwitch(str(tmp_path / "ks_consecutive.db"))

    def fail_once_per_call():
        raise RuntimeError("still down")

    with pytest.raises(RuntimeError):
        run_broker_operation(
            settings,
            "get_cash",
            fail_once_per_call,
            retry_state=state,
            kill_switch=kill_switch,
            enqueue_audit=_event_collector(events),
        )

    assert state["consecutive_failures"] == 1
    assert kill_switch.is_active() is False

    with pytest.raises(RuntimeError):
        run_broker_operation(
            settings,
            "get_cash",
            fail_once_per_call,
            retry_state=state,
            kill_switch=kill_switch,
            enqueue_audit=_event_collector(events),
        )

    assert state["consecutive_failures"] == 2
    assert kill_switch.is_active() is True
