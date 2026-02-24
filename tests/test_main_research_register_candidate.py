"""Tests for research candidate registration command wrapper."""

import hashlib
import json

import pytest

from config.settings import Settings
from main import cmd_research_register_candidate
from src.strategies.registry import StrategyRegistry


def _write_candidate(path, payload):
    path.mkdir(parents=True, exist_ok=True)
    (path / "candidate.json").write_text(json.dumps(payload), encoding="utf-8")


def test_cmd_research_register_candidate_rule_strategy(tmp_path):
    settings = Settings()
    candidate_dir = tmp_path / "candidate_rule"
    _write_candidate(
        candidate_dir,
        {
            "name": "uk_rule_alpha",
            "version": "0.1.0",
            "strategy_type": "rule",
            "parameters": {"threshold": 0.55},
            "experiment_id": "rule_exp_001",
            "artifact_sha256": "not_applicable_for_rule",
        },
    )

    output_dir = tmp_path / "reports"
    db_path = str(tmp_path / "trading.db")
    artifacts_dir = str(tmp_path / "strategies")

    result = cmd_research_register_candidate(
        settings,
        candidate_dir=str(candidate_dir),
        output_dir=str(output_dir),
        registry_db_path=db_path,
        artifacts_dir=artifacts_dir,
        reviewer_1="dev1",
        reviewer_2="dev2",
    )

    gate_path = output_dir / "integration_gate.json"
    assert gate_path.exists()
    gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate_payload["stage"] == "R2"
    assert gate_payload["decision"] == "PASS"
    assert gate_payload["strategy_registry_id"] == "uk_rule_alpha:0.1.0"
    assert gate_payload["registry_status"] == "experimental"
    assert result["strategy_id"] == "uk_rule_alpha:0.1.0"

    registry = StrategyRegistry(db_path=db_path, artifacts_dir=artifacts_dir)
    loaded = registry.load("uk_rule_alpha", "0.1.0")
    assert loaded["metadata"]["status"] == "experimental"


def test_cmd_research_register_candidate_nn_requires_model_weights(tmp_path):
    settings = Settings()
    candidate_dir = tmp_path / "candidate_nn"
    _write_candidate(
        candidate_dir,
        {
            "name": "uk_nn_alpha",
            "version": "0.1.0",
            "strategy_type": "nn",
            "parameters": {"layers": [16, 8]},
            "experiment_id": "nn_exp_001",
            "artifact_sha256": "deadbeef",
        },
    )

    with pytest.raises(ValueError, match="requires model.pt"):
        cmd_research_register_candidate(
            settings,
            candidate_dir=str(candidate_dir),
            output_dir=str(tmp_path / "reports"),
            registry_db_path=str(tmp_path / "trading.db"),
            artifacts_dir=str(tmp_path / "strategies"),
        )


def test_cmd_research_register_candidate_nn_sha_verified(tmp_path):
    settings = Settings()
    candidate_dir = tmp_path / "candidate_nn_ok"
    model_bytes = b"fake-model-weights"
    sha = hashlib.sha256(model_bytes).hexdigest()
    _write_candidate(
        candidate_dir,
        {
            "name": "uk_nn_alpha_ok",
            "version": "0.1.0",
            "strategy_type": "nn",
            "parameters": {"layers": [32, 16]},
            "experiment_id": "nn_exp_002",
            "artifact_sha256": sha,
        },
    )
    (candidate_dir / "model.pt").write_bytes(model_bytes)

    result = cmd_research_register_candidate(
        settings,
        candidate_dir=str(candidate_dir),
        output_dir=str(tmp_path / "reports"),
        registry_db_path=str(tmp_path / "trading.db"),
        artifacts_dir=str(tmp_path / "strategies"),
    )

    assert result["sha256_verified"] is True
