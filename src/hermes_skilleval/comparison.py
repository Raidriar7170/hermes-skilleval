from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_skilleval.metrics import (
    abstention_rate,
    accepted_recall_at_k,
    coverage,
    negative_accepted_rate,
    selection_rate_at_k,
)


METRIC_FIELDS = (
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "precision_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "coverage",
    "selection_rate_at_5",
    "abstention_rate",
    "accepted_recall_at_5",
    "negative_accepted_rate",
    "latency_ms",
)


def write_comparison_report(
    router_results: dict[str, Path | str],
    output_path: Path | str,
) -> None:
    if not router_results:
        raise ValueError("router_results must not be empty")

    rows = [
        _summary_row(router, _read_jsonl(Path(results_path)))
        for router, results_path in sorted(router_results.items())
    ]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_comparison(rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"no result records found in {path}")
    return records


def _summary_row(router: str, records: list[dict[str, Any]]) -> dict[str, float | str | int]:
    return {
        "router": router,
        "tasks": len(records),
        **{
            field: sum(_metric_value(record, field) for record in records) / len(records)
            for field in METRIC_FIELDS
        },
    }


def _render_comparison(rows: list[dict[str, float | str | int]]) -> str:
    lines = [
        "# Hermes SkillEval Router Comparison",
        "",
        "| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["router"]),
                    str(row["tasks"]),
                    _fmt(row["recall_at_1"]),
                    _fmt(row["recall_at_3"]),
                    _fmt(row["recall_at_5"]),
                    _fmt(row["precision_at_5"]),
                    _fmt(row["mrr"]),
                    _fmt(row["ndcg_at_5"]),
                    _fmt(row["negative_hit_rate"]),
                    _fmt(row["coverage"]),
                    _fmt(row["selection_rate_at_5"]),
                    _fmt(row["abstention_rate"]),
                    _fmt(row["accepted_recall_at_5"]),
                    _fmt(row["negative_accepted_rate"]),
                    _fmt(row["latency_ms"]),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | str | int) -> str:
    return f"{float(value):.3f}"


def _metric_value(record: dict[str, Any], field: str) -> float:
    value = record.get(field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)

    selected = list(record["selected_skill_ids"])
    gold = list(record["gold_skills"])
    negative = list(record["negative_skills"])
    if field == "coverage":
        return coverage(selected)
    if field == "selection_rate_at_5":
        return selection_rate_at_k(selected, 5)
    if field == "abstention_rate":
        return abstention_rate(selected)
    if field == "accepted_recall_at_5":
        return accepted_recall_at_k(selected, gold, 5)
    if field == "negative_accepted_rate":
        return negative_accepted_rate(selected, negative, 5)
    raise KeyError(f"missing metric field: {field}")
