from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_skilleval.remote_paths import validate_a100_user_path
from hermes_skilleval.skill_patch_simulation import compare_route_records


METRIC_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
    "selection_rate_at_5",
)
LIST_FIELDS = (
    "robustness_tags",
    "selected_skill_ids",
    "gold_skills",
    "negative_skills",
)
REQUIRED_FIELDS = (
    "task_id",
    "category",
    "difficulty",
    "split",
    *LIST_FIELDS,
    *METRIC_FIELDS,
)


def write_blind_validation_summary(
    *,
    baseline_results_path: Path | str,
    candidate_results_path: Path | str,
    output_dir: Path | str,
    baseline_router: str,
    candidate_router: str,
    model_dir: str,
    task_root: str,
) -> dict[str, Any]:
    baseline_records = _read_jsonl(baseline_results_path)
    candidate_records = _read_jsonl(candidate_results_path)
    _validate_route_records(
        baseline_records,
        label="baseline",
        path=baseline_results_path,
    )
    _validate_route_records(
        candidate_records,
        label="candidate",
        path=candidate_results_path,
    )
    _validate_test_split(baseline_records, label="baseline")
    _validate_test_split(candidate_records, label="candidate")

    diffs = compare_route_records(baseline_records, candidate_records)
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    summary = {
        "phase": "Phase 16",
        "artifact_type": "phase16-blind-validation",
        "task_root": task_root,
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": validate_a100_user_path(model_dir, field="model_dir"),
        "model_checkpoint_committed": False,
        "split_policy": "blind task root; all records must use split == 'test'",
        "task_count": len(candidate_records),
        "blind_task_ids": sorted(str(record["task_id"]) for record in candidate_records),
        "guard_status": "PASS" if regression_count == 0 else "REVIEW_REQUIRED",
        "baseline_mean_metrics": baseline_metrics,
        "candidate_mean_metrics": candidate_metrics,
        "metric_deltas": {
            field: round(candidate_metrics[field] - baseline_metrics[field], 6)
            for field in METRIC_FIELDS
        },
        "regression_count": regression_count,
        "improvement_count": improvement_count,
        "input_paths": {
            "baseline_results": str(baseline_results_path),
            "candidate_results": str(candidate_results_path),
            "task_root": task_root,
        },
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "route-diffs.jsonl", diffs)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "comparison.md").write_text(
        _render_markdown(summary, diffs),
        encoding="utf-8",
    )
    return summary


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"no records found in {path}")
    return records


def _validate_route_records(
    records: list[dict[str, Any]],
    *,
    label: str,
    path: Path | str,
) -> None:
    for index, record in enumerate(records):
        for field in REQUIRED_FIELDS:
            if field not in record:
                raise ValueError(
                    f"{label} route result {path} record {index} "
                    f"task {record.get('task_id', '<missing-task-id>')} "
                    f"missing required field: {field}"
                )
        for field in LIST_FIELDS:
            if not isinstance(record[field], list):
                raise ValueError(
                    f"{label} route result {path} record {index} "
                    f"task {record['task_id']} field {field} must be a list"
                )
        for field in METRIC_FIELDS:
            value = record[field]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(
                    f"{label} route result {path} record {index} "
                    f"task {record['task_id']} field {field} must be int or float"
                )


def _validate_test_split(records: list[dict[str, Any]], *, label: str) -> None:
    mismatched = [
        str(record.get("task_id", "<missing-task-id>"))
        for record in records
        if record.get("split") != "test"
    ]
    if mismatched:
        raise ValueError(
            f"all {label} records must use split == 'test': {', '.join(mismatched)}"
        )


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _mean_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    return {
        field: round(sum(float(record[field]) for record in records) / len(records), 6)
        for field in METRIC_FIELDS
    }


def _render_markdown(summary: dict[str, Any], diffs: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 16 Blind Validation",
        "",
        f"- Baseline: `{summary['baseline_router']}`",
        f"- Candidate: `{summary['candidate_router']}`",
        f"- Task root: `{summary['task_root']}`",
        f"- Task count: {summary['task_count']}",
        f"- Guard status: {summary['guard_status']}",
        f"- Model checkpoint committed: {summary['model_checkpoint_committed']}",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for field in METRIC_FIELDS:
        lines.append(
            f"| {field} | {summary['baseline_mean_metrics'][field]:.6f} | "
            f"{summary['candidate_mean_metrics'][field]:.6f} | "
            f"{summary['metric_deltas'][field]:+.6f} |"
        )

    flagged = [
        diff for diff in diffs if diff["regression_flags"] or diff["improvement_flags"]
    ]
    lines.extend(["", "## Guard Flags", ""])
    if not flagged:
        lines.append("No per-task regression or improvement flags were observed.")
    else:
        lines.extend(["| Task | Regression Flags | Improvement Flags |", "|---|---|---|"])
        for diff in flagged:
            regression_flags = ", ".join(diff["regression_flags"]) or "-"
            improvement_flags = ", ".join(diff["improvement_flags"]) or "-"
            lines.append(
                "| "
                f"{diff['task_id']} | "
                f"{regression_flags} | "
                f"{improvement_flags} |"
            )
    lines.append("")
    return "\n".join(lines)
