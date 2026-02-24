# Quick Navigation Guide

**Lost? Don't know where to start?** Use this guide to find the right documentation.

---

## 🎯 What Do You Want to Do?

### 📋 Understand the Big Picture
→ Start with [CLAUDE.md](CLAUDE.md) (5 min read)
- Architecture overview
- Where things live
- Three core pillars
- Quick run commands

### 🔄 See Control Flow & Execution Sequence
→ Read [EXECUTION_FLOW.md](EXECUTION_FLOW.md) (10 min read)
- Paper trading flow (paper mode)
- Backtest flow (simulation)
- Research flow (feature engineering)
- Mermaid diagrams (interactive on GitHub)
- Per-bar decision tree
- Module dependency graph

**Want interactive visualizations?** See [EXECUTION_FLOW_VIEWER.md](EXECUTION_FLOW_VIEWER.md) for options (GitHub rendering, local HTML, D3.js)

### 🚀 Add a New Feature (Strategy, Provider, Indicator)
→ [CLAUDE.md](CLAUDE.md) section: "How to add a new strategy"
→ [.python-style-guide.md](.python-style-guide.md) — Follow these conventions
→ [DATA_MODELS.md](DATA_MODELS.md) — Data types reference

### 🧪 Run a Backtest
→ [CLAUDE.md](CLAUDE.md) section: "How to run"
```bash
python main.py backtest --start 2022-01-01 --end 2024-01-01
```

### 📝 Run Paper Trading (UK Paper)
→ [UK_OPERATIONS.md](UK_OPERATIONS.md) (operational runbook)
```bash
python main.py uk_health_check --profile uk_paper --strict-health
python main.py paper_trial --confirm-paper-trial --profile uk_paper
```

### 📊 What's Currently Being Worked On?
→ [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) (single source of truth)
- All current tasks + status
- Prompts (7 total)
- Next steps + blockers
- Progress tracking

### 🛡️ Understand the Risk Controls
→ [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md)
- 8 risk categories
- 3 P0 gaps + 3 P1 gaps + 2 P2 findings
- Implementation sketches
- Effort estimates

### 🧬 Do Research (Features, Labels, Models)
→ [research/README.md](research/README.md) — Research governance
→ [research/specs/UK_UNIVERSE.md](research/specs/UK_UNIVERSE.md) — Which symbols to analyze
→ [research/specs/FEATURE_LABEL_SPEC.md](research/specs/FEATURE_LABEL_SPEC.md) — How to engineer features
→ [research/specs/VALIDATION_PROTOCOL.md](research/specs/VALIDATION_PROTOCOL.md) — How to validate
→ [research/specs/ML_BASELINE_SPEC.md](research/specs/ML_BASELINE_SPEC.md) — Model governance

### 🎓 Onboard Someone New (30 mins)
1. [CLAUDE.md](CLAUDE.md) — Project purpose & architecture (5 min)
2. [EXECUTION_FLOW.md](EXECUTION_FLOW.md) — How it runs (10 min)
3. [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) — Feature categories (5 min)
4. [.python-style-guide.md](.python-style-guide.md) — Code standards (5 min)
5. Clone repo, run health check:
   ```bash
   python main.py uk_health_check --profile uk_paper --strict-health
   ```

### 💾 Understand the Data Model
→ [DATA_MODELS.md](DATA_MODELS.md) (reference guide)
- Core types: Bar, Signal, Order, Position
- Configs: DataConfig, RiskConfig, StrategyConfig
- Database schema
- Type hints

### 🔌 Integrate a New Data Provider
→ [docs/DATA_PROVIDERS_REFERENCE.md](docs/DATA_PROVIDERS_REFERENCE.md)
→ Specific provider docs (e.g., [docs/MASSIVE_API_REFERENCE.md](docs/MASSIVE_API_REFERENCE.md) for Polygon/Massive)

### 🎯 Understand the Promotion Framework
→ [docs/PROMOTION_FRAMEWORK.md](docs/PROMOTION_FRAMEWORK.md) (policy & gates)
→ [research/specs/RESEARCH_PROMOTION_POLICY.md](research/specs/RESEARCH_PROMOTION_POLICY.md) (research-specific)
→ [docs/PROMOTION_CHECKLIST.md](docs/PROMOTION_CHECKLIST.md) (operational checklist)

### 📅 Plan Weekly Review
→ [docs/WEEKLY_REVIEW_TEMPLATE.md](docs/WEEKLY_REVIEW_TEMPLATE.md) (9-section checklist)
- All CLI commands included
- P&L tracking, risk controls, signal quality, etc.

### 🏗️ Understand Code Organization
→ [CLAUDE.md](CLAUDE.md) section: "Architecture — where things live"

| Layer | Files | Responsibility |
|-------|-------|-----------------|
| Config | `config/settings.py` | All parameters — edit here |
| Data | `src/data/feeds.py` | Fetch OHLCV via providers |
| Strategies | `src/strategies/` | BaseStrategy + MA/RSI/Bollinger/MACD |
| Risk | `src/risk/manager.py` | VaR, guardrails, limits |
| Broker | `src/execution/broker.py` | IBKR/Alpaca/Paper brokers |
| Audit | `src/audit/logger.py` | Immutable audit events |
| Portfolio | `src/portfolio/tracker.py` | P&L, FX conversion |
| Backtest | `backtest/engine.py` | Zero-lookahead replay |
| CLI | `main.py` | Entry point |

### ✅ Verify Code Quality
→ [CODE_STYLE_SETUP.md](CODE_STYLE_SETUP.md) (tools & commands)
```bash
black --check src/ tests/         # Format check
pylint src/ --rcfile=.pylintrc    # Linting
pytest tests/ -v                  # Run tests
```

---

## 📄 Full Documentation Index

**See:** [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) for complete list of all docs (27+ files)

---

## 🔑 Key Files at a Glance

| File | Purpose | Length | Update Freq |
|------|---------|--------|------------|
| [CLAUDE.md](CLAUDE.md) | Architecture context | 500 | Per feature |
| [EXECUTION_FLOW.md](EXECUTION_FLOW.md) | Control flow diagrams | 600 | With refactors |
| [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) | Current tasks + status | 2100 | Per completion |
| [.python-style-guide.md](.python-style-guide.md) | Code standards | 400 | Rarely |
| [CODE_STYLE_SETUP.md](CODE_STYLE_SETUP.md) | Tools & commands | 200 | With tool updates |
| [DATA_MODELS.md](DATA_MODELS.md) | Data types reference | 400 | With schema changes |
| [UK_OPERATIONS.md](UK_OPERATIONS.md) | UK runbook | 280 | With changes |
| [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) | Feature roadmap | 800 | Weekly |
| [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md) | Risk gaps | 500 | Per remediation |
| [research/readme.md](research/README.md) | Research governance | 300 | Per phase |

---

## 🏃 Quick Commands Cheat Sheet

```bash
# Health check
python main.py uk_health_check --profile uk_paper --strict-health

# Paper trading (30 min session, UK symbols)
python main.py paper_trial --confirm-paper-trial --profile uk_paper --paper-duration-seconds 1800

# Backtest (full year)
python main.py backtest --start 2025-01-01 --end 2026-01-01 --profile uk_paper

# Run tests
python -m pytest tests/ -v

# Format code
black src/ tests/

# Check code quality
pylint src/ --rcfile=.pylintrc --exit-zero
```

---

## 🎓 Learning Paths

### Path 1: I'm a Developer (Add Features)
1. [CLAUDE.md](CLAUDE.md) — Project purpose
2. [EXECUTION_FLOW.md](EXECUTION_FLOW.md) — How it runs
3. [.python-style-guide.md](.python-style-guide.md) — Code standards
4. [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) — Feature categories
5. Pick a task from [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)
6. Implement + test + PR

### Path 2: I'm a Data Scientist (Research Features & Models)
1. [CLAUDE.md](CLAUDE.md) — Project purpose
2. [research/README.md](research/README.md) — Research governance
3. [research/specs/UK_UNIVERSE.md](research/specs/UK_UNIVERSE.md) — What to analyze
4. [research/specs/FEATURE_LABEL_SPEC.md](research/specs/FEATURE_LABEL_SPEC.md) — How to engineer
5. [research/specs/VALIDATION_PROTOCOL.md](research/specs/VALIDATION_PROTOCOL.md) — How to validate
6. Pick a research prompt from [research/prompts/](research/prompts/) or [docs/DATA_PROVIDERS_REFERENCE.md](docs/DATA_PROVIDERS_REFERENCE.md)

### Path 3: I'm a Risk Manager (Understand Controls)
1. [CLAUDE.md](CLAUDE.md) — Project purpose
2. [EXECUTION_FLOW.md](EXECUTION_FLOW.md) — Control flow
3. [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md) — Gap analysis
4. [UK_OPERATIONS.md](UK_OPERATIONS.md) — Operational checks
5. [docs/WEEKLY_REVIEW_TEMPLATE.md](docs/WEEKLY_REVIEW_TEMPLATE.md) — Monitoring

### Path 4: I'm an Operator (Run & Monitor)
1. [UK_OPERATIONS.md](UK_OPERATIONS.md) — Operational runbook
2. [TRIAL_MANIFEST.md](TRIAL_MANIFEST.md) — Paper trial setup
3. [docs/WEEKLY_REVIEW_TEMPLATE.md](docs/WEEKLY_REVIEW_TEMPLATE.md) — Weekly checklist
4. [docs/PROMOTION_CHECKLIST.md](docs/PROMOTION_CHECKLIST.md) — Pre-promotion checks

---

## 🤔 Still Confused?

**Check:** [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) for the full list (sorted by layer)

**Or search** for keywords:
- "execution" → [EXECUTION_FLOW.md](EXECUTION_FLOW.md)
- "risk" → [docs/RISK_ARCHITECTURE_REVIEW.md](docs/RISK_ARCHITECTURE_REVIEW.md)
- "research" → [research/README.md](research/README.md)
- "paper" → [UK_OPERATIONS.md](UK_OPERATIONS.md)
- "style" → [.python-style-guide.md](.python-style-guide.md)
- "tasks" → [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md)

---

**Last updated:** Feb 24, 2026
