import json

import pytest

from hermes_skilleval.provenance import write_finetuned_provenance_pack


def test_write_finetuned_provenance_pack_summarizes_sources_without_checkpoints(
    tmp_path,
):
    training_summary = tmp_path / "training-summary.json"
    train_config = tmp_path / "train-config.json"
    train_run_summary = tmp_path / "train-run-summary.json"
    model_manifest = tmp_path / "model-manifest.json"
    regression_summary = tmp_path / "regression-summary.json"
    output_dir = tmp_path / "phase15"
    training_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "pair_count": 28,
                "positive_count": 16,
                "hard_negative_count": 12,
                "leakage_guard": "PASS",
            }
        ),
        encoding="utf-8",
    )
    train_config.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "base_model": "/mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2",
                "output_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
                "hard_negative_margin": 1.5,
                "model_checkpoint_committed": False,
            }
        ),
        encoding="utf-8",
    )
    train_run_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "device": "cuda:0",
                "epoch_count": 3,
                "trained_pair_count": 11,
                "trained_hard_negative_pair_count": 8,
                "optimizer_step_count": 6,
                "hard_negative_optimizer_step_count": 3,
                "final_loss": 0.2228596806526184,
            }
        ),
        encoding="utf-8",
    )
    model_manifest.write_text(
        json.dumps(
            {
                "phase": "Phase 15",
                "artifact_type": "phase15-model-file-manifest",
                "model_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "model_checkpoint_committed": False,
                "file_count": 2,
                "total_size_bytes": 42,
                "files": [
                    {"path": "config.json", "size_bytes": 3, "sha256": "0" * 64},
                    {"path": "modules.json", "size_bytes": 3, "sha256": "1" * 64},
                ],
            }
        ),
        encoding="utf-8",
    )
    regression_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 15",
                "artifact_type": "phase15-heldout-finetuned-embedding-eval",
                "evaluated_split": "test",
                "source_task_count": 12,
                "baseline_source_task_count": 12,
                "candidate_source_task_count": 12,
                "task_count": 4,
                "guard_status": "PASS",
                "regression_count": 0,
                "model_checkpoint_committed": False,
                "metric_deltas": {
                    "recall_at_5": 0.0,
                    "mrr": 0.0,
                    "ndcg_at_5": 0.0,
                    "negative_hit_rate": 0.0,
                    "negative_accepted_rate": 0.0,
                    "selection_rate_at_5": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )

    pack = write_finetuned_provenance_pack(
        training_summary_path=training_summary,
        train_config_path=train_config,
        train_run_summary_path=train_run_summary,
        model_manifest_path=model_manifest,
        regression_summary_path=regression_summary,
        output_dir=output_dir,
    )

    assert pack["phase"] == "Phase 15"
    assert pack["artifact_type"] == "phase15-heldout-provenance-pack"
    assert pack["model_checkpoint_committed"] is False
    assert pack["heldout_eval"]["evaluated_split"] == "test"
    assert pack["heldout_eval"]["baseline_source_task_count"] == 12
    assert pack["heldout_eval"]["candidate_source_task_count"] == 12
    assert pack["training"]["pair_count"] == 28
    assert pack["remote_run"]["epoch_count"] == 3
    assert (output_dir / "provenance.json").exists()
    markdown = (output_dir / "provenance.md").read_text(encoding="utf-8")
    assert "checkpoint is not committed" in markdown
    assert "Baseline source task count: 12" in markdown
    assert "Candidate source task count: 12" in markdown
    assert "standard external benchmark" in markdown


def test_write_finetuned_provenance_pack_allows_tokenizer_model_file(tmp_path):
    paths = _write_minimal_provenance_inputs(tmp_path)
    model_manifest = paths["model_manifest"]
    manifest = json.loads(model_manifest.read_text(encoding="utf-8"))
    manifest["files"] = [
        {"path": "tokenizer.json", "size_bytes": 2, "sha256": "0" * 64}
    ]
    model_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    pack = write_finetuned_provenance_pack(
        training_summary_path=paths["training_summary"],
        train_config_path=paths["train_config"],
        train_run_summary_path=paths["train_run_summary"],
        model_manifest_path=model_manifest,
        regression_summary_path=paths["regression_summary"],
        output_dir=tmp_path / "phase15",
    )

    assert pack["model_manifest"]["files"][0]["path"] == "tokenizer.json"


@pytest.mark.parametrize(
    "sensitive_value",
    [
        "AKIA1234567890",
        "PRIVATE KEY",
        "BEGIN OPENSSH",
        "ssh-rsa AAAA",
        "ssh-ed25519 AAAA",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "/root",
        "//root",
        "192.168.1.10",
        "sk-1234567890abcdef",
        "api_key=abc12345",
        "Bearer abc12345",
    ],
)
def test_write_finetuned_provenance_pack_rejects_sensitive_values(
    tmp_path,
    sensitive_value,
):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"value": sensitive_value}), encoding="utf-8")

    with pytest.raises(ValueError, match="sensitive value"):
        write_finetuned_provenance_pack(
            training_summary_path=path,
            train_config_path=path,
            train_run_summary_path=path,
            model_manifest_path=path,
            regression_summary_path=path,
            output_dir=tmp_path / "out",
        )


def _write_minimal_provenance_inputs(tmp_path):
    training_summary = tmp_path / "training-summary.json"
    train_config = tmp_path / "train-config.json"
    train_run_summary = tmp_path / "train-run-summary.json"
    model_manifest = tmp_path / "model-manifest.json"
    regression_summary = tmp_path / "regression-summary.json"
    training_summary.write_text(
        json.dumps(
            {
                "pair_count": 28,
                "positive_count": 16,
                "hard_negative_count": 12,
                "leakage_guard": "PASS",
            }
        ),
        encoding="utf-8",
    )
    train_config.write_text(
        json.dumps(
            {
                "base_model": "/mnt/data/minghongsun/models/all-MiniLM-L6-v2",
                "output_dir": "/mnt/data/minghongsun/phase14/models/minilm",
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
            }
        ),
        encoding="utf-8",
    )
    train_run_summary.write_text(
        json.dumps(
            {
                "device": "cuda:0",
                "epoch_count": 3,
                "trained_pair_count": 11,
                "trained_hard_negative_pair_count": 8,
                "optimizer_step_count": 6,
                "hard_negative_optimizer_step_count": 3,
                "final_loss": 0.2228596806526184,
            }
        ),
        encoding="utf-8",
    )
    model_manifest.write_text(
        json.dumps(
            {
                "model_dir": "/mnt/data/minghongsun/phase14/models/minilm",
                "file_count": 1,
                "total_size_bytes": 2,
                "files": [{"path": "config.json", "size_bytes": 2, "sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )
    regression_summary.write_text(
        json.dumps(
            {
                "evaluated_split": "test",
                "source_task_count": 12,
                "task_count": 4,
                "guard_status": "PASS",
                "regression_count": 0,
                "metric_deltas": {"recall_at_5": 0.0},
            }
        ),
        encoding="utf-8",
    )
    return {
        "training_summary": training_summary,
        "train_config": train_config,
        "train_run_summary": train_run_summary,
        "model_manifest": model_manifest,
        "regression_summary": regression_summary,
    }
