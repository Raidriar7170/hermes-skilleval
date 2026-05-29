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


def write_finetuned_eval_summary(
    *,
    baseline_results_path: Path | str,
    candidate_results_path: Path | str,
    output_dir: Path | str,
    baseline_router: str,
    candidate_router: str,
    model_dir: str,
    apply_split: str = "all",
    write_filtered_results: bool = False,
) -> dict[str, Any]:
    validated_model_dir = validate_a100_user_path(model_dir, field="model_dir")

    baseline_source_records = _read_jsonl(baseline_results_path)
    candidate_source_records = _read_jsonl(candidate_results_path)
    baseline_records = _filter_records_by_split(
        baseline_source_records,
        apply_split=apply_split,
        label="baseline",
    )
    candidate_records = _filter_records_by_split(
        candidate_source_records,
        apply_split=apply_split,
        label="candidate",
    )
    diffs = compare_route_records(baseline_records, candidate_records)
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    summary = {
        "phase": "Phase 15" if apply_split == "test" else "Phase 14",
        "artifact_type": (
            "phase15-heldout-finetuned-embedding-eval"
            if apply_split == "test"
            else "phase14-finetuned-embedding-eval"
        ),
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": validated_model_dir,
        "model_checkpoint_committed": False,
        "evaluated_split": apply_split,
        "split_policy": _split_policy(apply_split),
        "source_task_count": len(candidate_source_records),
        "baseline_source_task_count": len(baseline_source_records),
        "candidate_source_task_count": len(candidate_source_records),
        "task_count": len(candidate_records),
        "guard_status": "PASS" if regression_count == 0 else "REVIEW_REQUIRED",
        "baseline_mean_metrics": baseline_metrics,
        "candidate_mean_metrics": candidate_metrics,
        "metric_deltas": {
            field: round(candidate_metrics[field] - baseline_metrics[field], 6)
            for field in METRIC_FIELDS
        },
        "regression_count": regression_count,
        "improvement_count": improvement_count,
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if write_filtered_results:
        suffix = "all" if apply_split == "all" else apply_split
        _write_jsonl(output / f"baseline-{suffix}-results.jsonl", baseline_records)
        _write_jsonl(output / f"finetuned-{suffix}-results.jsonl", candidate_records)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "comparison.md").write_text(_report(summary, diffs), encoding="utf-8")
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


def _mean_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    return {
        field: round(sum(float(record[field]) for record in records) / len(records), 6)
        for field in METRIC_FIELDS
    }


def _filter_records_by_split(
    records: list[dict[str, Any]],
    *,
    apply_split: str,
    label: str,
) -> list[dict[str, Any]]:
    if apply_split not in {"dev", "test", "all"}:
        raise ValueError("apply_split must be 'dev', 'test', or 'all'")
    filtered = (
        records
        if apply_split == "all"
        else [record for record in records if record.get("split") == apply_split]
    )
    if not filtered:
        raise ValueError(f"no {label} records found for split {apply_split!r}")
    return filtered


def _split_policy(apply_split: str) -> str:
    if apply_split == "all":
        return "all source records"
    return f"records where split == {apply_split!r}"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _report(summary: dict[str, Any], diffs: list[dict[str, Any]]) -> str:
    lines = [
        (
            "# Phase 15 Held-Out Fine-Tuned Embedding Router Evaluation"
            if summary["evaluated_split"] == "test"
            else "# Phase 14 Fine-Tuned Embedding Router Evaluation"
        ),
        "",
        f"- Baseline: `{summary['baseline_router']}`",
        f"- Candidate: `{summary['candidate_router']}`",
        f"- Evaluated split: `{summary['evaluated_split']}`",
        f"- Source task count: {summary['source_task_count']}",
        f"- Evaluated task count: {summary['task_count']}",
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
