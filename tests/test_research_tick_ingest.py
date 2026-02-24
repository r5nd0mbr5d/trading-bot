import zipfile

import pandas as pd
import pytest

from research.data.tick_ingest import load_tick_csv, load_tick_zip


def test_load_tick_csv_with_symbol_override(tmp_path):
    sample = tmp_path / "ticks.csv"
    sample.write_text(
        "timestamp,price,size,bid,ask\n"
        "2026-02-20T10:00:00Z,100.0,50,99.9,100.1\n"
        "2026-02-20T10:00:01Z,100.2,30,100.1,100.3\n"
    )

    df = load_tick_csv(sample, symbol="TEST")
    assert set(["symbol", "timestamp", "price", "size", "bid", "ask"]).issubset(df.columns)
    assert df["symbol"].unique().tolist() == ["TEST"]
    assert df["timestamp"].dt.tz is not None


def test_load_tick_csv_missing_symbol_rejected(tmp_path):
    sample = tmp_path / "ticks.csv"
    sample.write_text("timestamp,price,size,bid,ask\n2026-02-20T10:00:00Z,100.0,50,99.9,100.1\n")

    with pytest.raises(ValueError, match="symbol must be provided"):
        load_tick_csv(sample)


def test_load_tick_csv_respects_symbol_column(tmp_path):
    sample = tmp_path / "ticks.csv"
    sample.write_text(
        "timestamp,price,size,bid,ask,symbol\n"
        "2026-02-20T10:00:00Z,100.0,50,99.9,100.1,AAA\n"
        "2026-02-20T10:00:01Z,100.2,30,100.1,100.3,AAA\n"
    )

    df = load_tick_csv(sample)
    assert df["symbol"].unique().tolist() == ["AAA"]
    assert isinstance(df["timestamp"].iloc[0], pd.Timestamp)


def test_load_tick_zip_with_downloaded_schema(tmp_path):
    csv_name = "polygon_ticks.csv"
    csv_content = (
        "sip_timestamp,price,size,ticker\n"
        "2026-02-20T10:00:00Z,100.0,50,AAA\n"
        "2026-02-20T10:00:01Z,100.2,30,AAA\n"
    )
    zip_path = tmp_path / "ticks.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(csv_name, csv_content)

    df = load_tick_zip(zip_path)
    assert set(["symbol", "timestamp", "price", "size", "bid", "ask"]).issubset(df.columns)
    assert df["symbol"].unique().tolist() == ["AAA"]


def test_load_tick_zip_requires_symbol_when_missing(tmp_path):
    csv_name = "ticks.csv"
    csv_content = "sip_timestamp,price,size\n" "2026-02-20T10:00:00Z,100.0,50\n"
    zip_path = tmp_path / "ticks.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(csv_name, csv_content)

    with pytest.raises(ValueError, match="symbol must be provided"):
        load_tick_zip(zip_path)
