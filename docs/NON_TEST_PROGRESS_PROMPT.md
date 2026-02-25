# Non-Test Progress Prompt (Copy/Paste)

Use this while MO-2 tests are running to advance backlog items that do not depend on live session outcomes.

---

## Prompt

You are working in the trading-bot repo. Progress non-test work only (no MO-2 script runs).

Constraints:
- Do not run `run_mo2_end_to_end.ps1`, `run_step1a_*`, or `paper_trial` commands.
- Do not modify architecture decisions or Opus-gated items (Steps 32/57/62/67/68).
- Prefer the highest-priority actionable non-operational item in backlog.

Tasks:
1. Read queue tables in `IMPLEMENTATION_BACKLOG.md` and identify the top non-test actionable item.
2. If Step 72 is top priority, produce a concrete implementation checklist with:
   - exact files to edit,
   - function/class names to add,
   - test cases to implement,
   - acceptance checks.
3. Create/update a run artifact file with:
   - selected item,
   - why selected,
   - 5–10 execution steps,
   - blocking risks and mitigations.
4. Append a brief `SESSION_LOG.md` entry noting non-test progress.

Output format:
- Selected item
- Deliverable path(s)
- Ready-to-start checklist
- Next coding command (non-operational)

---

## Suggested non-operational command

`python -m pytest tests/test_ibkr_broker.py tests/test_session_summary.py -v`

(Use only for regression confidence while avoiding live operational workflows.)
