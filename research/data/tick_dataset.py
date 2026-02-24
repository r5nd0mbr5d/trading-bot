"""Manifest-driven tick dataset loading and splitting utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import json
import pandas as pd


@dataclass
class TickDatasetSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def load_tick_manifest(manifest_path: str | Path) -> Dict[str, object]:
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Tick manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_ticks_from_manifest(
    *,
    manifest_path: str | Path,
    symbol: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    manifest = load_tick_manifest(manifest_path)
    data_dir = Path(str(manifest.get("data_dir", "")))
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Tick manifest entries must be a list")

    selected_files: List[Path] = []
    start_ts = pd.Timestamp(start_date).date() if start_date else None
    end_ts = pd.Timestamp(end_date).date() if end_date else None

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_symbol = entry.get("symbol")
        entry_date = entry.get("trade_date")
        entry_file = entry.get("file")
        if not entry_file:
            continue

        if symbol and entry_symbol and str(entry_symbol) != symbol:
            continue

        if entry_date:
            d = pd.Timestamp(str(entry_date)).date()
            if start_ts and d < start_ts:
                continue
            if end_ts and d > end_ts:
                continue

        selected_files.append(data_dir / str(entry_file))

    if not selected_files:
        return pd.DataFrame(columns=["symbol", "timestamp", "price", "size", "bid", "ask"])

    frames: List[pd.DataFrame] = []
    for path in selected_files:
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["symbol", "timestamp", "price", "size", "bid", "ask"])

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    if symbol:
        merged = merged[merged["symbol"] == symbol]

    return merged


def split_ticks_by_date(
    ticks: pd.DataFrame,
    *,
    train_end: str,
    val_end: str,
) -> TickDatasetSplit:
    if ticks.empty:
        empty = pd.DataFrame(columns=["symbol", "timestamp", "price", "size", "bid", "ask"])
        return TickDatasetSplit(train=empty, val=empty, test=empty)

    df = ticks.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    train_cutoff = pd.Timestamp(train_end).tz_localize("UTC") if pd.Timestamp(train_end).tzinfo is None else pd.Timestamp(train_end).tz_convert("UTC")
    val_cutoff = pd.Timestamp(val_end).tz_localize("UTC") if pd.Timestamp(val_end).tzinfo is None else pd.Timestamp(val_end).tz_convert("UTC")

    train = df[df["timestamp"] <= train_cutoff].copy()
    val = df[(df["timestamp"] > train_cutoff) & (df["timestamp"] <= val_cutoff)].copy()
    test = df[df["timestamp"] > val_cutoff].copy()

    return TickDatasetSplit(train=train, val=val, test=test)
