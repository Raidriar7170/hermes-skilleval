from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from hermes_skilleval.models import BenchmarkTask, Skill


def export_embedding_training_pairs(
    *,
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    input_paths: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skill_by_id = {skill.id: skill for skill in skills}
    pairs: list[dict[str, Any]] = []

    for task in sorted(tasks, key=lambda item: item.id):
        for skill_id in task.gold_skills:
            pairs.append(
                _pair(
                    task,
                    skill_by_id,
                    skill_id,
                    label=1,
                    pair_type="positive",
                    source="gold_skill",
                )
            )
        for skill_id in task.negative_skills:
            pairs.append(
                _pair(
                    task,
                    skill_by_id,
                    skill_id,
                    label=0,
                    pair_type="hard_negative",
                    source="negative_skill",
                )
            )

    return pairs, _summary(tasks, skills, pairs, input_paths)


def write_training_pairs(
    pairs: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    pairs_path: Path | str,
    summary_path: Path | str,
) -> None:
    pairs_output = Path(pairs_path)
    summary_output = Path(summary_path)
    pairs_output.parent.mkdir(parents=True, exist_ok=True)
    pairs_output.write_text(
        "".join(json.dumps(pair, sort_keys=True) + "\n" for pair in pairs),
        encoding="utf-8",
    )
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_train_config(
    *,
    training_pairs: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    if not output_dir.startswith("/mnt/data/minghongsun/"):
        raise ValueError("A100 training output_dir must be under /mnt/data/minghongsun/")
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")
    return {
        "phase": "Phase 14",
        "base_model": base_model,
        "training_pairs": training_pairs,
        "output_dir": output_dir,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "loss": "MultipleNegativesRankingLoss",
        "seed": seed,
        "model_checkpoint_committed": False,
    }


def write_train_config(config: dict[str, Any], output_path: Path | str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_model_card(config: dict[str, Any], summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 14 Fine-Tuned Embedding Router Model Card",
            "",
            "## Scope",
            "",
            "This artifact records a domain-specific SentenceTransformer "
            "fine-tuning path for Hermes-style skill routing. The model "
            "checkpoint is not committed to this repo.",
            "",
            "## Training Data",
            "",
            f"- Source: `{config['training_pairs']}`",
            f"- Pair count: {summary['pair_count']}",
            f"- Positive pairs: {summary['positive_count']}",
            f"- Hard-negative pairs: {summary['hard_negative_count']}",
            "- Labels: gold skill positives and task negative hard negatives",
            "- Split policy: dev pairs for training, test pairs held out for reporting",
            "",
            "## Training Command",
            "",
            "```bash",
            "python scripts/train_embedding_router.py \\",
            "  --config docs/demo/phase14-finetuned-embedding-router/train-config.json",
            "```",
            "",
            "## Evaluation",
            "",
            "`baseline-results.jsonl`, `finetuned-results.jsonl`, "
            "`regression-summary.json`, and `comparison.md` are committed only "
            "after a real fine-tuned model path is evaluated.",
            "",
            "## Limitations",
            "",
            "This is a self-built Hermes-style skill-routing benchmark. It is "
            "not a standard external benchmark and does not establish SOTA.",
            "",
        ]
    )


def write_model_card(
    config: dict[str, Any],
    summary: dict[str, Any],
    output_path: Path | str,
) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_model_card(config, summary), encoding="utf-8")


def _pair(
    task: BenchmarkTask,
    skill_by_id: dict[str, Skill],
    skill_id: str,
    *,
    label: int,
    pair_type: str,
    source: str,
) -> dict[str, Any]:
    if skill_id not in skill_by_id:
        raise ValueError(f"task {task.id} references missing skill: {skill_id}")
    skill = skill_by_id[skill_id]
    return {
        "pair_id": f"{task.id}/{pair_type}/{skill_id}",
        "task_id": task.id,
        "split": task.split,
        "query_text": _task_text(task),
        "skill_id": skill.id,
        "skill_text": _skill_text(skill),
        "label": label,
        "pair_type": pair_type,
        "source": source,
    }


def _summary(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    pairs: list[dict[str, Any]],
    input_paths: dict[str, str],
) -> dict[str, Any]:
    pairs_by_split = Counter(str(pair["split"]) for pair in pairs)
    pairs_by_type = Counter(str(pair["pair_type"]) for pair in pairs)
    positive_count = sum(1 for pair in pairs if int(pair["label"]) == 1)
    hard_negative_count = sum(1 for pair in pairs if int(pair["label"]) == 0)
    return {
        "phase": "Phase 14",
        "artifact_type": "phase14-embedding-training-data",
        "pair_count": len(pairs),
        "task_count": len(tasks),
        "skill_count": len(skills),
        "pairs_by_split": dict(sorted(pairs_by_split.items())),
        "pairs_by_type": dict(sorted(pairs_by_type.items())),
        "positive_count": positive_count,
        "hard_negative_count": hard_negative_count,
        "leakage_guard": _leakage_guard(tasks),
        "input_paths": dict(sorted(input_paths.items())),
    }


def _leakage_guard(tasks: list[BenchmarkTask]) -> str:
    task_ids_by_split: dict[str, set[str]] = {}
    for task in tasks:
        task_ids_by_split.setdefault(task.split, set()).add(task.id)
    train_like_ids = (
        task_ids_by_split.get("train", set()) | task_ids_by_split.get("dev", set())
    )
    test_ids = task_ids_by_split.get("test", set())
    return "PASS" if not (train_like_ids & test_ids) else "FAIL"


def _task_text(task: BenchmarkTask) -> str:
    return " ".join(
        [
            task.id.replace("-", " "),
            task.category,
            task.difficulty,
            task.prompt,
            " ".join(task.robustness_tags),
        ]
    )


def _skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )
