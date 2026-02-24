#!/usr/bin/env python
"""Test strategy signal generation with UK symbols."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings
from main import apply_runtime_profile
from src.data.feeds import MarketDataFeed
from src.strategies.ma_crossover import MACrossoverStrategy

settings = Settings()
apply_runtime_profile(settings, "uk_paper")

feed = MarketDataFeed(settings)
strategy = MACrossoverStrategy(settings)

print(f"Strategy config: fast={settings.strategy.fast_period}, slow={settings.strategy.slow_period}")
print(f"Min bars required: {strategy.min_bars_required()}")
print(f"\nFetching 5d/1m bars for HSBA.L...")
df = feed.fetch_historical("HSBA.L", period="5d", interval="1m")
print(f"  Loaded {len(df)} bars")

bars = feed.to_bars("HSBA.L", df)
print(f"  Converted to {len(bars)} Bar objects")

signal_count = 0
for i, bar in enumerate(bars[-20:]):  # Show last 20 bars
    print(f"  Bar {i}: {bar.timestamp} O={bar.open:.2f} C={bar.close:.2f}")
    sig = strategy.on_bar(bar)
    if sig:
        signal_count += 1
        print(f"    >>> SIGNAL: {sig.signal_type.value} strength={sig.strength:.2f}")

print(f"\nTotal signals generated: {signal_count}")
