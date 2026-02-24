# GitHub Copilot Instructions — Trading Bot

These instructions are read automatically by GitHub Copilot in this workspace.
Follow them for every suggestion, completion, and edit in this repository.

---

## Reading Order (do this before any structural change)

1. **`PROJECT_DESIGN.md`** — Why things are built the way they are (ADRs, RFCs, debt register)
2. **`CLAUDE.md`** — Session context, invariants, file layout, run commands
3. **`IMPLEMENTATION_BACKLOG.md`** — What to build next and in what priority order
4. **`.python-style-guide.md`** — How to write the code

For non-trivial tasks, read all four before generating code.

---

## Hard Invariants — Never Break These

- `RiskManager.approve_signal()` is the **only** path from `Signal` to `Order`. Never submit orders directly from strategies.
- `BacktestEngine` uses `PaperBroker`, not `AlpacaBroker`. Never mix them.
- `generate_signal()` must return `None` if `len(df) < min_bars_required()`. No exceptions.
- `Signal.strength` must be in `[0.0, 1.0]`. It scales position size.
- Never hardcode ticker symbols or dates. Use `config/settings.py`.
- All timestamps must be timezone-aware (UTC). Use `pd.to_datetime(..., utc=True)`.
- Neural network models must be version-controlled with metadata (training date, params, metrics).

---

## Architecture

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| Config | `config/settings.py` | All parameters — edit here first |
| Data | `src/data/feeds.py` | Fetch OHLCV via yfinance |
| Models | `src/data/models.py` | Bar, Signal, Order, Position dataclasses |
| Strategies | `src/strategies/` | One file per strategy; all inherit `BaseStrategy` |
| Risk | `src/risk/manager.py` | Gate between signals and orders |
| Broker | `src/execution/broker.py` | `AlpacaBroker` (live/paper) + `PaperBroker` (backtest) |
| Portfolio | `src/portfolio/tracker.py` | P&L and metrics |
| Backtest | `backtest/engine.py` | Bar replay, zero lookahead |
| Entry | `main.py` | CLI: backtest / paper / live modes |

---

## Code Style — Key Rules

- **Type hints** on all public functions: `def fetch(symbol: str) -> pd.DataFrame:`
- **NumPy-style docstrings** on all public classes and functions
- **Private methods** prefixed with `_`: `def _validate()`
- **UTC-aware timestamps**: `pd.to_datetime(df.index, utc=True)`
- **One statement per line** — no compound `if x: return y`
- **No `eval()`, `exec()`, or `__getattr__` magic**
- **No mutable default arguments** — use `None` sentinel: `def f(items=None): items = items or []`
- **No late-binding closures** — capture loop variables explicitly: `lambda x=val: x`
- **No circular imports** — `src/` must not import from `main.py`
- **Prefer pure functions** for computations; reserve classes for stateful components
- **Boolean tests**: `if x:` not `if x == True:`
- **String building**: `''.join(parts)` not `s += part` in a loop
- **Throwaway variables**: `_` for intentionally unused

---

## LPDD System (Architecture Decision Records)

This project uses a **Living Project Design Document** in `PROJECT_DESIGN.md`.

When you make or suggest a structural change, you must:

| Event | Action |
|-------|--------|
| Completing a backlog step | Mark the corresponding RFC as CLOSED in `PROJECT_DESIGN.md §4`; append to `§6 Evolution Log` |
| Making a new structural decision | Add an ADR to `PROJECT_DESIGN.md §3` (copy existing format); reference ADR number in commits |
| Raising a design question | Add an RFC to `PROJECT_DESIGN.md §4` with status `PROPOSED`; link to backlog step |
| Discovering technical debt | Add entry to `PROJECT_DESIGN.md §5`; create a backlog step if actionable |

ADR numbering: `ADR-013`, `ADR-014`, ... (check §3 for last used number).
RFC numbering: `RFC-004`, `RFC-005`, ... (check §4 for last used number).
**Never** retroactively change ACCEPTED ADRs — supersede them with a new one.

---

## What NOT to Do

- Do not import from `main.py` in `src/` modules (hidden coupling — see TD-001)
- Do not add new features to `main.py` directly — it is a refactor target (RFC-001)
- Do not add `IBKRBroker` logic without inheriting `BrokerBase` (RFC-002)
- Do not skip `Signal.strength` range validation (RFC-003)
- Do not add SQLite connections in reporting functions — share one connection
- Do not hardcode `IEX Cloud` credentials or references — provider was removed
- Do not create a new `.md` file for a session-specific result — use `archive/` or `PROJECT_DESIGN.md §6`

---

## Testing

All tests must pass before any task is considered complete:

```bash
python -m pytest tests/ -v
```

Never skip a failing test. Fix the underlying code.

---

## Adding a New Strategy

1. Create `src/strategies/<name>.py` subclassing `BaseStrategy`
2. Implement `generate_signal(symbol) -> Optional[Signal]`
3. Set `min_bars_required()` to the longest lookback period
4. Register in `main.py` STRATEGIES dict
5. Add tests in `tests/test_strategies.py`

The MA crossover (`src/strategies/ma_crossover.py`) is the canonical example.

---

*For full context: see `PROJECT_DESIGN.md` (LPDD), `CLAUDE.md` (session context), `IMPLEMENTATION_BACKLOG.md` (task queue), `.python-style-guide.md` (code style).*

**Last Updated:** February 24, 2026
