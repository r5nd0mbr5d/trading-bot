"""Unit tests for StrategyRegistry."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.strategies.registry import StrategyRegistry


@pytest.fixture
def reg(tmp_path):
    return StrategyRegistry(
        db_path=str(tmp_path / "registry.db"),
        artifacts_dir=str(tmp_path / "strategies"),
    )


def _write_checklist(reg, strategy, decision="READY", failures=None):
    failures = failures or []
    overall_ready = decision == "READY"
    payload = {
        "checklist_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "base_currency": "GBP",
        "summary_json_path": None,
        "pre_paper_checks": [
            {
                "id": "tests_all_pass",
                "label": "All test suites pass",
                "required": True,
                "status": "pass" if overall_ready else "pending",
                "evidence": "pytest",
            }
        ],
        "in_paper_checks": [
            {
                "id": "paper_readiness_metrics",
                "label": "Paper readiness threshold checks",
                "required": True,
                "status": "pass" if overall_ready else "fail",
                "evidence": failures,
            }
        ],
        "exit_criteria": [
            {
                "id": "manual_review_signoff",
                "label": "Manual review and sign-off recorded",
                "required": True,
                "status": "pass" if overall_ready else "pending",
                "evidence": "decision rubric",
            }
        ],
        "paper_readiness_failures": failures,
        "overall_ready": overall_ready,
        "decision": decision,
    }
    path = Path(reg._db_path).parent / f"{strategy}_checklist.json"
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return str(path)


class TestStrategyRegistry:

    # ------------------------------------------------------------------
    # save / load round-trip
    # ------------------------------------------------------------------

    def test_save_and_load_rule_strategy(self, reg):
        reg.save("bollinger", "1.0.0", "rule", {"period": 20, "std": 2.0})
        result = reg.load("bollinger", "1.0.0")
        assert result["metadata"]["name"] == "bollinger"
        assert result["metadata"]["version"] == "1.0.0"
        assert result["metadata"]["type"] == "rule"
        assert result["metadata"]["parameters"]["period"] == 20
        assert result["weights"] is None

    def test_save_and_load_nn_strategy(self, reg):
        fake_weights = b"\x00\x01\x02\x03fake_model_bytes"
        reg.save("cnn_model", "2.0.0", "nn", {"layers": 3}, weights=fake_weights)
        result = reg.load("cnn_model", "2.0.0")
        assert result["weights"] == fake_weights
        assert result["metadata"]["artifact_sha256"] is not None

    def test_load_returns_correct_parameters(self, reg):
        params = {"fast": 10, "slow": 50, "threshold": 0.55}
        reg.save("ma_cross", "1.1.0", "rule", params)
        result = reg.load("ma_cross", "1.1.0")
        assert result["metadata"]["parameters"] == params

    def test_save_returns_strategy_id(self, reg):
        sid = reg.save("rsi", "0.9.0", "rule", {})
        assert sid == "rsi:0.9.0"

    # ------------------------------------------------------------------
    # Hash verification
    # ------------------------------------------------------------------

    def test_hash_mismatch_raises(self, reg, tmp_path):
        weights = b"original_weights"
        reg.save("cnn", "1.0.0", "nn", {}, weights=weights)
        # Tamper with the artifact file on disk
        artifact_path = tmp_path / "strategies" / "cnn" / "1.0.0" / "model.pt"
        artifact_path.write_bytes(b"tampered_weights")
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            reg.load("cnn", "1.0.0")

    def test_missing_artifact_raises(self, reg, tmp_path):
        weights = b"some_weights"
        reg.save("cnn2", "1.0.0", "nn", {}, weights=weights)
        # Delete the artifact
        artifact_path = tmp_path / "strategies" / "cnn2" / "1.0.0" / "model.pt"
        artifact_path.unlink()
        with pytest.raises(ValueError, match="Artifact file missing"):
            reg.load("cnn2", "1.0.0")

    def test_load_not_found_raises(self, reg):
        with pytest.raises(ValueError, match="Strategy not found"):
            reg.load("nonexistent", "0.0.0")

    # ------------------------------------------------------------------
    # promote
    # ------------------------------------------------------------------

    def test_promote_changes_status(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        result = reg.load("strat", "1.0.0")
        assert result["metadata"]["status"] == "approved_for_paper"

    def test_promote_to_live(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        checklist_path = _write_checklist(reg, "strat", decision="READY")
        reg.promote(
            "strat",
            "1.0.0",
            "approved_for_live",
            paper_summary={
                "closed_trade_count": 25,
                "win_rate": 0.62,
                "profit_factor": 1.45,
                "realized_pnl": 1200.0,
                "fill_rate": 0.97,
                "avg_slippage_pct": 0.0012,
            },
            checklist_path=checklist_path,
        )
        result = reg.load("strat", "1.0.0")
        assert result["metadata"]["status"] == "approved_for_live"

    def test_promote_to_live_requires_paper_summary(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        checklist_path = _write_checklist(reg, "strat", decision="READY")
        with pytest.raises(ValueError, match="paper_summary is required"):
            reg.promote(
                "strat",
                "1.0.0",
                "approved_for_live",
                checklist_path=checklist_path,
            )

    def test_promote_to_live_requires_paper_status_first(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        checklist_path = _write_checklist(reg, "strat", decision="READY")
        with pytest.raises(ValueError, match="requires current status approved_for_paper"):
            reg.promote(
                "strat",
                "1.0.0",
                "approved_for_live",
                paper_summary={
                    "closed_trade_count": 30,
                    "win_rate": 0.6,
                    "profit_factor": 1.3,
                    "realized_pnl": 1000.0,
                    "fill_rate": 0.95,
                    "avg_slippage_pct": 0.001,
                },
                checklist_path=checklist_path,
            )

    def test_promote_to_live_fails_readiness_gate(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        checklist_path = _write_checklist(reg, "strat", decision="READY")
        with pytest.raises(ValueError, match="Paper readiness gate failed"):
            reg.promote(
                "strat",
                "1.0.0",
                "approved_for_live",
                paper_summary={
                    "closed_trade_count": 4,
                    "win_rate": 0.25,
                    "profit_factor": 0.7,
                    "realized_pnl": -50.0,
                    "fill_rate": 0.40,
                    "avg_slippage_pct": 0.01,
                },
                checklist_path=checklist_path,
            )

    def test_promote_to_live_with_custom_thresholds(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        checklist_path = _write_checklist(reg, "strat", decision="READY")
        reg.promote(
            "strat",
            "1.0.0",
            "approved_for_live",
            paper_summary={
                "closed_trade_count": 8,
                "win_rate": 0.52,
                "profit_factor": 1.08,
                "realized_pnl": 5.0,
                "fill_rate": 0.85,
                "avg_slippage_pct": 0.003,
            },
            readiness_thresholds={
                "min_closed_trade_count": 5,
                "min_profit_factor": 1.05,
                "min_fill_rate": 0.80,
                "max_avg_slippage_pct": 0.004,
            },
            checklist_path=checklist_path,
        )
        result = reg.load("strat", "1.0.0")
        assert result["metadata"]["status"] == "approved_for_live"

    def test_promote_invalid_status_raises(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        with pytest.raises(ValueError, match="Invalid status"):
            reg.promote("strat", "1.0.0", "invalid_status")

    def test_promote_not_found_raises(self, reg):
        with pytest.raises(ValueError, match="Strategy not found"):
            reg.promote("ghost", "9.9.9", "approved_for_paper")

    def test_promote_to_live_requires_checklist(self, reg):
        reg.save("strat", "1.0.0", "rule", {})
        reg.promote("strat", "1.0.0", "approved_for_paper")
        with pytest.raises(ValueError, match="Promotion checklist is required"):
            reg.promote(
                "strat",
                "1.0.0",
                "approved_for_live",
                paper_summary={
                    "closed_trade_count": 30,
                    "win_rate": 0.6,
                    "profit_factor": 1.3,
                    "realized_pnl": 1000.0,
                    "fill_rate": 0.95,
                    "avg_slippage_pct": 0.001,
                },
            )

    # ------------------------------------------------------------------
    # list_strategies
    # ------------------------------------------------------------------

    def test_list_all_strategies(self, reg):
        reg.save("a", "1.0.0", "rule", {})
        reg.save("b", "1.0.0", "rule", {})
        rows = reg.list_strategies()
        assert len(rows) == 2

    def test_list_filtered_by_status(self, reg):
        reg.save("a", "1.0.0", "rule", {})
        reg.save("b", "1.0.0", "rule", {})
        reg.promote("a", "1.0.0", "approved_for_paper")
        approved = reg.list_strategies(status="approved_for_paper")
        assert len(approved) == 1
        assert approved[0]["name"] == "a"

    def test_list_empty_registry(self, reg):
        assert reg.list_strategies() == []

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_invalid_type_raises(self, reg):
        with pytest.raises(ValueError, match="Invalid strategy_type"):
            reg.save("x", "1.0.0", "bad_type", {})

    def test_invalid_status_raises(self, reg):
        with pytest.raises(ValueError, match="Invalid status"):
            reg.save("x", "1.0.0", "rule", {}, status="deployed")

    def test_nn_without_weights_raises(self, reg):
        with pytest.raises(ValueError, match="weights are required"):
            reg.save("cnn", "1.0.0", "nn", {})

    def test_upsert_overwrites_existing(self, reg):
        reg.save("strat", "1.0.0", "rule", {"v": 1})
        reg.save("strat", "1.0.0", "rule", {"v": 2})
        result = reg.load("strat", "1.0.0")
        assert result["metadata"]["parameters"]["v"] == 2
