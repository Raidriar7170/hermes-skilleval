import json
from pathlib import Path

import pytest

from hermes_skilleval.embedding_training import (
    build_train_config,
    export_embedding_diagnostics,
    render_model_card,
    write_embedding_diagnostics,
    write_train_config,
)
from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.training_input import TrainingInputError, load_training_input


def test_export_embedding_diagnostics_is_versioned_prompt_only_and_not_accepted():
    task = BenchmarkTask(
        id="browser-local-dashboard",
        category="browser-gui",
        difficulty="medium",
        prompt="Open the static HTML dashboard and verify that it is nonblank.",
        gold_skills=["browser-smoke-testing"],
        negative_skills=["systematic-debugging"],
        verifier="manual",
        split="dev",
        robustness_tags=["migration"],
    )
    skills = [
        Skill(
            id="browser-smoke-testing",
            name="Browser Smoke Testing",
            path="skills/browser-smoke-testing/SKILL.md",
            category="browser-gui",
            description="Open a local web target and verify rendering.",
            body="# Browser Smoke Testing",
            trigger_terms=["browser", "dashboard"],
            token_count_estimate=10,
        ),
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="skills/systematic-debugging/SKILL.md",
            category="superpowers",
            description="Investigate bugs before changing code.",
            body="# Systematic Debugging",
            trigger_terms=["debug", "failure"],
            token_count_estimate=10,
        ),
    ]

    pairs, summary = export_embedding_diagnostics(
        tasks=[task],
        skills=skills,
        input_paths={"tasks": "fixture/tasks", "skills_index": "fixture/skills.json"},
    )

    assert [pair["candidate_type"] for pair in pairs] == [
        "positive_candidate",
        "negative_candidate",
    ]
    assert all(
        pair["schema_version"] == "router-training-data-v2-embedding-diagnostic-pair-v3"
        for pair in pairs
    )
    assert all(pair["artifact_version"] == 3 for pair in pairs)
    assert all(pair["query_text_policy"] == "prompt_only" for pair in pairs)
    assert all(pair["accepted_for_training"] is False for pair in pairs)
    assert pairs[0]["skill_id"] == "browser-smoke-testing"
    assert "nonblank" in pairs[0]["query_text"]
    assert "Browser Smoke Testing" in pairs[0]["skill_text"]
    assert pairs[1]["skill_id"] == "systematic-debugging"
    forbidden = {
        "label",
        "training_split",
        "supervision_label",
        "review_status",
        "reviewer",
        "review_reason",
        "source_hash",
        "acceptance_hash",
    }
    assert all(not (set(pair) & forbidden) for pair in pairs)
    assert summary["schema_version"] == (
        "router-training-data-v2-embedding-diagnostic-summary-v3"
    )
    assert summary["artifact_version"] == 3
    assert summary["positive_candidate_count"] == 1
    assert summary["negative_candidate_count"] == 1
    assert summary["can_start_training"] is False
    assert summary["leakage_guard"] == "PASS"


def test_export_embedding_diagnostics_rejects_missing_gold_skill():
    task = BenchmarkTask(
        id="task-001",
        category="browser-gui",
        difficulty="medium",
        prompt="Open a dashboard.",
        gold_skills=["missing-skill"],
        negative_skills=[],
        verifier="manual",
        split="dev",
    )

    with pytest.raises(ValueError, match="missing skill"):
        export_embedding_diagnostics(tasks=[task], skills=[], input_paths={})


def test_write_embedding_diagnostics_writes_jsonl_and_summary(tmp_path: Path):
    pairs = [
        {
            "pair_id": "task-001/positive/gold",
            "task_id": "task-001",
            "source_split": "dev",
            "query_text": "query",
            "query_text_policy": "prompt_only",
            "skill_id": "gold",
            "skill_text": "skill",
            "accepted_for_training": False,
            "candidate_type": "positive_candidate",
            "source_annotation": "gold_skill",
        }
    ]
    summary = {"phase": "Phase 14", "pair_count": 1}

    write_embedding_diagnostics(
        pairs,
        summary,
        pairs_path=tmp_path / "diagnostic" / "diagnostic-pairs.jsonl",
        summary_path=tmp_path / "diagnostic" / "diagnostic-summary.json",
    )

    written_pair = json.loads(
        (tmp_path / "diagnostic" / "diagnostic-pairs.jsonl").read_text(encoding="utf-8")
    )
    written_summary = json.loads(
        (tmp_path / "diagnostic" / "diagnostic-summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert written_pair["pair_id"] == "task-001/positive/gold"
    assert written_summary["pair_count"] == 1


def test_diagnostic_export_is_categorically_rejected_as_training_input(tmp_path):
    task = BenchmarkTask(
        id="synthetic-diagnostic-task",
        category="browser-gui",
        difficulty="medium",
        prompt="Inspect a synthetic dashboard.",
        gold_skills=["synthetic-skill"],
        negative_skills=[],
        verifier="manual",
        split="dev",
    )
    skill = Skill(
        id="synthetic-skill",
        name="Synthetic Skill",
        path="skills/synthetic/SKILL.md",
        category="browser-gui",
        description="Synthetic test skill.",
        body="# Synthetic Skill",
        trigger_terms=["synthetic"],
        token_count_estimate=10,
    )
    rows, summary = export_embedding_diagnostics(
        tasks=[task], skills=[skill], input_paths={}
    )
    pairs_path = tmp_path / "diagnostic-pairs.jsonl"
    write_embedding_diagnostics(
        rows,
        summary,
        pairs_path=pairs_path,
        summary_path=tmp_path / "diagnostic-summary.json",
    )

    with pytest.raises(TrainingInputError, match="manifest.*fields"):
        load_training_input(pairs_path)


def test_build_train_config_keeps_outputs_under_minghongsun_path():
    config = build_train_config(
        training_input_manifest="synthetic/training-input-manifest.json",
        output_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    assert config["schema_version"] == "router-training-data-v2-train-config-v3"
    assert config["artifact_version"] == 3
    assert config["policy_id"] == "router-training-data-v2-training-admission-v3"
    assert config["artifact_type"] == "router-training-data-v2-train-config"
    assert "phase" not in config
    assert config["output_root"] == "/mnt/data/minghongsun"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["loss"] == "MultipleNegativesRankingLoss+ContrastiveLoss"
    assert config["hard_negative_margin"] == 1.5
    assert config["model_checkpoint_committed"] is False


def test_build_train_config_records_local_root_and_relative_output_dir(tmp_path):
    root = tmp_path / "portable-output"

    config = build_train_config(
        training_input_manifest="training-input-manifest.json",
        output_root=root,
        output_dir="models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    assert config["output_root"] == str(root.resolve(strict=False))
    assert config["output_dir"] == str(
        (root / "models/minilm-skill-router").resolve(strict=False)
    )


def test_build_train_config_resolves_relative_root_from_process_cwd(
    monkeypatch,
    tmp_path,
):
    process_cwd = tmp_path / "process-cwd"
    process_cwd.mkdir()
    monkeypatch.chdir(process_cwd)

    config = build_train_config(
        training_input_manifest="training-input-manifest.json",
        output_root="portable-output",
        output_dir="models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    expected_root = (process_cwd / "portable-output").resolve(strict=False)
    assert config["output_root"] == str(expected_root)
    assert config["output_dir"] == str(
        (expected_root / "models/minilm-skill-router").resolve(strict=False)
    )


def test_build_train_config_rejects_existing_file_output_root(tmp_path):
    output_root = tmp_path / "root-file"
    output_root.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(ValueError, match="output_root must be a directory"):
        build_train_config(
            training_input_manifest="training-input-manifest.json",
            output_root=output_root,
            output_dir="models/minilm-skill-router",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )


def test_build_train_config_rejects_non_path_output_root():
    with pytest.raises(ValueError, match="output_root must be a path"):
        build_train_config(
            training_input_manifest="training-input-manifest.json",
            output_root=7170,  # type: ignore[arg-type]
            output_dir="models/minilm-skill-router",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )


def test_build_train_config_rejects_outputs_outside_minghongsun_path():
    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        build_train_config(
            training_input_manifest="training-input-manifest.json",
            output_dir="/tmp/models/minilm-skill-router",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )


def test_build_train_config_rejects_traversal_outside_minghongsun_path():
    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        build_train_config(
            training_input_manifest="training-input-manifest.json",
            output_dir="/mnt/data/minghongsun/../leak/model",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )


def test_write_train_config_writes_json(tmp_path: Path):
    config = build_train_config(
        training_input_manifest="synthetic/training-input-manifest.json",
        output_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    write_train_config(config, tmp_path / "train-config.json")

    written = json.loads((tmp_path / "train-config.json").read_text(encoding="utf-8"))
    assert written["seed"] == 7170


def test_render_model_card_documents_default_and_local_output_roots():
    card = render_model_card(
        {"training_input_manifest": "training-input-manifest.json"},
        {"pair_count": 1, "positive_count": 1, "hard_negative_count": 0},
    )

    assert "Configured output root: `/mnt/data/minghongsun`" in card
    assert "CLI `--output-root` overrides the config" in card
    assert '--output-root "$PWD/.hermes-training"' in card
    assert "# Router Training Data V2 V3 Embedding Router Model Card" in card
    assert "router-training-data-v2-train-config-v3.json" in card
    assert "Phase 14" not in card


def test_render_model_card_uses_configured_output_root():
    card = render_model_card(
        {
            "training_input_manifest": "training-input-manifest.json",
            "output_root": "/work/hermes",
        },
        {"pair_count": 1, "positive_count": 1, "hard_negative_count": 0},
    )

    assert "Configured output root: `/work/hermes`" in card
