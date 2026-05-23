from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


METRIC_ROWS = (
    ("Recall@1", "recall_at_1", True),
    ("Recall@5", "recall_at_5", True),
    ("MRR", "mrr", True),
    ("NDCG@5", "ndcg_at_5", True),
    ("Negative Hit Rate", "negative_hit_rate", False),
    ("Avg Latency ms", "latency_ms", False),
)


def write_failure_analysis_report(
    router_results: Mapping[str, Path | str],
    output_path: Path | str,
    *,
    baseline: str | None = None,
    candidate: str | None = None,
) -> None:
    if not router_results:
        raise ValueError("router_results must not be empty")

    records_by_router = {
        router: _read_jsonl(Path(results_path))
        for router, results_path in sorted(router_results.items())
    }
    _validate_task_sets(records_by_router)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _render_report(records_by_router, baseline=baseline, candidate=candidate),
        encoding="utf-8",
    )


def result_paths_from_comparison_dir(runs_dir: Path | str) -> dict[str, Path]:
    root = Path(runs_dir)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"runs directory does not exist: {root}")

    result_paths = {
        child.name: child / "results.jsonl"
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "results.jsonl").exists()
    }
    if not result_paths:
        raise ValueError(f"no router results.jsonl files found under {root}")
    return result_paths


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"no result records found in {path}")
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"expected object in {path} at line {index}")
    return records


def _validate_task_sets(records_by_router: Mapping[str, list[dict[str, Any]]]) -> None:
    expected: set[str] | None = None
    for router, records in records_by_router.items():
        task_ids = {str(record["task_id"]) for record in records}
        if expected is None:
            expected = task_ids
        elif task_ids != expected:
            raise ValueError("all router result files must contain the same task ids")
        routers_in_file = {str(record["router"]) for record in records}
        if len(routers_in_file) != 1:
            raise ValueError(f"mixed routers in results for {router}")


def _render_report(
    records_by_router: Mapping[str, list[dict[str, Any]]],
    *,
    baseline: str | None,
    candidate: str | None,
) -> str:
    lines = [
        "# Hermes SkillEval Failure Analysis",
        "",
        "## Failure Summary",
        "",
        "| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for router, records in records_by_router.items():
        summary = _failure_summary(records)
        lines.append(
            "| "
            + " | ".join(
                [
                    router,
                    str(summary["tasks"]),
                    str(summary["top1_misses"]),
                    str(summary["missing_gold_at_5"]),
                    str(summary["negative_hits_at_5"]),
                    str(summary["any_failure"]),
                ]
            )
            + " |"
        )

    if baseline is not None or candidate is not None:
        lines.extend(["", *_render_candidate_section(records_by_router, baseline, candidate)])

    lines.extend(["", "## Failure Cases By Task", ""])
    lines.extend(
        [
            "| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    failure_rows = _failure_rows(records_by_router)
    if failure_rows:
        lines.extend(failure_rows)
    else:
        lines.append("| No failures |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def _failure_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    summaries = [_failure_flags(record) for record in records]
    return {
        "tasks": len(records),
        "top1_misses": sum(flags["top1_miss"] for flags in summaries),
        "missing_gold_at_5": sum(flags["missing_gold_at_5"] for flags in summaries),
        "negative_hits_at_5": sum(flags["negative_hit_at_5"] for flags in summaries),
        "any_failure": sum(any(flags.values()) for flags in summaries),
    }


def _failure_flags(record: dict[str, Any]) -> dict[str, bool]:
    selected = list(record["selected_skill_ids"])
    top5 = selected[:5]
    gold = set(record["gold_skills"])
    negative = set(record["negative_skills"])
    return {
        "top1_miss": bool(gold) and (not selected or selected[0] not in gold),
        "missing_gold_at_5": bool(gold - set(top5)),
        "negative_hit_at_5": bool(negative & set(top5)),
    }


def _issue_labels(record: dict[str, Any]) -> list[str]:
    selected = list(record["selected_skill_ids"])
    top5 = selected[:5]
    gold = set(record["gold_skills"])
    negative_hits = [skill_id for skill_id in top5 if skill_id in set(record["negative_skills"])]
    labels = []
    if negative_hits:
        labels.append(f"negative-hit@5: {', '.join(negative_hits)}")
    missing_gold = sorted(gold - set(top5))
    if missing_gold:
        labels.append(f"missing-gold@5: {', '.join(missing_gold)}")
    if bool(gold) and (not selected or selected[0] not in gold):
        labels.append("top1-miss")
    return labels


def _issues_text(record: dict[str, Any]) -> str:
    return "; ".join(_issue_labels(record)) or "ok"


def _failure_rows(records_by_router: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    rows = []
    for router, records in records_by_router.items():
        for record in records:
            if not _issue_labels(record):
                continue
            rows.append(
                "| "
                + " | ".join(
                    [
                        _escape(record["task_id"]),
                        _escape(record.get("category", "")),
                        _escape(router),
                        _escape(_issues_text(record)),
                        _escape(", ".join(record["gold_skills"])),
                        _escape(", ".join(record["negative_skills"])),
                        _escape(", ".join(record["selected_skill_ids"][:5])),
                    ]
                )
                + " |"
            )
    return rows


def _render_candidate_section(
    records_by_router: Mapping[str, list[dict[str, Any]]],
    baseline: str | None,
    candidate: str | None,
) -> list[str]:
    if baseline is None or candidate is None:
        raise ValueError("--baseline and --candidate must be provided together")
    if baseline not in records_by_router:
        raise ValueError(f"unknown baseline router: {baseline}")
    if candidate not in records_by_router:
        raise ValueError(f"unknown candidate router: {candidate}")

    baseline_records = _by_task(records_by_router[baseline])
    candidate_records = _by_task(records_by_router[candidate])
    lines = [
        "## Candidate vs Baseline",
        "",
        f"- Baseline: `{baseline}`",
        f"- Candidate: `{candidate}`",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, field, higher_is_better in METRIC_ROWS:
        base_value = _mean(records_by_router[baseline], field)
        candidate_value = _mean(records_by_router[candidate], field)
        delta = candidate_value - base_value
        if not higher_is_better:
            delta = -delta
        lines.append(
            f"| {label} | {_fmt(base_value)} | {_fmt(candidate_value)} | {_signed_fmt(delta)} |"
        )

    lines.extend(
        [
            "",
            "## Candidate Task Changes",
            "",
            "| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    change_rows = []
    for task_id in sorted(baseline_records):
        baseline_record = baseline_records[task_id]
        candidate_record = candidate_records[task_id]
        change = _change_type(baseline_record, candidate_record)
        if change == "unchanged":
            continue
        change_rows.append(
            "| "
            + " | ".join(
                [
                    _escape(task_id),
                    change,
                    _escape(_issues_text(baseline_record)),
                    _escape(_issues_text(candidate_record)),
                    _escape(", ".join(baseline_record["selected_skill_ids"][:5])),
                    _escape(", ".join(candidate_record["selected_skill_ids"][:5])),
                ]
            )
            + " |"
        )
    lines.extend(change_rows or ["| No candidate changes |  |  |  |  |  |"])
    return lines


def _by_task(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record["task_id"]): record for record in records}


def _mean(records: list[dict[str, Any]], field: str) -> float:
    return sum(float(record[field]) for record in records) / len(records)


def _change_type(baseline_record: dict[str, Any], candidate_record: dict[str, Any]) -> str:
    baseline_issues = set(_issue_labels(baseline_record))
    candidate_issues = set(_issue_labels(candidate_record))
    base_issue_count = len(baseline_issues)
    candidate_issue_count = len(candidate_issues)
    if baseline_issues and candidate_issues and baseline_issues != candidate_issues:
        return "trade-off"
    if candidate_issue_count < base_issue_count:
        return "improved"
    if candidate_issue_count > base_issue_count:
        return "regressed"
    if float(candidate_record["mrr"]) > float(baseline_record["mrr"]):
        return "improved"
    if float(candidate_record["mrr"]) < float(baseline_record["mrr"]):
        return "regressed"
    return "unchanged"


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def _signed_fmt(value: float) -> str:
    return f"{value:+.3f}"


def _escape(value: object) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "\\|")
