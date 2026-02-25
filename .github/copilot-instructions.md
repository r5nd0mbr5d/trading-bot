# GitHub Copilot Instructions — Trading Bot

These instructions are read automatically by GitHub Copilot in this workspace.
Follow them for every suggestion, completion, and edit in this repository.

---

## Reading Order (do this before any structural change)

1. **`PROJECT_DESIGN.md`** — Why things are built the way they are (ADRs, RFCs, debt register)
2. **`CLAUDE.md`** — Session context, invariants, file layout, run commands
3. **`IMPLEMENTATION_BACKLOG.md`** — What to build next; start at the **Copilot Task Queue** section
4. **`.python-style-guide.md`** — How to write the code

For non-trivial tasks, read all four before generating code.

---

## Task Pickup Protocol

Follow these steps at the start of every Copilot session:

1. **Read the four docs above** — understand the current state before touching any code
2. **Open `IMPLEMENTATION_BACKLOG.md` → Copilot Task Queue** — find the highest-priority NOT STARTED step in the "Immediately Actionable" table
3. **Read the full step definition** — scroll to the `### Step N` entry and read every field
4. **Check pre-conditions** — confirm all listed dependencies have Status = COMPLETED; if not, pick the next unblocked step
5. **Implement** — follow the Execution Prompt exactly; create or extend files listed in Scope
6. **Run the full test suite** — `python -m pytest tests/ -v`; all tests must pass before marking done
7. **Update LPDD** (mandatory):
   - Change step Status to `COMPLETED` with today's date in `IMPLEMENTATION_BACKLOG.md`
   - Update the executive summary counts (Completed +1, Not Started −1, test count)
   - Append an entry to `PROJECT_DESIGN.md §6 Evolution Log`
8. **Commit** with a clear message referencing the step number: `feat(step-63): add CoinbaseBroker`

### When to Stop and Escalate to Claude Opus

Stop immediately and leave a `**BLOCKED:**` note in the step's Completion Notes if:

- The task is labelled **"Claude Opus"** in the Copilot Task Queue
- You need to make a structural/architectural decision not described in the step
- A test is failing due to a design ambiguity (not a bug)
- The step requires evaluating trade-offs between approaches
- You are about to create a new module with no existing pattern to follow
- Implementing the step would require modifying more than 5 files you haven't read

**Do not guess at architecture. Commit what you have, leave the blocker note, stop.**

---

## Hard Invariants — Never Break These

- `RiskManager.approve_signal()` is the **only** path from `Signal` to `Order`. Never submit orders directly from strategies.
- `BacktestEngine` uses `PaperBroker`, not `AlpacaBroker` or `CoinbaseBroker`. Never mix them.
- `generate_signal()` must return `None` if `len(df) < min_bars_required()`. No exceptions.
- `Signal.strength` must be in `[0.0, 1.0]`. It scales position size.
- Never hardcode ticker symbols or dates. Use `config/settings.py`.
- All timestamps must be timezone-aware (UTC). Use `pd.to_datetime(..., utc=True)`.
- Neural network models must be version-controlled with metadata (training date, params, metrics).
- `research/` layer must not import from `src/` at module level — only via `research/bridge/strategy_bridge.py`.
- `coinbase_sandbox` and `binance_testnet` must remain `True` until MO-2 is closed and equity live gate is passed.

---

## Architecture

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| Config | `config/settings.py` | All parameters — edit here first |
| Data | `src/data/feeds.py` | Fetch OHLCV via yfinance |
| Symbol utils | `src/data/symbol_utils.py` | Provider-specific symbol normalisation |
| Models | `src/data/models.py` | Bar, Signal, Order, Position, AssetClass dataclasses |
| Strategies | `src/strategies/` | One file per strategy (8 total); all inherit `BaseStrategy` |
| Risk | `src/risk/manager.py` | Gate between signals and orders; crypto overlay via `CryptoRiskConfig` |
| Broker — Equities paper | `src/execution/broker.py` → `AlpacaBroker` | Alpaca paper trading (equities) |
| Broker — Equities live | `src/execution/broker.py` → `IBKRBroker` | Interactive Brokers live |
| Broker — Crypto primary | `src/execution/broker.py` → `CoinbaseBroker` | Coinbase Advanced Trade (Step 63) |
| Broker — Crypto fallback | `src/execution/broker.py` → `BinanceBroker` | Binance fallback (testnet) |
| Broker — Backtest | `src/execution/broker.py` → `PaperBroker` | In-memory simulation; BacktestEngine only |
| Portfolio | `src/portfolio/tracker.py` | P&L and metrics |
| Backtest | `backtest/engine.py` | Bar replay, zero lookahead |
| Trading loop | `src/trading/loop.py` | `TradingLoopHandler`; broker factory with crypto fallback routing |
| CLI | `src/cli/arguments.py`, `src/cli/runtime.py` | Argument parsing and mode dispatch |
| Entry | `main.py` | 62-line wiring only — do NOT add logic here |

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

## LPDD Update Conventions

This project uses a **Living Project Design Document** in `PROJECT_DESIGN.md`.

| Event | Action |
|-------|--------|
| Completing a backlog step | Mark step COMPLETED + date; update executive summary; append to `PROJECT_DESIGN.md §6 Evolution Log` |
| Making a new structural decision | Add an ADR to `§3` (copy existing format); reference ADR number in commit message |
| Raising a design question | Add an RFC to `§4` with status `PROPOSED`; link to relevant backlog step |
| Discovering technical debt | Add entry to `§5`; create a backlog step if actionable |

- ADR numbering: `ADR-016`, `ADR-017`, ... (check §3 for last used number — currently ADR-015)
- RFC numbering: `RFC-005`, `RFC-006`, ... (check §4 for last used — currently RFC-004)
- **Never** retroactively change ACCEPTED ADRs — supersede with a new one

---

## What NOT to Do

- Do not import from `main.py` in `src/` modules (TD-001 — resolved; keep it that way)
- Do not add logic to `main.py` — it is entrypoint-only wiring (62 lines)
- Do not use `AlpacaBroker` or `CoinbaseBroker` in `BacktestEngine` — `PaperBroker` only
- Do not skip `Signal.strength` range validation (RFC-003)
- Do not add SQLite connections in reporting functions — share one connection
- Do not hardcode `IEX Cloud` credentials or references — provider was removed
- Do not create a new `.md` file for a session result — use `archive/` or `PROJECT_DESIGN.md §6`
- Do not set `coinbase_sandbox=False` or `binance_testnet=False` without explicit operator instruction
- Do not attempt steps labelled **"Needs Claude Opus"** in the Copilot Task Queue

---

## Testing

All tests must pass before any task is considered complete:

```bash
python -m pytest tests/ -v
```

Current baseline: **498 passing**. Never skip a failing test — fix the underlying code.

---

## Adding a New Strategy

1. Create `src/strategies/<name>.py` subclassing `BaseStrategy`
2. Implement `generate_signal(symbol) -> Optional[Signal]`
3. Set `min_bars_required()` to the longest lookback period (use ≥ 3× for ATR-dependent strategies — see TD-015)
4. Register in `src/cli/runtime.py` strategy map (not `main.py`)
5. Add tests in `tests/test_strategies.py`

The MA crossover (`src/strategies/ma_crossover.py`) is the canonical example.

---

## Adding a New Broker

1. Implement `MyBroker(BrokerBase)` in `src/execution/broker.py`
2. Add config fields to `BrokerConfig` in `config/settings.py` (read from env vars)
3. Add provider key to `normalize_symbol()` in `src/data/symbol_utils.py`
4. Register in broker factory in `src/trading/loop.py`
5. Add tests with fully mocked API calls — never make live API calls in tests

`BinanceBroker` is the canonical crypto broker pattern.

---

*For full context: `PROJECT_DESIGN.md` (LPDD) · `CLAUDE.md` (session context) · `IMPLEMENTATION_BACKLOG.md` (task queue + Copilot Queue) · `.python-style-guide.md` (code style)*

**Last Updated:** February 25, 2026
