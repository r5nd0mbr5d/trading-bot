#!/usr/bin/env python
"""Diagnose stale-data issue during streaming."""

import yfinance
import pandas as pd
from datetime import datetime, timezone

symbols = ["HSBA.L", "LLOY.L", "BP.L"]

for symbol in symbols:
    try:
        data = yfinance.download(symbol, period="5d", interval="1m", progress=False)
        if not data.empty:
            last_bar_ts = data.index[-1]
            now_utc = pd.Timestamp.now(tz="UTC")
            age_seconds = (now_utc - last_bar_ts).total_seconds()
            print(f"\n{symbol}:")
            print(f"  Last bar: {last_bar_ts}")
            print(f"  Age (seconds): {int(age_seconds)}")
            print(f"  Now (UTC): {now_utc}")
            print(f"  Stale? (>600s): {age_seconds > 600}")
    except Exception as e:
        print(f"{symbol}: ERROR {e}")
