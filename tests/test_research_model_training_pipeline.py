from research.experiments.harness import train_and_save_model


def test_train_and_save_model(tmp_path):
    def trainer(**kwargs):
        _ = kwargs
        return {"weights": [1, 2, 3]}, {"val_accuracy": 0.51}

    report = train_and_save_model(
        model_id="xgb_stub",
        trainer=trainer,
        trainer_kwargs={"X_train": [1], "y_train": [0], "X_val": [2], "y_val": [1]},
        metadata={
            "model_type": "pickle",
            "snapshot_id": "snap_42",
            "feature_version": "v1",
            "label_version": "l1",
            "train_window": "2020-01-01:2020-06-01",
            "val_window": "2020-06-02:2020-12-31",
        },
        artifacts_root=tmp_path,
    )

    assert report.model_dir.exists()
    assert report.metadata.model_id == "xgb_stub"
    assert "val_accuracy" in report.metadata.metrics
