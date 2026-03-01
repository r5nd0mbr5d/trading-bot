"""Tests for trial manifest loading and management."""

import json
from pathlib import Path

from src.trial.manifest import TrialBatch, TrialManifest


class TestTrialManifest:
    """Manifest load/save tests."""

    def test_manifest_from_json(self, tmp_path: Path) -> None:
        """Load manifest from JSON file."""
        manifest_file = tmp_path / "manifest.json"
        data = {
            "name": "Test Trial",
            "profile": "uk_paper",
            "strategy": "ma_crossover",
            "duration_seconds": 900,
            "symbols": ["AAPL", "MSFT"],
            "capital": 50_000.0,
            "expected_json": "expected.json",
            "tolerance_json": "tolerance.json",
            "output_dir": "reports/test",
            "db_path": "test.db",
            "strict_reconcile": True,
            "skip_health_check": False,
            "skip_rotate": False,
            "notes": "Test manifest",
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        manifest = TrialManifest.from_json(str(manifest_file))
        assert manifest.name == "Test Trial"
        assert manifest.profile == "uk_paper"
        assert manifest.strategy == "ma_crossover"
        assert manifest.duration_seconds == 900
        assert manifest.symbols == ["AAPL", "MSFT"]
        assert manifest.capital == 50_000.0
        assert manifest.strict_reconcile is True
        assert manifest.skip_rotate is False

    def test_manifest_to_json(self, tmp_path: Path) -> None:
        """Save manifest to JSON file."""
        manifest = TrialManifest(
            name="Test Trial",
            profile="uk_paper",
            strategy="ma_crossover",
            duration_seconds=1800,
            symbols=["NVDA"],
            capital=75_000.0,
            expected_json="exp.json",
            tolerance_json="tol.json",
            output_dir="reports/out",
            db_path="custom.db",
            strict_reconcile=False,
            skip_health_check=True,
            skip_rotate=False,
            notes="Saved manifest",
        )

        output_path = tmp_path / "saved_manifest.json"
        manifest.to_json(str(output_path))

        assert output_path.exists()
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["name"] == "Test Trial"
        assert data["duration_seconds"] == 1800
        assert data["symbols"] == ["NVDA"]
        assert data["skip_health_check"] is True
        assert data["notes"] == "Saved manifest"

    def test_manifest_defaults(self) -> None:
        """Manifest with minimal fields uses defaults."""
        manifest = TrialManifest(
            name="Minimal",
            profile="uk_paper",
            strategy="rsi_momentum",
            duration_seconds=600,
        )

        assert manifest.symbols is None
        assert manifest.capital == 100_000.0
        assert manifest.output_dir == "reports/reconcile"
        assert manifest.db_path is None
        assert manifest.strict_reconcile is False
        assert manifest.skip_health_check is False
        assert manifest.skip_rotate is False

    def test_manifest_roundtrip(self, tmp_path: Path) -> None:
        """Save and load manifest with full fidelity."""
        original = TrialManifest(
            name="Roundtrip Test",
            profile="uk_paper",
            strategy="bollinger_bands",
            duration_seconds=2400,
            symbols=["AAPL", "MSFT", "NVDA"],
            capital=200_000.0,
            expected_json="reports/expected.json",
            tolerance_json="reports/tolerance.json",
            output_dir="reports/roundtrip",
            db_path="roundtrip.db",
            strict_reconcile=True,
            skip_health_check=False,
            skip_rotate=True,
            notes="Full roundtrip test",
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "roundtrip.json"
        original.to_json(str(manifest_path))

        loaded = TrialManifest.from_json(str(manifest_path))
        assert loaded.name == original.name
        assert loaded.duration_seconds == original.duration_seconds
        assert loaded.symbols == original.symbols
        assert loaded.strict_reconcile == original.strict_reconcile
        assert loaded.skip_rotate == original.skip_rotate
        assert loaded.notes == original.notes


class TestTrialBatch:
    """Trial batch config load/save tests."""

    def test_trial_batch_roundtrip(self, tmp_path: Path) -> None:
        batch = TrialBatch(
            manifests=["configs/trial_a.json", "configs/trial_b.json"],
            output_dir="reports/batch",
            parallel=True,
        )

        out_path = tmp_path / "trial_batch.json"
        batch.to_json(str(out_path))

        loaded = TrialBatch.from_json(str(out_path))
        assert loaded.manifests == batch.manifests
        assert loaded.output_dir == batch.output_dir
        assert loaded.parallel is True
