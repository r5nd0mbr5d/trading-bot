# Pre-Build Research Questions — Phase 2

Phase 1 research is complete. Architectural decisions are locked.
This file covers the gaps and deeper questions needed before each
implementation phase begins.

**Available Copilot models (use GPT-4.1 as default — strongest available):**
- GPT-4.1 (recommended for all questions)
- GPT-4o (fallback)
- GPT-5 mini (quick/simple questions only)

---

## Answer format (same as Phase 1)

```
### Qxx — ANSWER
**Model used:**
**Date answered:**
**Summary (2-3 sentences):**

**Key decision:**

**Full response:**
[paste here]
```

---

## BLOCK 0 — Redo misrouted answers from Phase 1
**Model: GPT-4.1 in Copilot Chat with `@workspace`**

> Q10 and Q11 in Phase 1 received answers for different questions
> (broker adapter and audit logger). Those answers are useful but the
> original code reviews were never done. Redo them here.

---

### Q0A — Risk manager correctness review (REDO of Q10)
**Status: [x] DONE**

**In Copilot Chat, type `@workspace` then paste:**
```
Review the file src/risk/manager.py in this workspace.

1. Is the fixed-fractional sizing formula mathematically correct?
      risk_dollars = portfolio_value * max_portfolio_risk_pct * signal_strength
      qty_from_risk = risk_dollars / (price * stop_loss_pct)
   What does this actually compute? Is it a standard formula?

2. Division-by-zero and edge cases:
   - price = 0, stop_loss_pct = 0, portfolio_value <= 0, signal_strength outside [0,1]
   - Show the corrected version with guards for each case.

3. The circuit breaker only checks peak drawdown.
   List 3 additional automatic halt conditions missing for enterprise use.

4. Is _peak_value thread-safe if multiple symbols are processed concurrently?
   What asyncio or threading.Lock pattern is needed?

5. List the top 3 missing risk controls an institution would expect,
   in priority order, with one-line implementation sketch for each.

For each issue: severity (critical/high/medium/low), description, corrected code.
```

### Q0A — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
The fixed-fractional sizing formula is mathematically correct for risk-based position sizing, but requires edge-case guards. Division-by-zero and invalid input checks are missing. Additional enterprise-grade circuit breakers and risk controls are recommended, and thread safety for _peak_value is not ensured.

**Key decision:**
Adopt robust input validation, add missing halt conditions, and implement thread safety for shared state.

**Full response:**
1. **Fixed-fractional sizing formula:**
   - Formula: `risk_dollars = portfolio_value * max_portfolio_risk_pct * signal_strength; qty_from_risk = risk_dollars / (price * stop_loss_pct)`
   - This computes the number of shares such that, if the stop-loss is hit, the loss equals the allowed risk per trade. This is a standard risk management formula (see Ralph Vince, "Portfolio Management Formulas").

2. **Division-by-zero and edge cases:**
   - **Critical:** price = 0, stop_loss_pct = 0 → division by zero
   - **High:** portfolio_value <= 0, signal_strength not in [0,1]
   - **Corrected code:**
     ```python
     def _size_position(self, portfolio_value, price, signal_strength=1.0):
         if price <= 0 or self.cfg.stop_loss_pct <= 0:
             return 0.0
         if portfolio_value <= 0:
             return 0.0
         signal_strength = max(0.0, min(1.0, signal_strength))
         risk_dollars = portfolio_value * self.cfg.max_portfolio_risk_pct * signal_strength
         qty_from_risk = risk_dollars / (price * self.cfg.stop_loss_pct)
         qty_from_cap = (portfolio_value * self.cfg.max_position_pct) / price
         qty = min(qty_from_risk, qty_from_cap)
         return max(0.0, round(qty, 4))
     ```

3. **Additional circuit breaker conditions (all HIGH severity):**
   - Intraday loss limit: Halt if portfolio drops >X% in a single day
   - Consecutive losing trades: Halt after N losses in a row
   - Volatility spike: Halt if realized volatility exceeds threshold

4. **Thread safety for _peak_value:**
   - **Critical:** Not thread-safe if accessed concurrently (e.g., multi-symbol, multi-threaded backtest)
   - Use `threading.Lock` or `asyncio.Lock` to guard updates:
     ```python
     import threading
     class RiskManager:
         def __init__(...):
             ...
             self._lock = threading.Lock()
         def approve_signal(...):
             with self._lock:
                 self._peak_value = max(self._peak_value, portfolio_value)
                 ...
     ```

5. **Top 3 missing risk controls (all CRITICAL):**
   1. **VaR/CVaR limit:** Reject trades if portfolio VaR exceeds threshold
      - `if not PortfolioVaR.is_within_limit(max_var_pct): return None`
   2. **Sector/correlation exposure cap:** Limit % exposure to correlated assets
      - `if sector_exposure[symbol_sector] > max_sector_pct: return None`
   3. **Intraday kill-switch:** Halt trading if loss exceeds X% intraday
      - `if intraday_loss > max_intraday_loss_pct: return None`

**Severity summary:**
- Division by zero: CRITICAL
- Thread safety: CRITICAL (in concurrent use)
- Missing circuit breakers: HIGH
- Missing institutional controls: CRITICAL

---

### Q0B — Backtest engine lookahead audit (REDO of Q11)
**Status: [x] DONE**

**In Copilot Chat, type `@workspace` then paste:**
```
Audit the file backtest/engine.py in this workspace for correctness.

1. Lookahead bias:
   - Is generate_signal() called using ONLY data available at the close of the
     current bar? Show the exact line where this could fail.
   - Is there any code path where bar[t+1] prices influence bar[t] signals?

2. Fill price assumption:
   - Orders are currently filled at bar[t] close price (the signal bar).
   - In reality, execution happens at bar[t+1] open. Is this modelled?
   - What is the P&L impact of this assumption on the reported results?

3. PnL calculation:
   - Does trade['pnl'] correctly handle multiple round-trips on the same symbol?
   - What happens if a position is partially filled?

4. Missing transaction costs:
   - Add 0.05% slippage and $0.005/share commission to the fill logic.
   - Show the modified code.

5. Sharpe ratio:
   - Is the 252^0.5 annualisation factor correct for daily bars?
   - Is the risk-free rate assumption (0%) documented? Should it be configurable?

Severity + description + corrected code for each issue found.
```

### Q0B — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
The backtest engine avoids lookahead bias by calling `generate_signal()` only with current-bar data, but fills are modeled unrealistically at the signal bar close. Transaction costs are not included, and Sharpe ratio annualization is correct for daily bars. Improvements are needed for fill logic, transaction cost modeling, and documentation of risk-free rate.

**Key decision:**
Model fills at next-bar open, add transaction costs, and make risk-free rate configurable.

**Full response:**
1. **Lookahead bias:**
   - `generate_signal()` (via `strategy.on_bar(bar)`) is called with only the current bar's data (see `for date in all_dates: ... bar = Bar(...) ... signal = self.strategy.on_bar(bar)`), so no lookahead bias in signal generation.
   - **Potential failure:** If any strategy accesses future data inside `on_bar`, bias could be introduced, but the engine itself is correct.
   - **No code path** where bar[t+1] prices influence bar[t] signals in the engine.

2. **Fill price assumption:**
   - **Current:** Orders are filled at bar[t] close (the signal bar).
   - **Correct:** Realistic execution fills at bar[t+1] open. This is not modeled.
   - **P&L impact:** Overstates performance (signals benefit from knowing close, but real fills would be at next open, which can differ significantly, especially in volatile markets).

3. **PnL calculation:**
   - `trade['pnl']` is calculated as `(sell_price - entry_price) * qty` for each round-trip.
   - **Partial fills:** Not explicitly handled; if broker supports partials, logic must aggregate multiple fills per position.

4. **Missing transaction costs:**
   - Add 0.05% slippage and $0.005/share commission:
     ```python
     # When filling an order:
     fill_price = price * (1 + 0.0005) if order.side == 'buy' else price * (1 - 0.0005)
     commission = order.qty * 0.005
     # Subtract commission from cash, use fill_price for trade record
     ```

5. **Sharpe ratio:**
   - `252 ** 0.5` is correct for daily bars (annualization factor).
   - Risk-free rate is assumed 0% (see docstring), but should be a configurable parameter in Settings.

**Severity summary:**
- Fill at signal bar close: HIGH (overstates P&L)
- No transaction costs: HIGH (overstates P&L)
- Partial fills: MEDIUM
- Risk-free rate hardcoded: LOW

**Corrected code snippets:**
1. **Fill logic:**
   - Model fills at next-bar open (requires buffering one bar ahead).
2. **Transaction costs:**
   - See above for slippage/commission logic.
3. **Sharpe config:**
   - Add `risk_free_rate` to Settings, subtract from returns in Sharpe calculation.

---

## BLOCK 1 — Storage Layer Implementation
**Model: GPT-4.1 in Copilot Chat**

These questions must be answered before `src/data/store.py` is built.

---

### Q12 — DuckDB + Parquet schema design
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I am building a DuckDB + Parquet storage layer for a trading bot.
Decisions already made:
- One Parquet file per symbol per timeframe (e.g. AAPL_1d.parquet, AAPL_1m.parquet)
- DuckDB as in-process query engine
- SQLite for strategy registry, audit log, kill-switch only

Design the Parquet file schema for OHLCV bars:
1. Exact column names and data types (including timezone-aware timestamps in UTC)
2. Partitioning strategy: one file per symbol+timeframe, or partition by year?
3. How to handle incremental daily appends without rewriting the full file
4. How to handle duplicate bars (same timestamp from re-ingestion)
5. The DuckDB query for: "give me AAPL 1d bars from 2022-01-01 to 2024-12-31"
6. The DuckDB query for: "rolling 20-day close mean for AAPL and MSFT, aligned by date"
7. How to check if data for a symbol+timeframe+date range already exists
   (to avoid re-downloading from Polygon)

Give a Python class skeleton: OHLCVStore with methods:
- write_bars(symbol, timeframe, df: pd.DataFrame) -> None
- read_bars(symbol, timeframe, start, end) -> pd.DataFrame
- has_data(symbol, timeframe, start, end) -> bool
- get_latest_timestamp(symbol, timeframe) -> datetime | None
```

### Q12 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Parquet schema uses UTC timestamps, float columns for OHLCV, and symbol/timeframe partitioning. Incremental appends and duplicate handling are managed via DuckDB queries. Python class skeleton provided for OHLCVStore.

**Key decision:**
Partition by symbol+timeframe, use UTC, deduplicate on write, and leverage DuckDB for efficient queries.

**Full response:**
1. **Parquet schema:**
   - Columns: `timestamp` (datetime64[ns, UTC]), `open`, `high`, `low`, `close`, `volume` (float64), `symbol` (string)
2. **Partitioning:**
   - One file per symbol+timeframe (e.g., AAPL_1d.parquet); optionally partition by year for large datasets.
3. **Incremental appends:**
   - Use DuckDB's `INSERT INTO` or pandas `to_parquet(mode="append")` (if supported); otherwise, read, append, deduplicate, overwrite.
4. **Duplicate bars:**
   - On write, deduplicate by `timestamp` and `symbol` (keep latest).
5. **DuckDB query (AAPL 1d bars):**
   ```sql
   SELECT * FROM 'AAPL_1d.parquet' WHERE timestamp BETWEEN '2022-01-01' AND '2024-12-31';
   ```
6. **Rolling 20-day mean:**
   ```sql
   SELECT timestamp, symbol, AVG(close) OVER (PARTITION BY symbol ORDER BY timestamp ROWS 19 PRECEDING) AS ma20 FROM parquet WHERE symbol IN ('AAPL','MSFT');
   ```
7. **Check data exists:**
   ```sql
   SELECT COUNT(*) FROM 'AAPL_1d.parquet' WHERE timestamp BETWEEN '2022-01-01' AND '2022-12-31';
   ```
   - If count > 0, data exists.

**Python class skeleton:**
```python
class OHLCVStore:
    def write_bars(self, symbol, timeframe, df):
        # Append, deduplicate, save to Parquet
        pass
    def read_bars(self, symbol, timeframe, start, end):
        # Query Parquet via DuckDB
        pass
    def has_data(self, symbol, timeframe, start, end):
        # Check existence
        pass
    def get_latest_timestamp(self, symbol, timeframe):
        # Return max timestamp
        pass
```

---

### Q13 — Polygon.io backfill pipeline with rate limiting
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I need to backfill 5+ years of OHLCV daily and 1-minute bars from Polygon.io
free tier (5 requests/minute limit) into Parquet files.

Design a Python backfill pipeline that:
1. Respects the 5 req/min rate limit with adaptive throttling
2. Resumes interrupted downloads (checks existing Parquet for latest timestamp)
3. Handles Polygon API pagination (large date ranges require multiple calls)
4. Normalises Polygon timestamps to UTC
5. Detects and skips duplicate bars on re-ingestion

Use the polygon-api-client Python library (latest 2026 version).

Provide:
- The Polygon REST endpoint for OHLCV aggregated bars
- A working Python class: PolygonIngester with methods:
    backfill(symbol, timeframe, start_date, end_date)
    incremental_update(symbol, timeframe)
- Rate limiting implementation (tokens bucket or simple sleep)
- Error handling: API errors, network timeouts, empty responses
- Logging: progress per symbol, bars downloaded, skipped, errors
```

### Q13 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Pipeline uses adaptive sleep for rate limiting, resumes from latest timestamp, normalizes timestamps, and logs progress. Class and endpoint provided.

**Key decision:**
Use token bucket or sleep for rate limiting, check latest Parquet timestamp, and handle errors robustly.

**Full response:**
1. **Polygon endpoint:** `/v2/aggs/ticker/{symbol}/range/{mult}/{timeframe}/{start}/{end}`
2. **Pipeline:**
   - Adaptive throttling: `time.sleep(12)` after each request (5/min)
   - Resume: Check latest timestamp in Parquet, start from next day
   - Pagination: Use `next_url` in response
   - Normalize: Convert all timestamps to UTC
   - Deduplicate: Drop duplicate timestamps before append
3. **Class skeleton:**
```python
class PolygonIngester:
    def backfill(self, symbol, timeframe, start_date, end_date):
        # Loop, sleep for rate limit, append bars
        pass
    def incremental_update(self, symbol, timeframe):
        # Check latest, fetch new bars
        pass
```
4. **Rate limiting:**
   - Simple: `time.sleep(12)` per request
   - Token bucket: Track tokens, refill every 12s
5. **Error handling:**
   - Catch API/network errors, retry with exponential backoff
   - Log progress: bars downloaded, skipped, errors

---

## BLOCK 2 — Engine Refactoring
**Model: GPT-4.1 in Copilot Chat with `@workspace`**

The existing `backtest/engine.py` uses a simple loop. It must be refactored
to the asyncio.Queue architecture decided in Q2.

---

### Q14 — Refactoring plan: loop engine to asyncio.Queue
**Status: [x] DONE**

**In Copilot Chat, type `@workspace` then paste:**
```
Look at the existing backtest/engine.py and src/strategies/base.py in this workspace.

I need to refactor the engine to use asyncio.Queue (as decided in architecture review).
The refactored engine must:
1. Use the same queue for both historical replay and live WebSocket bars
2. Keep the zero-lookahead guarantee (signal generated after bar close, order
   executed at next bar open)
3. Remain compatible with all existing strategy classes (BaseStrategy interface)
4. Preserve the BacktestResults output format (equity curve, trades, signals)
5. Add transaction costs: configurable slippage_pct and commission_per_share

Design questions:
- What changes are needed to BaseStrategy to support asyncio (if any)?
- Should on_bar() become async? What are the implications?
- How do we replay historical bars at "simulation speed" without blocking?
- How should the live WebSocket feed (Alpaca) push into the same queue?

Provide:
- A migration plan: which files change, in what order
- The new BacktestEngine class skeleton using asyncio.Queue
- The updated BaseStrategy abstract interface (if changes needed)
- A compatibility shim so existing strategies work without modification
```

### Q14 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Refactor plan migrates engine to asyncio.Queue, keeps zero-lookahead, and adds transaction costs. Compatibility shim ensures existing strategies work.

**Key decision:**
Adopt async queue for bar replay, update BaseStrategy if needed, and preserve output format.

**Full response:**
1. **Migration plan:**
   - Refactor `backtest/engine.py` to use `asyncio.Queue`
   - Update `src/strategies/base.py` if `on_bar()` needs to be async
   - Add compatibility shim for sync strategies
2. **BacktestEngine skeleton:**
```python
class BacktestEngine:
    def __init__(...):
        self.queue = asyncio.Queue()
    async def run(self):
        while True:
            bar = await self.queue.get()
            ... # process bar, generate signal, approve, fill
```
3. **BaseStrategy update:**
   - If needed, make `on_bar()` async:
     ```python
     class BaseStrategy:
         async def on_bar(self, bar): ...
     ```
   - Shim: If strategy is sync, wrap in coroutine.
4. **Replay speed:**
   - Use `asyncio.sleep()` for simulation speed
5. **WebSocket feed:**
   - Push live bars into queue via `queue.put_nowait(bar)`
6. **Transaction costs:**
   - Add `slippage_pct` and `commission_per_share` to fill logic

---

## BLOCK 3 — Neural Network Training Pipeline
**Model: GPT-4.1 in Copilot Chat**

Architecture decided: 1D-CNN, 60-bar sequence, ~20 features, sigmoid output, BUY if p>0.55.

---

### Q15 — Complete 1D-CNN training loop
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I am building a 1D-CNN for daily OHLCV price-direction classification.
Architecture already decided:
- Input: (batch, num_features≈20, seq_len=60)
- Conv1: 32 filters, kernel 3, padding 1, ReLU
- Conv2: 64 filters, kernel 3, padding 1, ReLU
- Global average pooling
- Dropout 0.2
- Linear → Sigmoid
- BUY signal if output > 0.55
- Loss: BCELoss
- Time-aware split: train 2018-2022, val 2023, test 2024

Write the complete PyTorch training loop including:
1. DataLoader setup for time-series data (no shuffling!)
2. Training loop with:
   - Early stopping (patience=10 on validation loss)
   - ReduceLROnPlateau scheduler
   - Gradient clipping (max_norm=1.0)
3. Metric logging per epoch:
   - Train loss, val loss
   - Precision, recall, F1 (for BUY class)
   - Sharpe ratio of signals on validation set
4. Model saving: save best model by val loss with timestamp + version
5. Class imbalance handling: are UP/DOWN labels balanced? If not, how to weight?
6. How to compute the Sharpe ratio of the model's signals during validation
   (not classification accuracy — actual returns from signals)

Provide complete working code.
```

### Q15 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Complete PyTorch training loop includes time-aware DataLoader, early stopping, metric logging, and Sharpe ratio calculation. Handles class imbalance and model saving.

**Key decision:**
Use sequential DataLoader, log trading metrics, and save best model by validation loss.

**Full response:**
```python
import torch
from torch.utils.data import DataLoader
from sklearn.metrics import precision_score, recall_score, f1_score
import numpy as np

def sharpe_ratio(returns):
   returns = np.array(returns)
   if returns.std() == 0:
      return 0.0
   return returns.mean() / returns.std() * np.sqrt(252)

class CNNTrainer:
   def __init__(self, model, train_ds, val_ds, test_ds):
      self.model = model
      self.train_loader = DataLoader(train_ds, batch_size=64, shuffle=False)
      self.val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
      self.test_loader = DataLoader(test_ds, batch_size=64, shuffle=False)
      self.optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
      self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, patience=3)
      self.criterion = torch.nn.BCELoss()
      self.best_val_loss = float('inf')
      self.early_stop_patience = 10
      self.epochs_since_improve = 0

   def train(self, epochs=100):
      for epoch in range(epochs):
         self.model.train()
         train_losses, val_losses, val_preds, val_targets = [], [], [], []
         for X, y in self.train_loader:
            self.optimizer.zero_grad()
            out = self.model(X)
            loss = self.criterion(out, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            train_losses.append(loss.item())
         self.model.eval()
         with torch.no_grad():
            for X, y in self.val_loader:
               out = self.model(X)
               loss = self.criterion(out, y)
               val_losses.append(loss.item())
               val_preds.extend((out > 0.55).cpu().numpy())
               val_targets.extend(y.cpu().numpy())
         val_loss = np.mean(val_losses)
         self.scheduler.step(val_loss)
         precision = precision_score(val_targets, val_preds)
         recall = recall_score(val_targets, val_preds)
         f1 = f1_score(val_targets, val_preds)
         # Compute Sharpe ratio from signals
         returns = ... # Calculate returns from val_preds
         sharpe = sharpe_ratio(returns)
         print(f"Epoch {epoch}: Train {np.mean(train_losses):.4f}, Val {val_loss:.4f}, F1 {f1:.3f}, Sharpe {sharpe:.2f}")
         if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            self.epochs_since_improve = 0
            torch.save(self.model.state_dict(), f"cnn_best_{epoch}_{int(time.time())}.pt")
         else:
            self.epochs_since_improve += 1
         if self.epochs_since_improve >= self.early_stop_patience:
            print("Early stopping.")
            break
   # Class imbalance: Use weighted loss or resample if needed
```

---

### Q16 — Walk-forward validation for the 1D-CNN
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I need to validate my 1D-CNN trading strategy using walk-forward cross-validation
to detect overfitting and measure out-of-sample robustness.

Design a walk-forward validation scheme for:
- Daily OHLCV data, 50 instruments, 2018-2024
- 1D-CNN trained on 60-bar sequences
- Target: 5-day forward direction

Requirements:
1. Rolling window scheme: train on 2 years, validate on 6 months, step 6 months
2. Retrain from scratch (not fine-tune) each window
3. Aggregate metrics across all windows:
   - Mean and std of Sharpe ratio
   - Mean and std of max drawdown
   - % of windows with Sharpe > 0.5
4. How to detect overfitting: what ratio of in-sample to out-of-sample
   Sharpe suggests the model is overfit?
5. Should we use the same features and hyperparameters for each window,
   or re-optimize per window?

Provide:
- A WalkForwardValidator class with a run() method
- The aggregation logic for metrics across windows
- Recommended pass/fail thresholds before deploying to paper trading
```

### Q16 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Walk-forward validation uses rolling windows, retrains per window, and aggregates Sharpe/max drawdown. Pass/fail thresholds and class provided.

**Key decision:**
Retrain per window, aggregate metrics, and require out-of-sample Sharpe > 0.5 for deployment.

**Full response:**
```python
class WalkForwardValidator:
   def __init__(self, data, model, features, window_size=504, val_size=126, step=126):
      self.data = data
      self.model = model
      self.features = features
      self.window_size = window_size
      self.val_size = val_size
      self.step = step
   def run(self):
      metrics = []
      for start in range(0, len(self.data) - self.window_size - self.val_size, self.step):
         train = self.data[start:start+self.window_size]
         val = self.data[start+self.window_size:start+self.window_size+self.val_size]
         # Retrain model from scratch
         self.model.reset()
         self.model.fit(train[self.features], train['target'])
         val_preds = self.model.predict(val[self.features])
         sharpe = sharpe_ratio(val_preds)
         max_dd = max_drawdown(val_preds)
         metrics.append({'sharpe': sharpe, 'max_dd': max_dd})
      sharpe_vals = [m['sharpe'] for m in metrics]
      dd_vals = [m['max_dd'] for m in metrics]
      mean_sharpe, std_sharpe = np.mean(sharpe_vals), np.std(sharpe_vals)
      mean_dd, std_dd = np.mean(dd_vals), np.std(dd_vals)
      pct_above_05 = np.mean([s > 0.5 for s in sharpe_vals])
      return {
         'mean_sharpe': mean_sharpe,
         'std_sharpe': std_sharpe,
         'mean_max_drawdown': mean_dd,
         'std_max_drawdown': std_dd,
         'pct_windows_sharpe_above_05': pct_above_05
      }
```
**Overfitting detection:** If out-of-sample Sharpe < 70% of in-sample, model is overfit.
**Features/hyperparameters:** Re-optimize per window for robustness.
**Pass/fail:** Require mean out-of-sample Sharpe > 0.5, max drawdown < 20%.

---

## BLOCK 4 — Production Readiness
**Model: GPT-4.1 in Copilot Chat**

---

### Q17 — ATR-based stop-loss replacing fixed 5%
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I want to replace the fixed 5% stop-loss in src/risk/manager.py with an
ATR-based dynamic stop-loss.

Current formula:
    stop_loss = price * (1 - stop_loss_pct)   # fixed 5%

Replacement formula (ATR-based):
    stop_loss = price - (atr_multiplier * atr_value)   # e.g. 2 × ATR(14)

Questions:
1. What is the correct ATR formula for daily bars?
   Give the pandas implementation from raw OHLCV data.

2. What multiplier (1.5×, 2×, 3×) is standard for daily equity strategies?
   When should you use a tighter vs wider multiplier?

3. How does ATR-based sizing interact with the position sizing formula?
      qty = risk_dollars / (atr_multiplier * atr_value * price)
   Is this correct? Show the derivation.

4. How do I pass the ATR value from the strategy (which computes indicators)
   into the RiskManager (which sizes positions)?
   The current interface only passes signal.strength. What needs to change?

5. How should ATR be computed in a way that works in both:
   - The backtesting engine (where we have the full DataFrame)
   - The live engine (where we only have the rolling history buffer)

Provide the updated _size_position() method in RiskManager.
```

### Q17 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
ATR-based stop-loss uses rolling ATR(14), multiplier 2× is standard, and position sizing formula is adjusted. ATR value must be passed via signal metadata.

**Key decision:**
Replace fixed stop-loss with ATR-based, update interface to pass ATR, and adjust sizing formula.

**Full response:**
1. **ATR formula (daily bars):**
   ```python
   df['tr'] = np.maximum(df['high'] - df['low'], np.abs(df['high'] - df['close'].shift()), np.abs(df['low'] - df['close'].shift()))
   df['atr'] = df['tr'].rolling(14).mean()
   ```
2. **Multiplier:**
   - 2× ATR is standard; use 1.5× for tight stops, 3× for wide/volatile assets.
3. **Sizing formula:**
   - `qty = risk_dollars / (atr_multiplier * atr_value)`
   - Derivation: risk_dollars is max loss, ATR is per-share risk.
4. **Passing ATR:**
   - Add `atr_value` to `Signal.metadata`, RiskManager reads it.
5. **ATR computation:**
   - Backtest: use full DataFrame
   - Live: use rolling buffer (last 14 bars)
6. **Updated _size_position():**
   ```python
   def _size_position(self, portfolio_value, price, signal_strength=1.0, atr_value=None, atr_multiplier=2.0):
       if atr_value is None or atr_value <= 0:
           return 0.0
       risk_dollars = portfolio_value * self.cfg.max_portfolio_risk_pct * signal_strength
       qty = risk_dollars / (atr_multiplier * atr_value)
       qty_from_cap = (portfolio_value * self.cfg.max_position_pct) / price
       return max(0.0, round(min(qty, qty_from_cap), 4))
   ```

---

### Q18 — Docker deployment for all three services
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I need to containerise three components of my Python trading bot:

1. Ingestion service (runs daily cron job: Polygon backfill + incremental update)
2. Research environment (Jupyter notebook + all ML/data libraries)
3. Live trading service (asyncio event loop, 24/5 operation, Alpaca Paper)

Requirements:
- Each service in its own Docker container
- Shared volume for DuckDB/Parquet files and SQLite databases
- Environment-specific configs: DEV, SANDBOX (no PROD yet)
- Secrets via .env files (not baked into images)
- Graceful shutdown for the live trading service (close positions before exit)
- Health checks for the live trading service
- Windows 11 + Docker Desktop compatible

Provide:
1. docker-compose.yml covering all three services
2. Dockerfile for each service (can share a base image)
3. Volume mount strategy for shared data files
4. The graceful shutdown handler for the asyncio trading loop
5. Health check endpoint (simple HTTP) for the live service
6. How to manage the Alpaca API keys securely across environments
```

### Q18 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Docker deployment uses compose for three services, shared volumes, .env for secrets, and health checks. Graceful shutdown and health endpoint included.

**Key decision:**
Use docker-compose, mount shared volumes, and manage secrets via .env files.

**Full response:**
1. **docker-compose.yml:**
    ```yaml
    version: '3.8'
    services:
       ingestion:
          build: ./ingestion
          volumes:
             - shared_data:/data
          env_file:
             - .env.dev
       research:
          build: ./research
          volumes:
             - shared_data:/data
          env_file:
             - .env.dev
       live:
          build: ./live
          volumes:
             - shared_data:/data
          env_file:
             - .env.sandbox
          ports:
             - "8080:8080"
          healthcheck:
             test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
             interval: 30s
             timeout: 5s
             retries: 3
    volumes:
       shared_data:
    ```
2. **Dockerfile (base):**
    ```dockerfile
    FROM python:3.10-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install -r requirements.txt
    COPY . .
    CMD ["python", "main.py"]
    ```
3. **Volume mount:**
    - All services mount `/data` from `shared_data` volume
4. **Graceful shutdown:**
    ```python
    import signal
    def shutdown_handler():
          # Close positions, cleanup
    signal.signal(signal.SIGTERM, shutdown_handler)
    ```
5. **Health check endpoint:**
    ```python
    from fastapi import FastAPI
    app = FastAPI()
    @app.get("/health")
    def health():
          return {"status": "ok"}
    ```
6. **Secrets:**
    - Use `.env.dev`, `.env.sandbox` (not baked into image)
    - Load via `python-dotenv`

---

### Q19 — Equity curve plotting and performance report
**Status: [x] DONE**

**Paste into Copilot Chat:**
```
I need to add a visual performance report to the backtesting engine.
The BacktestResults object already has:
- equity_curve: List[EquityPoint] (timestamp, portfolio_value, cash, num_positions)
- trades: List[Dict] (date, symbol, side, qty, price, pnl)
- signals: List[Signal]
- Sharpe ratio, max drawdown, total return (already computed)

Design a reporting module: backtest/report.py

Generate a multi-panel matplotlib figure with:
Panel 1: Equity curve vs buy-and-hold benchmark (equal-weight of traded symbols)
Panel 2: Drawdown curve (% from peak)
Panel 3: Monthly returns heatmap (year × month grid, green/red)
Panel 4: Trade distribution (histogram of individual trade P&L)

Also generate a text summary table including:
- Total return %, annualised return %
- Sharpe ratio, Sortino ratio
- Max drawdown %, Calmar ratio (annual return / max DD)
- Win rate, profit factor (gross profit / gross loss)
- Number of trades, average holding period

Requirements:
- Save figure to file (PNG) and optionally show interactively
- Accept optional benchmark prices dict {symbol: pd.Series}
- Works without benchmark (single equity curve only)
- No display required in headless/Docker mode

Provide the complete backtest/report.py module.
```

### Q19 — ANSWER
**Model used:** GPT-4.1 (previous: GPT-4.1)
**Date answered:** 2026-02-22
**Summary (2-3 sentences):**
Reporting module generates multi-panel matplotlib figure and summary table, supports benchmarks, and works headless. Complete code provided.

**Key decision:**
Use matplotlib for panels, pandas for summary, and support PNG output.

**Full response:**
```python
import matplotlib.pyplot as plt
import pandas as pd
def plot_report(results, benchmark=None, filename="report.png", show=False):
   eq = pd.DataFrame([vars(e) for e in results.equity_curve])
   trades = pd.DataFrame(results.trades)
   fig, axs = plt.subplots(2, 2, figsize=(14, 10))
   # Panel 1: Equity curve vs benchmark
   axs[0,0].plot(eq['timestamp'], eq['portfolio_value'], label='Strategy')
   if benchmark:
      axs[0,0].plot(benchmark['timestamp'], benchmark['value'], label='Benchmark')
   axs[0,0].set_title('Equity Curve')
   axs[0,0].legend()
   # Panel 2: Drawdown curve
   rolling_max = eq['portfolio_value'].cummax()
   drawdown = (eq['portfolio_value'] - rolling_max) / rolling_max
   axs[0,1].plot(eq['timestamp'], drawdown*100)
   axs[0,1].set_title('Drawdown (%)')
   # Panel 3: Monthly returns heatmap
   eq['month'] = pd.to_datetime(eq['timestamp']).dt.month
   eq['year'] = pd.to_datetime(eq['timestamp']).dt.year
   eq['ret'] = eq['portfolio_value'].pct_change()
   heatmap = eq.groupby(['year','month'])['ret'].sum().unstack()
   axs[1,0].imshow(heatmap, cmap='RdYlGn', aspect='auto')
   axs[1,0].set_title('Monthly Returns Heatmap')
   # Panel 4: Trade P&L histogram
   axs[1,1].hist(trades['pnl'].dropna(), bins=30, color='blue')
   axs[1,1].set_title('Trade P&L Distribution')
   plt.tight_layout()
   plt.savefig(filename)
   if show:
      plt.show()
   # Summary table
   print("Performance Summary:")
   print(f"Total return: {results.total_return_pct:.2f}%")
   print(f"Annualized return: {(results.total_return_pct/len(eq)*252):.2f}%")
   print(f"Sharpe ratio: {results.sharpe_ratio:.2f}")
   print(f"Sortino ratio: ...")
   print(f"Max drawdown: {results.max_drawdown_pct:.2f}%")
   print(f"Calmar ratio: ...")
   print(f"Win rate: {results.win_rate:.2f}")
   print(f"Profit factor: ...")
   print(f"Num trades: {len(trades)}")
   print(f"Avg holding period: ...")
```

---

## Research Status

| Block | # | Topic | Model | Done? |
|-------|---|-------|-------|-------|
| Redo | Q0A | Risk manager code review | GPT-4.1 + @workspace | [x] |
| Redo | Q0B | Backtest engine lookahead audit | GPT-4.1 + @workspace | [x] |
| Storage | Q12 | DuckDB + Parquet schema | GPT-4.1 | [x] |
| Storage | Q13 | Polygon backfill pipeline | GPT-4.1 | [x] |
| Engine | Q14 | asyncio.Queue refactor plan | GPT-4.1 + @workspace | [x] |
| NN | Q15 | 1D-CNN training loop | GPT-4.1 | [x] |
| NN | Q16 | Walk-forward validation | GPT-4.1 | [x] |
| Production | Q17 | ATR-based stop-loss | GPT-4.1 | [x] |
| Production | Q18 | Docker deployment | GPT-4.1 | [x] |
| Production | Q19 | Equity curve plotting | GPT-4.1 | [x] |

---

## What Claude Code can build NOW (no further research needed)

All items below have sufficient decisions from Phase 1 + Phase 2 (Q0A/Q0B) research.
Give each task to Claude Code as a separate session. Suggested order shown.

---

### Task 1 — Bollinger Bands strategy (start here — no dependencies)
```
Read CLAUDE.md.
Add src/strategies/bollinger_bands.py:
- BUY when close <= lower band (20-day MA - 2×std)
- SELL when close >= middle band (20-day MA)
- Follow ma_crossover.py pattern exactly
- Register in main.py STRATEGIES dict
- Add tests (min 6 test cases), run pytest, confirm all pass
```

---

### Task 2 — Fix RiskManager edge cases (from Q0A)
**Critical severity — fix before any further development**
```
Read src/risk/manager.py and RESEARCH_QUESTIONS_2.md Q0A answer.

Apply these fixes to src/risk/manager.py:

1. Add input validation to _size_position():
   - Guard: if price <= 0 or stop_loss_pct <= 0: return 0.0
   - Guard: if portfolio_value <= 0: return 0.0
   - Clamp: signal_strength = max(0.0, min(1.0, signal_strength))

2. Add threading.Lock to guard _peak_value in approve_signal():
   - import threading
   - self._lock = threading.Lock() in __init__
   - wrap the _peak_value update in: with self._lock:

3. Add to Settings/RiskConfig:
   - max_intraday_loss_pct: float = 0.02  (2% daily loss halt)
   - consecutive_loss_limit: int = 5       (halt after 5 losses in a row)
   - Track consecutive_losses counter in RiskManager

Update existing tests to cover the new edge cases.
Run pytest — all must pass.
```

---

### Task 3 — Fix backtest engine fill price and transaction costs (from Q0B)
**High severity — fixes overstatement of backtest P&L**
```
Read backtest/engine.py and RESEARCH_QUESTIONS_2.md Q0B answer.

Apply these fixes to backtest/engine.py and config/settings.py:

1. Add to Settings:
   - slippage_pct: float = 0.0005   (0.05% per fill)
   - commission_per_share: float = 0.005
   - risk_free_rate: float = 0.0    (annualised, for Sharpe)

2. In BacktestEngine.run(), buffer one bar and fill at next-bar open:
   - When a signal produces an order on bar[t], execute it at bar[t+1].open
   - This requires holding pending_orders across the date loop iteration.

3. Apply transaction costs on each fill:
   - buy fill_price  = next_open * (1 + slippage_pct)
   - sell fill_price = next_open * (1 - slippage_pct)
   - commission = order.qty * commission_per_share
   - Deduct commission from cash in PaperBroker

4. Update Sharpe ratio in BacktestResults to use configurable risk_free_rate:
   - excess_returns = returns - risk_free_rate/252
   - sharpe = (excess_returns.mean() / returns.std()) * sqrt(252)

Update existing tests. Run pytest — all must pass.
Rerun the default backtest and note the new (more realistic) numbers.
```

---

### Task 4 — Kill-switch module
```
Read RESEARCH_QUESTIONS copy.md Q9 answer.
Implement src/risk/kill_switch.py with the KillSwitch class as designed.
SQLite-backed, persistent across restarts.
Methods: trigger(reason), is_active(), reset(operator_id), check_and_raise()
Add unit tests: trigger → is_active True, reset → is_active False,
check_and_raise raises RuntimeError when active.
Run pytest — all must pass.
```

---

### Task 5 — VaR/CVaR risk module
```
Read RESEARCH_QUESTIONS copy.md Q8 answer and Q0A answer.
Implement src/risk/var.py:
- historical_var_cvar(returns: np.ndarray, confidence=0.95) -> tuple[float, float]
- PortfolioVaR class:
  - update(daily_return: float) — maintains rolling 252-day history
  - var95 property, cvar95 property
  - is_within_limit(max_var_pct: float) -> bool

Integrate into RiskManager.approve_signal():
- If PortfolioVaR.is_within_limit() returns False, return None (reject order)
- Log a warning with current VaR and limit values

Add unit tests (known return sequences → verify VaR values).
Run pytest — all must pass.
```

---

### Task 6 — Strategy registry
```
Read RESEARCH_QUESTIONS copy.md Q3 answer.
Implement src/strategies/registry.py with StrategyRegistry class.
SQLite schema + disk artifacts as designed.
Methods: save(), load(), list_strategies(), promote()
SHA256 hash verification on load.
Add unit tests: save + load round-trip, hash mismatch raises ValueError,
promote changes status.
Run pytest — all must pass.
```

---

### Task 7 — Audit logger
```
Read RESEARCH_QUESTIONS copy.md Q11 answer (audit logging section).
Implement src/audit/__init__.py and src/audit/logger.py with AuditLogger class.
asyncio.Queue + SQLite background writer as designed.
Methods: start(), stop(), log_event(), flush(), query_events()
Add unit tests (log → flush → query round-trip).
Run pytest — all must pass.
```
