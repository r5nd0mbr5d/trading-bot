import json

from research.data.tick_backlog import build_tick_backlog_manifest


def test_build_tick_backlog_manifest(tmp_path):
    data_dir = tmp_path / "ticks"
    data_dir.mkdir(parents=True, exist_ok=True)

    sample = data_dir / "polygon_AAPL_2026-02-20.csv"
    sample.write_text(
        "symbol,timestamp,price,size,bid,ask\n"
        "AAPL,2026-02-20T10:00:00Z,100.0,10,100.0,100.0\n"
        "AAPL,2026-02-20T10:00:01Z,100.1,20,100.1,100.1\n",
        encoding="utf-8",
    )

    out = tmp_path / "manifest.json"
    result = build_tick_backlog_manifest(data_dir=data_dir, output_path=out)

    assert result.exists()
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["file_count"] == 1
    entry = payload["entries"][0]
    assert entry["file"] == "polygon_AAPL_2026-02-20.csv"
    assert entry["symbol"] == "AAPL"
    assert entry["trade_date"] == "2026-02-20"
    assert entry["rows"] == 2
    assert entry["sha256"]
    assert entry["timestamp_min"] is not None
    assert entry["timestamp_max"] is not None
