import gzip
import io
import json

import pandas as pd
import pytest

from research.data.flat_file_ingestion import ingest_flat_files


def _sample_csv_bytes():
    data = (
        "ticker,volume,open,close,high,low,vwap,transactions,timestamp\n"
        "AAPL,100,10,11,12,9,10.5,5,1704067200000\n"
        "MSFT,200,20,21,22,19,20.5,6,1704067200000\n"
    )
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as handle:
        handle.write(data.encode("utf-8"))
    return buf.getvalue()


class _FakeBody:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload


class _FakeS3:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.requests = []

    def get_object(self, Bucket, Key):
        self.requests.append({"Bucket": Bucket, "Key": Key})
        return {"Body": _FakeBody(self._payload)}


def test_ingest_flat_files_writes_parquet_and_manifest(tmp_path):
    pytest.importorskip("pyarrow")
    payload = _sample_csv_bytes()
    s3_client = _FakeS3(payload)

    result = ingest_flat_files(
        symbols=["AAPL"],
        start="2024-01-01",
        end="2024-01-01",
        output_dir=str(tmp_path),
        s3_client=s3_client,
        skip_existing=False,
    )

    parquet_path = tmp_path / "AAPL" / "2024-01-01.parquet"
    assert parquet_path.exists()

    frame = pd.read_parquet(parquet_path)
    assert len(frame) == 1
    assert frame["symbol"].iloc[0] == "AAPL"

    manifest_path = result.manifest_path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["file_count"] == 1
    assert payload["total_rows"] == 1
    assert payload["files"][0]["symbol"] == "AAPL"
