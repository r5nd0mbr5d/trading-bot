"""Historical tick download utilities (Polygon-first)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import json
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


def build_polygon_trades_url(
    *,
    symbol: str,
    trade_date: str,
    limit: int = 50000,
    api_key: Optional[str] = None,
) -> str:
    """Build Polygon v3 trades endpoint URL for a single UTC date."""
    date_start = datetime.fromisoformat(trade_date).replace(tzinfo=timezone.utc)
    date_end = date_start + timedelta(days=1)

    params = {
        "timestamp.gte": date_start.isoformat().replace("+00:00", "Z"),
        "timestamp.lt": date_end.isoformat().replace("+00:00", "Z"),
        "limit": int(limit),
        "sort": "timestamp",
        "order": "asc",
    }
    if api_key:
        params["apiKey"] = api_key

    query = urlencode(params)
    return f"https://api.polygon.io/v3/trades/{symbol}?{query}"


def download_url(url: str, output_path: str | Path) -> Path:
    """Download raw URL payload to a local file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with urlopen(url) as response:  # nosec - URL provided by controlled helper/CLI
        payload = response.read()

    out.write_bytes(payload)
    return out


def _fetch_json(url: str) -> Dict[str, Any]:
    with urlopen(url) as response:  # nosec - URL provided by controlled helper/CLI
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def fetch_polygon_trades_payload(
    *,
    symbol: str,
    trade_date: str,
    api_key: Optional[str] = None,
    limit: int = 50000,
    max_pages: int = 20,
) -> Dict[str, Any]:
    """Fetch Polygon trades payload with pagination merged into one result set."""
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    url = build_polygon_trades_url(
        symbol=symbol,
        trade_date=trade_date,
        limit=limit,
        api_key=api_key,
    )

    merged_results: List[Dict[str, Any]] = []
    page_count = 0
    next_url: Optional[str] = url

    while next_url and page_count < max_pages:
        payload = _fetch_json(next_url)
        page_count += 1
        results = payload.get("results", [])
        if isinstance(results, list):
            merged_results.extend(results)

        next_url = payload.get("next_url")
        if next_url and api_key and "apiKey=" not in next_url:
            separator = "&" if "?" in next_url else "?"
            next_url = f"{next_url}{separator}apiKey={api_key}"

    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "page_count": page_count,
        "results_count": len(merged_results),
        "results": merged_results,
    }


def polygon_response_to_ticks(payload: Dict[str, Any], *, symbol: Optional[str] = None) -> pd.DataFrame:
    """Convert Polygon v3 trades JSON payload into canonical tick frame."""
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Polygon payload 'results' must be a list")

    rows = []
    for row in results:
        price = row.get("price")
        size = row.get("size")
        sip_ts = row.get("sip_timestamp")
        ticker = row.get("ticker") or symbol

        if price is None or size is None or sip_ts is None or ticker is None:
            continue

        ts = pd.to_datetime(int(sip_ts), unit="ns", utc=True)
        bid = float(price)
        ask = float(price)
        rows.append(
            {
                "symbol": str(ticker),
                "timestamp": ts,
                "price": float(price),
                "size": float(size),
                "bid": bid,
                "ask": ask,
            }
        )

    return pd.DataFrame.from_records(rows)


def download_polygon_trades_json(
    *,
    symbol: str,
    trade_date: str,
    output_dir: str | Path,
    api_key: Optional[str] = None,
    limit: int = 50000,
    max_pages: int = 20,
) -> Path:
    """Download Polygon trades JSON for a symbol/date to disk."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    payload = fetch_polygon_trades_payload(
        symbol=symbol,
        trade_date=trade_date,
        api_key=api_key,
        limit=limit,
        max_pages=max_pages,
    )
    out_path = root / f"polygon_{symbol}_{trade_date}.json"
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path


def download_polygon_trades_range(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    output_dir: str | Path,
    api_key: Optional[str] = None,
    limit: int = 50000,
    max_pages: int = 20,
) -> List[Path]:
    """Download Polygon trades JSON files for each day in [start_date, end_date]."""
    start_ts = datetime.fromisoformat(start_date).date()
    end_ts = datetime.fromisoformat(end_date).date()
    if end_ts < start_ts:
        raise ValueError("end_date must be >= start_date")

    outputs: List[Path] = []
    current = start_ts
    while current <= end_ts:
        day = current.isoformat()
        outputs.append(
            download_polygon_trades_json(
                symbol=symbol,
                trade_date=day,
                output_dir=output_dir,
                api_key=api_key,
                limit=limit,
                max_pages=max_pages,
            )
        )
        current = current + timedelta(days=1)

    return outputs


def convert_polygon_json_to_tick_csv(
    json_path: str | Path,
    *,
    output_csv: str | Path,
    symbol_override: Optional[str] = None,
) -> Path:
    """Convert downloaded Polygon JSON payload to canonical tick CSV."""
    source = Path(json_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    ticks = polygon_response_to_ticks(payload, symbol=symbol_override)

    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    ticks.to_csv(out, index=False)
    return out
