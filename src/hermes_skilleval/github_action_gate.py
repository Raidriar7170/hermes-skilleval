from __future__ import annotations

import json
from pathlib import Path

from hermes_skilleval.metrics import (
    accepted_count,
    accepted_recall_at_k,
    coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_accepted_rate,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
    selection_rate_at_k,
)
from hermes_skilleval.models import BenchmarkTask, RouteResult
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.task_loader import load_tasks


SCHEMA_VERSION = "github-action-gate.v1"
BOUNDARY = (
    "Reusable GitHub Action RC; not a Marketplace Action release, not hosted "
    "GitHub Actions proof, not GitHub API PR comments, not PR "
    "annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not "
    "benchmark status, not production readiness, not release approval, not "
    "automatic merge approval, and not a v0.2.0 release."
)


def run_github_action_gate(
    *,
    skill_path: Path,
    benchmark_path: Path,
    min_recall_at_k: float,
    max_negative_hit_rate: float,
    output_dir: Path,
    top_k: int = 5,
) -> dict[str, object]:
    if top_k <= 0:
        raise ValueError("--top-k must be positive")
    if not 0.0 <= min_recall_at_k <= 1.0:
        raise ValueError("--min-recall-at-k must be between 0.0 and 1.0")
    if not 0.0 <= max_negative_hit_rate <= 1.0:
        raise ValueError("--max-negative-hit-rate must be between 0.0 and 1.0")

    output_dir.mkdir(parents=True, exist_ok=True)
    skills = scan_skills(skill_path)
    tasks = load_tasks(benchmark_path)
    router = HybridRouter()

    records: list[dict[str, object]] = []
    for task in tasks:
        result = router.route(task, skills, top_k)
        records.append(_result_record(task, result, top_k))

    results_path = output_dir / "results.jsonl"
    results_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

    metrics = _aggregate_metrics(records)
    failed_policies = _failed_policies(
        metrics,
        min_recall_at_k=min_recall_at_k,
        max_negative_hit_rate=max_negative_hit_rate,
    )
    decision = "BLOCK_MERGE" if failed_policies else "ALLOW_MERGE"
    gate = {
        "artifact_type": "github_action_gate",
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "router": "hybrid",
        "top_k": top_k,
        "task_count": len(tasks),
        "skill_count": len(skills),
        "thresholds": {
            "min_recall_at_k": min_recall_at_k,
            "max_negative_hit_rate": max_negative_hit_rate,
        },
        "metrics": metrics,
        "failed_policies": failed_policies,
        "report_paths": {
            "results": str(results_path),
            "gate_report": str(output_dir / "gate-report.json"),
            "gate_markdown": str(output_dir / "gate-report.md"),
            "ci_summary": str(output_dir / "ci-summary.json"),
            "ci_markdown": str(output_dir / "ci-summary.md"),
        },
        "scope": BOUNDARY,
    }

    _write_json(output_dir / "gate-report.json", gate)
    (output_dir / "gate-report.md").write_text(_render_gate_markdown(gate), encoding="utf-8")

    summary = _ci_summary(gate)
    _write_json(output_dir / "ci-summary.json", summary)
    (output_dir / "ci-summary.md").write_text(
        _render_ci_summary_markdown(summary),
        encoding="utf-8",
    )
    return gate


def _result_record(
    task: BenchmarkTask,
    result: RouteResult,
    top_k: int,
) -> dict[str, object]:
    selected = result.selected_skill_ids
    gold = task.gold_skills
    negative = task.negative_skills
    return {
        "task_id": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "split": task.split,
        "router": result.router,
        "selected_skill_ids": selected,
        "scores": result.scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": result.latency_ms,
        "recall_at_1": recall_at_k(selected, gold, 1),
        "recall_at_3": recall_at_k(selected, gold, 3),
        "recall_at_5": recall_at_k(selected, gold, min(5, top_k)),
        "precision_at_5": precision_at_k(selected, gold, min(5, top_k)),
        "mrr": mean_reciprocal_rank(selected, gold),
        "ndcg_at_5": ndcg_at_k(selected, gold, min(5, top_k)),
        "negative_hit_rate": negative_hit_rate(selected, negative, min(5, top_k)),
        "accepted_count": accepted_count(selected),
        "coverage": coverage(selected),
        "selection_rate_at_5": selection_rate_at_k(selected, min(5, top_k)),
        "accepted_recall_at_5": accepted_recall_at_k(selected, gold, min(5, top_k)),
        "negative_accepted_rate": negative_accepted_rate(selected, negative, min(5, top_k)),
    }


def _aggregate_metrics(records: list[dict[str, object]]) -> dict[str, float]:
    fields = [
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "precision_at_5",
        "mrr",
        "ndcg_at_5",
        "negative_hit_rate",
        "coverage",
        "selection_rate_at_5",
        "accepted_recall_at_5",
        "negative_accepted_rate",
    ]
    return {
        field: round(
            sum(float(record[field]) for record in records) / len(records),
            6,
        )
        for field in fields
    }


def _failed_policies(
    metrics: dict[str, float],
    *,
    min_recall_at_k: float,
    max_negative_hit_rate: float,
) -> list[str]:
    failed: list[str] = []
    if metrics["recall_at_5"] < min_recall_at_k:
        failed.append("recall_at_5 below threshold")
    if metrics["negative_hit_rate"] > max_negative_hit_rate:
        failed.append("negative_hit_rate above threshold")
    return failed


def _ci_summary(gate: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_type": "github_action_ci_summary",
        "schema_version": "github-action-ci-summary.v1",
        "decision": gate["decision"],
        "checks": [
            {
                "name": "github-action-gate",
                "normalized_status": "PASS"
                if gate["decision"] == "ALLOW_MERGE"
                else "FAIL",
                "raw_status": gate["decision"],
            }
        ],
        "gate_report": gate["report_paths"],
        "scope": BOUNDARY,
    }


def _render_gate_markdown(gate: dict[str, object]) -> str:
    metrics = gate["metrics"]
    assert isinstance(metrics, dict)
    failed = gate["failed_policies"]
    assert isinstance(failed, list)
    lines = [
        "# Reusable GitHub Action RC Gate",
        "",
        f"Decision: `{gate['decision']}`",
        "",
        f"Scope: {BOUNDARY}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in ["recall_at_5", "negative_hit_rate", "mrr", "ndcg_at_5"]:
        lines.append(f"| `{key}` | {metrics[key]} |")
    lines.extend(["", "## Failed Policies", ""])
    if failed:
        lines.extend(f"- {policy}" for policy in failed)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_ci_summary_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Reusable GitHub Action RC CI Summary",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        f"Scope: {BOUNDARY}",
        "",
        "## Checks",
        "",
        "| Check | Normalized | Raw status |",
        "|---|---|---|",
    ]
    checks = summary["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        lines.append(
            "| {name} | {normalized_status} | {raw_status} |".format(**check)
        )
    lines.append("")
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
