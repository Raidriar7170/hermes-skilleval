from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)

REQUIRED_FIELDS = {
    "task_id",
    "router",
    "selected_skill_ids",
    "gold_skills",
    "negative_skills",
    "latency_ms",
}


def write_markdown_report(results_path: Path | str, output_path: Path | str) -> None:
    results = _read_results(Path(results_path))
    router = results[0]["router"]

    rows = [_metric_row(record) for record in results]
    top_selected = Counter(
        skill_id for record in results for skill_id in record["selected_skill_ids"]
    ).most_common(10)
    failures = [
        (record, row)
        for record, row in zip(results, rows, strict=True)
        if row["recall@5"] == 0.0 or row["negative_hit_rate"] > 0.0
    ]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _render_report(
            router=str(router),
            record_count=len(results),
            metrics=_mean_metrics(rows),
            top_selected=top_selected,
            task_rows=list(zip(results, rows, strict=True)),
            failures=failures,
        ),
        encoding="utf-8",
    )


def _read_results(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
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
            _validate_record(record, path, line_number)
            records.append(record)
    if not records:
        raise ValueError(f"no result records found in {path}")
    return records


def _validate_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        raise ValueError(
            f"missing fields in {path} at line {line_number}: {', '.join(missing)}"
        )
    for field in ("selected_skill_ids", "gold_skills", "negative_skills"):
        if not isinstance(record[field], list) or not all(
            isinstance(value, str) for value in record[field]
        ):
            raise ValueError(
                f"field {field!r} must be a list of strings in {path} at line {line_number}"
            )
    if not isinstance(record["task_id"], str) or not isinstance(record["router"], str):
        raise ValueError(
            f"fields 'task_id' and 'router' must be strings in {path} at line {line_number}"
        )
    if not isinstance(record["latency_ms"], int | float):
        raise ValueError(f"field 'latency_ms' must be numeric in {path} at line {line_number}")


def _metric_row(record: dict[str, Any]) -> dict[str, float]:
    selected = record["selected_skill_ids"]
    gold = record["gold_skills"]
    negative = record["negative_skills"]
    return {
        "recall@1": recall_at_k(selected, gold, 1),
        "recall@3": recall_at_k(selected, gold, 3),
        "recall@5": recall_at_k(selected, gold, 5),
        "precision@5": precision_at_k(selected, gold, 5),
        "mrr": mean_reciprocal_rank(selected, gold),
        "ndcg@5": ndcg_at_k(selected, gold, 5),
        "negative_hit_rate": negative_hit_rate(selected, negative, 5),
        "latency_ms": float(record["latency_ms"]),
    }


def _mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: sum(row[key] for row in rows) / len(rows)
        for key in (
            "recall@1",
            "recall@3",
            "recall@5",
            "precision@5",
            "mrr",
            "ndcg@5",
            "negative_hit_rate",
            "latency_ms",
        )
    }


def _render_report(
    *,
    router: str,
    record_count: int,
    metrics: dict[str, float],
    top_selected: list[tuple[str, int]],
    task_rows: list[tuple[dict[str, Any], dict[str, float]]],
    failures: list[tuple[dict[str, Any], dict[str, float]]],
) -> str:
    lines = [
        "# Hermes SkillEval Report",
        "",
        f"- Router: {router}",
        f"- Records: {record_count}",
        "",
        "## Metrics",
        "",
        "| Metric | Mean |",
        "| --- | ---: |",
        f"| Recall@1 | {_format_metric(metrics['recall@1'])} |",
        f"| Recall@3 | {_format_metric(metrics['recall@3'])} |",
        f"| Recall@5 | {_format_metric(metrics['recall@5'])} |",
        f"| Precision@5 | {_format_metric(metrics['precision@5'])} |",
        f"| MRR | {_format_metric(metrics['mrr'])} |",
        f"| NDCG@5 | {_format_metric(metrics['ndcg@5'])} |",
        f"| Negative Hit Rate | {_format_metric(metrics['negative_hit_rate'])} |",
        f"| Average Latency (ms) | {_format_metric(metrics['latency_ms'])} |",
        "",
        "## Top Selected Skills",
        "",
    ]
    if top_selected:
        lines.extend(["| Skill | Count |", "| --- | ---: |"])
        lines.extend(f"| {skill_id} | {count} |" for skill_id, count in top_selected)
    else:
        lines.append("No selected skills.")

    lines.extend(["", "## Task Results", ""])
    lines.extend(
        [
            "| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for record, row in task_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    record["task_id"],
                    _format_metric(row["recall@5"]),
                    _format_metric(row["negative_hit_rate"]),
                    _format_metric(row["latency_ms"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Failure Cases", ""])
    if failures:
        lines.extend(
            [
                "| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |",
                "| --- | --- | --- | ---: | ---: |",
            ]
        )
        for record, row in failures:
            lines.append(
                "| "
                + " | ".join(
                    [
                        record["task_id"],
                        ", ".join(record["selected_skill_ids"]),
                        ", ".join(record["gold_skills"]),
                        _format_metric(row["recall@5"]),
                        _format_metric(row["negative_hit_rate"]),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No failure cases.")
    lines.append("")
    return "\n".join(lines)


def _format_metric(value: float) -> str:
    return f"{value:.3f}"
