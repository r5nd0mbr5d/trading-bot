import json

from research.data.tick_bundle import build_tick_split_bundles


def _write_tick_csv(path, symbol, rows):
    lines = ["symbol,timestamp,price,size,bid,ask"]
    for ts, px, sz in rows:
        lines.append(f"{symbol},{ts},{px},{sz},{px},{px}")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_build_tick_split_bundles(tmp_path):
    data_dir = tmp_path / "ticks"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "polygon_AAPL_2026-02-20.csv"
    _write_tick_csv(
        csv_path,
        "AAPL",
        [
            ("2026-02-20T10:00:00Z", 100.0, 10),
            ("2026-02-21T10:00:00Z", 101.0, 10),
            ("2026-02-22T10:00:00Z", 102.0, 10),
        ],
    )

    manifest = {
        "data_dir": str(data_dir),
        "entries": [{"file": csv_path.name, "symbol": "AAPL", "trade_date": "2026-02-20"}],
    }
    manifest_path = tmp_path / "tick_backlog_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    output_dir = tmp_path / "splits"
    outputs = build_tick_split_bundles(
        manifest_path=manifest_path,
        output_dir=output_dir,
        symbol="AAPL",
        start_date="2026-02-20",
        end_date="2026-02-22",
        train_end="2026-02-20T23:59:59Z",
        val_end="2026-02-21T23:59:59Z",
    )

    assert outputs["train"].exists()
    assert outputs["val"].exists()
    assert outputs["test"].exists()
    assert outputs["summary"].exists()

    train_rows = outputs["train"].read_text(encoding="utf-8").strip().splitlines()
    val_rows = outputs["val"].read_text(encoding="utf-8").strip().splitlines()
    test_rows = outputs["test"].read_text(encoding="utf-8").strip().splitlines()

    assert len(train_rows) == 2  # header + 1 row
    assert len(val_rows) == 2
    assert len(test_rows) == 2

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert summary["rows_train"] == 1
    assert summary["rows_val"] == 1
    assert summary["rows_test"] == 1
