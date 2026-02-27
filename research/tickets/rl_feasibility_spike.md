# RL Trading Track Feasibility Spike — Decision Memo

**Step**: 67
**Ticket**: (intake)
**Session**: ARCH-2026-02-26
**Decision**: DEFER (conditional no-go)

---

## 1. Summary

Reinforcement learning (RL) appears frequently in external trading bot literature (e.g., AishaRL, pskrunner14/trading-bot) but introduces high architecture risk, poor reproducibility, and governance complexity that is disproportionate to the platform's current maturity level.

**Verdict: DEFER.** RL is not appropriate until the supervised-learning pipeline is proven through at least R3 (paper trial) and specific failure modes are identified where supervised approaches fall short.

---

## 2. Compatibility Assessment

### 2a. UK-First, Paper-Before-Live Governance

| Criterion | Assessment |
|---|---|
| Paper-only sandbox enforcement | ⚠️ RL requires a simulation environment that can drift from real market mechanics. Must enforce paper-only in `config/settings.py` and never allow RL agents to submit live orders without full MO-2+ sign-off chain. |
| LPDD invariant compliance | ⚠️ `RiskManager.approve_signal()` must remain the only path from Signal to Order. RL action selection must emit a `Signal`, not bypass risk management. |
| Audit trail | ⚠️ RL policies are opaque. Each action selection must be logged with state, Q-values/policy logits, and chosen action for post-hoc review. |
| Session window constraints | ✅ Training is offline. Inference in paper sessions follows existing window rules. |

### 2b. Reproducibility Requirements

| Requirement | Difficulty |
|---|---|
| Deterministic seed control | HIGH — RL training varies across seeds, hardware, and floating-point ordering |
| Walk-forward validation | HIGH — RL episodes don't map cleanly to walk-forward folds; requires custom harness |
| Hyperparameter sensitivity | HIGH — reward shaping, discount factor, exploration schedule are all fragile |
| Baseline comparison | MEDIUM — must compare against XGBoost/MLP Sharpe, not just "RL Sharpe" |

### 2c. Reward Function Pitfalls

1. **Transaction cost leakage**: Reward functions that ignore slippage/commission produce agents that churn excessively.
2. **Terminal bias**: Episode boundaries at fixed dates create artificial signals.
3. **Reward hacking**: Over-specified rewards lead to degenerate strategies (e.g., hold cash forever for zero drawdown).
4. **Market impact**: RL agents trained on historical data assume zero market impact — dangerous for anything beyond micro positions.
5. **Temporal inconsistency**: Discount factor choices implicitly define a time preference that may conflict with strategy holding period intent.

### 2d. Minimal Sandbox Boundaries (if ever approved)

- RL research MUST reside entirely in `research/models/rl/` — no `src/` imports at module level.
- RL agents MUST emit `Signal` objects through `research/bridge/strategy_bridge.py` to use in paper sessions.
- Environment MUST use historical OHLCV from `MarketDataStore`, not live feeds.
- Reward function MUST include: transaction costs, slippage estimate (0.1%), and position sizing constraints.
- Training logs MUST include: episode count, reward distribution, policy entropy, and convergence metrics.
- Maximum training budget: 24 hours wall-clock on consumer hardware.

---

## 3. Go/No-Go Criteria

### Conditions to revisit (ALL must be true):

1. XGBoost has reached R4 (live validation with positive Sharpe > 0.5)
2. MLP (Step 62) and LSTM (Step 32) have at least R3 evidence
3. A specific trading scenario is identified where supervised models fail to capture regime-dependent dynamics that RL could plausibly address
4. Operator explicitly authorizes RL research track with designated compute budget and timeline

### If conditions are met:

Define a minimal 3-step plan:
1. **Environment scaffold**: `research/models/rl/trading_env.py` — OpenAI Gym compatible, historical bar replay
2. **Baseline agent**: PPO or A2C on simplified feature set (5 features, single symbol)
3. **Comparison gate**: RL must beat MLP baseline by ≥0.03 PR-AUC and ≥0.2 Sharpe on same walk-forward folds

### Rollback criteria:

- If after 160 hours of compute the RL agent does not exceed the MLP baseline on any fold, close the track permanently.
- If reward function cannot be stabilized across 3 different seeds (Sharpe std > 1.0), close the track.

---

## 4. Rejection Rationale

1. **Premature complexity**: The supervised pipeline (XGBoost → MLP → LSTM) is not yet through R3. Adding RL before basic ML works is architectural scope creep.
2. **Reproducibility burden**: RL training is 5-10× harder to reproduce than supervised training. The RESEARCH_PROMOTION_POLICY.md evidence requirements would need significant extension.
3. **Governance overhead**: Auditing RL decisions requires logging Q-values/policy outputs at every timestep — significant storage and tooling.
4. **External evidence quality**: Reviewed RL trading papers (AishaRL, pskrunner14) show high-return claims without adequate transaction cost or out-of-sample evidence — CAUTION flags per Step 65 claim-integrity gate.
5. **Operational cost**: No measurable near-term reliability gain. RL does not solve the current blockers (MO-2 paper sessions, fill detection, data pipeline).

---

## 5. References

- ADR-005: XGBoost before LSTM (progressive complexity)
- Step 62: MLP baseline (pre-LSTM gate)
- Step 65: Research claim-integrity gate (anti-hype controls)
- research/specs/RESEARCH_PROMOTION_POLICY.md: R1-R4 promotion path
- research/tickets/external_literature_deep_review_2026-02.md: Source reviews with RL caveats

**Filed by**: Claude Opus (ARCH session 2026-02-26)
**Next review**: When all 4 go/no-go conditions are met, or at next ARCH session if new evidence appears.
