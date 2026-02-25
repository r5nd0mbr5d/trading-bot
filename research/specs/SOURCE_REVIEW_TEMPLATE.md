# Source Review Template

Use this template for each external source review.

---

## 1) Source Metadata

- `source_id`:
- `source_type` (`repo` | `paper` | `article` | `video` | `other`):
- `title`:
- `url`:
- `review_date_utc`:
- `reviewer`:

## 2) Dimension Scores (0-100)

- `reproducibility`:
- `maintenance_health`:
- `test_evidence`:
- `risk_controls`:
- `lpdd_invariant_fit`:
- `operational_realism`:

## 3) Auto-Derived Output (from `scripts/source_review.py`)

- `weighted_score`:
- `recommended_verdict` (`Adopt now` | `Research first` | `Reject`):

## 4) Analyst Verdict

- `final_verdict` (`Adopt now` | `Research first` | `Reject`):
- `verdict_rationale`:

## 5) Reusable Items

- What can be reused directly in this repository?
- What needs adaptation before use?

## 6) LPDD Conflicts / Constraint Violations

- List any conflicts with `PROJECT_DESIGN.md` §7 hard constraints.
- Include severity (`low` | `medium` | `high`) and mitigation options.

## 7) Ticket Recommendations

- Recommended backlog ticket(s) to create or update
- Agent assignment (`Copilot` | `Claude Opus` | `Operator`)
- Acceptance criteria

## 8) Evidence Notes

- Test evidence found:
- Cost/slippage assumptions found:
- Out-of-sample protocol found:
- Limitations explicitly acknowledged by source:
