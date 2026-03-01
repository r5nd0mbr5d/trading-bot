# configs/

This directory contains **trial run configuration JSON files** used by the paper-trial
and trial-batch CLI modes.

| File | Purpose |
|------|---------|
| `trial_aggressive.json` | High-risk trial profile (wider stops, larger position sizes). |
| `trial_conservative.json` | Low-risk trial profile (tight stops, small positions). |
| `trial_standard.json` | Baseline trial profile — default starting point. |

## Usage

Pass a file from this directory as a trial manifest:

```bash
python main.py paper_trial --manifest configs/trial_standard.json --confirm-paper-trial
```

Or run a batch of trials:

```bash
python main.py trial_batch --manifests configs/trial_*.json --confirm-paper-trial
```

> **Note:** These files are trial *run* manifests (duration, symbols, capital, expected metrics).
> They are distinct from the Python configuration module in `config/`, which defines runtime
> parameters loaded at startup via `from config.settings import Settings`.
