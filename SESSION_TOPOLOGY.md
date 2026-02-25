# Session Topology — LLM-Managed Copilot Sessions

**Version:** 1.1
**Last Updated:** Feb 25, 2026
**Status:** ACTIVE
**ADR:** ADR-016

> This document defines how to structure, route, and hand off GitHub Copilot
> (and Claude Opus) sessions for maximum effectiveness in the LPDD workflow.
> It is read by LLM agents to understand which session type they are in and
> what context to load.

---

## §1 Why Session Topology Matters

LLM sessions are stateless by default. Without a structured handoff protocol:
- Each session re-reads the entire project from scratch (wasted context window)
- Previous decisions are lost or contradicted
- Queue states drift from reality
- The same investigation gets repeated across sessions

A **session topology** solves this by:
1. **Classifying** each session into a known type with a defined pre-read list
2. **Routing** the right context to the right agent
3. **Logging** what happened so the next session starts informed
4. **Bounding** scope so sessions stay focused

---

## §2 Session Types

Every Copilot or Claude Opus session falls into one of six types.
The agent should identify its type within the first few messages and
follow the corresponding protocol.

### Type 1: Implementation (`IMPL`)

| Field | Value |
|---|---|
| **Purpose** | Pick up and complete backlog steps from the Copilot Task Queue |
| **Agent** | GitHub Copilot |
| **Pre-reads** | `IMPLEMENTATION_BACKLOG.md` → Copilot Task Queue, `.python-style-guide.md`, `SESSION_LOG.md` (last 2 entries) |
| **Artifacts** | Code changes, new/updated tests, LPDD step status updates |
| **Handoff** | Mark step COMPLETED, update executive summary counts, append §6 Evolution Log entry, write `SESSION_LOG.md` entry |
| **Scope guard** | Do not make architectural decisions not described in the step definition |

**Trigger phrases:** "implement step X", "pick up next task", "continue backlog work", "write the code for..."

---

### Type 2: Architecture (`ARCH`)

| Field | Value |
|---|---|
| **Purpose** | Design decisions, trade-off analysis, new module interfaces, ADR/RFC work |
| **Agent** | Claude Opus (preferred) or Copilot with escalation awareness |
| **Pre-reads** | `PROJECT_DESIGN.md` (§1–§5 in full), relevant source files, `SESSION_LOG.md` (last 3 entries) |
| **Artifacts** | New ADRs in §3, RFC updates in §4, design specs in `docs/` |
| **Handoff** | ADR/RFC entries committed, blocker notes in backlog if implementation is deferred |
| **Scope guard** | Do not write production code — produce decisions and specs only |

**Trigger phrases:** "design the interface for...", "should we use X or Y?", "architecture review", "evaluate trade-offs"

---

### Type 3: Research (`RSRCH`)

| Field | Value |
|---|---|
| **Purpose** | ML experiments, paper/article reviews, methodology decisions, feature engineering |
| **Agent** | Claude Opus (methodology) or Copilot (implementation of reviewed designs) |
| **Pre-reads** | `research/specs/*`, `research/README.md`, relevant external papers, `SESSION_LOG.md` (last entry) |
| **Artifacts** | Experiment configs, review scorecards, new backlog steps, updated research specs |
| **Handoff** | Updated specs, new step definitions in backlog, scorecard entries in `research/reviews/` |
| **Scope guard** | Research code stays in `research/`. Do not modify `src/` without a promotion gate. |

**Trigger phrases:** "review this paper...", "design the ML pipeline for...", "run experiment...", "evaluate this approach"

---

### Type 4: Operations (`OPS`)

| Field | Value |
|---|---|
| **Purpose** | Run paper trials, execute MO-* milestones, IBKR health checks, burn-in sessions |
| **Agent** | Operator (human) assisted by Copilot |
| **Pre-reads** | `UK_OPERATIONS.md`, `SESSION_TOPOLOGY.md` §3 (checklists below), `PROJECT_DESIGN.md` §9 Milestones, `SESSION_LOG.md` (last entry) |
| **Artifacts** | Burn-in evidence in `reports/burnin/`, log files, MO-* status updates |
| **Handoff** | Update MO-* status in §9, fill evidence in backlog tracker, write `SESSION_LOG.md` entry |
| **Scope guard** | Do not modify source code. Run predefined scripts and record results. |

**Trigger phrases:** "run paper trial", "check IBKR health", "execute burn-in run", "schedule in-window session"

---

### Type 5: Debug / Triage (`DEBUG`)

| Field | Value |
|---|---|
| **Purpose** | Fix failing tests, resolve runtime errors, investigate unexpected behaviour |
| **Agent** | GitHub Copilot |
| **Pre-reads** | Test output / error log, relevant source files, `SESSION_LOG.md` (last entry for recent changes) |
| **Artifacts** | Bug fixes, regression tests, TD-* entries if structural debt discovered |
| **Handoff** | Updated test baseline, new TD entries in §5 if applicable, write `SESSION_LOG.md` entry |
| **Scope guard** | Fix the bug, not the architecture. If the fix requires structural change, escalate to ARCH. |

**Trigger phrases:** "tests are failing", "this error...", "why is X returning Y?", "debug the..."

---

### Type 6: Review / Consolidation (`REVIEW`)

| Field | Value |
|---|---|
| **Purpose** | External source review, documentation consolidation, queue hygiene, LPDD maintenance |
| **Agent** | Claude Opus (external review) or Copilot (documentation maintenance) |
| **Pre-reads** | `DOCUMENTATION_INDEX.md`, `PROJECT_DESIGN.md` (§1–§3), `SESSION_LOG.md` (last 3 entries) |
| **Artifacts** | Updated docs, reclassified queue items, archived stale files, scorecard entries |
| **Handoff** | Updated queue counts, index refreshes, write `SESSION_LOG.md` entry |
| **Scope guard** | Do not write production code. Consolidate, archive, and organize. |

**Trigger phrases:** "review these sources...", "clean up the docs", "update the queues", "consolidate..."

---

## §3 Context Loading Priority

When the context window is limited, load files in this priority order per session type.
**Bold** = mandatory. Regular = load if context permits.

| Priority | IMPL | ARCH | RSRCH | OPS | DEBUG | REVIEW |
|---|---|---|---|---|---|---|
| 1 | **SESSION_LOG.md** (last 2) | **SESSION_LOG.md** (last 3) | **SESSION_LOG.md** (last 1) | **SESSION_LOG.md** (last 1) | **Error output** | **SESSION_LOG.md** (last 3) |
| 2 | **IMPLEMENTATION_BACKLOG.md** (queue) | **PROJECT_DESIGN.md** (full) | **research/specs/*** | **UK_OPERATIONS.md** | **Failing test file** | **DOCUMENTATION_INDEX.md** |
| 3 | **.python-style-guide.md** | Relevant source files | research/README.md | §9 Milestones | Relevant source | **PROJECT_DESIGN.md** (§1–§5) |
| 4 | Step definition (full) | SESSION_LOG.md (older) | External paper/article | Burn-in tracker | SESSION_LOG.md | IMPLEMENTATION_BACKLOG.md (queues) |
| 5 | Relevant source files | IMPLEMENTATION_BACKLOG.md | IMPLEMENTATION_BACKLOG.md | SESSION_TOPOLOGY.md | .python-style-guide.md | Relevant docs |
| 6 | PROJECT_DESIGN.md (§7) | .python-style-guide.md | PROJECT_DESIGN.md (§3) | — | PROJECT_DESIGN.md (§5) | — |

---

## §4 Session Log Protocol

Every session **must** append an entry to `SESSION_LOG.md` before ending.
This is the primary handoff mechanism between sessions.

### Entry Format

```markdown
## [YYYY-MM-DD HH:MM UTC] — TYPE — Agent

**Goal:** One-sentence description of what this session set out to do.

**Outcome:**
- Bullet list of what was accomplished
- Include step numbers, test counts, and key decisions

**Queue Changes:**
- Steps started: (list or "none")
- Steps completed: (list or "none")
- Steps blocked: (list with reason, or "none")
- MO-* updates: (list or "none")

**Files Modified:**
- path/to/file.py — what changed
- path/to/other.md — what changed

**Test Baseline:** NNN passing (if tests were run)

**Handoff Notes:**
> Free-form notes for the next session. What should they know?
> What was left unfinished? What decision is pending?
```

### Rules
1. **Always append, never edit** previous entries (append-only log)
2. **Maximum 20 lines** per entry — be concise
3. **Include test baseline** whenever tests were run
4. **Tag the session type** so future sessions can filter by type
5. **If the session was trivial** (< 5 minutes, single file read), a one-liner is acceptable:
   ```markdown
   ## [2026-02-25 14:00 UTC] — DEBUG — Copilot
   Fixed typo in `config/settings.py` line 42. Tests: 521 passing.
   ```

---

## §5 Agent Routing Decision Tree

Use this flowchart when starting a session to determine the correct type:

```
Is the user asking about a specific failing test or runtime error?
├─ YES → DEBUG
│
Is the user asking to implement a specific backlog step or write code?
├─ YES → Is the step marked "Needs Claude Opus"?
│         ├─ YES → ARCH (escalate)
│         └─ NO  → IMPL
│
Is the user asking about design decisions, trade-offs, or interfaces?
├─ YES → ARCH
│
Is the user asking about ML methodology, papers, or experiments?
├─ YES → RSRCH
│
Is the user asking to run paper trials, check IBKR, or execute milestones?
├─ YES → OPS
│
Is the user asking to clean up docs, review queues, or consolidate?
├─ YES → REVIEW
│
Ambiguous?
└─ Default to REVIEW (safest — read-only, no code changes)
```

---

## §6 Session Continuity Patterns

> §6a defines multi-session continuity patterns.
> §6b defines agent-type handoff protocol.
> §6c provides the handoff packet template.
> §6d defines the pre-handoff consistency gate.

### §6a Continuity Patterns

#### Pattern A: Multi-Session Implementation Sprint

When implementing a large feature across multiple sessions:

1. **Session 1 (IMPL):** Implement core module + tests. Log entry notes "Part 1 of N".
2. **Session 2 (IMPL):** Read Session 1 log entry. Continue from where it left off.
3. **Session N (IMPL):** Complete final piece. Update backlog step to COMPLETED.

**Key rule:** Each session must leave the codebase in a passing-test state. No partial implementations that break tests across session boundaries.

#### Pattern B: Design → Implement Handoff

When an architecture session feeds into an implementation session:

1. **Session 1 (ARCH):** Produce ADR + spec. Log entry includes "Ready for IMPL: Step N".
2. **Session 2 (IMPL):** Read Session 1 log entry. Find the ADR/spec. Implement.

**Key rule:** The ARCH session must produce machine-readable output (ADR, spec with acceptance criteria) — not just chat conclusions.

#### Pattern C: Debug → Fix → Verify

When a debug session discovers a non-trivial issue:

1. **Session 1 (DEBUG):** Diagnose root cause. If fix is straightforward, apply it. If structural, escalate.
2. **Session 2 (ARCH or IMPL):** Read Session 1 diagnosis. Implement the fix.
3. **Session 3 (DEBUG):** Verify the fix holds. Update test baseline.

#### Pattern D: Operations → Evidence → Closure

When running MO-* milestones:

1. **Session 1 (OPS):** Run the trial/check. Record evidence in burn-in tracker.
2. **Session 2 (OPS):** Run next trial. Record evidence. Check if milestone criteria met.
3. **Session 3 (REVIEW):** Review all evidence. Close the MO-* milestone. Update §9.

---

### §6b Agent-Type Handoff Protocol

> When a session reaches the boundary of its scope guard, the agent must hand off
> to the correct agent type rather than exceeding its mandate.
> This section defines **when** to hand off, **what** must travel with the handoff,
> and the **expected artifact** from the receiving agent.

### Handoff Matrix

| From | To | Trigger | Required in Handoff Packet | Expected Artifact |
|---|---|---|---|---|
| **IMPL** → **ARCH** | Step requires a structural decision not described in the step definition | Diagnosis of why the current pattern is insufficient + candidate options identified | ADR or RFC entry in `PROJECT_DESIGN.md` |
| **IMPL** → **DEBUG** | A test fails during implementation and root cause is unclear | Failing test output, reproduction command, files changed so far | Bug fix commit or TD-* entry if structural |
| **DEBUG** → **IMPL** | Root cause identified and fix is straightforward code change | Root cause diagnosis, affected files, proposed fix outline | Code fix + passing test suite |
| **DEBUG** → **ARCH** | Fix requires structural change (new module, interface change, invariant relaxation) | Root cause diagnosis + explanation of why a code-level fix is insufficient | ADR with decision + new backlog step(s) |
| **ARCH** → **IMPL** | Design decision made, ready for implementation | ADR/RFC reference number, acceptance criteria, scope (files to create/modify) | Completed backlog step with tests |
| **RSRCH** → **IMPL** | Research methodology approved, needs runtime integration | Spec reference, promotion gate evidence, bridge file path | Code in `src/` via `research/bridge/` |
| **OPS** → **DEBUG** | Burn-in or paper trial fails unexpectedly | Run evidence (JSON artifacts, logs), failure symptoms, run parameters | Root cause + fix or TD-* entry |
| **REVIEW** → **IMPL** | Doc review reveals an actionable code gap | Description of gap, affected files, proposed resolution | Code fix or new backlog step |
| **Any** → **REVIEW** | Session changed >3 LPDD docs but did not run consistency check | List of modified docs | Consistency check pass + any drift fixes |

### Handoff Protocol Steps

1. **Recognise the boundary** — if your next action would violate your session type's scope guard (§2), stop.
2. **Prepare the handoff packet** — fill in the template from §6c below. Do not skip fields.
3. **Append a SESSION_LOG.md entry** — mark the handoff explicitly: `**Handoff:** TYPE → TYPE. See packet below.`
4. **Run the pre-handoff gate** if handing off from ARCH or REVIEW (see §6d).
5. **Commit your work** — the codebase must be in a passing-test state (or explicitly note that tests are known-broken and why).
6. **In VS Code:** The receiving agent reads `SESSION_LOG.md` (last entry) to pick up the handoff packet and continue.

### VS Code Multi-Agent Session Flow

VS Code supports multiple agent types (Local Copilot, Background agents in worktrees, Cloud agents on PRs).
When handing off between agents in VS Code:

1. **Select the target agent type** from the chat dropdown — this creates a new session carrying conversation history.
2. **The original session is archived** — the receiving agent gets the full context but starts in its own session.
3. **Both sessions appear in the Session List** (`chat.viewSessions.enabled: true`) for audit and reference.
4. **Parallel sessions are supported** — an IMPL session and a REVIEW session can run simultaneously on different files.

---

### §6c Handoff Packet Template

> Copy this template into `SESSION_LOG.md` when handing off between agent types.
> All fields are mandatory. If a field is genuinely N/A, write "N/A" explicitly.

```markdown
### Handoff Packet: [FROM_TYPE] → [TO_TYPE]

**Goal for receiving agent:** One-sentence description of what the next session should accomplish.

**What was done:**
- Bullet list of completed work in this session

**What remains:**
- Bullet list of specific next actions for the receiving agent

**Blockers / open questions:**
- Any ambiguities, missing information, or decisions that must be made

**Changed files (this session):**
- path/to/file — what changed

**Commands run:**
- `command` — outcome (pass/fail/output summary)

**Evidence links:**
- Path to test output, burn-in JSON, ADR reference, or other artifacts

**Test baseline:** NNN passing (or "tests known-broken: reason")
```

---

### §6d Pre-Handoff Gate

Before handing off from **ARCH** or **REVIEW** sessions (which modify governance docs),
run the LPDD consistency checker to ensure no drift:

```bash
python scripts/lpdd_consistency_check.py --root .
```

**Gate rules:**
- If the check **passes** (0 issues): proceed with handoff.
- If the check **fails**: fix the issues before handing off. Do not pass broken governance state to the next agent.
- If the checker is unavailable: manually verify that `PROJECT_DESIGN.md`, `IMPLEMENTATION_BACKLOG.md`, `SESSION_LOG.md`, and `DOCUMENTATION_INDEX.md` all have current `Last Updated` fields and consistent counts.

---

## §7 VS Code Integration

### Snippets

Use the VS Code snippets defined in `.vscode/session.code-snippets` to quickly
create session log entries. Type the prefix in any `.md` file:

| Prefix | Description |
|---|---|
| `slog` | Full session log entry template |
| `slog-short` | One-line session log entry |
| `slog-queue` | Queue changes sub-section |

### Tasks

The workspace task `Session: New Entry` (in `.vscode/tasks.json`) opens
`SESSION_LOG.md` and inserts a timestamped template.

### Recommended Workflow

1. **Start of session:** Open `SESSION_LOG.md`, read last 2–3 entries
2. **Identify session type** using §5 decision tree
3. **Load context** per §3 priority table
4. **Do the work**
5. **End of session:** Use `slog` snippet to append entry to `SESSION_LOG.md`
6. **Commit** with message: `docs(session): TYPE — brief summary`

---

## §8 Session Log Maintenance

### Rotation
When `SESSION_LOG.md` exceeds **50 entries**, archive the oldest 40 to
`archive/session_logs/SESSION_LOG_YYYY_MM.md` and keep the most recent 10
in the active file. This keeps the context-loading cost manageable.

### Metrics (Optional)
Track session statistics monthly by counting entries per type:

```markdown
## Monthly Summary — YYYY-MM
| Type | Count | Avg Duration | Key Outcomes |
|---|---|---|---|
| IMPL | 12 | ~45 min | Steps 64–66 completed |
| ARCH | 3 | ~30 min | ADR-016, ADR-017 |
| DEBUG | 5 | ~15 min | 3 test regressions fixed |
| OPS | 4 | ~20 min | MO-2 burn-in 2/3 complete |
| RSRCH | 2 | ~60 min | 2 papers reviewed |
| REVIEW | 1 | ~20 min | Queue hygiene pass |
```

---

## §9 Quick Reference Card

**Starting a session?**
1. Read `SESSION_LOG.md` — last 2 entries minimum
2. Identify your session type → §2
3. Load files per §3 priority table
4. Follow the scope guard for your type

**Ending a session?**
1. Append entry to `SESSION_LOG.md` using `slog` snippet
2. Include: goal, outcome, queue changes, files modified, test baseline, handoff notes
3. Commit: `docs(session): TYPE — summary`

**Unsure which type?**
→ Use the decision tree in §5

**Context window too small?**
→ Use §3 priority table — load mandatory items first, skip lower priorities

**Session seems to span two types?**
→ Split into two entries. A single session can log multiple types if the work naturally shifts (e.g., DEBUG that leads to a quick IMPL fix).

---

## §10 LPDD End-of-Session Sync Checklist

Before ending any non-trivial session, run this quick consistency check:

1. **Backlog status sync**
   - If a step changed state, update `IMPLEMENTATION_BACKLOG.md` status and completion notes
   - Refresh executive summary counts if totals changed

2. **Design log sync**
   - If structural/design decisions changed, update `PROJECT_DESIGN.md` (§3 ADR, §4 RFC, or §6 Evolution Log)

3. **Session handoff sync**
   - Append a `SESSION_LOG.md` entry with goal, outcome, queue changes, files modified, and test baseline

4. **Consistency check (optional but recommended)**
   - Run: `python scripts/lpdd_consistency_check.py --root .`
   - Ensure no missing required docs, malformed summary lines, or missing `Last Updated` fields

