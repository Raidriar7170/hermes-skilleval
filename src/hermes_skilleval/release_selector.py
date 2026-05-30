from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


APPROVE_CANDIDATE = "APPROVE_CANDIDATE"
KEEP_BASELINE = "KEEP_BASELINE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NO_CHANGE = "NO_CHANGE"
REQUIRED_METRIC_DELTAS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
)
DEFAULT_RELEASE_POLICY: dict[str, float | int] = {
    "max_regressions": 0,
    "max_negative_hit_delta": 0.0,
    "max_negative_accepted_delta": 0.0,
    "min_recall_at_5_delta": 0.0,
    "min_mrr_delta": 0.0,
    "min_ndcg_at_5_delta": 0.0,
}


def select_release_router(
    *,
    summary: dict[str, Any] | Path | str,
    route_diffs: list[Any] | Path | str,
    policy: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    summary_path = str(summary) if isinstance(summary, str | Path) else None
    diffs_path = str(route_diffs) if isinstance(route_diffs, str | Path) else None
    summary_record = _load_summary(summary)
    diff_records = _load_route_diffs(route_diffs)
    effective_policy = {**DEFAULT_RELEASE_POLICY, **(policy or {})}

    reasons = _validation_reasons(summary_record, diff_records)
    if reasons:
        return _decision_record(
            summary=summary_record if isinstance(summary_record, dict) else {},
            route_diffs=diff_records if isinstance(diff_records, list) else [],
            policy=effective_policy,
            decision=REVIEW_REQUIRED,
            selected_router=None,
            reasons=reasons,
            summary_path=summary_path,
            diffs_path=diffs_path,
        )

    assert isinstance(summary_record, dict)
    assert isinstance(diff_records, list)
    policy_reasons = _policy_reasons(summary_record, effective_policy)
    if policy_reasons:
        decision = KEEP_BASELINE
        selected_router = summary_record["baseline_router"]
        approved = False
        reasons = policy_reasons
    else:
        decision = APPROVE_CANDIDATE
        selected_router = summary_record["candidate_router"]
        approved = True
        reasons = ["Phase16 guard_status and release policy budgets pass"]

    record = _decision_record(
        summary=summary_record,
        route_diffs=diff_records,
        policy=effective_policy,
        decision=decision,
        selected_router=selected_router,
        reasons=reasons,
        summary_path=summary_path,
        diffs_path=diffs_path,
    )
    record["approved_for_default"] = approved
    return record


def write_release_decision(
    *,
    regression_summary_path: Path | str,
    route_diffs_path: Path | str,
    output_dir: Path | str,
    policy: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    decision = select_release_router(
        summary=regression_summary_path,
        route_diffs=route_diffs_path,
        policy=policy,
    )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    (output / "release-decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "task-decisions.jsonl").write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in decision["task_decisions"]
        ),
        encoding="utf-8",
    )
    (output / "release-decision.md").write_text(
        _render_markdown(decision),
        encoding="utf-8",
    )
    return decision


def _load_summary(source: dict[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    if not path.exists():
        return {"_missing_input": f"missing regression summary: {path}"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"malformed regression summary JSON: {source}") from error
    if not isinstance(data, dict):
        return {"_malformed": "regression summary must be an object"}
    return data


def _load_route_diffs(source: list[Any] | Path | str) -> list[Any]:
    if isinstance(source, list):
        return source
    path = Path(source)
    if not path.exists():
        return [{"_missing_input": f"missing route diffs: {path}"}]
    records: list[Any] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"malformed route diff JSON on line {line_number}: {source}"
            ) from error
    return records


def _validation_reasons(summary: dict[str, Any], route_diffs: list[Any]) -> list[str]:
    reasons: list[str] = []
    if summary.get("_missing_input"):
        reasons.append(str(summary["_missing_input"]))
    for record in route_diffs:
        if isinstance(record, dict) and record.get("_missing_input"):
            reasons.append(str(record["_missing_input"]))
    if summary.get("artifact_type") != "phase16-blind-validation":
        reasons.append("wrong artifact_type; expected phase16-blind-validation")
    if not _non_empty_string(summary.get("baseline_router")):
        reasons.append("baseline_router must be a non-empty string")
    if not _non_empty_string(summary.get("candidate_router")):
        reasons.append("candidate_router must be a non-empty string")
    if not _non_empty_string(summary.get("guard_status")):
        reasons.append("guard_status must be a non-empty string")

    task_count = summary.get("task_count")
    if isinstance(task_count, bool) or not isinstance(task_count, int) or task_count <= 0:
        reasons.append("task_count must be a positive integer")

    blind_task_ids = summary.get("blind_task_ids")
    if not isinstance(blind_task_ids, list) or not all(
        _non_empty_string(task_id) for task_id in blind_task_ids
    ):
        reasons.append("blind_task_ids must be a list of non-empty strings")
        blind_task_ids = []
    if len(set(blind_task_ids)) != len(blind_task_ids):
        reasons.append("duplicate task ids in blind_task_ids")
    if isinstance(task_count, int) and task_count > 0 and len(blind_task_ids) != task_count:
        reasons.append("task_count does not match blind_task_ids")

    metric_deltas = summary.get("metric_deltas")
    if not isinstance(metric_deltas, dict):
        reasons.append("metric_deltas must be an object")
    else:
        for field in REQUIRED_METRIC_DELTAS:
            value = metric_deltas.get(field)
            if isinstance(value, bool) or not isinstance(value, int | float):
                reasons.append(f"metric_deltas.{field} must be numeric")

    for field in ("regression_count", "improvement_count"):
        value = summary.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            reasons.append(f"{field} must be an integer")

    if not route_diffs:
        reasons.append("route-diffs must not be empty")

    diff_task_ids: list[str] = []
    for index, record in enumerate(route_diffs):
        if not isinstance(record, dict):
            reasons.append(f"route diff record {index} must be an object")
            continue
        task_id = record.get("task_id")
        if not _non_empty_string(task_id):
            reasons.append(f"route diff record {index} missing task_id")
            continue
        diff_task_ids.append(task_id)
        diff_metric_deltas = record.get("metric_deltas")
        if not isinstance(diff_metric_deltas, dict):
            reasons.append(f"route diff record {index} metric_deltas must be an object")
            continue
        for field in REQUIRED_METRIC_DELTAS:
            value = diff_metric_deltas.get(field)
            if isinstance(value, bool) or not isinstance(value, int | float):
                reasons.append(
                    f"route diff record {index} metric_deltas.{field} must be numeric"
                )

    duplicate_diff_ids = sorted(
        task_id for task_id, count in Counter(diff_task_ids).items() if count > 1
    )
    if duplicate_diff_ids:
        reasons.append("duplicate task ids in route diffs: " + ", ".join(duplicate_diff_ids))
    if isinstance(task_count, int) and task_count > 0 and len(diff_task_ids) != task_count:
        reasons.append("task_count does not match route diffs")
    if blind_task_ids and set(diff_task_ids) != set(blind_task_ids):
        reasons.append("task ids mismatch between summary and route diffs")

    return reasons


def _policy_reasons(
    summary: dict[str, Any],
    policy: dict[str, float | int],
) -> list[str]:
    metric_deltas = summary["metric_deltas"]
    checks = [
        (
            summary["guard_status"] == "PASS",
            "source guard_status is not PASS",
        ),
        (
            summary["regression_count"] <= policy["max_regressions"],
            "regression_count exceeds policy",
        ),
        (
            metric_deltas["negative_hit_rate"] <= policy["max_negative_hit_delta"],
            "negative_hit_rate delta exceeds policy",
        ),
        (
            metric_deltas["negative_accepted_rate"]
            <= policy["max_negative_accepted_delta"],
            "negative_accepted_rate delta exceeds policy",
        ),
        (
            metric_deltas["recall_at_5"] >= policy["min_recall_at_5_delta"],
            "recall_at_5 delta is below policy",
        ),
        (
            metric_deltas["mrr"] >= policy["min_mrr_delta"],
            "mrr delta is below policy",
        ),
        (
            metric_deltas["ndcg_at_5"] >= policy["min_ndcg_at_5_delta"],
            "ndcg_at_5 delta is below policy",
        ),
    ]
    return [message for ok, message in checks if not ok]


def _decision_record(
    *,
    summary: dict[str, Any],
    route_diffs: list[Any],
    policy: dict[str, float | int],
    decision: str,
    selected_router: str | None,
    reasons: list[str],
    summary_path: str | None,
    diffs_path: str | None,
) -> dict[str, Any]:
    task_decisions = _task_decisions(route_diffs, aggregate_decision=decision)
    return {
        "phase": "Phase 17",
        "artifact_type": "phase17-calibrated-release-selector",
        "source_phase": summary.get("phase"),
        "source_guard_status": summary.get("guard_status"),
        "decision": decision,
        "selected_router": selected_router,
        "baseline_router": summary.get("baseline_router"),
        "candidate_router": summary.get("candidate_router"),
        "approved_for_default": decision == APPROVE_CANDIDATE,
        "policy": policy,
        "reasons": reasons,
        "task_count": summary.get("task_count", len(task_decisions)),
        "regression_count": summary.get("regression_count", 0),
        "improvement_count": summary.get("improvement_count", 0),
        "metric_deltas": summary.get("metric_deltas", {}),
        "regression_flag_counts": _regression_flag_counts(route_diffs),
        "task_decisions": task_decisions,
        "input_paths": _input_paths(summary, summary_path, diffs_path),
    }


def _task_decisions(
    route_diffs: list[Any],
    *,
    aggregate_decision: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in route_diffs:
        if not isinstance(record, dict):
            continue
        regression_flags = list(record.get("regression_flags") or [])
        improvement_flags = list(record.get("improvement_flags") or [])
        if regression_flags:
            task_decision = KEEP_BASELINE
        elif improvement_flags:
            task_decision = APPROVE_CANDIDATE
        else:
            task_decision = NO_CHANGE
        records.append(
            {
                "task_id": record.get("task_id"),
                "decision": task_decision,
                "decision_scope": "task-level",
                "aggregate_decision": aggregate_decision,
                "regression_flags": regression_flags,
                "improvement_flags": improvement_flags,
                "metric_deltas": record.get("metric_deltas", {}),
                "selection_changed": bool(record.get("selection_changed", False)),
            }
        )
    return records


def _regression_flag_counts(route_diffs: list[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in route_diffs:
        if isinstance(record, dict):
            counts.update(str(flag) for flag in record.get("regression_flags") or [])
    return dict(sorted(counts.items()))


def _input_paths(
    summary: dict[str, Any],
    summary_path: str | None,
    diffs_path: str | None,
) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    if isinstance(summary.get("input_paths"), dict):
        paths.update(summary["input_paths"])
    if summary_path is not None:
        paths["regression_summary"] = summary_path
    if diffs_path is not None:
        paths["route_diffs"] = diffs_path
    return paths


def _render_markdown(decision: dict[str, Any]) -> str:
    lines = [
        "# Phase 17 Calibrated Release Selector",
        "",
        f"- Source phase: {decision['source_phase']}",
        f"- Source guard status: `{decision['source_guard_status']}`",
        f"- Aggregate decision: `{decision['decision']}`",
        f"- Selected router: `{decision['selected_router']}`",
        f"- Baseline router: `{decision['baseline_router']}`",
        f"- Candidate router: `{decision['candidate_router']}`",
        f"- Approved for default: `{decision['approved_for_default']}`",
        f"- Task count: {decision['task_count']}",
        f"- Regression count: {decision['regression_count']}",
        "",
        "## Policy",
        "",
        "| Budget | Value |",
        "|---|---:|",
    ]
    for key, value in decision["policy"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Reasons", ""])
    lines.extend(f"- {reason}" for reason in decision["reasons"])
    lines.extend(
        [
            "",
            "## Task-level Decisions",
            "",
            "`NO_CHANGE` is a task-level status only; aggregate release decisions are "
            "`APPROVE_CANDIDATE`, `KEEP_BASELINE`, or `REVIEW_REQUIRED`.",
            "",
            "| Task | Task-level decision | Regression flags |",
            "|---|---|---|",
        ]
    )
    for record in decision["task_decisions"]:
        flags = ", ".join(record["regression_flags"]) or "-"
        lines.append(f"| {record['task_id']} | `{record['decision']}` | {flags} |")
    lines.append("")
    return "\n".join(lines)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
