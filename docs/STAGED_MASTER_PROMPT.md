# Staged Master Prompt (Single-Run Orchestrator)

Use this in a fresh session when you want one prompt to do what the master workflow does **and** execute all currently unblocked items grouped by agent.

---

## Prompt (Copy/Paste)

You are working in the trading-bot repo.
Run a single ARCH→IMPL→OPS orchestration pass that:
1) performs the same control function as the master prompt (context, queue authority, blocker validation, LPDD sync), and
2) stages unblocked items together where they are owned by the same agent and can be completed in one run.

### Required pre-reads (in order)
1. `SESSION_LOG.md` (last 2–3 entries)
2. `SESSION_TOPOLOGY.md` §5
3. `PROJECT_DESIGN.md`
4. `CLAUDE.md`
5. `IMPLEMENTATION_BACKLOG.md` (top queue tables + full entries for selected steps)
6. `.python-style-guide.md`

### Queue authority and scope rules
- Treat the three top tables in `IMPLEMENTATION_BACKLOG.md` as authoritative queue state.
- Respect LPDD invariants in `PROJECT_DESIGN.md` §7.
- Do not modify accepted ADRs retroactively.
- If any selected item is Opus-gated and unresolved, do not implement it; create a blocker note and move on.
- If no implementation item is unblocked for the current agent, produce handoff artifacts only.

### Stage 0 — Inventory all item types
Build a table with every active item type:
- Copilot implementation steps
- Opus-gated design steps
- Operator milestones (MO-*)
- RFC/ADR follow-up actions

For each item include:
- owner (`Copilot`, `Claude Opus`, `Operator`)
- status (`unblocked`, `blocked`, `deferred`, `completed`)
- blocker dependency
- can-bundle (`yes/no`)

### Stage 1 — Build staged bundles by same-agent ownership
Create grouped execution bundles using this rule:
- same owner
- no unresolved dependency between items in the same bundle
- can be completed in one continuous session

Label bundles:
- `BUNDLE-COPILOT-*`
- `BUNDLE-OPUS-*`
- `BUNDLE-OPS-*`

### Stage 2 — Execute unblocked bundles for the current agent
Execute only bundles that belong to your current agent role.
For other-agent bundles, produce explicit handoff packets with exact next command/checklist.

#### Current-state priority guidance (as of 2026-02-26)
If still valid after queue re-check, prioritize:
1. `BUNDLE-COPILOT-01`:
   - ADR-018 enforcement task: add client-id band guard in `src/execution/ibkr_broker.py` + tests
   - Research policy anti-substitution control in `research/specs/RESEARCH_PROMOTION_POLICY.md`
2. `BUNDLE-COPILOT-02`:
   - Step 62 implementation (`research/models/mlp_classifier.py`, config, tests, harness wiring)
3. `BUNDLE-OPS-01` (handoff only):
   - MO-2 in-window run sequence
   - MO-7 evidence commit checklist
   - MO-8 reviewer sign-off checklist

If queue state differs, adapt bundles dynamically and explain delta.

### Stage 3 — Validation and LPDD synchronization
After any implementation work:
1. Run targeted tests first, then full suite: `python -m pytest tests/ -v`
2. Update backlog step statuses and completion notes
3. Append `PROJECT_DESIGN.md` §6 evolution log entry
4. Append `SESSION_LOG.md` structured handoff entry
5. Run LPDD consistency gate: `python scripts/lpdd_consistency_check.py --root .`

### Required output format
1. **Inventory Table** (all active items/types)
2. **Bundle Plan** (grouped by owner)
3. **Execution Log** (what was completed in this run)
4. **Handoffs** (other-agent actionable packets)
5. **Blocker Register** (ID, owner, unblock criteria)
6. **Final Recommendation** (one sentence)

### Hard constraints
- Keep paper/sandbox safety defaults (`coinbase_sandbox=true`, `binance_testnet=true`).
- Keep `RiskManager.approve_signal()` as sole Signal→Order path.
- No architecture drift outside explicitly selected items.
- Minimal, reversible changes only.

End state requirement:
- The session must leave a clean, updated LPDD trail and clear next actions for each owner class.

---

## Quick Operator Variant (No code edits)

Use this variant when you only want staging + commands and no implementation:

"Read queue authority tables and produce staged bundles by owner. Execute none. Return only operator-ready commands, Copilot-ready implementation checklist, and blocker register with unblock criteria."

---

## Opus Step 82/83 Shortcut

Use [OPUS_STEP82_83_PROMPT.md](OPUS_STEP82_83_PROMPT.md) when you want a focused Claude Opus ARCH session to resolve Step 82 and Step 83 policy decisions (lane split + duration policy) before Copilot implementation.
