"""Lightweight LPDD consistency checker.

Checks for:
- required LPDD/session files existence
- `Last Updated` marker presence in key docs
- canonical queue summary line patterns in IMPLEMENTATION_BACKLOG.md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_FILES = [
    "PROJECT_DESIGN.md",
    "CLAUDE.md",
    "IMPLEMENTATION_BACKLOG.md",
    "SESSION_TOPOLOGY.md",
    "SESSION_LOG.md",
    ".github/copilot-instructions.md",
]

LAST_UPDATED_REQUIRED = [
    "PROJECT_DESIGN.md",
    "SESSION_TOPOLOGY.md",
    "DOCUMENTATION_INDEX.md",
    ".github/copilot-instructions.md",
]

BACKLOG_REQUIRED_PATTERNS = [
    r"\*\*Total Items\*\*:\s*\d+",
    r"\*\*Completed\*\*:\s*\d+",
    r"\*\*In Progress\*\*:\s*\d+",
    r"\*\*Not Started\*\*:\s*\d+",
    r"## Copilot Task Queue",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required_files(root: Path) -> list[str]:
    issues: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            issues.append(f"Missing required file: {relative}")
    return issues


def check_last_updated_markers(root: Path) -> list[str]:
    issues: list[str] = []
    for relative in LAST_UPDATED_REQUIRED:
        path = root / relative
        if not path.exists():
            continue
        text = _read_text(path)
        if "Last Updated:" not in text:
            issues.append(f"Missing 'Last Updated:' marker in {relative}")
    return issues


def check_backlog_patterns(root: Path) -> list[str]:
    issues: list[str] = []
    backlog = root / "IMPLEMENTATION_BACKLOG.md"
    if not backlog.exists():
        return ["Missing required file: IMPLEMENTATION_BACKLOG.md"]

    text = _read_text(backlog)
    for pattern in BACKLOG_REQUIRED_PATTERNS:
        if re.search(pattern, text) is None:
            issues.append(f"Backlog missing expected pattern: {pattern}")
    return issues


def run_checks(root: Path) -> dict[str, object]:
    issues: list[str] = []
    issues.extend(check_required_files(root))
    issues.extend(check_last_updated_markers(root))
    issues.extend(check_backlog_patterns(root))

    return {
        "passed": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LPDD consistency checks")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root path")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = run_checks(args.root)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
