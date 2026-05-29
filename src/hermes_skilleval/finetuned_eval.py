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
) -> dict[str, Any]:
    validated_model_dir = validate_a100_user_path(model_dir, field="model_dir")

    baseline_records = _read_jsonl(baseline_results_path)
    candidate_records = _read_jsonl(candidate_results_path)
    diffs = compare_route_records(baseline_records, candidate_records)
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    summary = {
        "phase": "Phase 14",
        "artifact_type": "phase14-finetuned-embedding-eval",
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": validated_model_dir,
        "model_checkpoint_committed": False,
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


def _report(summary: dict[str, Any], diffs: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 14 Fine-Tuned Embedding Router Evaluation",
        "",
        f"- Baseline: `{summary['baseline_router']}`",
        f"- Candidate: `{summary['candidate_router']}`",
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
