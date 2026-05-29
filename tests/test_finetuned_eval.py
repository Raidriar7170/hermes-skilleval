import json
from pathlib import Path

import pytest

from hermes_skilleval.finetuned_eval import write_finetuned_eval_summary


def test_write_finetuned_eval_summary_flags_negative_hit_regression(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(_record(selected=["bad"], recall=0.0, negative_hit=1.0))
        + "\n",
        encoding="utf-8",
    )

    summary = write_finetuned_eval_summary(
        baseline_results_path=baseline,
        candidate_results_path=candidate,
        output_dir=tmp_path / "phase14",
        baseline_router="embedding-minilm",
        candidate_router="finetuned-embedding",
        model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
    )

    assert summary["guard_status"] == "REVIEW_REQUIRED"
    assert summary["regression_count"] == 1
    assert summary["model_checkpoint_committed"] is False
    assert (tmp_path / "phase14" / "regression-summary.json").exists()
    assert (tmp_path / "phase14" / "comparison.md").exists()


def test_write_finetuned_eval_summary_records_source_counts_by_router(
    tmp_path: Path,
):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n"
        + json.dumps(
            {
                **_record(selected=["gold"], recall=1.0, negative_hit=0.0),
                "task_id": "dev-baseline-only",
                "split": "dev",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )

    summary = write_finetuned_eval_summary(
        baseline_results_path=baseline,
        candidate_results_path=candidate,
        output_dir=tmp_path / "phase15",
        baseline_router="embedding-minilm",
        candidate_router="finetuned-embedding",
        model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        apply_split="test",
    )

    assert summary["source_task_count"] == 1
    assert summary["baseline_source_task_count"] == 2
    assert summary["candidate_source_task_count"] == 1
    assert summary["task_count"] == 1


def test_write_finetuned_eval_summary_rejects_model_dir_inside_repo(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        write_finetuned_eval_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "phase14",
            baseline_router="embedding-minilm",
            candidate_router="finetuned-embedding",
            model_dir="docs/demo/phase14-finetuned-embedding-router/checkpoint",
        )


def test_write_finetuned_eval_summary_rejects_model_dir_traversal(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0))
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        write_finetuned_eval_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "phase14",
            baseline_router="embedding-minilm",
            candidate_router="finetuned-embedding",
            model_dir="/mnt/data/minghongsun/../leak/model",
        )


def _record(*, selected, recall, negative_hit):
    return {
        "task_id": "task-001",
        "category": "browser-gui",
        "difficulty": "medium",
        "split": "test",
        "robustness_tags": ["phase14"],
        "selected_skill_ids": selected,
        "gold_skills": ["gold"],
        "negative_skills": ["bad"],
        "recall_at_5": recall,
        "mrr": recall,
        "ndcg_at_5": recall,
        "negative_hit_rate": negative_hit,
        "negative_accepted_rate": negative_hit,
        "selection_rate_at_5": 0.2,
    }
