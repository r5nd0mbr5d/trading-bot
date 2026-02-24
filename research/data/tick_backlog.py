"""Tick backlog manifest utilities for reproducible downloaded datasets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import hashlib
import json
import pandas as pd


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_symbol_date_from_name(path: Path) -> tuple[Optional[str], Optional[str]]:
    # Expected pattern: polygon_<SYMBOL>_<YYYY-MM-DD>.csv
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 3 and parts[0] == "polygon":
        symbol = parts[1]
        trade_date = parts[-1]
        return symbol, trade_date
    return None, None


def build_tick_backlog_manifest(
    *,
    data_dir: str | Path,
    output_path: str | Path,
) -> Path:
    root = Path(data_dir)
    if not root.exists():
        raise FileNotFoundError(f"Tick data directory not found: {root}")

    csv_files = sorted(root.glob("*.csv"))
    entries: List[Dict[str, object]] = []

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        rows = int(len(df))

        timestamp_min = None
        timestamp_max = None
        if "timestamp" in df.columns and rows > 0:
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            valid = ts.dropna()
            if not valid.empty:
                timestamp_min = valid.min().isoformat()
                timestamp_max = valid.max().isoformat()

        symbol, trade_date = _parse_symbol_date_from_name(csv_path)
        if symbol is None and "symbol" in df.columns and rows > 0:
            symbol = str(df["symbol"].iloc[0])

        entries.append(
            {
                "file": csv_path.name,
                "symbol": symbol,
                "trade_date": trade_date,
                "rows": rows,
                "sha256": _sha256(csv_path),
                "timestamp_min": timestamp_min,
                "timestamp_max": timestamp_max,
            }
        )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(root),
        "file_count": len(entries),
        "entries": entries,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out
