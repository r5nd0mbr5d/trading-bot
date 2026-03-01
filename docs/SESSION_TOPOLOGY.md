# Session Topology — Trading-Bot PAIOS Integration

**Version:** 1.0  
**Last Updated:** Feb 28, 2026  
**Status:** ACTIVE  
**Related:** `src/bridge/paios_types.py`, `docs/LPDD_GOVERNANCE.md`, root `SESSION_TOPOLOGY.md`

---

## §1 Purpose

This document extends the root-level `SESSION_TOPOLOGY.md` with trading-bot-specific
session type definitions adapted for PAIOS-orchestrated agent handoffs.  
It ensures every Copilot or Claude session knows:

1. Which **pre-read files** to load before acting
2. What **scope boundaries** apply (what it can and cannot change)
3. How to emit a structured **handoff packet** when finished

The session types in this file map 1-to-1 to the `SessionType` enum defined in
`src/bridge/paios_types.py`. Any change to one **must** be reflected in the other
(consistency contract — see §7).

---

## §2 Session Types

| Type | Purpose | Primary Agent |
|------|---------|---------------|
| `IMPL` | Strategy implementation, indicator code, broker adapters | GitHub Copilot |
| `ARCH` | System architecture, pipeline design, ADR authoring | Claude Opus |
| `RSRCH` | Market research, backtest analysis, experiment evaluation | Claude Opus |
| `OPS` | Deployment, CI/CD, configuration management | GitHub Copilot |
| `DEBUG` | Bug investigation (data gaps, order failures, test failures) | GitHub Copilot |
| `REVIEW` | Code review, strategy validation, LPDD step sign-off | Claude Opus |

---

## §3 Pre-Read Lists

### IMPL — Implementation

Load before writing any code:

1. `SESSION_LOG.md` (last 2 entries)
2. `IMPLEMENTATION_BACKLOG.md` → Copilot Task Queue section
3. `.python-style-guide.md`
4. `src/trading/loop.py`
5. `src/strategies/` (directory listing + any strategy being modified)
6. The specific source files listed in the backlog step's **Scope** field

### ARCH — Architecture

Load before designing or refactoring:

1. `SESSION_LOG.md` (last 2 entries)
2. `PROJECT_DESIGN.md` (all ADRs and active RFCs)
3. `IMPLEMENTATION_BACKLOG.md` (full context)
4. `src/data/models.py`
5. `src/risk/manager.py`
6. `src/execution/broker.py`
7. `src/trading/loop.py`

### RSRCH — Research

Load before analysing or evaluating:

1. `SESSION_LOG.md` (last 2 entries)
2. `IMPLEMENTATION_BACKLOG.md` (research tasks section)
3. `backtest/engine.py`
4. Relevant strategy file(s)
5. Any existing backtest results in `reports/`

### OPS — Operations

Load before configuring or deploying:

1. `SESSION_LOG.md` (last 2 entries)
2. `config/settings.py`
3. `pyproject.toml`
4. `requirements.txt`
5. `.github/` CI/CD workflow files (if present)

### DEBUG — Debugging

Load before investigating failures:

1. `SESSION_LOG.md` (last 2 entries)
2. The failing test file
3. The source file under investigation
4. `src/data/models.py` (data contract)
5. Relevant logs or error traces

### REVIEW — Review

Load before reviewing:

1. `SESSION_LOG.md` (last 2 entries)
2. `PROJECT_DESIGN.md` §3 (ADRs) for design intent
3. `.python-style-guide.md`
4. All files changed in the PR or step being reviewed
5. Associated test files

---

## §4 Scope Guards

Each session type has hard boundaries to keep sessions focused.

### IMPL
| Action | Allowed |
|--------|---------|
| Modify strategy logic in `src/strategies/` | ✅ Yes |
| Modify broker adapters in `src/execution/` | ✅ Yes |
| Add/update tests in `tests/` | ✅ Yes |
| Change risk parameters in `src/risk/manager.py` | ❌ No |
| Change broker config credentials in `config/settings.py` | ❌ No |
| Author new ADRs or RFCs | ❌ No |
| Make architectural decisions not described in backlog step | ❌ No |

### ARCH
| Action | Allowed |
|--------|---------|
| Author new ADRs in `PROJECT_DESIGN.md` | ✅ Yes |
| Design new module layouts and interfaces | ✅ Yes |
| Update `IMPLEMENTATION_BACKLOG.md` with new steps | ✅ Yes |
| Modify existing strategy logic directly | ❌ No |
| Submit or modify broker orders | ❌ No |

### RSRCH
| Action | Allowed |
|--------|---------|
| Read all source files | ✅ Yes |
| Run backtests and generate reports | ✅ Yes |
| Modify `research/` directory | ✅ Yes |
| Modify live-trading source in `src/` | ❌ No |
| Modify `config/settings.py` live parameters | ❌ No |

### OPS
| Action | Allowed |
|--------|---------|
| Edit `config/settings.py` (non-strategy fields) | ✅ Yes |
| Edit `pyproject.toml`, `requirements.txt` | ✅ Yes |
| Manage CI/CD configurations | ✅ Yes |
| Modify strategy logic in `src/strategies/` | ❌ No |
| Modify risk logic in `src/risk/` | ❌ No |

### DEBUG
| Action | Allowed |
|--------|---------|
| Fix the specific bug under investigation | ✅ Yes |
| Add regression test for the fix | ✅ Yes |
| Refactor unrelated modules | ❌ No |
| Change architecture or data models unrelated to the bug | ❌ No |

### REVIEW
| Action | Allowed |
|--------|---------|
| Leave review comments and feedback | ✅ Yes |
| Approve or request changes on backlog steps | ✅ Yes |
| Merge code or modify files directly | ❌ No |

---

## §5 Routing Decision Tree

Use this decision tree to classify an incoming prompt into a session type.
The `session_classifier.classify_prompt()` function implements this logic in code.

```
Is the prompt about deployment, CI, docker, environment config, or setup?
  └─ YES → OPS

Is the prompt about a bug, error, crash, fix, or broken test?
  └─ YES → DEBUG

Is the prompt about reviewing, auditing, checking, validating, or approving?
  └─ YES → REVIEW

Is the prompt about research, backtesting, analysing, comparing, or studying?
  └─ YES → RSRCH

Is the prompt about architecture, design, refactoring, or system patterns?
  └─ YES → ARCH

Default
  └─ IMPL
```

**Priority order:** OPS > DEBUG > REVIEW > RSRCH > ARCH > IMPL  
The first matching rule wins.

---

## §6 Handoff Matrix

This matrix shows which session-type transitions are allowed and which
require an intermediate ARCH or REVIEW step.

| From \ To | IMPL | ARCH | RSRCH | OPS | DEBUG | REVIEW |
|-----------|------|------|-------|-----|-------|--------|
| **IMPL**  | ✅   | ✅   | ✅    | ✅  | ✅    | ✅     |
| **ARCH**  | ✅   | ✅   | ✅    | ✅  | ✅    | ✅     |
| **RSRCH** | ✅   | ✅   | ✅    | ❌  | ❌    | ✅     |
| **OPS**   | ✅   | ✅   | ❌    | ✅  | ✅    | ✅     |
| **DEBUG** | ✅   | ✅   | ❌    | ✅  | ✅    | ✅     |
| **REVIEW**| ✅   | ✅   | ✅    | ✅  | ✅    | ✅     |

> **Note:** RSRCH→OPS and RSRCH→DEBUG transitions require explicit operator
> approval because research sessions are read-only and should not directly
> trigger operational or debugging changes.

### Handoff JSON Template

When a session completes, emit a `session.handoff` event using
`src/bridge/hooks.make_handoff_event()`.  The packet should follow this shape:

```json
{
  "source_session_type": "impl",
  "target_session_type": "review",
  "summary": "Implemented CoinbaseBroker (Step 63). All 551 tests pass.",
  "context_files": [
    "src/execution/broker.py",
    "tests/test_coinbase_broker.py",
    "config/settings.py"
  ],
  "parent_job_id": "job-paios-12345",
  "metadata": {
    "step": 63,
    "tests_passed": 551,
    "lpdd_updated": true
  }
}
```

---

## §7 Consistency Contract

The six session types defined in §2 **must** remain in sync with
`SessionType` enum values in `src/bridge/paios_types.py`.

| This document | `SessionType` enum value |
|---------------|--------------------------|
| `IMPL`        | `"impl"`                 |
| `ARCH`        | `"arch"`                 |
| `RSRCH`       | `"rsrch"`                |
| `OPS`         | `"ops"`                  |
| `DEBUG`       | `"debug"`                |
| `REVIEW`      | `"review"`               |

Any addition or removal of a session type requires simultaneous updates to:
1. This document (§2–§6)
2. `src/bridge/paios_types.py` — `SessionType` enum
3. `src/bridge/session_classifier.py` — keyword routing
4. `docs/LPDD_GOVERNANCE.md` — governance rules
5. `SESSION_LOG.md` — handoff notes
