from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.remote_paths import (
    A100_USER_ROOT,
    resolve_path_root,
    validate_path_within_root,
)
from hermes_skilleval.router_query import router_query_text


def export_embedding_diagnostics(
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
                    candidate_type="positive_candidate",
                    source_annotation="gold_skill",
                )
            )
        for skill_id in task.negative_skills:
            pairs.append(
                _pair(
                    task,
                    skill_by_id,
                    skill_id,
                    candidate_type="negative_candidate",
                    source_annotation="negative_skill",
                )
            )

    return pairs, _summary(tasks, skills, pairs, input_paths)


def write_embedding_diagnostics(
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
        "".join(
            json.dumps(pair, ensure_ascii=False, sort_keys=True) + "\n"
            for pair in pairs
        ),
        encoding="utf-8",
    )
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_train_config(
    *,
    training_input_manifest: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    output_root: str | Path = A100_USER_ROOT,
) -> dict[str, Any]:
    validated_output_root = resolve_path_root(output_root, field="output_root")
    validated_output_dir = validate_path_within_root(
        output_dir,
        root=validated_output_root,
        field="output_dir",
    )
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")
    return {
        "schema_version": "router-training-data-v2-train-config-v3",
        "artifact_version": 3,
        "policy_id": "router-training-data-v2-training-admission-v3",
        "artifact_type": "router-training-data-v2-train-config",
        "base_model": base_model,
        "training_input_manifest": training_input_manifest,
        "output_root": validated_output_root,
        "output_dir": validated_output_dir,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
        "hard_negative_margin": 1.5,
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
    output_root = config.get("output_root", str(A100_USER_ROOT))
    return "\n".join(
        [
            "# Router Training Data V2 V3 Embedding Router Model Card",
            "",
            "## Scope",
            "",
            "This artifact describes the Router Training Data V2 v3 "
            "SentenceTransformer training contract for skill routing. A model "
            "checkpoint is not committed to this repo.",
            "",
            "## Training Data",
            "",
            f"- V3 training-input manifest: `{config['training_input_manifest']}`",
            f"- Pair count: {summary['pair_count']}",
            f"- Positive pairs: {summary['positive_count']}",
            f"- Hard-negative pairs: {summary['hard_negative_count']}",
            "- Admission: exact reviewed v3 accepted-pair package only",
            "- Diagnostic candidates and raw labels are not training authorization",
            "",
            "The training script consumes train-like positive pairs with "
            "`MultipleNegativesRankingLoss` and train-like hard negatives "
            "with `ContrastiveLoss` at margin 1.5.",
            "",
            "## Output Root",
            "",
            f"- Configured output root: `{output_root}`",
            "- Configs without `output_root` default to `/mnt/data/minghongsun`.",
            "- CLI `--output-root` overrides the config; relative roots resolve "
            "from the trainer process working directory.",
            "- Relative `output_dir` values resolve beneath the selected root; "
            "absolute values must already be contained by it.",
            "",
            "## Training Command",
            "",
            "```bash",
            "python scripts/train_embedding_router.py \\",
            "  --config /path/to/router-training-data-v2-train-config-v3.json",
            "```",
            "",
            "For a local config with a relative `output_dir`, override the root:",
            "",
            "```bash",
            "python scripts/train_embedding_router.py \\",
            "  --config /path/to/router-training-data-v2-train-config-v3.json \\",
            '  --output-root "$PWD/.hermes-training"',
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
    candidate_type: str,
    source_annotation: str,
) -> dict[str, Any]:
    if skill_id not in skill_by_id:
        raise ValueError(f"task {task.id} references missing skill: {skill_id}")
    skill = skill_by_id[skill_id]
    query_text = router_query_text(task.prompt)
    return {
        "schema_version": "router-training-data-v2-embedding-diagnostic-pair-v3",
        "artifact_version": 3,
        "pair_id": f"{task.id}/{candidate_type}/{skill_id}",
        "task_id": task.id,
        "source_split": task.split,
        "query_text": query_text,
        "query_text_policy": "prompt_only",
        "prompt_text_sha256": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
        "skill_id": skill.id,
        "skill_text": _skill_text(skill),
        "candidate_type": candidate_type,
        "source_annotation": source_annotation,
        "accepted_for_training": False,
    }


def _summary(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    pairs: list[dict[str, Any]],
    input_paths: dict[str, str],
) -> dict[str, Any]:
    pairs_by_split = Counter(str(pair["source_split"]) for pair in pairs)
    pairs_by_type = Counter(str(pair["candidate_type"]) for pair in pairs)
    positive_count = sum(
        1 for pair in pairs if pair["candidate_type"] == "positive_candidate"
    )
    negative_count = sum(
        1 for pair in pairs if pair["candidate_type"] == "negative_candidate"
    )
    return {
        "schema_version": "router-training-data-v2-embedding-diagnostic-summary-v3",
        "artifact_version": 3,
        "artifact_type": "embedding-diagnostic-only",
        "can_start_training": False,
        "query_text_policy": "prompt_only",
        "pair_count": len(pairs),
        "task_count": len(tasks),
        "skill_count": len(skills),
        "pairs_by_source_split": dict(sorted(pairs_by_split.items())),
        "candidates_by_type": dict(sorted(pairs_by_type.items())),
        "positive_candidate_count": positive_count,
        "negative_candidate_count": negative_count,
        "leakage_guard": _leakage_guard(tasks),
        "input_paths": dict(sorted(input_paths.items())),
    }


def _leakage_guard(tasks: list[BenchmarkTask]) -> str:
    task_ids_by_split: dict[str, set[str]] = {}
    for task in tasks:
        task_ids_by_split.setdefault(task.split, set()).add(task.id)
    train_like_ids = task_ids_by_split.get("train", set()) | task_ids_by_split.get(
        "dev", set()
    )
    test_ids = task_ids_by_split.get("test", set())
    return "PASS" if not (train_like_ids & test_ids) else "FAIL"


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
