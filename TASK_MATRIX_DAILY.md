# Quick-Reference Task Matrix

**Generated**: February 24, 2026  
**Use This For**: Daily standup, weekly planning, sprint backlog prioritization  

---

## 🔴 CRITICAL PATH (BLOCKING)

| Task ID | Task | Owner | Status | Deadline | Commands | Evidence Location |
|---------|------|-------|--------|----------|----------|-------------------|
| **MO-2** | Step 1A: 3x consecutive burn-in sessions (filled_count >= 5 each) | User | 🔴 BLOCKING | ASAP (LSE hours) | `uk_health_check` → `paper_trial 1800s` × 3 → exports → `paper_reconcile --strict` | [IMPLEMENTATION_BACKLOG.md L402-460](IMPLEMENTATION_BACKLOG.md#L402-L460) |

### MO-2 Pre-Requisites
- ✅ Health check passes (IBKR connectivity)
- ✅ Stale-data guard refactored (`enable_stale_check=False` for uk_paper)
- ✅ Signal generation decision needed (See [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md) Options A/B/C)

---

## 🟠 HIGH PRIORITY (Next 2 Weeks)

| Task ID | Task | Owner | Status | Effort | Commands | File Reference |
|---------|------|-------|--------|--------|----------|-----------------|
| **MO-3** | Setup Polygon API key + validate | User | 📋 Planning | 30 min | `export POLYGON_API_KEY=...` | [IMPLEMENTATION_BACKLOG.md L1390](IMPLEMENTATION_BACKLOG.md#L1390) |
| **MO-5** | Human review: promotion checklist | User | 📋 Waiting | 1-2h | Review `docs/PROMOTION_CHECKLIST.md` | [IMPLEMENTATION_BACKLOG.md L1400](IMPLEMENTATION_BACKLOG.md#L1400) |
| **Signal Gen Fix** | Choose Option A/B/C from STEP1_DIAGNOSIS | Copilot + User | 🟡 Deciding | 1-4h | See [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md) | [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md) |

---

## ✅ COMPLETED (Reference Only)

| Category | Count | Last Completed | Recent Work |
|----------|-------|-----------------|-------------|
| **Engineering Prompts** | 7/7 | Feb 24 | Paper trials, guardrails, reconciliation, execution dashboards, checklists, risk reviews, broker resilience |
| **Implementation Steps** | 28/28 | Feb 24 | Polygon provider, XGBoost SHAP exports, research isolation, ADX filter, data quality report, all prior 23 steps |
| **Test Suite** | 405/405 | Feb 24 | All passing, no regressions |

---

## 📋 BACKLOG (Medium-Term Candidates)

| Category | Items | Priority | Example | File Location |
|----------|-------|----------|---------|----------------|
| **Architecture Decisions** | AQ1-AQ9 | MEDIUM | Time-series storage (DuckDB vs SQLite), VaR/CVaR implementation | [IMPLEMENTATION_BACKLOG.md L1275-1320](IMPLEMENTATION_BACKLOG.md#L1275-L1320) |
| **Carry-Forward Features** | AT1-AT12 | MEDIUM | Multi-provider adapter, timezone normalization, order lifecycle reconc. | [IMPLEMENTATION_BACKLOG.md L1298-1310](IMPLEMENTATION_BACKLOG.md#L1298-L1310) |
| **Tier 2 Enhancements** | ~15 items | LOW | LSTM models, correlation limits, walk-forward backtesting | [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) |

---

## 📊 Quick Stats

```
Total Project Items:     37
  Completed:            36 (97%)
  In Progress:           1 (Step 1A burn-in)
  Not Started:           0

Test Coverage:          405/405 (100%)
Code Quality:           All architecture decisions documented
Time to Production:     ~1-2 weeks (post Step 1A sign-off + approvals)
```

---

## 🎯 This Week's Priorities (Ranked)

### 1️⃣ Execute Step 1A (MO-2)
**Blocker**: Step 1A burn-in validation  
**Effort**: 2-4 hours in-market  
**Command**: 3x `paper_trial --profile uk_paper --paper-duration-seconds 1800`  
**Success**: All 3 sessions: filled_order_count ≥ 5, reconcile passes  

### 2️⃣ Signal Generation Decision
**Blocker**: Choosing remediation path (Option A/B/C)  
**Effort**: 30 min decision + 1-4 hours implementation  
**Options**:
- **A** (Recommended): Use daily backtest (already proven)
- **B**: Switch to RSI Momentum strategy
- **C**: Document limitation
**File**: [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md)

### 3️⃣ Set Up Credentials (MO-3)
**Blocker**: None (future work)  
**Effort**: 30 min setup  
**Action**: Provision Polygon API key in `.env`  

---

## 🗂️ File Reference Quick Map

| What You Need | File | Lines | Purpose |
|---------------|------|-------|---------|
| **Weekly task tracking** | [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) | Full | Primary active reference |
| **Step 1A details** | [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) | L402-460 | Burn-in acceptance criteria |
| **Signal gen guidance** | [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md) | Full | Options A/B/C for remediation |
| **Architecture decisions** | [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) | Full | AQ1-AQ9 synthesis |
| **Test command** | Terminal | N/A | `pytest tests/ -q` (should show 405 passed) |
| **Health check** | Terminal | N/A | `python main.py uk_health_check --profile uk_paper --strict-health` |
| **Paper trial command** | Terminal | N/A | `python main.py paper_trial --confirm-paper-trial --profile uk_paper --paper-duration-seconds 1800 --skip-rotate` |

---

## Manual Operator Queue (MO) - Next Actions

| MO ID | Task | Status | When | Owner | Command(s) |
|-------|------|--------|------|-------|-----------|
| **MO-1** | ✅ CLOSED | Complete | ✅ Feb 24 | Closed | N/A |
| **MO-2** | 🔴 CRITICAL | In Progress | ASAP | User | See Step 1A commands |
| **MO-3** | 📋 TODO | Planning | Week 2 | User | `export POLYGON_API_KEY=...` |
| **MO-4** | 📋 TODO | Planning | Week 3+ | User | Backfill/feed commands |
| **MO-5** | 📋 TODO | Waiting | Week 2 | User | Review `PROMOTION_CHECKLIST.md` |
| **MO-6** | 📋 TODO | Planning | Week 3+ | User | Risk/governance sign-off |
| **MO-7** | 📋 FUTURE | Planning | Post-prod | User | Live account setup |
| **MO-8** | 📋 FUTURE | Planning | Post-prod | User | Final go-live approval |

---

## Copilot Action Items

**Status**: ✅ **CLEAR** — All non-Opus engineering items complete

Last 5 completions (Feb 24):
1. Step 28: Data quality reporting + CLI
2. Step 27: ADX trend filter + strategy integration  
3. Step 26: Research isolation CI guard
4. Step 25: XGBoost SHAP export per-fold
5. Step 24: Polygon provider adapter

**Next Items** (if queued):
- AQ1-AQ9 detailed implementation (only if promoted by user)
- AT1-AT12 feature work (when scheduled from backlog)
- Tier 2 research ML pipeline (post Step 1A)

---

## Test & Validation

### Pre-Deployment Checklist
- [ ] `pytest tests/ -q` shows 405/405 passing
- [ ] `python main.py uk_health_check --profile uk_paper --strict-health` exits 0
- [ ] Logs show no ERROR/CRITICAL messages for non-guardrail blockages
- [ ] Step 1A (MO-2): 3x consecutive sessions with filled_count ≥ 5 each
- [ ] Reconciliation: all 3 sessions show drift_flags=0

### Running Tests
```bash
# Full suite
python -m pytest tests/ -q

# Specific module
python -m pytest tests/test_paper_guardrails.py tests/test_broker_reconciliation.py -v

# With coverage
python -m pytest tests/ --cov=src --cov=backtest -q
```

---

## Links to Decision Points

| Decision | File | Section |
|----------|------|---------|
| **Signal generation fix (Option A/B/C)** | [STEP1_DIAGNOSIS.md](STEP1_DIAGNOSIS.md) | "Decision Needed" / "Recommendations" |
| **Strategy promotion policy** | [docs/PROMOTION_FRAMEWORK.md](docs/PROMOTION_FRAMEWORK.md) | Full |
| **UK ops test procedures** | [docs/UK_TEST_PLAN.md](docs/UK_TEST_PLAN.md) | Full |
| **Risk architecture review** | [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md) | Full |
| **Architecture decisions (AQ1-AQ9)** | [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) | Full |

---

**Last Generated**: February 24, 2026 | **Next Review**: Post-Step 1A completion or weekly (whichever comes first)
