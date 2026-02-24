# Pre-Build Research Questions

Answer each question in LibreChat using the model specified.
Paste the response into the answer slot and mark the status `[x]`.

When a block is fully answered, open a Claude Code session and say:
> "Read RESEARCH_QUESTIONS.md — Block N is answered. Use those decisions to implement [component]."

---

## How to format your answers

Paste LibreChat responses in this structure (example shown for Q1):

```
### Q1 — ANSWER
**Model used:** qwen2.5-coder 32B (deep)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
DuckDB + Parquet is the recommended choice for this use case. It requires
no Docker setup, handles 50-instrument rolling-window queries in milliseconds
via columnar storage, and produces portable .parquet files for later migration.
TimescaleDB adds operational complexity (PostgreSQL instance, extension install)
that is not justified at solo-developer scale.

**Key decision:**
Use DuckDB + Parquet for the time-series store.
- Parquet files: one file per symbol per timeframe (e.g. AAPL_1d.parquet)
- DuckDB: in-process query engine, no server required
- SQLAlchemy (existing): retained for strategy registry / signals / audit log only

**Full response:**
[paste the complete LibreChat response here]
```

---

## BLOCK 1 — Storage & Architecture
**Model: qwen2.5-coder 32B (deep) in LibreChat**
These three questions must all be answered before the storage layer is built.

---

### Q1 — Time-series storage choice
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I am building a Python algorithmic trading platform for US equities and crypto.
I need to store OHLCV bars (1m, 5m, 1h, 1d) plus trade ticks for 10-50
instruments over 5+ years of history. The system is self-hosted on a Windows
11 developer machine with Docker available.

Compare three approaches:
1. TimescaleDB (PostgreSQL + hypertables, runs in Docker)
2. DuckDB + Parquet files (in-process, no server)
3. SQLite + SQLAlchemy (already scaffolded in the project)

For each, give:
- Query performance for rolling-window backtests across 10+ instruments
- Operational complexity and Docker setup effort
- Schema migration approach
- Suitability for incremental daily appends
- Your final recommendation for a solo developer, with justification

Be concrete. Give example query patterns for each.
```

### Q1 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q2 — Event-driven vs vectorised backtesting engine
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I have an existing bar-by-bar (event-driven) backtesting engine in Python.
The enterprise requirement mandates event-driven style so the same strategy
code can run in both backtests and live WebSocket trading.

Answer these questions:
1. What are the performance and correctness tradeoffs between event-driven
   and vectorised (pandas/numpy) backtesting?
2. For a system that connects to a live WebSocket feed, which approach causes
   less code duplication between backtest and live?
3. What is the recommended Python architecture for an event-driven engine:
   - Queue-based (asyncio.Queue)
   - Callback-based (on_bar() hooks)
   - Async generator-based
4. How should historical data replay be structured to be zero-lookahead?
   Specifically: when is it safe to call generate_signal() relative to the
   bar timestamp?

Give a concrete Python skeleton for whichever architecture you recommend.
```

### Q2 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q3 — Strategy registry design
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I need a strategy registry for a Python trading platform. It must track:
- strategy_id, name, version (semantic versioning)
- type: rule-based or NN-based
- parameters (dict, JSON-serialisable)
- model artifact path (path to .pt weights file, if NN-based)
- status: experimental | approved_for_paper | approved_for_live

Requirements:
- Load a strategy by name + version
- List all strategies and their metadata
- Approve/promote a strategy through the status pipeline
- Store PyTorch .pt weight files alongside metadata

Compare:
A) YAML/JSON files on disk (one per strategy version)
B) SQLite table (alongside the market data DB)
C) Hybrid: metadata in SQLite, artifacts on disk with hash verification

Give:
- Tradeoffs for a solo developer
- Your recommended approach with justification
- A concrete Python class skeleton for the registry
- How to version PyTorch model weights alongside strategy metadata
```

### Q3 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

## BLOCK 2 — Data Providers & APIs
**Model: `gemini-2.5-flash` in LibreChat** (select this exact model — the pro variants are non-functional)
> Why Gemini for this block: these questions need current 2025/2026 API limit data.
> Gemini 2.5 Flash has up-to-date knowledge; local models do not.

---

### Q4 — Free data provider capabilities
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I am building a self-hosted trading bot on a free/low-cost budget.
For each provider below, give the current (early 2026) free tier limits:

1. Polygon.io
   - How many years of OHLCV history on free tier?
   - Rate limits (requests/minute)?
   - WebSocket access on free tier?

2. Tiingo
   - Free tier OHLCV history depth and rate limits?

3. Alpha Vantage
   - Free tier daily bar history depth and rate limits?

4. Yahoo Finance (via yfinance Python library)
   - Any known reliability issues or API changes in 2025/2026?
   - Is it still suitable for 5+ years of daily OHLCV?

5. Alpaca Markets (paper trading account, free tier)
   - How many years of historical data via REST API?
   - Does the free paper account include real-time WebSocket bar streaming?
   - Rate limits?

Final question: which combination gives the most complete free stack for:
- 5+ years of daily bars for backtesting
- Real-time 1-minute bars for paper trading
```

### Q4 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q5 — Alpaca Paper API WebSocket streaming
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I want to use Alpaca Paper Trading as my sandbox execution provider and
real-time data source using the alpaca-py Python SDK (latest version, 2026).

Answer:
1. Does the Alpaca Paper account provide real-time WebSocket bar/trade streams,
   or is polling required?
2. What subscription tier is needed for 1-minute bar streaming?
3. What are the reconnection and heartbeat requirements?
4. Are there known reliability issues with Alpaca Paper in 2025/2026?

Then give a working Python code example using alpaca-py that:
- Subscribes to 1-minute bars for ["AAPL", "MSFT"]
- Handles automatic reconnection on disconnect
- Prints each bar as it arrives
- Runs as an async coroutine

Use the current alpaca-py API (not the legacy alpaca-trade-api library).
```

### Q5 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

## BLOCK 3 — Neural Network Strategy Pipeline
**Model: GitHub Copilot Chat (recommended) OR qwen2.5 14B in LibreChat**
> **Use Copilot** for Q6 and Q7. GPT-4o (which powers Copilot) is significantly stronger
> than qwen2.5 14B on PyTorch, ML architecture, and financial feature engineering.
> In VS Code: open Copilot Chat, type `@workspace` then paste the prompt below.

---

### Q6 — Feature engineering for price direction classification
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I want to build a neural-net strategy that predicts whether a stock's
close price will be higher in N bars (binary classification: 1=up, 0=down).
Input data: daily OHLCV bars. Target: 5-day forward return direction.

Answer:
1. What OHLCV-derived features work best for this task?
   Include a prioritised list covering: rolling returns, log returns,
   volatility, RSI, MACD histogram, Bollinger Band position,
   volume ratios (today vs rolling avg), and any others worth including.

2. What rolling window sizes are standard (e.g. 10, 20, 60 bars)?
   Which window gives the best signal-to-noise ratio for daily data?

3. How should features be normalised across different instruments
   and time periods WITHOUT lookahead bias?
   - Rolling z-score? Expanding window? Min-max?

4. How do I create the binary label (1 = close[t+5] > close[t])
   without leaking future data into training?
   Show the pandas code for creating this label column correctly.

5. What percentage of features typically survive a feature importance
   filter (e.g. only keep top 20)?
```

### Q6 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q7 — NN architecture baseline for price direction
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I need a baseline PyTorch neural network for binary price-direction
classification on daily OHLCV features (from Q6 above).

Compare these architectures:
1. Simple MLP (2-3 hidden layers)
2. 1D-CNN (convolutional over time steps)
3. LSTM (sequential, handles temporal dependencies)

For each, give:
- Input shape (sequence_length, num_features)
- Recommended hidden dimensions for a first prototype
- Training time estimate on 5 years of daily data, 50 instruments, CPU-only
- Ease of integration as a trading strategy (must call strategy.generate_signal())

Then:
- Recommend one architecture for a first prototype, with justification
- Give a complete PyTorch class skeleton (nn.Module) for that architecture
- State: loss function, output activation, threshold for BUY signal
- Explain how to do a time-aware train/val/test split that avoids data leakage
  (e.g. train on 2018-2022, val on 2023, test on 2024)
- List 3 metrics to track beyond accuracy (precision, Sharpe of signals, etc.)
```

### Q7 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

## BLOCK 4 — Risk Management
**Model: GitHub Copilot Chat (recommended) OR qwen2.5 14B in LibreChat**
> **Use Copilot** for Q8 and Q9. GPT-4o handles quantitative finance mathematics
> (VaR, CVaR, Kelly criterion) and asyncio design patterns more reliably than
> qwen2.5 14B. No file context needed — just paste the prompt.

---

### Q8 — VaR and CVaR implementation
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
I want to add Value at Risk (VaR) and Conditional VaR (CVaR / Expected
Shortfall) limits to a Python trading bot risk manager.

The system: Python, pandas/numpy, daily bars, portfolio of 5-20 positions,
$10k-$100k notional, retail (not institutional).

Answer:
1. Which VaR method is most practical for retail:
   - Historical simulation (uses actual past returns)
   - Parametric / variance-covariance (assumes normality)
   - Monte Carlo (simulates scenarios)
   Compare accuracy vs implementation complexity.

2. How many days of return history are needed for reliable 95% VaR estimates?
   What's the minimum usable history?

3. Give the numpy implementation for both:
   - 1-day 95% Historical VaR (portfolio level)
   - 1-day 95% CVaR (Expected Shortfall)

4. How should the VaR limit be used operationally?
   - Reject new orders when projected portfolio VaR exceeds X% of capital?
   - Or use it as a reporting metric only?

5. Is ATR-based position sizing a simpler alternative that gives similar
   protection? Compare the two approaches for a retail bot.

Give working Python code for the final recommendation.
```

### Q8 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q9 — Kill-switch design
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
My Python trading bot needs a kill-switch that satisfies these requirements:
- Triggered manually: operator writes a file or sets an env var
- Triggered automatically: drawdown limit exceeded, data feed errors,
  or N consecutive order rejections
- Must PERSIST across process restarts (bot stays halted after a crash)
- When triggered: close all open positions in the correct sequence
- Must be resettable: operator reviews situation, then clears the halt

Design the kill-switch for a Python asyncio trading loop.

Provide:
1. The state persistence mechanism (file vs SQLite vs env var) with tradeoffs
2. The position liquidation sequence:
   - What order type to use for emergency close (market vs limit)?
   - How to handle partial fills during liquidation?
   - What to log for audit trail?
3. The safe resume protocol: what checks before re-enabling trading?
4. A Python class skeleton: KillSwitch with methods:
   - trigger(reason: str) -> None
   - is_active() -> bool
   - reset(operator_id: str) -> None
   - check_and_raise() (called before each order)
5. How to integrate into an asyncio event loop without blocking
```

### Q9 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

## BLOCK 5 — Code Review of Existing Scaffold
**Model: GitHub Copilot Chat with `@workspace` (strongly recommended)**
> **Use Copilot** for Q10 and Q11. Copilot can read the actual project files
> directly via `@workspace` — no copy-pasting required. It will analyse the
> live source code in your IDE and give line-specific feedback.
>
> **How to use Copilot for these questions:**
> 1. Open Copilot Chat in VS Code (Ctrl+Shift+I or the chat icon)
> 2. Start your message with `@workspace`
> 3. Paste the review prompt — Copilot will read the referenced files itself
>
> **Alternative:** deepseek-coder 33B in LibreChat (paste file contents manually)

---

### Q10 — Risk manager correctness review
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
Review the following Python risk management module for a trading bot.

[PASTE THE FULL CONTENTS OF src/risk/manager.py HERE]

Review for:
1. Mathematical correctness of the fixed-fractional sizing formula:
      risk_dollars = portfolio_value * max_portfolio_risk_pct * signal_strength
      qty_from_risk = risk_dollars / (price * stop_loss_pct)
   Is this formula correct? What does it actually compute?

2. Division-by-zero or negative qty edge cases:
   - What happens if price = 0?
   - What if stop_loss_pct = 0?
   - What if portfolio_value = 0 or negative?
   - What if signal_strength is outside [0, 1]?

3. Missing circuit breaker conditions:
   - The current breaker only checks peak drawdown. What other automatic
     halt conditions are missing for enterprise use?

4. Thread safety:
   - Is _peak_value safe if multiple symbols are processed concurrently?
   - What locking is needed?

5. Top 3 missing risk controls an institution would expect, in priority order.

For each issue found, give: severity (critical/high/medium/low), description,
and the corrected code.
```

### Q10 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

### Q11 — Backtest engine lookahead bias audit
**Status: [ ] PENDING**

**Prompt to paste into LibreChat:**
```
Audit the following Python backtesting engine for correctness and bias.

[PASTE THE FULL CONTENTS OF backtest/engine.py HERE]

Review for:
1. Lookahead bias:
   - Is the signal generated on bar N using ONLY data available at the
     close of bar N?
   - Is there any path where price data from bar N+1 or later can
     influence the signal at bar N?

2. Off-by-one errors:
   - In rolling window calculations within strategies, is the boundary
     condition (min_bars_required) correctly enforced?

3. PnL calculation correctness:
   - Does the trade['pnl'] calculation correctly handle:
     - Multiple entries and exits on the same symbol?
     - Partial fills?
     - Multi-instrument portfolios?

4. Missing transaction costs:
   - What slippage and commission assumptions are missing?
   - How would adding realistic costs (0.05% slippage, $0.005/share)
     change the PnL calculation?

5. Sharpe ratio correctness:
   - Is the annualisation factor (252^0.5) correct for daily bars?
   - Is the risk-free rate assumption documented?

For each issue: severity, description, corrected code.
```

### Q11 — ANSWER
**Model used:**
**Date answered:**
**Summary:**

**Key decision:**

**Full response:**
[paste here]

---

## Research Status

Update the checkboxes as you complete each question.

| Block | # | Topic | Best model | Done? |
|-------|---|-------|------------|-------|
| Storage | Q1 | Time-series DB choice | LibreChat: qwen2.5-coder 32B | [ ] |
| Storage | Q2 | Backtest engine architecture | LibreChat: qwen2.5-coder 32B | [ ] |
| Storage | Q3 | Strategy registry design | LibreChat: qwen2.5-coder 32B | [ ] |
| Providers | Q4 | Free data provider limits | LibreChat: **gemini-2.5-flash** | [ ] |
| Providers | Q5 | Alpaca WebSocket streaming | LibreChat: **gemini-2.5-flash** | [ ] |
| NN | Q6 | Feature engineering | **Copilot Chat** (@workspace) | [ ] |
| NN | Q7 | NN architecture baseline | **Copilot Chat** (@workspace) | [ ] |
| Risk | Q8 | VaR / CVaR implementation | **Copilot Chat** | [ ] |
| Risk | Q9 | Kill-switch design | **Copilot Chat** | [ ] |
| Review | Q10 | Risk manager code review | **Copilot Chat** (@workspace) | [ ] |
| Review | Q11 | Backtest engine audit | **Copilot Chat** (@workspace) | [ ] |

**Immediate task (no research needed):**
Give Q12 directly to Claude Code:
> Add `src/strategies/bollinger_bands.py`: BUY at lower band, SELL at middle band.
> Follow `ma_crossover.py` pattern. Register in `main.py`. Add tests. All must pass.
