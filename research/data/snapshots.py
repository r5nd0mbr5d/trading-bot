"""Deterministic research dataset snapshot pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def _canonicalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    canonical = df.copy()
    canonical = canonical.sort_index()
    canonical = canonical.reindex(sorted(canonical.columns), axis=1)
    return canonical


def _stable_frame_bytes(df: pd.DataFrame) -> bytes:
    canonical = _canonicalize_frame(df)
    csv_payload = canonical.to_csv(index=True, lineterminator="\n")
    return csv_payload.encode("utf-8")


def snapshot_hash(df: pd.DataFrame, config: Dict[str, Any]) -> str:
    payload = {
        "config": config,
        "data_csv": _stable_frame_bytes(df).decode("utf-8"),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class SnapshotArtifact:
    snapshot_id: str
    snapshot_dir: Path
    data_path: Path
    metadata_path: Path
    metadata: Dict[str, Any]


def save_snapshot(
    df: pd.DataFrame,
    output_dir: str,
    config: Dict[str, Any],
    snapshot_id: str,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> SnapshotArtifact:
    root = Path(output_dir)
    snapshot_dir = root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    canonical = _canonicalize_frame(df)
    data_path = snapshot_dir / "dataset.csv"
    canonical.to_csv(data_path, index=True)

    digest = snapshot_hash(canonical, config)
    metadata = {
        "snapshot_id": snapshot_id,
        "hash": digest,
        "rows": int(canonical.shape[0]),
        "columns": list(canonical.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    metadata_path = snapshot_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return SnapshotArtifact(
        snapshot_id=snapshot_id,
        snapshot_dir=snapshot_dir,
        data_path=data_path,
        metadata_path=metadata_path,
        metadata=metadata,
    )


def load_snapshot(snapshot_dir: str) -> tuple[pd.DataFrame, Dict[str, Any]]:
    root = Path(snapshot_dir)
    data_path = root / "dataset.csv"
    metadata_path = root / "metadata.json"

    if not data_path.exists() or not metadata_path.exists():
        raise ValueError(f"Invalid snapshot directory: {snapshot_dir}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    df = pd.read_csv(data_path, index_col=0)
    if isinstance(df.index, pd.Index):
        try:
            parsed_index = pd.to_datetime(df.index)
            if isinstance(parsed_index, pd.Index):
                df.index = parsed_index
        except Exception:
            pass

    actual_hash = snapshot_hash(df, metadata.get("config", {}))
    expected_hash = str(metadata.get("hash", ""))
    if actual_hash != expected_hash:
        raise ValueError(
            f"Snapshot hash mismatch for {snapshot_dir}: expected={expected_hash} actual={actual_hash}"
        )

    return _canonicalize_frame(df), metadata
