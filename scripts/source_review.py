"""Compute weighted source-review scores and verdicts.

This script reads a JSON (or YAML when PyYAML is installed) source review file,
validates required dimensions, computes a weighted score, and emits a verdict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DIMENSION_WEIGHTS: dict[str, float] = {
    "reproducibility": 0.25,
    "maintenance_health": 0.15,
    "test_evidence": 0.15,
    "risk_controls": 0.20,
    "lpdd_invariant_fit": 0.15,
    "operational_realism": 0.10,
}


def parse_review_file(file_path: Path) -> dict[str, Any]:
    """Parse a source review file.

    Parameters
    ----------
    file_path : Path
        Path to a JSON or YAML review file.

    Returns
    -------
    dict[str, Any]
        Parsed review payload.

    Raises
    ------
    ValueError
        If parsing fails or an unsupported extension is provided.
    """
    suffix = file_path.suffix.lower()
    raw_text = file_path.read_text(encoding="utf-8")

    if suffix == ".json":
        return json.loads(raw_text)

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError(
                "YAML input requires PyYAML. Install pyyaml or provide JSON input."
            ) from exc
        parsed = yaml.safe_load(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("YAML review payload must be a mapping/object.")
        return parsed

    raise ValueError(f"Unsupported review format '{suffix}'. Use .json, .yaml, or .yml")


def validate_scores(payload: dict[str, Any]) -> dict[str, float]:
    """Validate score dimensions from a review payload.

    Parameters
    ----------
    payload : dict[str, Any]
        Review payload containing a `scores` mapping.

    Returns
    -------
    dict[str, float]
        Normalized numeric score mapping.

    Raises
    ------
    ValueError
        If required dimensions are missing or out of range.
    """
    if "scores" not in payload or not isinstance(payload["scores"], dict):
        raise ValueError("Review file must include a 'scores' object.")

    scores_obj = payload["scores"]
    missing = [dim for dim in DIMENSION_WEIGHTS if dim not in scores_obj]
    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(f"Missing required score dimensions: {missing_csv}")

    normalized: dict[str, float] = {}
    for dim in DIMENSION_WEIGHTS:
        value = scores_obj[dim]
        if not isinstance(value, (int, float)):
            raise ValueError(f"Score '{dim}' must be numeric.")
        numeric = float(value)
        if numeric < 0.0 or numeric > 100.0:
            raise ValueError(f"Score '{dim}' must be in [0, 100].")
        normalized[dim] = numeric

    return normalized


def weighted_score(scores: dict[str, float]) -> float:
    """Compute weighted score from validated dimensions.

    Parameters
    ----------
    scores : dict[str, float]
        Validated score map containing all required dimensions.

    Returns
    -------
    float
        Weighted score rounded to two decimal places.
    """
    total = 0.0
    for dim, weight in DIMENSION_WEIGHTS.items():
        total += scores[dim] * weight
    return round(total, 2)


def score_to_verdict(score: float) -> str:
    """Map weighted score to review verdict.

    Parameters
    ----------
    score : float
        Weighted score in [0, 100].

    Returns
    -------
    str
        One of: `Adopt now`, `Research first`, `Reject`.
    """
    if score >= 80.0:
        return "Adopt now"
    if score >= 50.0:
        return "Research first"
    return "Reject"


def evaluate_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a review payload and return machine-readable result.

    Parameters
    ----------
    payload : dict[str, Any]
        Parsed review content.

    Returns
    -------
    dict[str, Any]
        Evaluation result containing score and verdict.
    """
    scores = validate_scores(payload)
    final_score = weighted_score(scores)
    verdict = score_to_verdict(final_score)

    return {
        "source_id": payload.get("source_id", "unknown"),
        "weighted_score": final_score,
        "recommended_verdict": verdict,
        "weights": DIMENSION_WEIGHTS,
        "scores": scores,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate external source review scorecards")
    parser.add_argument("input", type=Path, help="Path to source review JSON/YAML file")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON path. If omitted, prints to stdout.",
    )
    return parser


def main() -> int:
    """CLI entrypoint for source review evaluation.

    Returns
    -------
    int
        Exit code (0 on success, 1 on validation/parsing errors).
    """
    parser = _build_parser()
    args = parser.parse_args()

    try:
        payload = parse_review_file(args.input)
        result = evaluate_review(payload)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    json_out = json.dumps(result, indent=2)
    if args.output is not None:
        args.output.write_text(json_out + "\n", encoding="utf-8")
    else:
        print(json_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
