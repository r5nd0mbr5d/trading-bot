"""Tests for minimal report schema compatibility adapter."""

import json
from pathlib import Path

from src.reporting.report_schema_adapter import ReportSchemaAdapter


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_list_resources_contains_expected_names(tmp_path: Path) -> None:
    adapter = ReportSchemaAdapter(tmp_path)
    resources = adapter.list_resources()
    assert resources == ["mo2_latest", "paper_session_summary", "step1a_latest"]


def test_get_resource_returns_missing_contract_when_absent(tmp_path: Path) -> None:
    adapter = ReportSchemaAdapter(tmp_path)
    result = adapter.get_resource("step1a_latest")
    assert result["ok"] is False
    assert result["error"] == "report_file_missing"


def test_get_resource_returns_normalized_payload(tmp_path: Path) -> None:
    step1a_path = tmp_path / "reports" / "uk_tax" / "step1a_burnin" / "step1a_burnin_latest.json"
    _write_json(
        step1a_path,
        {
            "generated_at_utc": "2026-02-26T00:00:00Z",
            "profile": "uk_paper",
            "run_objective_profile": "qualifying",
            "evidence_lane": "qualifying",
            "session_passed": True,
            "signoff_ready": True,
            "runs_completed": 3,
            "runs_passed": 3,
            "extra": "ignored",
        },
    )

    adapter = ReportSchemaAdapter(tmp_path)
    result = adapter.get_resource("step1a_latest")
    assert result["ok"] is True
    assert result["schema_version"] == "compat.v1"
    assert result["payload"]["profile"] == "uk_paper"
    assert result["payload"]["run_objective_profile"] == "qualifying"
    assert result["payload"]["evidence_lane"] == "qualifying"
    assert "extra" not in result["payload"]
