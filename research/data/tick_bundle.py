"""Build train/val/test tick CSV bundles from backlog manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from research.data.tick_dataset import load_ticks_from_manifest, split_ticks_by_date


def build_tick_split_bundles(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    symbol: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    train_end: str,
    val_end: str,
) -> dict[str, Path]:
    ticks = load_ticks_from_manifest(
        manifest_path=manifest_path,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )

    split = split_ticks_by_date(
        ticks,
        train_end=train_end,
        val_end=val_end,
    )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    train_path = root / "ticks_train.csv"
    val_path = root / "ticks_val.csv"
    test_path = root / "ticks_test.csv"

    split.train.to_csv(train_path, index=False)
    split.val.to_csv(val_path, index=False)
    split.test.to_csv(test_path, index=False)

    meta_path = root / "tick_split_summary.json"
    summary = {
        "rows_train": int(len(split.train)),
        "rows_val": int(len(split.val)),
        "rows_test": int(len(split.test)),
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "train_end": train_end,
        "val_end": val_end,
    }
    pd.Series(summary).to_json(meta_path)

    return {
        "train": train_path,
        "val": val_path,
        "test": test_path,
        "summary": meta_path,
    }
