from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermes_skilleval.metrics import (
    abstention_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    recall_at_k,
    selection_rate_at_k,
)

SUMMARY_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "abstention_rate",
    "selection_rate_at_5",
    "latency_ms",
)
REQUIRED_FIELDS = {
    "task_id",
    "router",
    "selected_skill_ids",
    "gold_skills",
    "negative_skills",
    "latency_ms",
}


@dataclass(frozen=True)
class DashboardRun:
    label: str
    source_path: str
    task_count: int
    metrics: dict[str, float]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "source_path": self.source_path,
            "task_count": self.task_count,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class DashboardRecord:
    run_label: str
    task_id: str
    router: str
    split: str
    category: str
    difficulty: str
    prompt: str
    selected_skill_ids: list[str]
    gold_skills: list[str]
    negative_skills: list[str]
    metrics: dict[str, float]
    failure_tags: list[str]
    score_ranking: list[dict[str, float | str]]
    raw: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run": self.run_label,
            "task_id": self.task_id,
            "router": self.router,
            "split": self.split,
            "category": self.category,
            "difficulty": self.difficulty,
            "prompt": self.prompt,
            "selected_skill_ids": self.selected_skill_ids,
            "gold_skills": self.gold_skills,
            "negative_skills": self.negative_skills,
            "metrics": self.metrics,
            "failure_tags": self.failure_tags,
            "score_ranking": self.score_ranking,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class DashboardPayload:
    source_path: str
    generated_at: str
    runs: list[DashboardRun]
    records: list[DashboardRecord]
    filters: dict[str, list[str]]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "generated_at": self.generated_at,
            "runs": [run.to_json_dict() for run in self.runs],
            "records": [record.to_json_dict() for record in self.records],
            "filters": self.filters,
        }


def build_dashboard_payload(runs_path: Path | str) -> DashboardPayload:
    root = Path(runs_path)
    if not root.is_dir():
        raise ValueError(f"dashboard runs path must be a directory: {root}")

    run_dirs = sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "results.jsonl").is_file()
    )
    if not run_dirs:
        raise ValueError(f"no dashboard runs found under {root}")

    runs: list[DashboardRun] = []
    records: list[DashboardRecord] = []
    for run_dir in run_dirs:
        raw_records = _read_jsonl(run_dir / "results.jsonl")
        normalized = [
            _normalize_record(record, run_dir / "results.jsonl", line_number)
            for line_number, record in raw_records
        ]
        dashboard_records = [
            DashboardRecord(
                run_label=run_dir.name,
                task_id=record["task_id"],
                router=record["router"],
                split=record["split"],
                category=record["category"],
                difficulty=record["difficulty"],
                prompt=record["prompt"],
                selected_skill_ids=record["selected_skill_ids"],
                gold_skills=record["gold_skills"],
                negative_skills=record["negative_skills"],
                metrics=record["metrics"],
                failure_tags=_failure_tags(
                    record["metrics"], record["selected_skill_ids"]
                ),
                score_ranking=_score_ranking(record),
                raw=record["raw"],
            )
            for record in normalized
        ]
        runs.append(
            DashboardRun(
                label=run_dir.name,
                source_path=str(run_dir / "results.jsonl"),
                task_count=len(dashboard_records),
                metrics=_mean_summary_metrics([record.metrics for record in dashboard_records]),
            )
        )
        records.extend(dashboard_records)

    filters = {
        "runs": [run.label for run in runs],
        "splits": _sorted_unique(record.split for record in records),
        "categories": _sorted_unique(record.category for record in records),
        "difficulties": _sorted_unique(record.difficulty for record in records),
        "failure_tags": _sorted_unique(tag for record in records for tag in record.failure_tags),
    }
    return DashboardPayload(
        source_path=str(root),
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        runs=runs,
        records=records,
        filters=filters,
    )


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"malformed JSONL in {path} at line {line_number}: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"expected object in {path} at line {line_number}")
            records.append((line_number, record))
    if not records:
        raise ValueError(f"no result records found in {path}")
    return records


def _normalize_record(
    record: dict[str, Any], path: Path, line_number: int
) -> dict[str, Any]:
    _validate_record(record, path, line_number)
    selected = _string_list_field(record, "selected_skill_ids", path, line_number)
    gold = _string_list_field(record, "gold_skills", path, line_number)
    negative = _string_list_field(record, "negative_skills", path, line_number)
    normalized = {
        "task_id": record["task_id"],
        "router": record["router"],
        "split": record.get("split", ""),
        "category": record.get("category", ""),
        "difficulty": record.get("difficulty", ""),
        "prompt": record.get("prompt", ""),
        "selected_skill_ids": selected,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": float(record["latency_ms"]),
        "scores": record.get("scores", {}),
        "raw": dict(record),
    }
    normalized["metrics"] = _record_metrics(
        record, selected, gold, negative, path, line_number
    )
    return normalized


def _validate_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        raise ValueError(
            f"missing fields in {path} at line {line_number}: {', '.join(missing)}"
        )
    for field in ("task_id", "router"):
        if not isinstance(record[field], str):
            raise ValueError(
                f"field {field!r} must be a string in {path} at line {line_number}"
            )
    for field in ("split", "category", "difficulty"):
        if field in record and not isinstance(record[field], str):
            raise ValueError(
                f"field {field!r} must be a string in {path} at line {line_number}"
            )
    if "prompt" in record and not isinstance(record["prompt"], str):
        raise ValueError(f"field 'prompt' must be a string in {path} at line {line_number}")
    for field in ("selected_skill_ids", "gold_skills", "negative_skills"):
        _string_list_field(record, field, path, line_number)
    if _finite_number(record["latency_ms"]) is None:
        raise ValueError(f"field 'latency_ms' must be finite in {path} at line {line_number}")


def _string_list_field(
    record: dict[str, Any], field: str, path: Path, line_number: int
) -> list[str]:
    value = record[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            f"field {field!r} must be a list of strings in {path} at line {line_number}"
        )
    return list(value)


def _record_metrics(
    record: dict[str, Any],
    selected: list[str],
    gold: list[str],
    negative: list[str],
    path: Path,
    line_number: int,
) -> dict[str, float]:
    return {
        "recall_at_5": _metric_or(
            record, "recall_at_5", recall_at_k(selected, gold, 5), path, line_number
        ),
        "mrr": _metric_or(
            record, "mrr", mean_reciprocal_rank(selected, gold), path, line_number
        ),
        "ndcg_at_5": _metric_or(
            record, "ndcg_at_5", ndcg_at_k(selected, gold, 5), path, line_number
        ),
        "negative_hit_rate": _metric_or(
            record,
            "negative_hit_rate",
            negative_hit_rate(selected, negative, 5),
            path,
            line_number,
        ),
        "abstention_rate": _metric_or(
            record, "abstention_rate", abstention_rate(selected), path, line_number
        ),
        "selection_rate_at_5": _metric_or(
            record,
            "selection_rate_at_5",
            selection_rate_at_k(selected, 5),
            path,
            line_number,
        ),
        "latency_ms": _metric_or(record, "latency_ms", 0.0, path, line_number),
    }


def _metric_or(
    record: dict[str, Any], field: str, fallback: float, path: Path, line_number: int
) -> float:
    if field not in record:
        return float(fallback)
    value = _finite_number(record[field])
    if value is None:
        raise ValueError(f"field {field!r} must be finite in {path} at line {line_number}")
    return value


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return numeric


def _failure_tags(metrics: dict[str, float], selected: list[str]) -> list[str]:
    tags: list[str] = []
    if metrics["recall_at_5"] < 1.0:
        tags.append("recall-miss")
    if metrics["negative_hit_rate"] > 0.0:
        tags.append("negative-hit")
    if not selected or metrics["abstention_rate"] > 0.0:
        tags.append("abstained")
    if metrics["selection_rate_at_5"] < 1.0:
        tags.append("low-selection")
    return tags


def _score_ranking(record: dict[str, Any]) -> list[dict[str, float | str]]:
    scores = record.get("scores")
    if not isinstance(scores, dict):
        return []
    rows: list[dict[str, float | str]] = []
    for skill_id, value in scores.items():
        score = _finite_number(value)
        if isinstance(skill_id, str) and score is not None:
            rows.append({"skill_id": skill_id, "score": score})
    return sorted(rows, key=lambda row: (-float(row["score"]), str(row["skill_id"])))


def _mean_summary_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        field: round(sum(row[field] for row in rows) / len(rows), 6)
        for field in SUMMARY_FIELDS
    }


def _sorted_unique(values: Any) -> list[str]:
    return sorted({value for value in values if value})
