"""Tests for offline harness safety guards."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config.settings import Settings
from main import apply_runtime_profile, resolve_runtime_db_path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "offline_harness.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_requires_explicit_confirm_flag() -> None:
    result = _run([])
    assert result.returncode == 2
    assert "--confirm-harness is required" in result.stdout


def test_rejects_runtime_db_path_even_with_confirm() -> None:
    settings = Settings()
    apply_runtime_profile(settings, "uk_paper")
    runtime_paper_db = resolve_runtime_db_path(settings, "paper")

    result = _run(
        [
            "--confirm-harness",
            "--profile",
            "uk_paper",
            "--db-path",
            runtime_paper_db,
        ]
    )

    assert result.returncode == 2
    assert "Harness DB must be isolated from runtime DBs" in result.stdout
