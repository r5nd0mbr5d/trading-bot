"""Tests for external source review scoring utility."""

import json

import pytest

from scripts.source_review import evaluate_review, score_to_verdict, validate_scores


def _base_payload() -> dict:
    return {
        "source_id": "sample",
        "scores": {
            "reproducibility": 80,
            "maintenance_health": 80,
            "test_evidence": 80,
            "risk_controls": 80,
            "lpdd_invariant_fit": 80,
            "operational_realism": 80,
        },
    }


def test_score_to_verdict_boundaries():
    assert score_to_verdict(80.0) == "Adopt now"
    assert score_to_verdict(79.99) == "Research first"
    assert score_to_verdict(50.0) == "Research first"
    assert score_to_verdict(49.99) == "Reject"


def test_evaluate_review_adopt_now():
    payload = _base_payload()
    result = evaluate_review(payload)
    assert result["weighted_score"] == 80.0
    assert result["recommended_verdict"] == "Adopt now"


def test_evaluate_review_research_first():
    payload = _base_payload()
    payload["scores"]["reproducibility"] = 40
    payload["scores"]["test_evidence"] = 40
    result = evaluate_review(payload)
    assert 50.0 <= result["weighted_score"] <= 79.0
    assert result["recommended_verdict"] == "Research first"


def test_evaluate_review_reject():
    payload = _base_payload()
    for key in payload["scores"]:
        payload["scores"][key] = 20
    result = evaluate_review(payload)
    assert result["weighted_score"] < 50.0
    assert result["recommended_verdict"] == "Reject"


def test_validate_scores_missing_dimension_raises():
    payload = _base_payload()
    del payload["scores"]["risk_controls"]
    with pytest.raises(ValueError, match="Missing required score dimensions"):
        validate_scores(payload)


def test_validate_scores_out_of_range_raises():
    payload = _base_payload()
    payload["scores"]["risk_controls"] = 101
    with pytest.raises(ValueError, match=r"must be in \[0, 100\]"):
        validate_scores(payload)


def test_evaluate_result_is_json_serializable():
    payload = _base_payload()
    result = evaluate_review(payload)
    encoded = json.dumps(result)
    assert "weighted_score" in encoded
