# ARCH Session Decision Package — 2026-02-26

**Session type**: ARCH → RSRCH → REVIEW
**Scope**: All Opus-gated intake items staged into single decision-and-spec pass
**Decision standards applied**: Reliability > migration breadth; read-only + paper-only defaults; incremental + reversible outcomes

---

## Output 1: Executive Verdict (8–12 bullets)

1. **Client-ID namespace (IBKR-DKR-04)**: ACCEPT as ADR-018. The two-band policy (runtime [1–499], assistant [5000–5099]) from Step 79 is sound. Formalize and add a lightweight guard in `IBKRBroker._connect()` to validate the starting client-id falls within its expected band.

2. **Reconnect lifecycle (RIBAPI-02)**: DEFER as RFC-007 (PROPOSED). Current process-restart approach is sufficient for MO-2 paper sessions. A formal state machine adds complexity that is not justified until we have evidence of mid-session connection drops. Revisit when daemon (Step 46) runs continuously for >8 hours.

3. **ib_async migration (IBASYNC-01)**: REJECT. ADR-011 trigger conditions have not been met. ib_insync still works with current TWS API. Migration is high-coupling, high-risk, and provides no measurable near-term reliability gain. No action needed.

4. **Session record/replay (YATWS-03)**: DEFER to post-MO-2. Valuable for fill-detection debugging but not critical-path. No architectural objection; can be picked up in a future IMPL session after paper sessions are signed off.

5. **Rust sidecar (YATWS-05 + RIBAPI-05)**: REJECT. No measurable near-term reliability gain. Python ib_insync handles current throughput. Operational complexity of maintaining a Rust+Python boundary is disproportionate to the platform's maturity. Not on the roadmap unless sub-millisecond latency becomes a requirement.

6. **Assistant safety policy (IBMCP-02)**: ACCEPT as ADR-019. Formalize the paper-only hard gate & read-only default for all assistant/MCP-facing surfaces. Existing Steps 79/81 already comply; the ADR codifies the policy for future capabilities.

7. **Steps 79/81 compatibility (IBMCP-04/05)**: CONFIRMED. Both `assistant_tool_policy.py` and `report_schema_adapter.py` are compatible with the proposed safety policy. No changes needed.

8. **Step 62 MLP architecture review**: APPROVED with two required additions (early stopping callback + input normalization). Layer sizes (128→64→32), Dropout(0.3), ExponentialLR(γ=0.9), and skorch wrapper are all sound. Opus gate CLEARED — Copilot may implement once XGBoost has R2 evidence.

9. **Step 67 RL feasibility**: DEFER (conditional no-go). RL is premature before supervised pipeline reaches R3. Four explicit go/no-go conditions defined. Design memo filed at `research/tickets/rl_feasibility_spike.md`.

10. **Step 68 deep-sequence governance**: ACCEPT. Governance gate defined with quantitative thresholds in `research/tickets/deep_sequence_governance_spike.md`. Current LSTM/MLP sequencing preserved. CNN/Transformer/hybrid NOT ADMITTED until evidence thresholds are met.

11. **Step 32 unblock criteria**: Formally documented. Dependency chain is MO-7/MO-8 → Step 62 (MLP) → Step 32 (LSTM). Step 62 Opus gate is now cleared; remaining blockers are MO-7/MO-8 evidence milestones.

12. **Synthetic order-stream admissibility (Step 83)**: REJECT for promotion gates. Synthetic streams may be used for infrastructure testing and CI but MUST NOT satisfy R1–R4 evidence requirements. Anti-substitution control to be added to RESEARCH_PROMOTION_POLICY.md.

---

## Output 2: Decision Matrix

| ID | Intake Ticket | Stage | Verdict | ADR/RFC | Copilot Task? | Operator Task? | Blocker? |
|---|---|---|---|---|---|---|---|
| A1 | IBKR-DKR-04 | A | **ACCEPT** | ADR-018 | Yes: add band guard to `_connect()` | No | No |
| A2 | RIBAPI-02 | A | **DEFER** | RFC-007 (PROPOSED) | No | No | Deferred |
| A3 | IBASYNC-01 | A | **REJECT** | — (ADR-011 unchanged) | No | No | No |
| B1 | YATWS-03 | B | **DEFER** | — | No | No | Deferred |
| B2 | YATWS-05+RIBAPI-05 | B | **REJECT** | — | No | No | No |
| C1 | IBMCP-02 | C | **ACCEPT** | ADR-019 | No (policy doc only) | No | No |
| C2 | IBMCP-04/05 | C | **CONFIRM** | — | No | No | No |
| D1a | Step 62 (MLP gate) | D | **APPROVED** | — | Yes: implement MLP baseline | No | Cleared |
| D1b | Step 32 (LSTM gate) | D | **KEEP BLOCKED** | — | No (gated behind Step 62) | MO-7/MO-8 | Yes |
| D2 | Step 67 (RL) | D | **DEFER** | — | No | No | Deferred |
| D3 | Step 68 (deep-seq gov.) | D | **ACCEPT** | — | No | No | No |
| D4 | Step 83 (synthetic streams) | D | **REJECT** (for gates) | — | No | No | No |

---

## Output 3: Spec Artifacts Created

### ADR-018: Client-ID Namespace Policy

- **Status**: ACCEPTED
- **Context**: Multiple IBKR client types (runtime, assistant, operator tools) share a single TWS gateway. Client-id collisions cause connection failures. Step 79 (`assistant_tool_policy.py`) introduced band ranges but they were not formalized as architecture policy.
- **Decision**: Formalize two-band client-id namespace:
  - **Runtime band**: [1–499] — production trading loop, paper sessions, burn-in scripts
  - **Assistant band**: [5000–5099] — MCP tools, assistant integrations, diagnostic probes
  - **Reserved**: [500–4999] — future use (e.g., monitoring, research runners)
  - **Reserved**: [5100+] — future use
- **Enforcement**: `IBKRBroker._connect()` must validate that the starting `clientId` falls within the expected band for its execution context. If `clientId` is in assistant range and execution context is runtime (or vice versa), log `ERROR` and refuse to connect.
- **Existing compliance**: `assistant_tool_policy.py` (Step 79) already validates bands for assistant tools. `run_step1a_burnin_auto_client.ps1` uses `InitialClientId=5000` (assistant band).
- **Consequences**: Client-id collision recovery (increment by 1) must stay within the originating band. If all IDs in a band are exhausted, fail with a clear error rather than spilling into the adjacent band.
- **Supersedes**: None (new policy)

### ADR-019: Assistant Tool Safety Policy

- **Status**: ACCEPTED
- **Context**: Assistant tools (MCP servers, Copilot agents) interact with the trading platform's data and potentially its execution layer. Without explicit boundaries, a future assistant capability could accidentally submit live orders or expose credentials.
- **Decision**: All assistant-facing surfaces must comply with these mandatory constraints:
  1. **Paper-only hard gate**: No assistant tool may submit orders to a live (non-paper, non-sandbox) broker account. The `is_paper_account()` check in `IBKRBroker` and `coinbase_sandbox`/`binance_testnet` flags must be verified before any order submission path is exposed to assistants.
  2. **Read-only default**: All report, data, and status resources exposed to assistants are read-only. Write operations require explicit justification and a new ADR.
  3. **Client-id isolation**: Per ADR-018, assistant tools use the [5000–5099] band and must never overlap with the runtime band.
  4. **No credential access**: Assistants must not read `.env`, credential stores, API keys, or private keys. All credential handling is via the runtime configuration layer.
  5. **Audit trail**: Every assistant tool invocation must be logged with: timestamp (UTC), tool name, parameters, result status. Log level: INFO.
  6. **Scope guard**: Each assistant agent file (`.github/agents/*.agent.md`) must declare its permitted operations. Undeclared operations are implicitly denied.
- **Existing compliance**: `assistant_tool_policy.py` (Step 79) enforces rules 3–4. `report_schema_adapter.py` (Step 81) enforces rule 2. No existing code violates rule 1 (no assistant order submission exists).
- **Consequences**: Any future assistant capability that touches the execution layer must receive an explicit ADR amendment before implementation.

### RFC-007: Reconnect Lifecycle State Contract (PROPOSED)

- **Status**: PROPOSED
- **Context**: `IBKRBroker._connect()` is a one-shot method called in `__init__`. If the connection drops mid-session, all broker methods return empty/default values with no automatic reconnection. The daemon (Step 46) handles this at the process level by restarting, but future long-running sessions may benefit from a formal reconnect state machine.
- **Proposed design**: Define a connection state enum: `DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING → ERROR → DISCONNECTED`. Implement an optional `auto_reconnect` mode with configurable backoff (initial=5s, max=60s, factor=2). Track reconnection attempts in a counter for observability.
- **Trigger to accept**: Evidence of mid-session connection drops during MO-2 paper sessions, OR daemon running continuously for >8 hours with connection instability.
- **Impact if accepted**: Moderate refactor of `IBKRBroker._connect()` and lifecycle methods. Must preserve existing behavior when `auto_reconnect=False` (default).

---

## Output 4: Copilot Handoff Packet (max 5 tasks)

### Task 1: ADR-018 Band Guard in IBKRBroker._connect()
**Priority**: HIGH
**Files**: `src/execution/ibkr_broker.py`, `tests/test_ibkr_broker.py`
**Spec**: Add a band validation check at the top of `IBKRBroker._connect()`. Import the runtime band boundaries from `assistant_tool_policy.py` or define them as module constants. If the starting `clientId` is outside [1–499] AND outside [5000–5099], log `ERROR` and set `self._ib = None`. If incrementing on collision would exit the current band, stop retrying. Tests: verify band enforcement, verify collision recovery stays within band.
**Depends on**: Nothing — immediately actionable.
**Estimated effort**: 2–3 hours

### Task 2: Implement Step 62 (MLP Baseline)
**Priority**: HIGH (Opus gate now cleared)
**Files**: Per Step 62 scope in IMPLEMENTATION_BACKLOG.md
**Architecture review addenda** (mandatory):
- Add `skorch.callbacks.EarlyStopping(patience=10, monitor='valid_loss')` to the NeuralNetBinaryClassifier
- Add `sklearn.preprocessing.StandardScaler` in the pipeline before the MLP, OR add `torch.nn.BatchNorm1d` as the first layer (prefer StandardScaler for simplicity)
- Use `batch_size=128` (appropriate for tabular financial data)
- Layer sizes (128→64→32), Dropout(0.3), ReLU, ExponentialLR(γ=0.9) all APPROVED as specified
- BCEWithLogitsLoss with `pos_weight` per Step 59 class-imbalance handling — REQUIRED
**Depends on**: XGBoost R2 evidence (MO-7 partial). Copilot CAN implement the code now; evaluation depends on R2 pipeline.
**Estimated effort**: 5–8 hours

### Task 3: Anti-Substitution Control in RESEARCH_PROMOTION_POLICY.md
**Priority**: MEDIUM
**Files**: `research/specs/RESEARCH_PROMOTION_POLICY.md`
**Spec**: Add a new section "§X Synthetic Data Admissibility" stating: (1) Synthetic order streams may be used for infrastructure testing, CI, schema validation, and smoke tests. (2) Synthetic data MUST NOT satisfy R1, R2, R3, or R4 evidence requirements. (3) Any research artifact submitted for promotion must include a `data_source` field with value `real_market` or `synthetic`. Artifacts with `data_source: synthetic` are automatically excluded from promotion gate evaluation. (4) Falsifying the `data_source` field constitutes an integrity violation per Step 65 claim-integrity gate.
**Depends on**: Nothing — immediately actionable.
**Estimated effort**: 1–2 hours

### Task 4: Update Step 67 Status to COMPLETED
**Priority**: LOW
**Files**: `IMPLEMENTATION_BACKLOG.md`
**Spec**: Mark Step 67 as COMPLETED with date 2026-02-26. Reference `research/tickets/rl_feasibility_spike.md` as the deliverable. Verdict: DEFER (conditional no-go). Update executive summary counts.
**Depends on**: Nothing — immediately actionable.
**Estimated effort**: 15 minutes

### Task 5: Update Step 68 Status to COMPLETED
**Priority**: LOW
**Files**: `IMPLEMENTATION_BACKLOG.md`
**Spec**: Mark Step 68 as COMPLETED with date 2026-02-26. Reference `research/tickets/deep_sequence_governance_spike.md` as the deliverable. Verdict: ACCEPT. Update executive summary counts.
**Depends on**: Nothing — immediately actionable.
**Estimated effort**: 15 minutes

---

## Output 5: Operator Handoff Packet

### MO-2: Paper Session Scheduling (CRITICAL PATH)
**Status**: OPEN — current blocker for all forward progress
**Action required**: Schedule 3 consecutive in-window paper sessions (08:00–16:00 UTC, Mon–Fri) using `scripts/run_step1a_burnin_auto_client.ps1`. Current evidence shows `non_qualifying_test_mode=true` — sessions are running outside LSE hours.
**Evidence needed**: `reports/burnin/` artefacts with `signoff_ready=true` × 3 consecutive sessions.
**Unblock chain**: MO-2 → MO-5/MO-6 (human review) → promotion to live.

### MO-7: R1/R2 Residuals + R3 Runtime Evidence
**Status**: OPEN
**Action required**: After XGBoost walk-forward experiments are run, commit real experiment outputs to `research/experiments/` with reviewer name and date. The `RESEARCH_PROMOTION_POLICY.md` requires dated artefact links.
**Unblock chain**: MO-7 → Step 62 MLP evaluation → Step 32 LSTM.
**Note**: Step 62 implementation can proceed NOW (Opus gate cleared), but its evaluation depends on MO-7 evidence being available for side-by-side comparison.

### MO-8: Production-Run Sign-Off
**Status**: OPEN
**Action required**: Once MO-7 evidence is committed, sign off with reviewer name and date in `research/specs/FEATURE_LABEL_SPEC.md`. This is a human accountability requirement — LLMs cannot self-sign.
**Unblock chain**: MO-8 → Step 32 LSTM.

### ADR-018/019 Acknowledgment
**No operator action required.** These are architecture policies. Operator should be aware that:
- Client-ID bands are now formalized (runtime [1–499], assistant [5000–5099])
- All assistant tools are paper-only and read-only by default. Any live execution capability requires a new ADR and operator sign-off.

---

## Output 6: Blocker Register

| Blocker ID | Description | Blocked Items | Unblock Criteria | Owner |
|---|---|---|---|---|
| **BLK-001** | MO-2 paper sessions not in-window | MO-5, MO-6, live promotion | 3× `signoff_ready=true` during 08:00–16:00 UTC Mon–Fri | Operator |
| **BLK-002** | MO-7 R1/R2 residual evidence missing | Step 62 evaluation, Step 32 | Real XGBoost experiment outputs committed with reviewer/date | Operator |
| **BLK-003** | MO-8 production-run sign-off pending | Step 32 | Reviewer sign-off in FEATURE_LABEL_SPEC.md | Operator |
| **BLK-004** | Step 62 MLP gate (PR-AUC/Sharpe) | Step 32 | MLP achieves PR-AUC ≥ 0.55 AND Sharpe ≥ 0.8 on OOS folds | Copilot + Operator |
| **BLK-005** | RL go/no-go conditions not met | Step 67 re-evaluation | XGBoost R4 + MLP/LSTM R3 + identified supervised failure mode | Claude Opus |
| **BLK-006** | ADR-011 ib_async trigger not met | IBASYNC-01 | ib_insync drops TWS API compatibility OR ib_async reaches stable release | Claude Opus |

---

## Output 7: Final Recommendation

**Accept ADR-018 (client-ID bands) and ADR-019 (assistant safety policy); clear the Opus gate on Step 62 MLP; defer reconnect lifecycle (RFC-007), RL (Step 67), and session replay (YATWS-03) to post-MO-2; reject ib_async migration and Rust sidecar; and prioritize MO-2 in-window paper sessions as the single highest-impact unblock for the entire forward pipeline.**

---

*Filed by: Claude Opus (ARCH→RSRCH→REVIEW session, 2026-02-26)*
