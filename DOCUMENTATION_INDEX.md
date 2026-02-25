# Trading Bot Documentation Index

Quick navigation for enterprise algorithmic trading platform documentation.

---

## 🎯 **Single Source of Truth for Active Work**

👉 **All current tasks, prompts, blockers, and priorities are tracked in:** [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)

Other docs below are references. Check the backlog first when deciding what to work on.

**Session startup order (LPDD + topology):**
1. `SESSION_LOG.md` (last 2–3 entries)
2. `SESSION_TOPOLOGY.md` §5
3. `PROJECT_DESIGN.md`
4. `CLAUDE.md`
5. `IMPLEMENTATION_BACKLOG.md`
6. `.python-style-guide.md`

---

## 📖 Documentation Files

### 0. **PROJECT_DESIGN.md** — LLM Project Design Document (LPDD)
**Read before any design or structural work.** The single authoritative source for *why* the project is built the way it is.
- Architecture Decision Records (ADRs 001–012) — all major decisions with context, rationale, and consequences
- Architecture Decision Records (ADRs 001–017) — all major decisions with context, rationale, and consequences
- Active RFCs (RFC-004–006) — currently tracked operational/reliability proposals
- Technical Debt Register — known issues with backlog step links
- Evolution Log — append-only record of major changes
- Hard constraints that cannot be changed without a new ADR
- Key document map

**Use for:** Understanding *why* things are the way they are; raising new design proposals; recording decisions

---

### 1. **CLAUDE.md** — Architecture Context
**Read this first for every session.** Session context and autonomous decision-making guide.
- Project purpose & three core pillars
- Current tech stack
- Where things live (file structure)
- How to add strategies (standard pattern)
- Quick run commands
- Current status & completion tracker
- Next immediate steps
- Enterprise checklist

**Length:** ~500 lines | **Update frequency:** After each major feature add

---

### 2. **DEVELOPMENT_GUIDE.md** — Development Patterns & Tools
**Reference guide** for adding features systematically.
- Enterprise project roadmap (three pillars)
- Pillar 1: Historical data collection & analysis (phases 1.1-1.3)
- Pillar 2: Strategy development & evaluation (phases 2.1-2.5)
- Pillar 3: Real-time trading & learning (phases 3.1-3.5)
- Testing & documentation standards
- Feature priority tiers (Tier 1/2/3)
- Timeline summary

**Length:** ~800 lines | **Update frequency:** As new phases complete

---

### 3. **PROJECT_ROADMAP.md** ~~— Comprehensive 8-Week Roadmap~~
> ⚠️ **ARCHIVED** — moved to `archive/PROJECT_ROADMAP.md`. Tasks superseded by
> **IMPLEMENTATION_BACKLOG.md** (authoritative task queue) and
> **PROJECT_DESIGN.md** (architectural decisions and evolution log).

---

### 4. **DATA_MODELS.md** — Data Types & Schema Reference
**Quick reference** for all data structures, enums, and database schemas.

**Contains:**
- Core data types: Bar, Signal, Order, Position
- Configuration dataclasses: DataConfig, StrategyConfig, RiskConfig, etc.
- Database schema (planned for Pillar 1)
- Data flow diagram
- Type hints & conventions
- Error handling patterns
- Signal strength to position sizing mapping

**Length:** ~400 lines | **Use for:** Implementation reference while coding

---

### 5. **PROJECT_STATUS.md** — Current Status & Summary
> ⚠️ **ARCHIVED** — moved to `archive/PROJECT_STATUS.md`. Content was stale (154 tests vs actual 317+).
> Use **IMPLEMENTATION_BACKLOG.md** for current progress tracking.

---

### 5b. **IMPLEMENTATION_BACKLOG.md** — Outstanding Tasks & Prompts
**Working document** tracking all outstanding implementation tasks and their status.

**Contains:**
- Executive summary (current single source of truth for prompts, next steps, blockers, and priorities)
- Claude Opus deferred execution queue (centralized handoff list) → `IMPLEMENTATION_BACKLOG.md` section: `Claude Opus Queue (Deferred)`
- Actionable now execution subset (immediate, non-noise queue) → `IMPLEMENTATION_BACKLOG.md` section: `Actionable Now Queue (Execution Subset)`
- Prompt Pack (7 explicit prompts with task descriptions, implementation plans, and success criteria)
  - ✅ Prompt 1: Paper session summary (COMPLETED)
- ✅ Prompt 2: Paper-only guardrails (COMPLETED)
- ✅ Prompt 3: Broker reconciliation (COMPLETED)
  - ✅ Prompt 6: Paper trial automation (COMPLETED)
  - ✅ Prompt 4: Promotion framework design (COMPLETED)
  - ✅ Prompt 5: UK test plan (COMPLETED)
  - ✅ Prompt 7: Risk architecture review (COMPLETED)
- Next Steps (7 operational milestones with blockers and dependencies)
- Progress timeline (recommended weekly schedule)
- Dependency graph (shows which tasks block others)
- How to use this document (task selection + status updates)

**Length:** ~400 lines | **Update frequency:** After each prompt completion

---

### 6. **README.md** (Recommended)
**User-facing introduction** (not yet created).
Would contain:
- What is this bot?
- Quick start in 5 minutes
- Example results
- Feature roadmap
- How to contribute

---

### 7. **UK_OPERATIONS.md** — UK Runtime & Tax Export Runbook
**Operational checklist** for UK-based execution and reporting.

**Contains:**
- IBKR paper prerequisites and startup checks
- `uk_paper` profile usage and guardrails
- Market-hours behavior and UK symbol conventions
- UK tax export command and output file interpretation
- Trial manifest examples (conservative/standard/aggressive presets)
- Troubleshooting for IBKR/data/export issues

**Length:** ~280 lines | **Use for:** Day-to-day UK paper trading workflow

---

### 8. **TRIAL_MANIFEST.md** — Paper Trial Configuration Framework (New)
**Configuration-driven approach** to repeatable paper trading validation.

**Contains:**
- Manifest JSON structure and field reference table
- Three preset profiles with use cases and success criteria
- How to create custom manifests for A/B testing
- Execution flow diagram and exit code semantics
- Troubleshooting: manifest loading, JSON validation, drift detection

**Length:** ~350 lines | **Use for:** Running standardized paper trials and pre-live validation

---

### 9. **research/README.md** — UK-First Strategy Research Track
**Research operating guide** for offline strategy R&D and promotion into runtime.

**Contains:**
- UK-first market scope and profitability objective
- In-repo research structure and governance boundaries
- Promotion contract from research candidates to runtime use
- Research pipeline outputs and troubleshooting references

**Use for:** Setting up and running strategy discovery safely

---

### 10. **research/prompts/UK_STRATEGY_PROMPTS.md** — Prompt + Agent Pack
**Execution-ready prompts** for UK-focused strategy research.

**Contains:**
- Prompt IDs with objective, best agent, and rationale
- Ready-to-use prompts for data, features, walk-forward, ML, and promotion policy
- Clear mapping of design prompts vs implementation prompts

**Use for:** Running structured research cycles with the right agent per task

---

### 11. **research/tickets/UK_RESEARCH_TICKETS.md** — Initial Build Tickets
**Concrete implementation tickets** for the first research sprint.

**Contains:**
- R1 snapshot reproducibility ticket
- R2 walk-forward harness ticket
- R3 strategy factory bridge ticket
- ✅ R4 methodology/governance spec ticket (COMPLETED)

**Use for:** Sprint planning and execution sequencing

---

### 12. **docs/PROMOTION_FRAMEWORK.md** — Institutional-Grade Promotion Framework
**Formal promotion policy** covering Gate A (code→paper) and Gate B (paper→live).

**Contains:**
- 4-gate lifecycle (experimental → paper → live → production)
- 5 metric categories with P0/P1/P2 severity levels
- Stakeholder sign-off and immutability requirements
- References decision rubric JSON schema

**Length:** ~300 lines | **Use for:** Promotion decisions and audit trail

---

### 13. **docs/WEEKLY_REVIEW_TEMPLATE.md** — Weekly Review Template
**9-section checklist** for recurring operational review.

**Contains:** System health, execution quality, P&L, risk controls, reconciliation, signal quality, promotion readiness, action items, sign-off (with all CLI commands)

**Use for:** Weekly operational review cadence

---

### 14. **docs/UK_TEST_PLAN.md** — UK Paper Test Plan
**Execution plan** for paper-trading validation across UK market regimes.

**Contains:** LSE session rules, symbol baskets, 5 regime types, power analysis, 5-phase execution, per-regime thresholds

**Use for:** Planning and executing paper trial campaigns

---

### 15. **docs/RISK_ARCHITECTURE_REVIEW.md** — Risk Architecture Blind Spot Review
**Prioritised gap analysis** across 8 risk categories.

**Contains:** 3 P0 gaps (stale data, execution drift, session boundary), 3 P1 gaps (broker outage, concentration, FX staleness), 2 P2 gaps (model drift, audit tamper) — all with implementation sketches and effort estimates

**Use for:** Sprint planning for risk hardening

---

### 16. **docs/PROMOTION_CHECKLIST.md** — Promotion Checklist (Operational)
**Short operational checklist** complementing PROMOTION_FRAMEWORK.md.

**Contains:** Pre-paper checks, in-paper checks, exit criteria, CLI command

**Use for:** Day-of-promotion verification

---

### 17. **reports/promotions/decision_rubric.json** — Decision Rubric Schema
**JSON Schema (draft-07)** for recording Gate B promotion decisions.

**Contains:** Required fields, enum validation, P0/P1 severity enforcement, inline example

**Use for:** Generating and validating promotion decision records

---

### 18. **research/specs/UK_UNIVERSE.md** — UK Tradable Universe Specification
**Canonical universe definition** for all research work. (Answers P1)

**Contains:** MVU (15 symbols), expanded universe (30-40), liquidity filters, regime coverage requirements, trade-offs table, validation procedure

**Use for:** Universe selection before any research study

---

### 19. **research/specs/FEATURE_LABEL_SPEC.md** — Feature & Label Specification
**Leakage-safe engineering spec** for features and labels. (Answers P3 + R4a)

**Contains:** Horizon definitions (H1/H5/H21), 6 feature families, 7 leakage traps + mitigations, class imbalance handling, walk-forward compatible split strategy, implementation schemas

**Use for:** Implementation guidance for P4 (features.py / labels.py)

---

### 20. **research/specs/VALIDATION_PROTOCOL.md** — Walk-Forward + Regime Validation Protocol
**Statistical evaluation protocol** for strategy research. (Answers P5 + R4b)

**Contains:** 8-fold expanding-window schedule, regime coverage requirements, confidence intervals (Wilson CI), per-fold and aggregate pass/fail gates, overfitting diagnostics, promotion_check.json schema

**Use for:** Running and evaluating walk-forward experiments

---

### 21. **research/specs/ML_BASELINE_SPEC.md** — ML Baseline Stack Specification
**Model governance spec** for XGBoost and optional LSTM. (Answers P7)

**Contains:** XGBoost rationale, hyperparameter config, calibration policy, PSI drift monitoring, fail-safe fallback levels, 11-item evidence bundle requirement

**Use for:** ML model development and governance

---

### 22. **research/specs/RESEARCH_PROMOTION_POLICY.md** — Research-to-Runtime Promotion Policy
**Governance policy** for research strategies entering the runtime registry. (Answers P9 + R4c)

**Contains:** 4-stage promotion path (R1–R4), 11-item evidence bundle, stage-by-stage acceptance criteria, rollback conditions, monitoring triggers, explicit no-go criteria

**Use for:** Gating research strategy promotion into production

---

### 23. **EXECUTION_FLOW.md** — Execution Flows & Architecture (NEW)
**Visual guide to control flow** through the bot startup and runtime sequences.

**Contains:**
- Paper trading flow (async bar processing → signal → risk gate → submission)
- Backtest flow (synchronous replay)
- Research flow (features → train → evaluate → register)
- Health check flow (broker, data, DB, credentials)
- Class hierarchy quick reference (BaseStrategy, BrokerBase, RiskManager, PortfolioTracker)
- Mermaid sequence diagram (paper mode, single bar lifecycle)
- Mermaid dependency graph (module connections)
- Per-bar decision tree (all checks in order)
- Async event handling (stream, fill monitor, heartbeat, errors)

**Includes:** Mermaid diagrams (interactive on GitHub + VS Code), ASCII flows, decision trees

**Length:** ~600 lines | **Update frequency:** When architecture changes

**Use for:** Onboarding, debugging, architecture review, code navigation

---

### 24. **EXECUTION_FLOW_VIEWER.md** — Interactive Execution Flow Viewer (NEW)
**How to generate interactive HTML** and graphical views of execution flows.

**Contains:**
- Option 1: GitHub Markdown rendering (easiest, no setup)
- Option 2: Local Mermaid HTML (5 minutes, self-contained)
- Option 3: D3.js visualization (full interactivity, browser-based code jumper)
- Option 4: Python script to auto-generate from code AST
- Recommended approach + viewing instructions
- Integration with VS Code markdown preview
- Keeping diagrams updated (manual vs automated)

**Use for:** Choosing visualization tool, setting up local viewing, automating diagram generation

---

### 25. **docs/DATA_PROVIDERS_REFERENCE.md** — Data Providers Reference
**LLM-optimised reference** for all 10 external data and execution providers.

**Contains:** Provider summary table, full detail per provider (full name, site, proposed use, auth env vars, cost, limitations, implementation file), historical data pipeline overview, backlog tasks for providers and ML/NN, 5 ready-to-execute Copilot/Opus prompts (Alpha Vantage adapter, LSTM baseline, WebSocket feed, flat-file ingestion, Benzinga sentiment), agent assignment matrix, env var reference

**Use for:** Adding new providers, understanding provider tier strategy, picking up ML/NN work, any LLM starting provider-related tasks

---

### 26. **docs/MASSIVE_API_REFERENCE.md** — Massive (formerly Polygon.io) API Reference
### 26. **docs/MASSIVE_API_REFERENCE.md** — Massive (formerly Polygon.io) API Reference
**LLM-optimised reference** for the Massive market data API (rebranded from Polygon.io, Oct 2025).

**Contains:** Auth pattern, REST base URLs, full stocks endpoint catalog (aggregates, trades, quotes, snapshots, technicals, fundamentals, corporate actions), WebSocket connection sequence and message schemas (AM/T/Q events), Flat Files S3 access pattern and column schemas, project-specific notes (env vars, UK symbol format, Step 24 adapter guidance)

**Use for:** Implementing `MassiveProvider` (Step 24), upgrading data feed from yfinance, any LLM working on the provider layer

---

### 27. **.github/copilot-instructions.md** — GitHub Copilot Workspace Instructions
**Auto-read by GitHub Copilot** in VS Code. Distils the key rules from CLAUDE.md and
PROJECT_DESIGN.md into a format Copilot consumes as workspace context.

**Contains:** Reading order (6 items including session log + topology), session protocol,
hard invariants, architecture table, code style summary, LPDD update conventions, what NOT to do

**Update:** When CLAUDE.md invariants, LPDD conventions, or session topology change materially.

---

### 28. **SESSION_TOPOLOGY.md** — Session Type Definitions & Routing
**Read at the start of every LLM session** to identify which session type applies (§5 decision tree).

**Contains:**
- 6 session types: IMPL, ARCH, RSRCH, OPS, DEBUG, REVIEW — each with pre-read list, scope guard, and handoff rules
- Context loading priority table (§3) — what to read first when context window is limited
- Agent routing decision tree (§5) — flowchart for type classification
- Session continuity patterns (§6) — multi-session sprints, design→implement handoffs, debug→fix→verify
- VS Code integration (§7) — snippets and tasks

**Length:** ~280 lines | **Use for:** Session management, handoff protocol, scope control
**ADR:** ADR-016 | **Update:** When adding new session types or changing routing rules

---

### 29. **SESSION_LOG.md** — Session Journal (Append-Only)
**Read the last 2–3 entries at the start of every session** for recent context and handoff notes.

**Contains:** Chronological session entries with structured format (goal, outcome, queue changes,
files modified, test baseline, handoff notes). Tagged by session type for filtering.

**Rules:** Append-only; rotate at 50 entries (archive to `archive/session_logs/`).
**Snippets:** Use `slog` / `slog-short` in VS Code (`.vscode/session.code-snippets`).

---

### 30. **External Resources** — Third-Party References

**IBKR Campus (QuantConnect / IBKR Quant)**

| Resource | URL | Relevance |
|---|---|---|
| IBKR Campus | https://www.interactivebrokers.com/campus/ | IBKR API patterns, error codes, order types |
| IBKR Quant News | https://www.interactivebrokers.com/campus/ibkr-quant-news/ | New synchronous TWS wrapper (`ibkr_python_ws`); future IBKR migration path |
| QuantConnect Docs | https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/getting-started | LEAN `QCAlgorithm` interface for Step 36 cross-validation |
| QuantConnect Pricing | https://www.quantconnect.com/pricing/?billing=mo | Free tier: cloud backtest (1 node, minute bars), 200 projects, UK/LSE supported |
| LEAN Engine (GitHub) | https://github.com/QuantConnect/Lean | Open-source engine; 150+ indicators reference; future migration candidate |

**Notes:**
- LEAN-CLI (local coding) requires paid tier ($60/mo) — cloud-only backtest is free
- `ibkr_python_ws` is IBKR's official async Python API; evaluate before any major `IBKRBroker` refactor
- Step 36 uses QuantConnect free cloud for cross-validation of MA Crossover + RSI vs Step 1 results
- See `PROJECT_DESIGN.md §3` (ADR-012) for LEAN migration decision rationale; `docs/ARCHITECTURE_DECISIONS.md` has the detailed comparative analysis

---

## 🎯 How to Use These Documents

### As a Developer (Adding Features)
1. Read **PROJECT_DESIGN.md** → understand architectural decisions and active RFCs
2. Read **CLAUDE.md** → understand session context and invariants
3. Review **DATA_MODELS.md** → understand data types
4. Check **IMPLEMENTATION_BACKLOG.md** → see which task to work on and priority
5. Use **DEVELOPMENT_GUIDE.md** for patterns → follow conventions

### As a Project Manager (Weekly Planning)
1. Check **IMPLEMENTATION_BACKLOG.md** → select this week's task (sort by Priority)
2. Review **PROJECT_DESIGN.md §6 Evolution Log** → recent changes
3. Verify test suite → all passing?
4. Check backtest results → performance on track?
5. Use **TRIAL_MANIFEST.md** → run preset trials for validation

### As an Architect (Design Decisions)
1. Start with **PROJECT_DESIGN.md** → ADRs, RFCs, debt register, hard constraints
2. Check **IMPLEMENTATION_BACKLOG.md** → see dependencies between tasks
3. Review **DATA_MODELS.md** → schema & data flow
4. Check **DEVELOPMENT_GUIDE.md** → testing/documentation standards
5. For new decisions: add ADR to **PROJECT_DESIGN.md §3**

### As a New Team Member (Onboarding)
1. Read **PROJECT_DESIGN.md** first (20 mins) — understand *why*
2. Read **CLAUDE.md** (20 mins) — understand *what* and *how to run*
3. Skim **IMPLEMENTATION_BACKLOG.md** (15 mins) — understand *what's next*
4. Review **DEVELOPMENT_GUIDE.md** > Pillar of interest (30 mins)
5. Deep dive code + docstrings (2-4 hours)
6. Run tests locally `pytest tests/ -v` (5 mins)

---

## 📊 Documentation Overview

| Document | Purpose | Length | Read First? | Update Freq |
|----------|---------|--------|-------------|-------------|
| PROJECT_DESIGN.md | LPDD — ADRs, RFCs, debt, history | 600+ | ✅ Yes (design work) | Per ADR/RFC |
| CLAUDE.md | Architecture context | 500 | ✅ Yes | Per feature |
| DEVELOPMENT_GUIDE.md | Development patterns | 800 | ⭐ Core | Per phase |
| IMPLEMENTATION_BACKLOG.md | Outstanding tasks & prompts | 400+ | 📋 Task selection | Per completion |
| DATA_MODELS.md | Data types & schema | 400 | 📖 Reference | Per schema change |
| UK_OPERATIONS.md | UK runtime & tax export | 280 | 🇬🇧 Operational | Per release |
| TRIAL_MANIFEST.md | Paper trial configuration | 350 | 📋 Runbook | Per update |
| docs/PROMOTION_FRAMEWORK.md | Promotion policy (Gate A/B) | 300 | 📋 Before promoting | Per policy update |
| docs/UK_TEST_PLAN.md | UK paper trial execution plan | 250 | 🇬🇧 Before paper trial | Per update |
| docs/RISK_ARCHITECTURE_REVIEW.md | Risk gap analysis + remediation | 350 | 🔍 Risk planning | Per sprint |
| research/specs/UK_UNIVERSE.md | UK tradable universe spec | 200 | 📊 Research start | Per universe change |
| research/specs/FEATURE_LABEL_SPEC.md | Feature/label leakage-safe spec | 300 | 🔬 Research engineering | Per feature set change |
| research/specs/VALIDATION_PROTOCOL.md | Walk-forward protocol | 250 | 🔬 Before experiments | Per protocol update |
| research/specs/ML_BASELINE_SPEC.md | ML model governance | 300 | 🤖 Before ML work | Per model change |
| research/specs/RESEARCH_PROMOTION_POLICY.md | Research → runtime policy | 250 | 🚀 Before promotion | Per policy change |
| CODE (src/) | Implementation | 3500+ | 🔍 Deep dive | Per feature |
| TESTS (tests/) | Validation | 2000+ | 🧪 Always | Per test add |

**Total documentation:** ~7,500 lines | **Total code:** ~6,500 lines | **Tests:** 317+ passing (see IMPLEMENTATION_BACKLOG.md for latest count)

---

## 🚀 Current Progress

### Completed (Foundation + UK Operational)
- ✅ 4 strategies (MA, RSI, MACD, Bollinger Bands)
- ✅ Backtesting engine (next-bar-open fills, slippage, commission)
- ✅ Risk manager (4 circuit breakers, VaR gate, thread-safe)
- ✅ Kill switch (persistent SQLite, survives restarts)
- ✅ VaR/CVaR analytics (historical simulation, 252-day rolling)
- ✅ Strategy registry (SQLite + SHA256 integrity + promotion checklist gate)
- ✅ Audit logger (async queue, SQLite, indexed)
- ✅ UK profile + IBKR routing + market session enforcement
- ✅ FX-normalized portfolio tracking (GBP base support)
- ✅ UK tax export CSV pipeline (ledger, realized gains, FX notes)
- ✅ Paper trading pre-warm + session summary + reconciliation + trial automation
- ✅ Trial manifest framework (3 presets + manifest-driven CLI)
- ✅ Paper-only live promotion gate (paper KPI thresholds + checklist enforcement)
- ✅ Institutional-grade promotion framework (Gate A/B, decision rubric, weekly review)
- ✅ UK paper test plan (symbol baskets, regimes, power analysis)
- ✅ Risk architecture review (8 categories, P0/P1/P2 prioritised gaps)
- ✅ Research track specs (universe, features, validation, ML baseline, promotion policy)
- ✅ 352+ passing tests (100% pass rate)

### In Progress (Tier 1 + Research Track)
- ⏳ ADX trend filter
- ⏳ Walk-forward validation harness (future expansion)
- ⏳ Feature/label pipeline implementation for research runtime sign-off
- ⏳ Step 1/1A in-window IBKR runtime closure

### Overall: ~75% of Tier 1 complete; Research track specs 100% complete

---

## 🔄 Document Relationships

```
┌─────────────────────────────────────────────────────────┐
│                    PROJECT_ROADMAP.md                   │
│          (Master timeline & all phases)                 │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
      ┌──────▼─────────┐        ┌──────▼──────────┐
      │ DEVELOPMENT_   │        │  DATA_MODELS.  │
      │ GUIDE.md       │        │  md             │
      │ (Patterns &    │        │ (Data types &   │
      │  processes)    │        │  schemas)       │
      └────────────────┘        └─────────────────┘
             │
   ┌─────────┴─────────┐
   │                   │
┌──▼──────────┐    ┌──▼─────────────┐
│ CLAUDE.md   │    │ PROJECT_STATUS │
│ (Arch &     │    │ .md            │
│  context)   │    │ (Progress)     │
└─────────────┘    └────────────────┘
```

---

## 📚 Key Concepts

### Three Pillars
1. **Data Collection & Analysis** — Historical OHLCV + EDA
2. **Strategy Development** — Rule-based + ML-based strategies
3. **Real-Time Trading** — Paper trading + feedback loop

### Tier System
- **Tier 1:** Foundation (weeks 1-4) — Data pipelines, core indicators, backtesting
- **Tier 2:** Enhancement (weeks 4-6) — Paper trading, risk controls, reporting
- **Tier 3:** Advanced (weeks 6-8+) — ML models, adaptive strategies, production deployment

### Phases
- **Phase X.1:** Infrastructure setup
- **Phase X.2:** Core implementation
- **Phase X.3:** Enhancements/validation
- **Phase X.4:** Integration
- **Phase X.5:** Optimization

---

## 📝 Writing Conventions

### In Code
- Docstrings on all public functions
- Type hints on all parameters & returns
- Example usage in docstrings
- Inline comments for non-obvious logic

### In Documentation
- Markdown headers (#, ##, ###)
- Code blocks with language tags
- Tables for comparison
- Bullet lists for sequences
- Bold for emphasis, code for variables
- Links to related files

### In Files
- SCREAMING_SNAKE_CASE for constants
- snake_case for variables/functions
- PascalCase for classes
- Strategy class names end with `Strategy`

---

## 🔗 Quick Links

**To add a new strategy:**
1. See: [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md#how-to-add-a-new-strategy)
2. Follow: [src/strategies/base.py](src/strategies/base.py)
3. Test: [tests/test_strategies.py](tests/test_strategies.py)
4. Register: [main.py](main.py)

**To understand risk controls:**
1. See: [DATA_MODELS.md](DATA_MODELS.md#riskconfig)
2. Check: [src/risk/manager.py](src/risk/manager.py)
3. Test: [tests/test_risk.py](tests/test_risk.py)
4. Configure: [config/settings.py](config/settings.py)

**To run backtests:**
1. See: [CLAUDE.md](CLAUDE.md#how-to-run)
2. Review: [backtest/engine.py](backtest/engine.py)
3. Inspect results in console output

**To understand data models:**
1. See: [DATA_MODELS.md](DATA_MODELS.md)
2. Check: [src/data/models.py](src/data/models.py)
3. Review examples in docstrings

---

## 🎓 Learning Path

**If you want to understand:**

**How strategies work:**
→ Read: CLAUDE.md section "How to add a new strategy"  
→ Study: src/strategies/ma_crossover.py (simplest example)  
→ Run: `python main.py backtest --strategy ma_crossover`

**How risk controls work:**
→ Read: DATA_MODELS.md section "RiskConfig"  
→ Study: src/risk/manager.py  
→ Run: `pytest tests/test_risk.py -v`

**How to build new features:**
→ Read: DEVELOPMENT_GUIDE.md section "Feature Roadmap"  
→ Check: PROJECT_ROADMAP.md for your phase  
→ Follow: Step-by-step tasks in your phase

**How data flows:**
→ Read: DATA_MODELS.md section "Data Flow Diagram"  
→ Study: src/data/feeds.py → strategies → risk/manager.py → broker  
→ Trace: A single bar through backtest/engine.py

---

## 📞 Getting Help

**Question: How do I add an indicator?**
→ See: PROJECT_ROADMAP.md > Phase 2.1 > Priority A/B/C  
→ Example: src/strategies/bollinger_bands.py (shows how to compute)

**Question: How do I modify signal strength?**
→ See: DATA_MODELS.md > Signal class  
→ Reference: Position sizing formula in DATA_MODELS.md

**Question: How do I test my changes?**
→ Run: `pytest tests/ -v`  
→ Add tests: tests/test_strategies.py (follow pattern)

**Question: What's the next priority?**
→ Check: IMPLEMENTATION_BACKLOG.md (single source of truth for current tasks)
→ Or: PROJECT_ROADMAP.md > Timeline

**Question: What's already been done?**
→ Check: IMPLEMENTATION_BACKLOG.md > Executive Summary
→ Or: CLAUDE.md > "How to run" (all strategies work)

---

## 📅 Maintenance Schedule

### Daily
- Run: `pytest tests/ -v` (ensure nothing broke)

### Weekly
- Update: IMPLEMENTATION_BACKLOG.md (progress tracking)
- Use: docs/WEEKLY_REVIEW_TEMPLATE.md (operational review)
- Review: Failed tests (if any)
- Check: Backtest results on key strategies

### Per Feature
- Create: New documentation if adding new component
- Update: CLAUDE.md if changing architecture
- Update: PROJECT_ROADMAP.md if changing timeline

### Monthly
- Comprehensive review of all documentation
- Update: DATA_MODELS.md if schema changes
- Refresh: DEVELOPMENT_GUIDE.md with patterns

---

**Last Updated:** February 25, 2026
**Total Documentation:** ~9,400 lines (26 active docs; 11 archived; 3 custom agent definitions)
**Test Coverage:** 551+ passing ✓ (see IMPLEMENTATION_BACKLOG.md for exact count)
**Status:** Foundation ~75% complete → UK paper-trading + promotion framework + research track specs all operational
**LPDD:** `PROJECT_DESIGN.md` is now the primary architectural authority — see it for ADRs, RFCs, and evolution log
**Session Management:** `SESSION_TOPOLOGY.md` + `SESSION_LOG.md` (ADR-016) — see `.github/copilot-instructions.md` for reading order
**Custom Agents:** `.github/agents/*.agent.md` (ADR-017) — lpdd-auditor, ops-runner, research-reviewer

