"""Read-only adapter exposing normalized resources from report files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportSchemaAdapter:
    """Expose minimal read-only resources from existing report artifacts."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self._root = Path(repo_root)
        self._resource_paths = {
            "step1a_latest": self._root / "reports" / "uk_tax" / "step1a_burnin" / "step1a_burnin_latest.json",
            "paper_session_summary": self._root / "reports" / "session" / "paper_session_summary.json",
            "mo2_latest": self._root / "reports" / "uk_tax" / "mo2_orchestrator" / "latest.json",
        }

    def list_resources(self) -> list[str]:
        """Return supported read-only resource names."""
        return sorted(self._resource_paths.keys())

    def get_resource(self, resource_name: str) -> dict[str, Any]:
        """Return normalized payload for a named report resource."""
        if resource_name not in self._resource_paths:
            raise KeyError(f"Unsupported resource: {resource_name}")

        path = self._resource_paths[resource_name]
        if not path.exists():
            return {
                "schema_version": "compat.v1",
                "resource": resource_name,
                "ok": False,
                "source_path": str(path).replace("\\", "/"),
                "error": "report_file_missing",
                "payload": {},
            }

        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "schema_version": "compat.v1",
            "resource": resource_name,
            "ok": True,
            "source_path": str(path).replace("\\", "/"),
            "payload": self._normalize_payload(resource_name, payload),
        }

    def _normalize_payload(self, resource_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if resource_name == "step1a_latest":
            return {
                "generated_at_utc": payload.get("generated_at_utc"),
                "profile": payload.get("profile"),
                "session_passed": payload.get("session_passed"),
                "signoff_ready": payload.get("signoff_ready"),
                "runs_completed": payload.get("runs_completed"),
                "runs_passed": payload.get("runs_passed"),
            }

        if resource_name == "paper_session_summary":
            return {
                "fill_rate": payload.get("fill_rate"),
                "win_rate": payload.get("win_rate"),
                "profit_factor": payload.get("profit_factor"),
                "realized_pnl": payload.get("realized_pnl"),
                "drift_flag_count": payload.get("drift_flag_count"),
            }

        return {
            "generated_at_utc": payload.get("generated_at_utc"),
            "profile": payload.get("profile"),
            "passed": payload.get("execution", {}).get("passed"),
            "exit_code": payload.get("execution", {}).get("exit_code"),
            "latest_burnin_report": payload.get("execution", {}).get("latest_burnin_report"),
        }
