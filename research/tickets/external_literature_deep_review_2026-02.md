# External Literature Deep-Review Synthesis Pack

**Ticket**: Step 70  
**Status**: IN PROGRESS  
**Updated**: 2026-02-25  
**Owner**: Copilot  
**Scope Guardrails**: UK-first equities, paper-before-live, governance-first; preserve LPDD hard invariants.

---

## 1) Objective

Consolidate all required Step 70 external inputs into a single weighted-score matrix and convert findings into LPDD-safe recommendations.

---

## 2) Scoring Method

Rubric: `docs/SOURCE_REVIEW_RUBRIC.md` with weighted dimensions:

- reproducibility (0.25)
- maintenance_health (0.15)
- test_evidence (0.15)
- risk_controls (0.20)
- lpdd_invariant_fit (0.15)
- operational_realism (0.10)

Verdict mapping:

- Adopt now: weighted score >= 80
- Research first: 50 to 79
- Reject: < 50 or hard-fail condition

---

## 3) Required-Input Consolidated Matrix

| Source | Type | Rubric Score | Verdict | Notes |
|---|---|---:|---|---|
| asavinov/intelligent-trading-bot | repo | 61.75 | Research first | Candidate documentation/traceability ideas; governance strictness gap |
| Mun-Min/ML_Trading_Bot | repo | 34.55 | Reject | Educational notebook flow; weak reproducibility and controls |
| shayleaschreurs/Machine-Learning-Trading-Bot | repo | 26.25 | Reject | High-level narrative, limited technical rigor |
| CodeDestroyer19/Neural-Network-MT5-Trading-Bot | repo | 41.75 | Reject | Containerization ideas; insufficient validation and governance fit |
| pskrunner14/trading-bot | repo | 41.75 | Reject | Historical RL reference only; stale maintenance |
| owocki/pytrader | repo | 27.50 | Reject | Very stale and low modern reproducibility confidence |
| awesome-deep-trading (Meta Analyses section) | repo/list | 53.50 | Research first | Useful index for paper triage; list itself is stale |
| DataPebbles DRL article | article | 57.05 | Research first | Strong educational scaffold and caveats; not production-grade |
| MLQ.ai DRL TensorFlow article | article | 46.50 | Reject | Intro tutorial only; weak operational realism |
| Javier Medium LSTM crypto article | article | 19.50 | Reject | Paywall-limited auditability |
| ImbueDeskPicasso transformer returns article | article | 29.25 | Reject | Extraordinary claims with low independent verifiability |
| Bitunix case studies article | article | 30.75 | Reject | Marketing-style narratives; non-reproducible claims |
| Alpaca deep-learning bot article | article | 54.70 | Research first | Good pedagogical flow; needs stronger validation gates |
| Devpost ML trading bot project | article/showcase | 34.75 | Reject | Showcase depth insufficient for implementation decisions |

---

## 4) Meta-Review Notes (awesome-deep-trading subsection)

The Step 70 required subsection lists five survey/meta papers:

- Application of machine learning in stock trading: a review (2018)
- Evaluating the Performance of Machine Learning Algorithms in Financial Market Forecasting: A Comprehensive Survey (2019)
- Reinforcement Learning in Financial Markets (2019)
- Financial Time Series Forecasting with Deep Learning: A Systematic Literature Review: 2005-2019 (2019)
- A systematic review of fundamental and technical analysis of stock market predictions (2019)

Use this subsection as discovery input only; each cited paper still needs independent claim-integrity and LPDD-fit evaluation before roadmap action.

---

## 5) Actionable Opportunities (Prioritized)

| Idea | Benefit to this repo | Effort | Risk | Recommended Agent | Ticket Action |
|---|---|---|---|---|---|
| Add broker adapter conformance checks inspired by CCXT capability normalization | Better multi-venue reliability and reduced adapter drift | M | Low | Copilot | Map to Step 63/64 hardening follow-up |
| Add integration maturity labels (planned/building/beta/stable) to broker docs/config | Clearer operator expectations and safer rollout discipline | S | Low | Copilot | Add under Step 70 synthesis recommendations |
| Add release-provenance checklist for third-party package intake | Supply-chain assurance improvement | S | Low | Copilot | Add operations hardening subtask under MO-2 stream |
| Extend research guidance with commission-aware and walk-forward RL caveats | Better ML governance and less overfit risk | S | Low | Copilot | Add Step 70 research-note deliverable |

---

## 6) No-Action / Rejection Register

| Idea/Source | Rejection Reason | LPDD Constraint/Invariant |
|---|---|---|
| Direct adoption of high-claim Medium/marketing case-study bots | Non-auditable methodology and weak reproducibility | Governance-first evidence threshold |
| Direct use of script-centric execution bots | No demonstrated strict risk-manager mediation | `RiskManager.approve_signal()` only path from signal to order |
| Direct use of stale archived repositories | Maintenance and dependency risk too high for operations | Operational realism + maintainability guardrails |

---

## 7) Validation Checklist

- [x] Required Step 70 non-README sources scored and recorded in YAML stubs.
- [x] README-resource expansion sources scored and recorded in YAML stubs.
- [x] Every scored source mapped to verdict and action/rejection rationale.
- [x] Recommendations constrained by LPDD hard invariants.
- [ ] LPDD evolution/backlog closure updates for Step 70 completion.

---

## 8) Consolidated Summary

- **Adopt now**: none from this required-input subset
- **Research first**: `asavinov/intelligent-trading-bot`, `awesome-deep-trading` meta subsection, DataPebbles DRL article, Alpaca deep-learning article
- **Reject**: all remaining required-input sources due to reproducibility, maintenance, or governance-fit deficits
- **Cross-cutting conclusion**: external sources are best used for research framing and guardrail design, not direct architecture transplant
