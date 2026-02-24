"""Tests for research snapshot reproducibility pipeline (R1)."""

import pandas as pd
import pytest

from research.data.snapshots import load_snapshot, save_snapshot


def _sample_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], tz="UTC")
    return pd.DataFrame(
        {
            "symbol": ["VOD.L", "VOD.L"],
            "close": [100.0, 101.0],
            "volume": [1000, 1200],
        },
        index=idx,
    )


def test_same_input_produces_same_hash(tmp_path):
    df = _sample_frame()
    config = {"symbols": ["VOD.L"], "timeframe": "1d"}

    a = save_snapshot(df, str(tmp_path), config, snapshot_id="snap_a")
    b = save_snapshot(df, str(tmp_path), config, snapshot_id="snap_b")

    assert a.metadata["hash"] == b.metadata["hash"]


def test_tampered_snapshot_fails_validation(tmp_path):
    df = _sample_frame()
    config = {"symbols": ["VOD.L"], "timeframe": "1d"}
    artifact = save_snapshot(df, str(tmp_path), config, snapshot_id="snap_1")

    tampered = artifact.data_path.read_text(encoding="utf-8").replace("101.0", "999.0")
    artifact.data_path.write_text(tampered, encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        load_snapshot(str(artifact.snapshot_dir))


def test_snapshot_accepts_extra_metadata(tmp_path):
    df = _sample_frame()
    config = {"symbols": ["VOD.L"], "timeframe": "1d"}

    artifact = save_snapshot(
        df,
        str(tmp_path),
        config,
        snapshot_id="snap_meta",
        extra_metadata={"nan_dropped_rows": 2},
    )

    assert artifact.metadata["nan_dropped_rows"] == 2
