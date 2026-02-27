# Opus Prompt — Step 57 BTC LSTM Feature Engineering Design Session

You are working in the trading-bot repo.
Run an ARCH decision session to unblock Step 57 only. Do not implement runtime code. Produce design decisions and a Copilot-ready implementation contract.

## Required pre-reads (in order)
1. `SESSION_LOG.md` (last 3 entries)
2. `SESSION_TOPOLOGY.md` §5
3. `PROJECT_DESIGN.md` (focus §4, §6, §7, §9)
4. `CLAUDE.md`
5. `IMPLEMENTATION_BACKLOG.md` (queue tables + full Step 57 + Step 32 dependency context)
6. `.python-style-guide.md`
7. `research/specs/FEATURE_LABEL_SPEC.md`
8. `research/specs/RESEARCH_PROMOTION_POLICY.md`

## Queue authority and boundaries
- Treat the top three queue tables in `IMPLEMENTATION_BACKLOG.md` as authoritative.
- Preserve all hard constraints in `PROJECT_DESIGN.md` §7.
- Do not modify accepted ADRs retroactively.
- Keep research/runtime separation invariant (`research/` must not import from `src/` at module level).

## Decision scope (Step 57 only)
1. Decide BTC multi-timeframe feature-set boundaries for LSTM-prep research inputs.
2. Define admissible indicator families and explicit leakage guards.
3. Decide train/validation split policy for crypto regime shifts.
4. Specify output schemas and metadata needed for later Step 32 gating.

## Required outputs
1. Inventory table (Step 57, Step 32, MO-7, MO-8) with owner/status/blocker/can-bundle.
2. Feature-set boundary package:
   - exact timeframe windows
   - exact feature families and per-family rationale
   - mandatory normalization and missing-data policy
3. Leakage control package:
   - prohibited transformations
   - lookahead-safe construction rules
   - validation checks to enforce leakage guards
4. Copilot implementation packet:
   - exact files to modify/create
   - exact tests to add
   - acceptance criteria and non-regression checks
5. Blocker register with explicit unblock criteria.
6. One-sentence final recommendation.

## LPDD sync requirements
- Append design decision entry to `PROJECT_DESIGN.md` §6.
- Update Step 57 notes in `IMPLEMENTATION_BACKLOG.md` with decision outputs and implementation handoff.
- Append structured session entry to `SESSION_LOG.md`.
- Run consistency gate:

`C:/Users/rando/Projects/trading-bot/.venv/Scripts/python.exe scripts/lpdd_consistency_check.py --root .`

## Hard constraints
- Minimal reversible documentation changes only.
- No runtime source edits in this session.
- No changes to MO-2 qualifying semantics.
- Do not claim Step 32 unblocked unless MO-7/MO-8 and Step 62 gate dependencies are explicitly satisfied.

Back to orchestrator prompt: [STAGED_MASTER_PROMPT.md](STAGED_MASTER_PROMPT.md)
