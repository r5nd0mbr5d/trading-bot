"""Model artifact persistence with hash verification."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import hashlib
import json
import pickle


@dataclass
class ModelArtifactMetadata:
    model_id: str
    model_type: str
    snapshot_id: str
    feature_version: str
    label_version: str
    train_window: str
    val_window: str
    metrics: Dict[str, float]
    artifact_hash: str
    created_at_utc: str
    model_file: str = "model.bin"
    extra_metadata: Optional[Dict[str, Any]] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_metadata(metadata: ModelArtifactMetadata, path: Path) -> None:
    payload = asdict(metadata)
    payload = {k: v for k, v in payload.items() if v is not None}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _save_model(model: Any, path: Path) -> None:
    if hasattr(model, "save_model"):
        model.save_model(str(path))
        return
    with path.open("wb") as handle:
        pickle.dump(model, handle)


def _load_model(path: Path, model_type: str) -> Any:
    if model_type == "xgboost" and path.suffix in {".json", ".txt", ".bin"}:
        try:
            import xgboost as xgb
        except ImportError as exc:
            raise RuntimeError("xgboost is required to load this model artifact") from exc

        model = xgb.XGBClassifier()
        model.load_model(str(path))
        return model

    with path.open("rb") as handle:
        return pickle.load(handle)


def save_model_artifact(
    model: Any,
    metadata: ModelArtifactMetadata,
    *,
    artifacts_root: str | Path = "research/models/artifacts",
) -> Tuple[Path, ModelArtifactMetadata]:
    root = Path(artifacts_root)
    model_dir = root / metadata.model_id
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / metadata.model_file
    _save_model(model, model_path)

    computed_hash = compute_sha256(model_path)
    if metadata.artifact_hash and metadata.artifact_hash != computed_hash:
        raise ValueError("Provided artifact_hash does not match saved artifact")

    updated = ModelArtifactMetadata(
        model_id=metadata.model_id,
        model_type=metadata.model_type,
        snapshot_id=metadata.snapshot_id,
        feature_version=metadata.feature_version,
        label_version=metadata.label_version,
        train_window=metadata.train_window,
        val_window=metadata.val_window,
        metrics=metadata.metrics,
        artifact_hash=computed_hash,
        created_at_utc=metadata.created_at_utc or _utc_now_iso(),
        model_file=metadata.model_file,
        extra_metadata=metadata.extra_metadata,
    )

    _write_metadata(updated, model_dir / "metadata.json")
    return model_dir, updated


def load_model_artifact(
    model_id: str,
    *,
    artifacts_root: str | Path = "research/models/artifacts",
    expected_feature_version: Optional[str] = None,
    expected_label_version: Optional[str] = None,
    expected_hash: Optional[str] = None,
) -> Tuple[Any, ModelArtifactMetadata]:
    root = Path(artifacts_root)
    model_dir = root / model_id
    metadata_path = model_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata.json for model_id={model_id}")

    payload = json.loads(metadata_path.read_text())
    metadata = ModelArtifactMetadata(**payload)

    if expected_feature_version and metadata.feature_version != expected_feature_version:
        raise ValueError("feature_version mismatch for model artifact")
    if expected_label_version and metadata.label_version != expected_label_version:
        raise ValueError("label_version mismatch for model artifact")

    model_path = model_dir / metadata.model_file
    if not model_path.exists():
        raise FileNotFoundError(f"Missing model file: {metadata.model_file}")

    computed_hash = compute_sha256(model_path)
    if metadata.artifact_hash != computed_hash:
        raise ValueError("artifact hash mismatch")
    if expected_hash and expected_hash != computed_hash:
        raise ValueError("artifact hash mismatch against expected_hash")

    model = _load_model(model_path, metadata.model_type)
    return model, metadata
