"""Tests for the promotion decision rubric JSON schema.

Validates that:
- The decision_rubric.json schema file is valid JSON and well-formed.
- Compliant rubric documents pass schema validation.
- Non-compliant rubric documents (missing required fields, wrong types,
  invalid enums) are rejected.
- APPROVED decisions with P0 failures are rejected.
- P1 overrides without two reviewers are rejected.
- paper_readiness_failures() produces output that matches schema expectations.

See docs/PROMOTION_FRAMEWORK.md for the full promotion policy.
"""

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUBRIC_SCHEMA_PATH = Path("reports/promotions/decision_rubric.json")


def load_schema() -> dict:
    with RUBRIC_SCHEMA_PATH.open() as f:
        return json.load(f)


def _valid_approved_rubric() -> dict:
    """Return a minimal valid APPROVED rubric document."""
    return {
        "rubric_version": "1.0.0",
        "strategy_id": "ma_crossover:1.0.0",
        "strategy_name": "ma_crossover",
        "strategy_version": "1.0.0",
        "promotion_level": "paper_to_live",
        "decision": "APPROVED",
        "decision_date": "2026-02-23T10:00:00Z",
        "reviewer_ids": ["alice@example.com"],
        "environment": "alpaca_paper",
        "market": "US",
        "base_currency": "USD",
        "metrics": {
            "closed_trade_count": 25,
            "win_rate": 0.56,
            "profit_factor": 1.45,
            "realized_pnl": 187.50,
            "fill_rate": 0.94,
            "avg_slippage_pct": 0.0019,
        },
        "p0_failures": [],
        "p1_overrides": [],
        "gate_b_automated_output": [],
        "notes": "All metrics passed cleanly.",
    }


def _valid_rejected_rubric() -> dict:
    return {
        "rubric_version": "1.0.0",
        "strategy_id": "rsi_momentum:1.0.0",
        "strategy_name": "rsi_momentum",
        "strategy_version": "1.0.0",
        "promotion_level": "paper_to_live",
        "decision": "REJECTED",
        "decision_date": "2026-02-23T10:00:00Z",
        "reviewer_ids": ["alice@example.com"],
        "metrics": {
            "closed_trade_count": 15,
            "win_rate": 0.40,
            "profit_factor": 0.95,
            "realized_pnl": -50.0,
            "fill_rate": 0.88,
            "avg_slippage_pct": 0.0032,
        },
        "p0_failures": [
            "closed_trade_count=15 < min_closed_trade_count=20",
            "win_rate=0.400000 < min_win_rate=0.500000",
            "fill_rate=0.880000 < min_fill_rate=0.900000",
        ],
        "p1_overrides": [],
        "rejection_reason": "Multiple P0 failures. Minimum sample size not reached.",
    }


# ---------------------------------------------------------------------------
# Schema file tests
# ---------------------------------------------------------------------------


class TestSchemaFile:
    def test_schema_file_exists(self):
        assert RUBRIC_SCHEMA_PATH.exists(), f"Schema file missing: {RUBRIC_SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        schema = load_schema()
        assert isinstance(schema, dict)

    def test_schema_has_required_fields(self):
        schema = load_schema()
        assert schema.get("type") == "object"
        assert "required" in schema
        required = schema["required"]
        expected_required = [
            "rubric_version",
            "strategy_id",
            "strategy_name",
            "strategy_version",
            "promotion_level",
            "decision",
            "decision_date",
            "reviewer_ids",
            "metrics",
            "p0_failures",
            "p1_overrides",
        ]
        for field in expected_required:
            assert field in required, f"Required field missing from schema: {field}"

    def test_schema_enums_are_correct(self):
        schema = load_schema()
        props = schema["properties"]

        decision_enum = props["decision"]["enum"]
        assert "APPROVED" in decision_enum
        assert "REJECTED" in decision_enum
        assert "DEFERRED" in decision_enum

        promotion_enum = props["promotion_level"]["enum"]
        assert "paper_to_live" in promotion_enum
        assert "experimental_to_paper" in promotion_enum

        rubric_enum = props["rubric_version"]["enum"]
        assert "1.0.0" in rubric_enum

    def test_schema_metrics_required_fields(self):
        schema = load_schema()
        metrics_props = schema["properties"]["metrics"]
        required_metrics = metrics_props.get("required", [])
        for field in [
            "closed_trade_count",
            "win_rate",
            "profit_factor",
            "realized_pnl",
            "fill_rate",
            "avg_slippage_pct",
        ]:
            assert field in required_metrics, f"Metric field missing from required: {field}"

    def test_schema_has_example(self):
        schema = load_schema()
        examples = schema.get("examples", [])
        assert len(examples) >= 1, "Schema should contain at least one example"
        example = examples[0]
        assert example["decision"] == "APPROVED"
        assert example["p0_failures"] == []


# ---------------------------------------------------------------------------
# Rubric document structure tests (without jsonschema dependency)
# ---------------------------------------------------------------------------


class TestRubricDocumentStructure:
    """Validate rubric documents against structural rules without jsonschema library."""

    def _validate_rubric(self, doc: dict) -> list[str]:
        """Return a list of validation errors. Empty = valid."""
        errors = []
        schema = load_schema()
        required_fields = schema["required"]

        for field in required_fields:
            if field not in doc:
                errors.append(f"Missing required field: {field}")

        if "rubric_version" in doc and doc["rubric_version"] not in ["1.0.0"]:
            errors.append(f"Invalid rubric_version: {doc['rubric_version']}")

        if "decision" in doc and doc["decision"] not in ["APPROVED", "REJECTED", "DEFERRED"]:
            errors.append(f"Invalid decision: {doc['decision']}")

        if "promotion_level" in doc:
            valid_levels = [
                "experimental_to_paper",
                "paper_to_live",
                "live_to_production",
                "demotion_to_paper",
                "demotion_to_experimental",
            ]
            if doc["promotion_level"] not in valid_levels:
                errors.append(f"Invalid promotion_level: {doc['promotion_level']}")

        if "strategy_id" in doc:
            if not re.match(r"^[a-zA-Z0-9_]+:[0-9]+\.[0-9]+\.[0-9]+$", doc["strategy_id"]):
                errors.append(f"Invalid strategy_id format: {doc['strategy_id']}")

        if "reviewer_ids" in doc:
            if not isinstance(doc["reviewer_ids"], list) or len(doc["reviewer_ids"]) < 1:
                errors.append("reviewer_ids must be a non-empty list")

        if "metrics" in doc:
            metrics = doc["metrics"]
            for field in [
                "closed_trade_count",
                "win_rate",
                "profit_factor",
                "realized_pnl",
                "fill_rate",
                "avg_slippage_pct",
            ]:
                if field not in metrics:
                    errors.append(f"Missing required metric: {field}")

            if "win_rate" in metrics:
                v = metrics["win_rate"]
                if not (isinstance(v, (int, float)) and 0.0 <= v <= 1.0):
                    errors.append(f"win_rate must be in [0.0, 1.0], got {v}")

            if "fill_rate" in metrics:
                v = metrics["fill_rate"]
                if not (isinstance(v, (int, float)) and 0.0 <= v <= 1.0):
                    errors.append(f"fill_rate must be in [0.0, 1.0], got {v}")

        if doc.get("decision") == "APPROVED" and "p0_failures" in doc:
            if len(doc["p0_failures"]) > 0:
                errors.append("APPROVED decisions must have zero p0_failures")

        if "p1_overrides" in doc:
            for i, override in enumerate(doc["p1_overrides"]):
                approved_by = override.get("approved_by", [])
                if len(approved_by) < 2:
                    errors.append(f"p1_overrides[{i}].approved_by requires at least 2 reviewers")

        return errors

    def test_valid_approved_rubric(self):
        doc = _valid_approved_rubric()
        errors = self._validate_rubric(doc)
        assert errors == [], f"Valid APPROVED rubric failed validation: {errors}"

    def test_valid_rejected_rubric(self):
        doc = _valid_rejected_rubric()
        errors = self._validate_rubric(doc)
        assert errors == [], f"Valid REJECTED rubric failed validation: {errors}"

    def test_missing_required_field_strategy_id(self):
        doc = _valid_approved_rubric()
        del doc["strategy_id"]
        errors = self._validate_rubric(doc)
        assert any("strategy_id" in e for e in errors)

    def test_missing_required_field_decision(self):
        doc = _valid_approved_rubric()
        del doc["decision"]
        errors = self._validate_rubric(doc)
        assert any("decision" in e for e in errors)

    def test_missing_required_field_metrics(self):
        doc = _valid_approved_rubric()
        del doc["metrics"]
        errors = self._validate_rubric(doc)
        assert any("metrics" in e for e in errors)

    def test_invalid_decision_enum(self):
        doc = _valid_approved_rubric()
        doc["decision"] = "MAYBE"
        errors = self._validate_rubric(doc)
        assert any("decision" in e for e in errors)

    def test_invalid_promotion_level_enum(self):
        doc = _valid_approved_rubric()
        doc["promotion_level"] = "paper_to_moon"
        errors = self._validate_rubric(doc)
        assert any("promotion_level" in e for e in errors)

    def test_invalid_strategy_id_format(self):
        doc = _valid_approved_rubric()
        doc["strategy_id"] = "no_version_here"
        errors = self._validate_rubric(doc)
        assert any("strategy_id" in e for e in errors)

    def test_invalid_strategy_id_bad_version(self):
        doc = _valid_approved_rubric()
        doc["strategy_id"] = "ma_crossover:v1"
        errors = self._validate_rubric(doc)
        assert any("strategy_id" in e for e in errors)

    def test_approved_with_p0_failures_invalid(self):
        doc = _valid_approved_rubric()
        doc["p0_failures"] = ["win_rate=0.45 < min_win_rate=0.50"]
        errors = self._validate_rubric(doc)
        assert any("p0_failures" in e for e in errors)

    def test_rejected_with_p0_failures_valid(self):
        doc = _valid_rejected_rubric()
        errors = self._validate_rubric(doc)
        assert errors == [], f"Valid REJECTED rubric with p0_failures failed: {errors}"

    def test_win_rate_out_of_range(self):
        doc = _valid_approved_rubric()
        doc["metrics"]["win_rate"] = 1.5
        errors = self._validate_rubric(doc)
        assert any("win_rate" in e for e in errors)

    def test_fill_rate_out_of_range(self):
        doc = _valid_approved_rubric()
        doc["metrics"]["fill_rate"] = -0.1
        errors = self._validate_rubric(doc)
        assert any("fill_rate" in e for e in errors)

    def test_p1_override_requires_two_reviewers(self):
        doc = _valid_approved_rubric()
        doc["p1_overrides"] = [
            {
                "metric": "sharpe_ratio",
                "threshold": 0.3,
                "actual_value": 0.25,
                "justification": "FOMC week volatility caused the miss.",
                "approved_by": ["alice@example.com"],  # Only one — should fail
            }
        ]
        errors = self._validate_rubric(doc)
        assert any("p1_overrides" in e for e in errors)

    def test_p1_override_with_two_reviewers_valid(self):
        doc = _valid_approved_rubric()
        doc["p1_overrides"] = [
            {
                "metric": "sharpe_ratio",
                "threshold": 0.3,
                "actual_value": 0.25,
                "justification": "FOMC week volatility caused a temporary miss. All P0 metrics clean.",
                "approved_by": ["alice@example.com", "bob@example.com"],
            }
        ]
        errors = self._validate_rubric(doc)
        assert errors == [], f"Valid P1 override failed: {errors}"

    def test_empty_reviewer_ids(self):
        doc = _valid_approved_rubric()
        doc["reviewer_ids"] = []
        errors = self._validate_rubric(doc)
        assert any("reviewer_ids" in e for e in errors)

    def test_missing_metric_closed_trade_count(self):
        doc = _valid_approved_rubric()
        del doc["metrics"]["closed_trade_count"]
        errors = self._validate_rubric(doc)
        assert any("closed_trade_count" in e for e in errors)

    def test_deferred_decision_valid(self):
        doc = _valid_approved_rubric()
        doc["decision"] = "DEFERRED"
        doc["p0_failures"] = []  # DEFERRED may have empty p0_failures
        doc["rejection_reason"] = "Insufficient trading days (8/10 required)."
        doc["next_review_date"] = "2026-03-09"
        errors = self._validate_rubric(doc)
        assert errors == [], f"Valid DEFERRED rubric failed: {errors}"

    def test_schema_example_is_valid(self):
        schema = load_schema()
        examples = schema.get("examples", [])
        assert len(examples) >= 1
        for example in examples:
            errors = self._validate_rubric(example)
            assert errors == [], f"Schema example failed validation: {errors}"


# ---------------------------------------------------------------------------
# Integration with paper_readiness_failures()
# ---------------------------------------------------------------------------


class TestPaperReadinessGateAlignment:
    """Verify that paper_readiness_failures() output aligns with rubric expectations."""

    def test_passing_summary_produces_empty_failures(self):
        from src.strategies.registry import paper_readiness_failures

        passing_summary = {
            "closed_trade_count": 25,
            "win_rate": 0.56,
            "profit_factor": 1.45,
            "realized_pnl": 100.0,
            "fill_rate": 0.94,
            "avg_slippage_pct": 0.0018,
        }
        failures = paper_readiness_failures(passing_summary)
        assert failures == [], f"Expected no failures, got: {failures}"

    def test_failing_summary_produces_failures(self):
        from src.strategies.registry import paper_readiness_failures

        failing_summary = {
            "closed_trade_count": 10,
            "win_rate": 0.40,
            "profit_factor": 0.95,
            "realized_pnl": -50.0,
            "fill_rate": 0.85,
            "avg_slippage_pct": 0.0050,
        }
        failures = paper_readiness_failures(failing_summary)
        assert len(failures) > 0
        # Failures should be strings that can populate p0_failures in rubric
        for failure in failures:
            assert isinstance(failure, str)
            assert len(failure) > 0

    def test_failures_are_rubric_compatible_strings(self):
        """Failures from paper_readiness_failures() must be valid p0_failures entries."""
        from src.strategies.registry import paper_readiness_failures

        borderline_summary = {
            "closed_trade_count": 5,
            "win_rate": 0.30,
            "profit_factor": 0.80,
            "realized_pnl": -200.0,
            "fill_rate": 0.70,
            "avg_slippage_pct": 0.0100,
        }
        failures = paper_readiness_failures(borderline_summary)
        # All failures are strings — valid for json serialisation into p0_failures
        rubric = _valid_approved_rubric()
        rubric["decision"] = "REJECTED"
        rubric["p0_failures"] = failures
        # This should now be JSON-serialisable
        serialised = json.dumps(rubric)
        restored = json.loads(serialised)
        assert restored["p0_failures"] == failures

    def test_inf_profit_factor_passes(self):
        from src.strategies.registry import paper_readiness_failures

        summary = {
            "closed_trade_count": 25,
            "win_rate": 0.60,
            "profit_factor": "inf",
            "realized_pnl": 300.0,
            "fill_rate": 0.95,
            "avg_slippage_pct": 0.0010,
        }
        failures = paper_readiness_failures(summary)
        assert failures == []

    def test_custom_thresholds_override_defaults(self):
        from src.strategies.registry import paper_readiness_failures

        # Stricter thresholds than default
        strict = {
            "min_closed_trade_count": 50,
            "min_win_rate": 0.60,
        }
        summary = {
            "closed_trade_count": 30,  # Would pass defaults (20), fails strict (50)
            "win_rate": 0.55,  # Would pass defaults (0.50), fails strict (0.60)
            "profit_factor": 1.20,
            "realized_pnl": 100.0,
            "fill_rate": 0.95,
            "avg_slippage_pct": 0.0015,
        }
        failures = paper_readiness_failures(summary, thresholds=strict)
        assert any("closed_trade_count" in f for f in failures)
        assert any("win_rate" in f for f in failures)
