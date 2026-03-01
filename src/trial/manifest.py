"""Trial manifest configuration — reusable paper trial settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TrialManifest:
    """Encapsulates all settings needed for a paper_trial run."""

    name: str
    profile: str
    strategy: str
    duration_seconds: int
    symbols: Optional[list[str]] = None
    capital: float = 100_000.0
    expected_json: Optional[str] = None
    tolerance_json: Optional[str] = None
    output_dir: str = "reports/reconcile"
    db_path: Optional[str] = None
    strict_reconcile: bool = False
    skip_health_check: bool = False
    skip_rotate: bool = False
    notes: Optional[str] = None

    @staticmethod
    def from_json(json_path: str) -> TrialManifest:
        """Load manifest from JSON file."""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return TrialManifest(**data)

    def to_json(self, output_path: str) -> None:
        """Save manifest to JSON file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": self.name,
                    "profile": self.profile,
                    "strategy": self.strategy,
                    "duration_seconds": self.duration_seconds,
                    "symbols": self.symbols,
                    "capital": self.capital,
                    "expected_json": self.expected_json,
                    "tolerance_json": self.tolerance_json,
                    "output_dir": self.output_dir,
                    "db_path": self.db_path,
                    "strict_reconcile": self.strict_reconcile,
                    "skip_health_check": self.skip_health_check,
                    "skip_rotate": self.skip_rotate,
                    "notes": self.notes,
                },
                f,
                indent=2,
            )


@dataclass
class TrialBatch:
    """Batch configuration for running multiple trial manifests."""

    manifests: list[str]
    output_dir: str = "reports/batch"
    parallel: bool = False

    @staticmethod
    def from_json(json_path: str) -> "TrialBatch":
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return TrialBatch(**data)

    def to_json(self, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "manifests": self.manifests,
                    "output_dir": self.output_dir,
                    "parallel": self.parallel,
                },
                f,
                indent=2,
            )
