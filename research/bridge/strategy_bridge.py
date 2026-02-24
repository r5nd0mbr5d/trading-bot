"""Candidate-to-runtime strategy bridge helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.strategies.registry import StrategyRegistry


REQUIRED_CANDIDATE_FIELDS = {
    "name",
    "version",
    "strategy_type",
    "parameters",
    "experiment_id",
    "artifact_sha256",
}


def validate_candidate_metadata(candidate: Dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_CANDIDATE_FIELDS if field not in candidate]
    if missing:
        raise ValueError(f"Candidate metadata missing required fields: {', '.join(sorted(missing))}")

    strategy_type = str(candidate.get("strategy_type", "")).strip().lower()
    if strategy_type not in {"rule", "nn"}:
        raise ValueError("strategy_type must be 'rule' or 'nn'")


def load_candidate_bundle(candidate_dir: str) -> Dict[str, Any]:
    root = Path(candidate_dir)
    metadata_path = root / "candidate.json"
    if not metadata_path.exists():
        raise ValueError(f"Missing candidate metadata: {metadata_path}")

    candidate = json.loads(metadata_path.read_text(encoding="utf-8"))
    validate_candidate_metadata(candidate)
    return candidate


def register_candidate_strategy(
    registry: "StrategyRegistry",
    candidate: Dict[str, Any],
    weights: Optional[bytes] = None,
) -> str:
    """Register candidate in runtime registry with experimental status."""
    validate_candidate_metadata(candidate)

    strategy_type = str(candidate["strategy_type"]).strip().lower()
    if strategy_type == "nn" and weights is None:
        raise ValueError("NN candidate registration requires weights bytes")

    return registry.save(
        name=str(candidate["name"]),
        version=str(candidate["version"]),
        strategy_type=strategy_type,
        parameters=dict(candidate["parameters"]),
        status="experimental",
        weights=weights,
    )
