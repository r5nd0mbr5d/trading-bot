"""Contract checks for Step1A handshake diagnostics payload fields."""

from pathlib import Path


def test_step1a_report_includes_handshake_diagnostics_fields() -> None:
    script = Path("scripts/run_step1a_burnin.ps1").read_text(encoding="utf-8")

    assert "handshake_diagnostics" in script
    assert "hint_bucket" in script
    assert "rejection_signature_hints" in script
    assert "endpoint_profile_tag" in script


def test_step1a_hint_bucket_labels_present() -> None:
    script = Path("scripts/run_step1a_burnin.ps1").read_text(encoding="utf-8")

    assert '"collision"' in script
    assert '"event_loop"' in script
    assert '"network_or_endpoint"' in script
    assert '"account_policy"' in script
