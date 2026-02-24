"""Tick data ingestion utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import zipfile

import pandas as pd

from research.data.ticks import validate_ticks


def _normalize_tick_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]

    timestamp_col = None
    for candidate in ["timestamp", "sip_timestamp", "participant_timestamp", "time"]:
        if candidate in out.columns:
            timestamp_col = candidate
            break
    if timestamp_col is None:
        raise ValueError("Missing timestamp column in tick data")
    if timestamp_col != "timestamp":
        out = out.rename(columns={timestamp_col: "timestamp"})

    if "price" not in out.columns:
        raise ValueError("Missing price column in tick data")
    if "size" not in out.columns:
        for candidate in ["quantity", "qty"]:
            if candidate in out.columns:
                out = out.rename(columns={candidate: "size"})
                break
    if "size" not in out.columns:
        raise ValueError("Missing size column in tick data")

    if "bid" not in out.columns:
        out["bid"] = out["price"]
    if "ask" not in out.columns:
        out["ask"] = out["price"]

    if "symbol" not in out.columns:
        for candidate in ["ticker", "sym"]:
            if candidate in out.columns:
                out = out.rename(columns={candidate: "symbol"})
                break

    return out


def load_tick_csv(
    path: str | Path,
    *,
    symbol: Optional[str] = None,
) -> pd.DataFrame:
    """Load ticks from a CSV file and validate schema.

    Expected columns: timestamp, price, size, bid, ask, symbol (optional override).
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Tick CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df = _normalize_tick_columns(df)

    if "symbol" not in df.columns:
        if not symbol:
            raise ValueError("symbol must be provided when CSV lacks a symbol column")
        df["symbol"] = symbol
    elif symbol:
        df["symbol"] = symbol

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    validate_ticks(df)
    return df


def load_tick_zip(
    path: str | Path,
    *,
    symbol: Optional[str] = None,
) -> pd.DataFrame:
    zip_path = Path(path)
    if not zip_path.exists():
        raise FileNotFoundError(f"Tick ZIP not found: {zip_path}")

    csv_names: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("No CSV files found in tick ZIP")

        frames = []
        for name in csv_names:
            with archive.open(name) as handle:
                frame = pd.read_csv(handle)
                frame = _normalize_tick_columns(frame)
                frames.append(frame)

    merged = pd.concat(frames, ignore_index=True)

    if "symbol" not in merged.columns:
        if not symbol:
            raise ValueError("symbol must be provided when ZIP data lacks a symbol column")
        merged["symbol"] = symbol
    elif symbol:
        merged["symbol"] = symbol

    merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
    validate_ticks(merged)
    return merged
