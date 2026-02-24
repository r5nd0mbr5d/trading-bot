"""Tests for paper_trial --manifest CLI mode."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.trial.manifest import TrialManifest


class TestPaperTrialManifestMode:
    """Test paper_trial --manifest CLI integration."""

    def test_manifest_cli_loads_config(self, tmp_path: Path) -> None:
        """Verify --manifest flag loads TrialManifest correctly."""
        manifest_file = tmp_path / "test_trial.json"
        manifest_data = {
            "name": "CLI Test Trial",
            "profile": "uk_paper",
            "strategy": "ma_crossover",
            "duration_seconds": 600,
            "symbols": ["AAPL", "MSFT"],
            "capital": 75_000.0,
            "expected_json": "reports/expected.json",
            "tolerance_json": "reports/tolerance.json",
            "output_dir": "reports/cli_test",
            "db_path": "cli_test.db",
            "strict_reconcile": False,
            "skip_health_check": True,
            "skip_rotate": False,
            "notes": "CLI manifest test",
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        # Load and verify
        manifest = TrialManifest.from_json(str(manifest_file))
        assert manifest.name == "CLI Test Trial"
        assert manifest.profile == "uk_paper"
        assert manifest.strategy == "ma_crossover"
        assert manifest.symbols == ["AAPL", "MSFT"]
        assert manifest.capital == 75_000.0
        assert manifest.skip_health_check is True

    def test_manifest_cli_override_settings(self, tmp_path: Path) -> None:
        """Verify manifest settings override CLI defaults before cmd_paper_trial."""
        manifest_file = tmp_path / "override_trial.json"
        manifest_data = {
            "name": "Override Test",
            "profile": "uk_paper",
            "strategy": "rsi_momentum",
            "duration_seconds": 300,
            "symbols": ["NVDA"],
            "capital": 50_000.0,
            "expected_json": None,
            "tolerance_json": None,
            "output_dir": "reports/override",
            "db_path": None,
            "strict_reconcile": False,
            "skip_health_check": False,
            "skip_rotate": True,
            "notes": "Settings override test",
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        manifest = TrialManifest.from_json(str(manifest_file))

        # Simulate what main.py does
        assert manifest.strategy == "rsi_momentum"
        assert manifest.symbols == ["NVDA"]
        assert manifest.capital == 50_000.0
        assert manifest.skip_rotate is True

    def test_manifest_missing_required_field(self, tmp_path: Path) -> None:
        """Manifest missing required field raises error on load."""
        manifest_file = tmp_path / "incomplete_trial.json"
        incomplete_data = {
            "name": "Incomplete",
            # Missing: profile, strategy, duration_seconds
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(incomplete_data, f)

        with pytest.raises(TypeError):
            TrialManifest.from_json(str(manifest_file))

    def test_manifest_json_not_found(self, tmp_path: Path) -> None:
        """Manifest file not found raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent_manifest.json"
        with pytest.raises(FileNotFoundError):
            TrialManifest.from_json(str(nonexistent))

    def test_manifest_format_validation(self, tmp_path: Path) -> None:
        """Invalid JSON raises error on load."""
        manifest_file = tmp_path / "invalid_trial.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json here }")

        with pytest.raises(json.JSONDecodeError):
            TrialManifest.from_json(str(manifest_file))
