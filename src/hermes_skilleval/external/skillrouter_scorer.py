from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from hermes_skilleval.external.skillrouter import SkillRouterAdapter


METRIC_NAMES = (
    "nDCG@1",
    "nDCG@3",
    "nDCG@10",
    "Hit@1",
    "Precision@3",
    "MRR@10",
    "Recall@10",
    "Recall@20",
    "Recall@50",
    "FullCoverage@3",
    "FullCoverage@5",
    "FullCoverage@10",
)


def score_skillrouter_predictions(
    *,
    data_root: Path | str,
    predictions_path: Path | str,
    mode: str = "core",
    tier: str | None = None,
    tiers: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    if mode not in {"core", "single"}:
        raise ValueError(f"unsupported SkillRouter scoring mode: {mode}")
    if tier and tiers:
        raise ValueError("use either tier or tiers, not both")

    adapter = SkillRouterAdapter(
        data_root=data_root,
        upstream_ref="scorer-only",
        license_note="scorer-only",
    )
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError("external validation failed")

    relevance_entries = adapter._load_relevance_entries()
    predictions = _load_predictions(Path(predictions_path))
    if tier:
        return _score_tier(
            adapter=adapter,
            relevance_entries=relevance_entries,
            predictions=predictions,
            mode=mode,
            tier=tier,
        )
    selected_tiers = tuple(tiers) if tiers else adapter.tiers
    by_tier = {
        selected_tier: _score_tier(
            adapter=adapter,
            relevance_entries=relevance_entries,
            predictions=predictions,
            mode=mode,
            tier=selected_tier,
        )
        for selected_tier in selected_tiers
    }
    return {
        "schema_version": "v0.3.skillrouter-official-scorer.v1",
        "benchmark_id": "skillrouter",
        "mode": mode,
        "metrics": list(METRIC_NAMES),
        "task_count": sum(report["task_count"] for report in by_tier.values()),
        "by_tier": by_tier,
    }


def _score_tier(
    *,
    adapter: SkillRouterAdapter,
    relevance_entries: dict[str, dict[str, Any]],
    predictions: dict[str, list[str]],
    mode: str,
    tier: str,
) -> dict[str, Any]:
    if tier not in adapter.tiers:
        raise ValueError(f"unsupported SkillRouter tier: {tier}")
    tier_pool = {skill.skill_id for skill in adapter.iter_skills(tier)}
    rows = []
    for task in adapter.load_tasks():
        entry = relevance_entries.get(task.task_id, {})
        selected_gt_ids = _selected_gt_ids(entry, mode)
        task_type = task.task_type
        if mode == "core" and task_type == "generic_only":
            continue
        if mode == "single" and len(selected_gt_ids) != 1:
            continue
        if task.task_id not in predictions:
            continue
        tier_relevance = {
            skill_id: grade
            for skill_id, grade in task.graded_relevance.items()
            if skill_id in tier_pool
        }
        gt_ids_in_pool = [
            skill_id for skill_id in selected_gt_ids if skill_id in tier_pool
        ]
        if not gt_ids_in_pool:
            continue
        ranking = predictions.get(task.task_id, [])
        rows.append(
            {
                "task_id": task.task_id,
                "task_type": task_type,
                "task_difficulty": task.tier,
                "evaluation_tier": tier,
                "gt_ids": gt_ids_in_pool,
                "gt_count": len(gt_ids_in_pool),
                "slice_gt_count": len(selected_gt_ids),
                "predictions": ranking,
                "tier_relevance": tier_relevance,
                "metrics": _task_metrics(ranking, gt_ids_in_pool, tier_relevance),
            }
        )

    return {
        "schema_version": "v0.3.skillrouter-official-scorer.v1",
        "benchmark_id": "skillrouter",
        "mode": mode,
        "tier": tier,
        "task_count": len(rows),
        "metrics": list(METRIC_NAMES),
        "aggregates": _aggregates(rows),
        "tasks": rows,
    }


def write_skillrouter_score_report(
    *,
    data_root: Path | str,
    predictions_path: Path | str,
    output_path: Path | str,
    mode: str = "core",
    tier: str | None = None,
    tiers: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    report = score_skillrouter_predictions(
        data_root=data_root,
        predictions_path=predictions_path,
        mode=mode,
        tier=tier,
        tiers=tiers,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _load_predictions(path: Path) -> dict[str, list[str]]:
    if path.suffix == ".jsonl":
        predictions: dict[str, list[str]] = {}
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path.name}:{line_number} prediction must be object")
                task_id = record.get("task_id")
                ranking = record.get("skill_ids") or record.get("predictions")
                predictions[_prediction_task_id(task_id)] = _prediction_list(ranking)
        return predictions
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("predictions JSON must be an object")
    predictions = {}
    for task_id, ranking in payload.items():
        predictions[_prediction_task_id(task_id)] = _prediction_list(ranking)
    return predictions


def _prediction_task_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("prediction task_id must be a non-empty string")
    return value


def _prediction_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("prediction ranking must be a list of skill ids")
    ranking = []
    for skill_id in value:
        ranking.append(skill_id)
    return ranking


def _selected_gt_ids(entry: dict[str, Any], mode: str) -> list[str]:
    if mode == "single":
        return _string_list(entry.get("gt_skill_ids", []))
    if "core_gt_ids" in entry:
        return _string_list(entry.get("core_gt_ids", []))
    return _string_list(entry.get("gt_skill_ids", []))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _task_metrics(
    predictions: list[str],
    gt_ids: list[str],
    relevance: dict[str, int | float],
) -> dict[str, float]:
    return {
        "nDCG@1": _ndcg_at_k(predictions, relevance, 1),
        "nDCG@3": _ndcg_at_k(predictions, relevance, 3),
        "nDCG@10": _ndcg_at_k(predictions, relevance, 10),
        "Hit@1": _hit_at_1(predictions, gt_ids),
        "Precision@3": _precision_at_k(predictions, gt_ids, 3),
        "MRR@10": _mrr_at_k(predictions, gt_ids, 10),
        "Recall@10": _recall_at_k(predictions, gt_ids, 10),
        "Recall@20": _recall_at_k(predictions, gt_ids, 20),
        "Recall@50": _recall_at_k(predictions, gt_ids, 50),
        "FullCoverage@3": _full_coverage_at_k(predictions, gt_ids, 3),
        "FullCoverage@5": _full_coverage_at_k(predictions, gt_ids, 5),
        "FullCoverage@10": _full_coverage_at_k(predictions, gt_ids, 10),
    }


def _ndcg_at_k(
    predictions: list[str],
    relevance: dict[str, int | float],
    k: int,
) -> float:
    if k <= 0 or not relevance:
        return 0.0
    dcg = 0.0
    for index, skill_id in enumerate(predictions[:k], start=1):
        if skill_id in relevance:
            dcg += _gain(float(relevance[skill_id])) / math.log2(index + 1)
    ideal_gains = sorted((_gain(float(value)) for value in relevance.values()), reverse=True)
    ideal = sum(
        gain / math.log2(index + 1)
        for index, gain in enumerate(ideal_gains[:k], start=1)
    )
    return dcg / ideal if ideal else 0.0


def _gain(relevance: float) -> float:
    return relevance


def _hit_at_1(predictions: list[str], gt_ids: list[str]) -> float:
    return 1.0 if predictions[:1] and predictions[0] in set(gt_ids) else 0.0


def _precision_at_k(
    predictions: list[str],
    gt_ids: list[str],
    k: int,
) -> float:
    if k <= 0:
        return 0.0
    gt_set = set(gt_ids)
    return sum(1 for skill_id in predictions[:k] if skill_id in gt_set) / k


def _mrr_at_k(predictions: list[str], gt_ids: list[str], k: int) -> float:
    gt_set = set(gt_ids)
    for index, skill_id in enumerate(predictions[:k], start=1):
        if skill_id in gt_set:
            return 1.0 / index
    return 0.0


def _recall_at_k(predictions: list[str], gt_ids: list[str], k: int) -> float:
    gt_set = set(gt_ids)
    if not gt_set or k <= 0:
        return 0.0
    return len(set(predictions[:k]) & gt_set) / len(gt_set)


def _full_coverage_at_k(predictions: list[str], gt_ids: list[str], k: int) -> float:
    gt_set = set(gt_ids)
    if not gt_set or k <= 0:
        return 0.0
    return 1.0 if gt_set <= set(predictions[:k]) else 0.0


def _aggregates(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "all": _aggregate(rows),
        "single": _aggregate([row for row in rows if row["slice_gt_count"] == 1]),
        "multi": _aggregate([row for row in rows if row["slice_gt_count"] > 1]),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"task_count": 0, "metrics": None}
    return {
        "task_count": len(rows),
        "metrics": {
            metric: sum(row["metrics"][metric] for row in rows) / len(rows)
            for metric in METRIC_NAMES
        },
    }
