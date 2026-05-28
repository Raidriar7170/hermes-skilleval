from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_TRACE_SCHEMA = "phase10.agent-loop.v1"
DEFAULT_JUDGE_SCHEMA = "phase11.evidence-judge.v1"
DEFAULT_BACKEND = "deterministic-rubric"
PASS_THRESHOLD = 0.75


def judge_agent_loop(
    *,
    traces_path: Path | str,
    output_dir: Path | str,
    run_label: str = "judge-agent-loop",
    backend: str = DEFAULT_BACKEND,
) -> dict[str, object]:
    if backend != DEFAULT_BACKEND:
        raise ValueError(f"unsupported judge backend: {backend}")

    traces = _read_jsonl(Path(traces_path))
    if not traces:
        raise ValueError(f"no trace records found in {traces_path}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    judge_records = [
        _judge_trace(trace, run_label, str(traces_path), backend)
        for trace in traces
    ]
    dashboard_records = [_dashboard_record(record, run_label) for record in judge_records]

    _write_jsonl(output / "judge-results.jsonl", judge_records)
    _write_jsonl(output / "results.jsonl", dashboard_records)
    summary = _summary(judge_records, run_label, backend)
    (output / "judge-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "judge-rubric.md").write_text(_rubric_markdown(), encoding="utf-8")
    return summary


def _judge_trace(
    trace: dict[str, object],
    run_label: str,
    traces_path: str,
    backend: str,
) -> dict[str, object]:
    if trace.get("trace_schema_version") != SUPPORTED_TRACE_SCHEMA:
        raise ValueError(
            f"unsupported trace_schema_version: {trace.get('trace_schema_version')}"
        )

    expected = _string_list(trace.get("expected_evidence", []), "expected_evidence")
    checks = trace.get("evidence_checks", [])
    evidence_score = _evidence_score(expected, checks)

    penalties: list[str] = []
    if evidence_score < 1.0:
        penalties.append("missing-evidence")
    if trace.get("failure_type") == "negative_skill_selected":
        penalties.append("negative-skill-failure")
    if trace.get("agent_success") is not True:
        penalties.append("agent-loop-failed")

    judge_score = max(0.0, evidence_score - 0.25 * len(penalties))
    judge_status = (
        "passed" if judge_score >= PASS_THRESHOLD and not penalties else "failed"
    )

    return {
        "judge_schema_version": DEFAULT_JUDGE_SCHEMA,
        "trace_schema_version": trace["trace_schema_version"],
        "trace_id": _required_string(trace.get("trace_id"), "trace_id"),
        "task_id": _required_string(trace.get("task_id"), "task_id"),
        "prompt": _required_string(trace.get("prompt"), "prompt"),
        "router": run_label,
        "execution_condition": trace.get("execution_condition", ""),
        "source_router": trace.get("source_router", ""),
        "source_traces_path": traces_path,
        "judge_backend": backend,
        "selected_skill_ids": _string_list(
            trace.get("selected_skill_ids", []), "selected_skill_ids"
        ),
        "expected_evidence": expected,
        "evidence_checks": checks,
        "evidence_score": round(evidence_score, 3),
        "judge_score": round(judge_score, 3),
        "judge_status": judge_status,
        "judge_pass": judge_status == "passed",
        "penalties": penalties,
        "failure_type": trace.get("failure_type"),
        "failure_reason": trace.get("failure_reason"),
    }


def _dashboard_record(record: dict[str, object], run_label: str) -> dict[str, object]:
    judge_pass = record["judge_pass"] is True
    selected = _string_list(record.get("selected_skill_ids", []), "selected_skill_ids")
    return {
        "task_id": record["task_id"],
        "router": run_label,
        "split": "test",
        "category": "agent-loop-judge",
        "difficulty": "",
        "prompt": record["prompt"],
        "selected_skill_ids": selected,
        "gold_skills": selected if judge_pass else [],
        "negative_skills": [],
        "latency_ms": 0.0,
        "recall_at_1": 1.0 if judge_pass else 0.0,
        "recall_at_3": 1.0 if judge_pass else 0.0,
        "recall_at_5": 1.0 if judge_pass else 0.0,
        "precision_at_5": 1.0 if judge_pass else 0.0,
        "mrr": 1.0 if judge_pass else 0.0,
        "ndcg_at_5": 1.0 if judge_pass else 0.0,
        "negative_hit_rate": 0.0,
        "accepted_count": len(selected) if judge_pass else 0,
        "coverage": 1.0 if selected else 0.0,
        "abstention_rate": 0.0 if selected else 1.0,
        "selection_rate_at_5": min(len(selected), 5) / 5,
        "accepted_recall_at_5": 1.0 if judge_pass else 0.0,
        "negative_accepted_rate": 0.0,
        "judge_score": record["judge_score"],
        "evidence_score": record["evidence_score"],
        "judge_pass_rate": 1.0 if judge_pass else 0.0,
        "judge_status": record["judge_status"],
        "execution_condition": record["execution_condition"],
        "penalties": record["penalties"],
    }


def _summary(
    records: list[dict[str, object]],
    run_label: str,
    backend: str,
) -> dict[str, object]:
    task_count = len(records)
    pass_count = sum(1 for record in records if record["judge_pass"] is True)
    judge_scores = [float(record["judge_score"]) for record in records]
    evidence_scores = [float(record["evidence_score"]) for record in records]
    conditions = sorted(
        {
            str(record["execution_condition"])
            for record in records
            if str(record.get("execution_condition", "")).strip()
        }
    )
    return {
        "artifact_type": "phase11-evidence-judge-summary",
        "phase": "Phase 11",
        "run_label": run_label,
        "judge_backend": backend,
        "execution_condition": conditions[0] if len(conditions) == 1 else "mixed",
        "task_count": task_count,
        "judge_pass_count": pass_count,
        "judge_pass_rate": round(pass_count / task_count, 3) if task_count else 0.0,
        "mean_judge_score": round(sum(judge_scores) / task_count, 3)
        if task_count
        else 0.0,
        "mean_evidence_score": round(sum(evidence_scores) / task_count, 3)
        if task_count
        else 0.0,
    }


def _rubric_markdown() -> str:
    return "\n".join(
        [
            "# Phase 11 Evidence Judge Rubric",
            "",
            "- Evidence score is satisfied evidence checks divided by expected evidence count.",
            "- Missing evidence adds `missing-evidence`.",
            "- Negative skill failures add `negative-skill-failure`.",
            "- Failed agent loops add `agent-loop-failed`.",
            f"- A record passes when `judge_score >= {PASS_THRESHOLD}` and no penalties remain.",
            "",
        ]
    )


def _evidence_score(expected: list[str], checks: object) -> float:
    if len(set(expected)) != len(expected):
        raise ValueError("expected_evidence must not contain duplicate entries")
    if not isinstance(checks, list):
        raise ValueError("evidence_checks must be a list")

    by_name: dict[str, bool] = {}
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            raise ValueError(f"evidence_checks[{index}] must be an object")
        name = _required_string(check.get("name"), f"evidence_checks[{index}].name")
        if name in by_name:
            raise ValueError(f"duplicate evidence check: {name}")
        satisfied = check.get("satisfied")
        if not isinstance(satisfied, bool):
            raise ValueError(f"evidence_checks[{index}].satisfied must be a boolean")
        by_name[name] = satisfied

    expected_names = set(expected)
    check_names = set(by_name)
    if check_names != expected_names:
        missing = sorted(expected_names - check_names)
        extra = sorted(check_names - expected_names)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(extra)}")
        raise ValueError(
            "evidence_checks must match expected_evidence"
            + (f" ({'; '.join(details)})" if details else "")
        )

    if not expected:
        return 0.0
    satisfied_count = sum(1 for name in expected if by_name[name])
    return satisfied_count / len(expected)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"expected object in {path} at line {line_number}")
        records.append(record)
    return records


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return list(value)
