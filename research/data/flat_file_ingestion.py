"""Massive (Polygon) flat file ingestion into per-symbol Parquet snapshots."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


@dataclass
class FlatFileIngestResult:
    manifest_path: Path
    file_count: int
    total_rows: int
    files: list[dict]


def _date_range(start: str, end: str) -> list[str]:
    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    if end_date < start_date:
        raise ValueError("end must be >= start")
    days = []
    current = start_date
    while current <= end_date:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _resolve_credentials() -> tuple[str, str]:
    access_key = os.getenv("MASSIVE_AWS_ACCESS_KEY", "").strip()
    secret_key = os.getenv("MASSIVE_AWS_SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("MASSIVE_AWS_ACCESS_KEY and MASSIVE_AWS_SECRET_KEY are required")
    return access_key, secret_key


def _read_day_csv(body: bytes) -> pd.DataFrame:
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as handle:
        frame = pd.read_csv(handle)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "ticker" in frame.columns and "symbol" not in frame.columns:
        frame = frame.rename(columns={"ticker": "symbol"})
    return frame


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "symbol" not in out.columns:
        raise ValueError("Flat file data missing symbol/ticker column")
    out["symbol"] = out["symbol"].astype(str).str.upper()

    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], unit="ms", utc=True)
    elif "t" in out.columns:
        out = out.rename(columns={"t": "timestamp"})
        out["timestamp"] = pd.to_datetime(out["timestamp"], unit="ms", utc=True)

    return out


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def ingest_flat_files(
    *,
    symbols: Iterable[str],
    start: str,
    end: str,
    output_dir: str = "research/data/snapshots",
    manifest_path: Optional[str] = None,
    skip_existing: bool = True,
    bucket: str = "flatfiles.polygon.io",
    prefix: str = "us_stocks_sip/day_aggs_v1",
    s3_client=None,
) -> FlatFileIngestResult:
    symbol_list = [s.strip().upper() for s in symbols if s and s.strip()]
    if not symbol_list:
        raise ValueError("At least one symbol is required")

    if s3_client is None:
        access_key, secret_key = _resolve_credentials()
        import boto3

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    total_rows = 0

    for day in _date_range(start, end):
        key = f"{prefix}/{day}.csv.gz"
        response = s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        frame = _read_day_csv(body)
        frame = _normalize_frame(frame)

        for symbol in symbol_list:
            symbol_frame = frame[frame["symbol"] == symbol]
            if symbol_frame.empty:
                continue

            symbol_dir = output_root / symbol
            symbol_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = symbol_dir / f"{day}.parquet"
            if skip_existing and parquet_path.exists():
                continue

            symbol_frame.to_parquet(parquet_path, index=False)
            row_count = int(symbol_frame.shape[0])
            total_rows += row_count

            files.append(
                {
                    "symbol": symbol,
                    "date": day,
                    "path": str(parquet_path),
                    "rows": row_count,
                    "sha256": _hash_file(parquet_path),
                }
            )

    manifest_payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "start": start,
        "end": end,
        "symbols": symbol_list,
        "file_count": len(files),
        "total_rows": total_rows,
        "bucket": bucket,
        "prefix": prefix,
        "files": files,
    }

    manifest_out = Path(manifest_path) if manifest_path else output_root / "flat_file_manifest.json"
    manifest_out.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    return FlatFileIngestResult(
        manifest_path=manifest_out,
        file_count=len(files),
        total_rows=total_rows,
        files=files,
    )
