import json
from pathlib import Path

import pytest

from hermes_skilleval.embedding_training import (
    build_train_config,
    export_embedding_training_pairs,
    render_model_card,
    write_train_config,
    write_training_pairs,
)
from hermes_skilleval.models import BenchmarkTask, Skill


def test_export_embedding_training_pairs_includes_gold_and_hard_negative_pairs():
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

    pairs, summary = export_embedding_training_pairs(
        tasks=[task],
        skills=skills,
        input_paths={"tasks": "fixture/tasks", "skills_index": "fixture/skills.json"},
    )

    assert [pair["pair_type"] for pair in pairs] == ["positive", "hard_negative"]
    assert pairs[0]["label"] == 1
    assert pairs[0]["skill_id"] == "browser-smoke-testing"
    assert "nonblank" in pairs[0]["query_text"]
    assert "Browser Smoke Testing" in pairs[0]["skill_text"]
    assert pairs[1]["label"] == 0
    assert pairs[1]["skill_id"] == "systematic-debugging"
    assert summary["phase"] == "Phase 14"
    assert summary["artifact_type"] == "phase14-embedding-training-data"
    assert summary["positive_count"] == 1
    assert summary["hard_negative_count"] == 1
    assert summary["leakage_guard"] == "PASS"


def test_export_embedding_training_pairs_rejects_missing_gold_skill():
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
        export_embedding_training_pairs(tasks=[task], skills=[], input_paths={})


def test_write_training_pairs_writes_jsonl_and_summary(tmp_path: Path):
    pairs = [
        {
            "pair_id": "task-001/positive/gold",
            "task_id": "task-001",
            "split": "dev",
            "query_text": "query",
            "skill_id": "gold",
            "skill_text": "skill",
            "label": 1,
            "pair_type": "positive",
            "source": "gold_skill",
        }
    ]
    summary = {"phase": "Phase 14", "pair_count": 1}

    write_training_pairs(
        pairs,
        summary,
        pairs_path=tmp_path / "phase14" / "training-pairs.jsonl",
        summary_path=tmp_path / "phase14" / "training-summary.json",
    )

    written_pair = json.loads(
        (tmp_path / "phase14" / "training-pairs.jsonl").read_text(encoding="utf-8")
    )
    written_summary = json.loads(
        (tmp_path / "phase14" / "training-summary.json").read_text(encoding="utf-8")
    )
    assert written_pair["pair_id"] == "task-001/positive/gold"
    assert written_summary["pair_count"] == 1


def test_build_train_config_keeps_outputs_under_minghongsun_path():
    config = build_train_config(
        training_pairs="docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl",
        output_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    assert config["phase"] == "Phase 14"
    assert config["output_root"] == "/mnt/data/minghongsun"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["loss"] == "MultipleNegativesRankingLoss+ContrastiveLoss"
    assert config["hard_negative_margin"] == 1.5
    assert config["model_checkpoint_committed"] is False


def test_build_train_config_records_local_root_and_relative_output_dir(tmp_path):
    root = tmp_path / "portable-output"

    config = build_train_config(
        training_pairs="training-pairs.jsonl",
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
        training_pairs="training-pairs.jsonl",
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


def test_build_train_config_rejects_outputs_outside_minghongsun_path():
    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        build_train_config(
            training_pairs="training-pairs.jsonl",
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
            training_pairs="training-pairs.jsonl",
            output_dir="/mnt/data/minghongsun/../leak/model",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )


def test_write_train_config_writes_json(tmp_path: Path):
    config = build_train_config(
        training_pairs="docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl",
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
        {"training_pairs": "training-pairs.jsonl"},
        {"pair_count": 1, "positive_count": 1, "hard_negative_count": 0},
    )

    assert "Configured output root: `/mnt/data/minghongsun`" in card
    assert "CLI `--output-root` overrides the config" in card
    assert '--output-root "$PWD/.hermes-training"' in card


def test_render_model_card_uses_configured_output_root():
    card = render_model_card(
        {
            "training_pairs": "training-pairs.jsonl",
            "output_root": "/work/hermes",
        },
        {"pair_count": 1, "positive_count": 1, "hard_negative_count": 0},
    )

    assert "Configured output root: `/work/hermes`" in card
