# Opus Prompt — Step 82/83 Policy Decision Session

You are working in the trading-bot repo.
Run an ARCH decision session to unblock Step 82 and Step 83 only. Do not implement runtime code. Produce policy decisions and a Copilot-ready implementation contract.

## Required pre-reads (in order)
1. `SESSION_LOG.md` (last 3 entries)
2. `SESSION_TOPOLOGY.md` §5
3. `PROJECT_DESIGN.md` (focus §4, §6, §7, §9)
4. `CLAUDE.md`
5. `IMPLEMENTATION_BACKLOG.md` (queue tables + full entries for Step 82/83)
6. `.python-style-guide.md`

## Queue authority and boundaries
- Treat the top three queue tables in `IMPLEMENTATION_BACKLOG.md` as authoritative.
- Preserve all hard constraints in `PROJECT_DESIGN.md` §7.
- Keep MO-2 qualifying semantics unchanged: in-window only, signoff-eligible.
- MO-2F must remain non-signoff and non-substitutable.
- Do not retroactively edit accepted ADRs.

## Decision scope
### A) Step 82 policy split (qualifying lane vs functional-only lane)
- Define an admissibility matrix: which evidence can satisfy which dependency class.
- Define mandatory lane markers and anti-confusion labels in artifacts.
- Define rejection criteria for attempts to use functional-only evidence as qualifying signoff.

### B) Step 83 duration policy
- Define objective profiles and minimum meaningful durations (e.g., smoke, orchestration, reconcile-confidence).
- Set default functional-only duration and escalation rules when failures occur.
- Define explicit guardrails preventing short runs from being interpreted as qualifying evidence.

## Required outputs
1. Inventory table of active relevant items (32, 57, 82, 83, MO-2, MO-2F, MO-7, MO-8, RFC-007) with owner/status/blocker/can-bundle.
2. Final policy package for Step 82:
   - lane taxonomy
   - admissibility matrix
   - artifact labeling schema (field names and allowed values)
   - anti-substitution rule text
3. Final policy package for Step 83:
   - objective profile matrix
   - duration policy per profile
   - promotion/signoff exclusion rules
4. Copilot implementation packet:
   - exact files to modify
   - exact acceptance tests to add
   - non-regression checks
5. Blocker register with clear unblock criteria.
6. One-sentence final recommendation.

## LPDD sync requirements
- Append a decision entry to `PROJECT_DESIGN.md` §6.
- Update Step 82 and Step 83 notes in `IMPLEMENTATION_BACKLOG.md` with policy decision results and Copilot handoff instructions.
- Append structured session entry to `SESSION_LOG.md`.
- Run consistency gate:

`C:/Users/rando/Projects/trading-bot/.venv/Scripts/python.exe scripts/lpdd_consistency_check.py --root .`

## Hard constraints
- Minimal reversible documentation changes only.
- No runtime source edits in this session.
- Keep paper/sandbox safety defaults unchanged.
- Keep `RiskManager.approve_signal()` as sole Signal→Order path unchanged.

---

Back to orchestrator prompt: [STAGED_MASTER_PROMPT.md](STAGED_MASTER_PROMPT.md)