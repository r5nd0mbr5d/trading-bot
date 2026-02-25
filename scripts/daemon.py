"""Portable paper-trading daemon wrapper for UK market hours."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class DaemonConfig:
    """Configuration for paper daemon runtime."""

    command: list[str]
    max_retries: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0
    sleep_outside_window_seconds: float = 60.0
    log_path: str = "logs/daemon.log"


class PaperDaemon:
    """Run paper trading process continuously during UK session window."""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self._logger = self._build_logger(config.log_path)

    @staticmethod
    def _build_logger(log_path: str) -> logging.Logger:
        logger = logging.getLogger("paper_daemon")
        logger.setLevel(logging.INFO)
        for existing_handler in list(logger.handlers):
            try:
                existing_handler.close()
            finally:
                logger.removeHandler(existing_handler)

        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)sZ %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    @staticmethod
    def is_in_market_window(now: datetime) -> bool:
        """Return True if timestamp is within Mon–Fri 08:00–16:00 UTC."""
        utc_now = now.astimezone(timezone.utc)
        if utc_now.weekday() >= 5:
            return False
        return 8 <= utc_now.hour < 16

    @staticmethod
    def seconds_until_next_open(now: datetime) -> float:
        """Compute seconds until next Mon–Fri 08:00 UTC market window."""
        utc_now = now.astimezone(timezone.utc)
        next_open = utc_now.replace(hour=8, minute=0, second=0, microsecond=0)
        if utc_now.weekday() >= 5:
            days_to_monday = 7 - utc_now.weekday()
            next_open = next_open + timedelta(days=days_to_monday)
        elif utc_now.hour >= 16:
            next_open = next_open + timedelta(days=1)
        elif utc_now.hour < 8:
            pass
        else:
            return 0.0

        while next_open.weekday() >= 5:
            next_open = next_open + timedelta(days=1)
        return max((next_open - utc_now).total_seconds(), 0.0)

    def _launch_paper_process(self) -> int:
        process = subprocess.Popen(self.config.command)
        return int(process.wait())

    def run_cycle(self) -> None:
        """Run one daemon cycle: wait for window, then run process with retries."""
        now = datetime.now(timezone.utc)
        if not self.is_in_market_window(now):
            sleep_seconds = max(
                self.seconds_until_next_open(now),
                float(self.config.sleep_outside_window_seconds),
            )
            self._logger.info("outside_market_window sleep_seconds=%s", round(sleep_seconds, 2))
            time.sleep(sleep_seconds)
            return

        retries = 0
        while retries <= self.config.max_retries:
            exit_code = self._launch_paper_process()
            if exit_code == 0:
                self._logger.info("paper_process_exit success exit_code=0")
                return

            retries += 1
            if retries > self.config.max_retries:
                self._logger.error(
                    "paper_process_exit failed retries_exhausted exit_code=%s", exit_code
                )
                return

            backoff = min(
                self.config.base_backoff_seconds * (2 ** (retries - 1)),
                self.config.max_backoff_seconds,
            )
            self._logger.warning(
                "paper_process_exit crash retry=%s backoff_seconds=%s exit_code=%s",
                retries,
                round(backoff, 2),
                exit_code,
            )
            time.sleep(backoff)

    def run_forever(self) -> None:
        """Run daemon indefinitely."""
        self._logger.info("paper_daemon_started")
        while True:
            self.run_cycle()


def main() -> None:
    """CLI entrypoint for paper daemon."""
    daemon = PaperDaemon(
        DaemonConfig(
            command=["python", "main.py", "paper", "--profile", "uk_paper", "--confirm-paper"],
        )
    )
    daemon.run_forever()


if __name__ == "__main__":
    main()
