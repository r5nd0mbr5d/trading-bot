import pytest

from research.models.artifacts import (
    ModelArtifactMetadata,
    load_model_artifact,
    save_model_artifact,
)


def _metadata() -> ModelArtifactMetadata:
    return ModelArtifactMetadata(
        model_id="dummy_model",
        model_type="pickle",
        snapshot_id="snap_001",
        feature_version="v1",
        label_version="l1",
        train_window="2020-01-01:2020-06-01",
        val_window="2020-06-02:2020-12-31",
        metrics={"val_accuracy": 0.55},
        artifact_hash="",
        created_at_utc="2026-02-23T00:00:00Z",
    )


def test_save_and_load_artifact_roundtrip(tmp_path):
    model = {"weights": [1, 2, 3]}
    metadata = _metadata()

    model_dir, stored = save_model_artifact(
        model,
        metadata,
        artifacts_root=tmp_path,
    )

    loaded_model, loaded_metadata = load_model_artifact(
        stored.model_id,
        artifacts_root=tmp_path,
    )

    assert model_dir.exists()
    assert loaded_model == model
    assert loaded_metadata.artifact_hash == stored.artifact_hash


def test_load_rejects_hash_mismatch(tmp_path):
    model = {"weights": [4, 5, 6]}
    metadata = _metadata()

    _, stored = save_model_artifact(
        model,
        metadata,
        artifacts_root=tmp_path,
    )

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_model_artifact(
            stored.model_id,
            artifacts_root=tmp_path,
            expected_hash="bad_hash",
        )
