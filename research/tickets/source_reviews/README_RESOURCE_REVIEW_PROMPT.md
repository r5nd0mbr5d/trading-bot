# Prompt — Add Source Reviews from README Resources

Use this prompt when you discover new candidate resources in any README and want to add source-review tickets in this repository.

---

## Copy/Paste Prompt

Create source-review ticket stubs for each resource listed below.

Requirements:
- Output format must match existing `research/tickets/source_reviews/*.yaml` structure.
- One file per source.
- File naming convention: lowercase `<owner>_<repo>.yaml` (or stable slug for non-GitHub links).
- Include fields:
  - `source_id`
  - `source_type` (`repo` unless otherwise specified)
  - `title`
  - `url`
  - `review_date_utc` (today)
  - `reviewer: copilot`
  - `status: NOT_STARTED`
  - `scores` keys with blank values:
    - `reproducibility`, `maintenance_health`, `test_evidence`, `risk_controls`, `lpdd_invariant_fit`, `operational_realism`
  - `notes` keys:
    - `final_verdict: TBD`
    - `review_scope: README + repository architecture + governance fit`
    - `reusable_items: []`
    - `conflicts: []`
    - `ticket_recommendations: []`

Constraint:
- Do not score or pre-judge sources in these stubs.
- Do not modify LPDD/Backlog unless explicitly requested.

Resource list:
- <paste URLs here>

---

## Optional Follow-On Prompt (After Stub Creation)

Now score these newly created source-review tickets using `docs/SOURCE_REVIEW_RUBRIC.md` and fill each YAML with:
- dimension scores,
- weighted score,
- final verdict (`Adopt now` | `Research first` | `Reject`),
- LPDD conflict notes,
- explicit ticket recommendations.
