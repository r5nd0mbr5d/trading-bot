"""Tests for research-to-runtime strategy bridge (R3)."""

import pytest

from research.bridge.strategy_bridge import register_candidate_strategy
from src.strategies.registry import StrategyRegistry


def _candidate(strategy_type: str = "rule"):
    return {
        "name": "uk_xgb_alpha",
        "version": "0.1.0",
        "strategy_type": strategy_type,
        "parameters": {"horizon": 5, "threshold": 0.55},
        "experiment_id": "xgb_h5_v1",
        "artifact_sha256": "abc123",
    }


def test_valid_candidate_registers_as_experimental(tmp_path):
    registry = StrategyRegistry(
        db_path=str(tmp_path / "registry.db"),
        artifacts_dir=str(tmp_path / "strategies"),
    )
    strategy_id = register_candidate_strategy(registry, _candidate("rule"))

    row = registry.load("uk_xgb_alpha", "0.1.0")
    assert strategy_id == "uk_xgb_alpha:0.1.0"
    assert row["metadata"]["status"] == "experimental"


def test_invalid_candidate_is_rejected(tmp_path):
    registry = StrategyRegistry(
        db_path=str(tmp_path / "registry.db"),
        artifacts_dir=str(tmp_path / "strategies"),
    )
    bad = {"name": "missing_fields"}

    with pytest.raises(ValueError, match="missing required fields"):
        register_candidate_strategy(registry, bad)


def test_nn_candidate_requires_weights(tmp_path):
    registry = StrategyRegistry(
        db_path=str(tmp_path / "registry.db"),
        artifacts_dir=str(tmp_path / "strategies"),
    )
    with pytest.raises(ValueError, match="requires weights"):
        register_candidate_strategy(registry, _candidate("nn"))
