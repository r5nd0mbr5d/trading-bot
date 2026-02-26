"""Async runtime hygiene checker for integration paths.

Scans Python files for blocking patterns inside ``async def`` functions and
returns a deterministic report suitable for CI and operator review.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

BLOCKING_PATTERNS: dict[str, str] = {
    r"\btime\.sleep\(": "Replace with await asyncio.sleep(...)",
    r"\brequests\.": "Use aiohttp/httpx async client in async paths",
    r"\bsubprocess\.run\(": "Use asyncio.create_subprocess_exec(...) or move to sync path",
}


def _iter_async_blocks(lines: list[str]) -> Iterable[tuple[int, int]]:
    """Yield start/end line ranges for top-level async function bodies."""
    stack: list[tuple[int, int]] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("async def "):
            stack.append((idx, indent))
            continue
        if stack:
            _, async_indent = stack[-1]
            if stripped and not stripped.startswith("#") and indent <= async_indent:
                start, _ = stack.pop()
                yield (start, idx - 1)
    for start, _ in stack:
        yield (start, len(lines))


def scan_file(path: Path) -> list[dict[str, object]]:
    """Return blocking-pattern findings for one file."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    findings: list[dict[str, object]] = []
    for start, end in _iter_async_blocks(lines):
        for line_no in range(start, end + 1):
            line = lines[line_no - 1]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for pattern, guidance in BLOCKING_PATTERNS.items():
                if re.search(pattern, line):
                    findings.append(
                        {
                            "file": str(path).replace("\\", "/"),
                            "line": line_no,
                            "pattern": pattern,
                            "guidance": guidance,
                            "code": stripped,
                        }
                    )
    return findings


def run_checks(paths: list[Path]) -> dict[str, object]:
    """Run checks and return a JSON-serializable result."""
    findings: list[dict[str, object]] = []
    scanned_files: list[str] = []
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        scanned_files.append(str(path).replace("\\", "/"))
        findings.extend(scan_file(path))

    checklist = [
        "No blocking network or sleep calls inside async functions",
        "All async-path external IO uses async-capable clients",
        "Blocking subprocess execution avoided in async paths",
    ]

    return {
        "passed": len(findings) == 0,
        "violation_count": len(findings),
        "scanned_file_count": len(scanned_files),
        "scanned_files": scanned_files,
        "checklist": checklist,
        "violations": findings,
    }


def _default_paths(root: Path) -> list[Path]:
    return [
        root / "src" / "trading" / "loop.py",
        root / "src" / "cli" / "runtime.py",
        root / "src" / "execution" / "ibkr_broker.py",
    ]


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Async runtime hygiene checker")
    parser.add_argument("--root", default=".", help="Repository root path")
    parser.add_argument("paths", nargs="*", help="Optional explicit files to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.paths:
        paths = [Path(p).resolve() for p in args.paths]
    else:
        paths = _default_paths(root)

    result = run_checks(paths)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
