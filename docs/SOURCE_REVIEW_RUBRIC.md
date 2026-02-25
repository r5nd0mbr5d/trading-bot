# Source Review Rubric

Purpose: provide a deterministic, LPDD-aligned triage method for external repositories,
papers, and blog posts before they influence backlog tickets or architecture changes.

---

## Scoring Dimensions (0-100 each)

1. **Reproducibility** (weight: 0.25)
   - Is there enough information to reproduce results?
   - Includes data window, symbols/universe, feature set, training/inference split,
     and deterministic run instructions.

2. **Maintenance Health** (weight: 0.15)
   - Signs the source is actively maintained or at least stable.
   - Includes dependency hygiene, recent commits, and issue quality.

3. **Test Evidence** (weight: 0.15)
   - Evidence of automated tests, validation harnesses, or benchmark reproducibility.

4. **Risk Controls** (weight: 0.20)
   - Demonstrates guardrails (position sizing, drawdown limits, kill switch,
     slippage/cost assumptions) instead of raw return chasing.

5. **LPDD Invariant Fit** (weight: 0.15)
   - Compatible with hard constraints in `PROJECT_DESIGN.md` §7.
   - Reject or heavily penalize content that bypasses risk-manager-style gating,
     uses lookahead bias, or assumes production-first rollout.

6. **Operational Realism** (weight: 0.10)
   - Uses plausible market assumptions (latency, costs, liquidity, fill uncertainty)
     rather than idealized backtests.

---

## Verdict Mapping

- **Adopt now**: weighted score >= 80
- **Research first**: 50 <= weighted score <= 79
- **Reject**: weighted score < 50

---

## Hard-Fail Heuristics

Even with a high numeric score, force `Reject` if any are true:

- Evidence of lookahead leakage with no mitigation plan
- Unrealistic return claims with no transaction cost or out-of-sample disclosure
- Recommendations that violate LPDD hard constraints

---

## Required Metadata

Each source review must include:

- `source_id` (stable slug)
- `source_type` (`repo`, `paper`, `article`, `video`, `other`)
- `url`
- `review_date_utc`
- `reviewer`
- `scores` (all 6 dimensions)
- `notes` (reusable ideas, conflicts, and ticket recommendations)

Use `research/specs/SOURCE_REVIEW_TEMPLATE.md` for manual reviews and
`scripts/source_review.py` to compute the weighted score + suggested verdict.
