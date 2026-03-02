"""Tests for LPDD consistency checker utility."""

from pathlib import Path

from scripts.lpdd_consistency_check import run_checks


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_minimal_repo(root: Path) -> None:
    _write(root / "PROJECT_DESIGN.md", "# x\n\nLast Updated: Feb 25, 2026\n")
    _write(root / "CLAUDE.md", "# x\n")
    _write(root / "SESSION_TOPOLOGY.md", "# x\n\nLast Updated: Feb 25, 2026\n")
    _write(root / "SESSION_LOG.md", "# x\n")
    _write(root / "DOCUMENTATION_INDEX.md", "# x\n\nLast Updated: Feb 25, 2026\n")
    _write(root / ".github/copilot-instructions.md", "# x\n\nLast Updated: Feb 25, 2026\n")
    _write(
        root / "IMPLEMENTATION_BACKLOG.md",
        "\n".join(
            [
                "# x",
                "**Total Items**: 80",
                "**Completed**: 69",
                "**In Progress**: 1",
                "**Not Started**: 9",
                "## Copilot Task Queue",
            ]
        ),
    )


def test_run_checks_passes_with_minimal_valid_structure(tmp_path):
    _seed_minimal_repo(tmp_path)
    result = run_checks(tmp_path)
    assert result["passed"] is True
    assert result["issue_count"] == 0


def test_run_checks_flags_missing_required_file(tmp_path):
    _seed_minimal_repo(tmp_path)
    (tmp_path / "SESSION_LOG.md").unlink()
    result = run_checks(tmp_path)
    assert result["passed"] is False
    assert any("Missing required file: SESSION_LOG.md" in issue for issue in result["issues"])


def test_run_checks_flags_missing_last_updated_marker(tmp_path):
    _seed_minimal_repo(tmp_path)
    _write(tmp_path / "PROJECT_DESIGN.md", "# x\n")
    result = run_checks(tmp_path)
    assert result["passed"] is False
    assert any(
        "Missing 'Last Updated:' marker in PROJECT_DESIGN.md" in issue for issue in result["issues"]
    )


def test_run_checks_flags_missing_backlog_pattern(tmp_path):
    _seed_minimal_repo(tmp_path)
    _write(tmp_path / "IMPLEMENTATION_BACKLOG.md", "# x\n**Total Items**: 80\n")
    result = run_checks(tmp_path)
    assert result["passed"] is False
    assert any("Backlog missing expected pattern" in issue for issue in result["issues"])
