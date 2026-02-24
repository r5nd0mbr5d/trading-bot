import json

from research.data.tick_dataset import load_ticks_from_manifest, split_ticks_by_date


def _write_tick_csv(path, symbol, rows):
    lines = ["symbol,timestamp,price,size,bid,ask"]
    for ts, px, sz in rows:
        lines.append(f"{symbol},{ts},{px},{sz},{px},{px}")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_load_ticks_from_manifest_filters_symbol_and_date(tmp_path):
    data_dir = tmp_path / "ticks"
    data_dir.mkdir(parents=True, exist_ok=True)

    f1 = data_dir / "polygon_AAPL_2026-02-20.csv"
    _write_tick_csv(
        f1,
        "AAPL",
        [
            ("2026-02-20T10:00:00Z", 100.0, 10),
            ("2026-02-20T10:00:01Z", 100.1, 20),
        ],
    )

    f2 = data_dir / "polygon_AAPL_2026-02-21.csv"
    _write_tick_csv(
        f2,
        "AAPL",
        [
            ("2026-02-21T10:00:00Z", 101.0, 10),
        ],
    )

    manifest = {
        "data_dir": str(data_dir),
        "entries": [
            {"file": f1.name, "symbol": "AAPL", "trade_date": "2026-02-20"},
            {"file": f2.name, "symbol": "AAPL", "trade_date": "2026-02-21"},
        ],
    }
    manifest_path = tmp_path / "tick_backlog_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    ticks = load_ticks_from_manifest(
        manifest_path=manifest_path,
        symbol="AAPL",
        start_date="2026-02-21",
        end_date="2026-02-21",
    )

    assert len(ticks) == 1
    assert ticks.iloc[0]["symbol"] == "AAPL"


def test_split_ticks_by_date(tmp_path):
    data_dir = tmp_path / "ticks"
    data_dir.mkdir(parents=True, exist_ok=True)

    f1 = data_dir / "polygon_AAPL_2026-02-20.csv"
    _write_tick_csv(
        f1,
        "AAPL",
        [
            ("2026-02-20T10:00:00Z", 100.0, 10),
            ("2026-02-21T10:00:00Z", 101.0, 10),
            ("2026-02-22T10:00:00Z", 102.0, 10),
        ],
    )

    manifest = {
        "data_dir": str(data_dir),
        "entries": [{"file": f1.name, "symbol": "AAPL", "trade_date": "2026-02-20"}],
    }
    manifest_path = tmp_path / "tick_backlog_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    ticks = load_ticks_from_manifest(manifest_path=manifest_path)
    split = split_ticks_by_date(
        ticks,
        train_end="2026-02-20T23:59:59Z",
        val_end="2026-02-21T23:59:59Z",
    )

    assert len(split.train) == 1
    assert len(split.val) == 1
    assert len(split.test) == 1
