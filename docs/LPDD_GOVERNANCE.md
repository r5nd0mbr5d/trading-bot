# LPDD Governance — Trading-Bot

**Version:** 1.0  
**Last Updated:** Feb 28, 2026  
**Status:** ACTIVE  
**Related:** `docs/SESSION_TOPOLOGY.md`, `src/bridge/paios_types.py`, `PROJECT_DESIGN.md`

---

## §1 What Is LPDD?

**Lightweight Process-Driven Development (LPDD)** is the governance model used
by this trading-bot to keep LLM-assisted development consistent, auditable, and
free from architectural drift.

LPDD answers three questions at the start of every agent session:

1. **What type of session is this?** (classify using `SESSION_TOPOLOGY.md` §5)
2. **What context must be loaded?** (pre-read list from `SESSION_TOPOLOGY.md` §3)
3. **What is out of scope?** (scope guard from `SESSION_TOPOLOGY.md` §4)

It answers three questions at the end of every session:

1. **What was completed?** (update `IMPLEMENTATION_BACKLOG.md` step status)
2. **What changed architecturally?** (append ADR to `PROJECT_DESIGN.md §3` if needed)
3. **What does the next session need to know?** (append `SESSION_LOG.md` entry + emit handoff packet)

---

## §2 Session Type Scoping Rules

Each session type enforces hard boundaries so that implementation work never
accidentally alters risk parameters, and research sessions never touch live code.

| Type   | Can do | Cannot do |
|--------|--------|-----------|
| `IMPL` | Write strategy/broker/indicator code, update tests, mark backlog steps COMPLETED | Change risk parameters, author ADRs, make unspecified architectural decisions |
| `ARCH` | Design modules, author ADRs and RFCs, update backlog with new steps | Modify strategy logic directly, submit orders |
| `RSRCH`| Run backtests, analyse reports, modify `research/` | Modify `src/` live-trading code, change `config/settings.py` live parameters |
| `OPS`  | Edit config, manage CI/CD, update dependencies | Modify strategy or risk logic |
| `DEBUG`| Fix the specific bug, add regression test | Refactor unrelated modules, change architecture |
| `REVIEW`| Comment, approve, request changes | Merge code or directly modify files |

Full scope guard tables are in `docs/SESSION_TOPOLOGY.md` §4.

---

## §3 How Handoffs Work

A **handoff** is the structured transfer of context from one session to the next.
It prevents information loss across stateless LLM sessions.

### Handoff Steps

1. **Outgoing session** constructs a `HandoffPacket`
   (see `src/bridge/paios_types.py`) with:
   - `source_session_type` / `target_session_type`
   - `summary` — what was done, what remains
   - `context_files` — files the next session must pre-read
   - `metadata` — step number, test counts, flags

2. **Outgoing session** calls `make_handoff_event(packet)` from
   `src/bridge/hooks.py` and logs the result to the audit trail.

3. **Outgoing session** appends a `SESSION_LOG.md` entry following the `slog`
   VS Code snippet template.

4. **Incoming session** reads `SESSION_LOG.md` (last 2–3 entries), identifies
   its type from the decision tree in `docs/SESSION_TOPOLOGY.md` §5, loads the
   pre-read list, and respects the scope guard.

### Handoff Packet Example

```python
from src.bridge.paios_types import HandoffPacket, SessionType
from src.bridge.hooks import make_handoff_event

packet = HandoffPacket(
    source_session_type=SessionType.IMPL,
    target_session_type=SessionType.REVIEW,
    summary="Step 63 done. CoinbaseBroker implemented. All 551 tests pass.",
    context_files=[
        "src/execution/broker.py",
        "tests/test_coinbase_broker.py",
        "IMPLEMENTATION_BACKLOG.md",
    ],
    metadata={"step": 63, "tests_passed": 551, "lpdd_updated": True},
)
event = make_handoff_event(packet)
# → emit event to audit trail / PAIOS orchestrator
```

---

## §4 PAIOS Integration

The `src/bridge/` package is the trading-bot's interface to the
[PAIOS](https://github.com/r5nd0mbr5d/PAIOS) orchestration system.

| Component | File | Purpose |
|-----------|------|---------|
| Session types | `src/bridge/paios_types.py` | `SessionType` enum mirrors PAIOS |
| Handoff model | `src/bridge/paios_types.py` | `HandoffPacket` dataclass |
| Session config | `src/bridge/paios_types.py` | `SessionConfig` dataclass |
| Prompt classifier | `src/bridge/session_classifier.py` | `classify_prompt()` heuristic |
| Event hooks | `src/bridge/hooks.py` | PAIOS-compatible event payloads |

PAIOS registers `session.classify` and `session.handoff` as actions.
The trading-bot emits compatible events via `make_handoff_event()` so PAIOS
can track inter-session transitions without tight coupling.

---

## §5 Consistency Contract

The session types defined in `docs/SESSION_TOPOLOGY.md` **must** match the
`SessionType` enum in `src/bridge/paios_types.py` at all times.

The test suite in `tests/test_bridge.py` validates this contract: if a new
session type is added to the enum, the tests will catch missing classifier
coverage.

### Adding a New Session Type

1. Add the new value to `SessionType` in `src/bridge/paios_types.py`
2. Add routing keywords in `src/bridge/session_classifier.py`
3. Add a row to the session type table in `docs/SESSION_TOPOLOGY.md` §2
4. Add the pre-read list in §3, scope guard table in §4, and handoff matrix row in §6
5. Add a column/row to the handoff matrix in §6
6. Update this document §2 table
7. Add tests in `tests/test_bridge.py`
8. Author an ADR in `PROJECT_DESIGN.md §3`

### Removing a Session Type

Removing a session type is a breaking change. Follow the same 8-step process
and supersede any ADR that originally introduced the type.

---

## §6 LPDD Evolution Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-28 | Initial LPDD governance doc created; `src/bridge/` package added | Copilot |
