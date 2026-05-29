import hashlib

import pytest

from hermes_skilleval.model_manifest import build_model_manifest, write_model_manifest


MODEL_LABEL = "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router"


def test_build_model_manifest_records_relative_paths_and_sha256(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model": "demo"}\n', encoding="utf-8")
    (model_dir / "modules.json").write_text("[]\n", encoding="utf-8")
    (model_dir / "model-manifest.json").write_text("{}\n", encoding="utf-8")
    (model_dir / "train-run-summary.json").write_text("{}\n", encoding="utf-8")

    manifest = build_model_manifest(
        model_dir=model_dir,
        model_dir_label=MODEL_LABEL,
    )

    assert manifest["phase"] == "Phase 15"
    assert manifest["artifact_type"] == "phase15-model-file-manifest"
    assert manifest["model_dir"] == MODEL_LABEL
    assert manifest["model_checkpoint_committed"] is False
    assert manifest["file_count"] == 2
    assert [item["path"] for item in manifest["files"]] == [
        "config.json",
        "modules.json",
    ]
    expected = hashlib.sha256(b'{"model": "demo"}\n').hexdigest()
    assert manifest["files"][0]["sha256"] == expected


def test_write_model_manifest_rejects_empty_model_dir(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    with pytest.raises(ValueError, match="no model files found"):
        write_model_manifest(
            model_dir=model_dir,
            model_dir_label=MODEL_LABEL,
            output_path=tmp_path / "model-manifest.json",
        )


def test_build_model_manifest_rejects_label_outside_a100_user_root(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="model_dir must be under"):
        build_model_manifest(
            model_dir=model_dir,
            model_dir_label="/root/hermes-skilleval/model",
        )
