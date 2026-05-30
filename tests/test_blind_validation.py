from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_skilleval.blind_validation import write_blind_validation_summary


def _record(
    task_id: str,
    *,
    selected: list[str],
    split: str = "test",
    negative_hit_rate: float = 0.0,
) -> dict:
    return {
        "task_id": task_id,
        "category": "codex",
        "difficulty": "medium",
        "split": split,
        "robustness_tags": [
            "blind-validation",
            "phase16",
            "real-skill-library-migration",
        ],
        "router": "embedding",
        "prompt": "Need a safe edit workflow.",
        "selected_skill_ids": selected,
        "scores": {
            skill_id: 1.0 / (index + 1)
            for index, skill_id in enumerate(selected)
        },
        "gold_skills": ["apply-patch-discipline"],
        "negative_skills": ["workspace-git-hygiene"],
        "latency_ms": 1.0,
        "recall_at_1": 1.0 if selected[0] == "apply-patch-discipline" else 0.0,
        "recall_at_3": 1.0,
        "recall_at_5": 1.0,
        "precision_at_5": 0.2,
        "mrr": 1.0 if selected[0] == "apply-patch-discipline" else 0.5,
        "ndcg_at_5": 1.0,
        "negative_hit_rate": negative_hit_rate,
        "accepted_count": len(selected),
        "coverage": 1.0,
        "selection_rate_at_5": len(selected) / 5,
        "abstention_rate": 0.0,
        "accepted_recall_at_5": 1.0,
        "negative_accepted_rate": negative_hit_rate,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_write_blind_validation_summary_detects_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(baseline, [_record("blind-task", selected=["apply-patch-discipline"])])
    _write_jsonl(
        candidate,
        [
            _record(
                "blind-task",
                selected=["apply-patch-discipline", "workspace-git-hygiene"],
                negative_hit_rate=1.0,
            )
        ],
    )

    summary = write_blind_validation_summary(
        baseline_results_path=baseline,
        candidate_results_path=candidate,
        output_dir=tmp_path / "out",
        baseline_router="baseline-minilm",
        candidate_router="finetuned-embedding",
        model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        task_root="benchmarks/blind-migration-tasks",
    )

    assert summary["phase"] == "Phase 16"
    assert summary["artifact_type"] == "phase16-blind-validation"
    assert summary["task_count"] == 1
    assert summary["guard_status"] == "REVIEW_REQUIRED"
    assert summary["regression_count"] == 1
    assert (tmp_path / "out" / "route-diffs.jsonl").is_file()
    assert (tmp_path / "out" / "comparison.md").is_file()


def test_write_blind_validation_summary_rejects_mismatched_task_ids(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(baseline, [_record("baseline-only", selected=["apply-patch-discipline"])])
    _write_jsonl(candidate, [_record("candidate-only", selected=["apply-patch-discipline"])])

    with pytest.raises(ValueError, match="task ids differ"):
        write_blind_validation_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "out",
            baseline_router="baseline-minilm",
            candidate_router="finetuned-embedding",
            model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            task_root="benchmarks/blind-migration-tasks",
        )


def test_write_blind_validation_summary_rejects_non_test_split(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(
        baseline,
        [_record("blind-task", selected=["apply-patch-discipline"], split="dev")],
    )
    _write_jsonl(candidate, [_record("blind-task", selected=["apply-patch-discipline"])])

    with pytest.raises(ValueError, match="split == 'test'"):
        write_blind_validation_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "out",
            baseline_router="baseline-minilm",
            candidate_router="finetuned-embedding",
            model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            task_root="benchmarks/blind-migration-tasks",
        )
