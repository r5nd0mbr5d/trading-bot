"""Tests for paper daemon scheduling and retry behavior."""

from datetime import datetime, timezone

from scripts.daemon import DaemonConfig, PaperDaemon


def _daemon(tmp_path):
    return PaperDaemon(
        DaemonConfig(
            command=["python", "main.py", "paper"],
            max_retries=3,
            base_backoff_seconds=1.0,
            max_backoff_seconds=8.0,
            sleep_outside_window_seconds=1.0,
            log_path=str(tmp_path / "daemon.log"),
        )
    )


def test_is_in_market_window_true_for_weekday_in_window(tmp_path):
    daemon = _daemon(tmp_path)
    now = datetime(2026, 2, 25, 9, 0, tzinfo=timezone.utc)

    assert daemon.is_in_market_window(now) is True


def test_is_in_market_window_false_for_weekend(tmp_path):
    daemon = _daemon(tmp_path)
    now = datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc)

    assert daemon.is_in_market_window(now) is False


def test_run_cycle_sleeps_outside_window(monkeypatch, tmp_path):
    daemon = _daemon(tmp_path)
    sleep_calls = []

    monkeypatch.setattr("scripts.daemon.datetime", type("_D", (), {
        "now": staticmethod(lambda _tz=None: datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc))
    }))
    monkeypatch.setattr("scripts.daemon.time.sleep", lambda seconds: sleep_calls.append(seconds))

    daemon.run_cycle()

    assert sleep_calls
    assert sleep_calls[0] >= 1.0


def test_run_cycle_retries_with_exponential_backoff(monkeypatch, tmp_path):
    daemon = _daemon(tmp_path)
    sleep_calls = []
    outcomes = iter([1, 1, 0])

    monkeypatch.setattr("scripts.daemon.datetime", type("_D", (), {
        "now": staticmethod(lambda _tz=None: datetime(2026, 2, 25, 9, 0, tzinfo=timezone.utc))
    }))
    monkeypatch.setattr("scripts.daemon.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(daemon, "_launch_paper_process", lambda: next(outcomes))

    daemon.run_cycle()

    assert sleep_calls == [1.0, 2.0]


def test_run_cycle_stops_after_max_retries(monkeypatch, tmp_path):
    daemon = _daemon(tmp_path)
    sleep_calls = []

    monkeypatch.setattr("scripts.daemon.datetime", type("_D", (), {
        "now": staticmethod(lambda _tz=None: datetime(2026, 2, 25, 9, 0, tzinfo=timezone.utc))
    }))
    monkeypatch.setattr("scripts.daemon.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(daemon, "_launch_paper_process", lambda: 1)

    daemon.run_cycle()

    assert sleep_calls == [1.0, 2.0, 4.0]
