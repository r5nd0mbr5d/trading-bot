"""Tests for async runtime hygiene checker."""

from pathlib import Path

from scripts.async_runtime_hygiene_check import run_checks


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_checker_flags_blocking_sleep_inside_async(tmp_path: Path) -> None:
    sample = tmp_path / "bad_async.py"
    _write(
        sample,
        "\n".join(
            [
                "import time",
                "",
                "async def run_task():",
                "    time.sleep(1)",
            ]
        ),
    )

    result = run_checks([sample])
    assert result["passed"] is False
    assert result["violation_count"] == 1
    violation = result["violations"][0]
    assert "time.sleep" in violation["code"]
    assert "asyncio.sleep" in violation["guidance"]


def test_checker_passes_clean_async_file(tmp_path: Path) -> None:
    sample = tmp_path / "good_async.py"
    _write(
        sample,
        "\n".join(
            [
                "import asyncio",
                "",
                "async def run_task():",
                "    await asyncio.sleep(0.01)",
            ]
        ),
    )

    result = run_checks([sample])
    assert result["passed"] is True
    assert result["violation_count"] == 0
    assert len(result["checklist"]) >= 3
