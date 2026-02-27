"""Policy-oriented checks for Step1A lane and duration profile wiring."""

from pathlib import Path


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_step1a_burnin_has_objective_profile_parameter() -> None:
    script = _read_text("scripts/run_step1a_burnin.ps1")
    assert "RunObjectiveProfile" in script
    assert "smoke" in script
    assert "orchestration" in script
    assert "reconcile" in script
    assert "qualifying" in script


def test_step1a_burnin_writes_lane_fields() -> None:
    script = _read_text("scripts/run_step1a_burnin.ps1")
    assert "evidence_lane" in script
    assert "lane_reason" in script
    assert "run_objective_profile" in script


def test_step1a_burnin_enforces_short_duration_non_signoff() -> None:
    script = _read_text("scripts/run_step1a_burnin.ps1")
    assert "DurationSeconds -lt 1800" in script
    assert 'signoff_ready = ($sessionPassed -and $sessionLaneInfo.evidence_lane -eq "qualifying")' in script


def test_mo2_orchestrator_forces_qualifying_profile() -> None:
    script = _read_text("scripts/run_mo2_end_to_end.ps1")
    assert '"-RunObjectiveProfile", "qualifying"' in script
    assert "expected_evidence_lane = \"qualifying\"" in script
    assert "$effectiveExitCode" in script
