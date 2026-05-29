from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.metrics import (
    abstention_rate,
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
from hermes_skilleval.skill_index import load_skill_index


TRACE_SCHEMA_VERSION = "phase10.agent-loop.v1"
CONDITIONS = {"no-skill", "routed-skill", "oracle-skill"}


def run_agent_loop(
    *,
    routes_path: Path | str,
    tasks_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
    condition: str = "routed-skill",
    run_label: str | None = None,
) -> dict[str, object]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown agent loop condition: {condition}")

    routes = _read_jsonl(Path(routes_path))
    if not routes:
        raise ValueError(f"no route records found in {routes_path}")

    tasks = _load_task_metadata(Path(tasks_path))
    skills = {skill.id: skill for skill in load_skill_index(skills_index_path)}
    source_router = _source_router(routes)
    label = run_label or _default_run_label(condition, source_router)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for route in routes:
        task_id = _string_field(route, "task_id", Path(routes_path))
        task = tasks.get(task_id)
        if task is None:
            raise ValueError(f"route references unknown task: {task_id}")
        selected = _selected_for_condition(route, task, condition)
        _validate_selected_skills(selected, skills, task_id)
        trace = _trace_record(
            task=task,
            route=route,
            selected=selected,
            condition=condition,
            run_label=label,
            source_router=source_router,
            routes_path=str(routes_path),
        )
        traces.append(trace)
        records.append(_result_record(trace, route, task, selected, label))

    _write_jsonl(output / "agent-traces.jsonl", traces)
    _write_jsonl(output / "results.jsonl", records)
    summary = _summary(label, source_router, condition, records)
    (output / "agent-loop-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(_report(summary, records), encoding="utf-8")
    return summary


def _load_task_metadata(root: Path) -> dict[str, dict[str, object]]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"tasks_path does not exist or is not a directory: {root}")
    tasks: dict[str, dict[str, object]] = {}
    for yaml_path in sorted(root.rglob("task.yaml")):
        task_dir = yaml_path.parent
        prompt_path = task_dir / "prompt.md"
        if not prompt_path.exists():
            raise ValueError(f"missing prompt.md in {task_dir}")
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"task.yaml must contain a mapping: {yaml_path}")
        task_id = _required_string(raw.get("id"), yaml_path, "id")
        tasks[task_id] = {
            "id": task_id,
            "category": _required_string(raw.get("category"), yaml_path, "category"),
            "difficulty": _required_string(
                raw.get("difficulty"),
                yaml_path,
                "difficulty",
            ),
            "split": raw.get("split", "dev"),
            "prompt": prompt_path.read_text(encoding="utf-8").strip(),
            "gold_skills": _string_list(raw.get("gold_skills"), yaml_path, "gold_skills"),
            "negative_skills": _string_list(
                raw.get("negative_skills"),
                yaml_path,
                "negative_skills",
            ),
            "robustness_tags": _string_list(
                raw.get("robustness_tags", []),
                yaml_path,
                "robustness_tags",
            ),
            "migration_source": raw.get("migration_source"),
            "expected_evidence": _string_list(
                raw.get("expected_evidence", []),
                yaml_path,
                "expected_evidence",
            ),
            "migration_dimensions": _string_list(
                raw.get("migration_dimensions", []),
                yaml_path,
                "migration_dimensions",
            ),
        }
    if not tasks:
        raise ValueError(f"no benchmark tasks found under {root}; expected task.yaml files")
    return tasks


def _trace_record(
    *,
    task: dict[str, object],
    route: dict[str, object],
    selected: list[str],
    condition: str,
    run_label: str,
    source_router: str,
    routes_path: str,
) -> dict[str, object]:
    gold = _string_list(task["gold_skills"], Path("<task>"), "gold_skills")
    negative = _string_list(task["negative_skills"], Path("<task>"), "negative_skills")
    expected_evidence = _string_list(
        task["expected_evidence"],
        Path("<task>"),
        "expected_evidence",
    )
    migration_dimensions = _string_list(
        task["migration_dimensions"],
        Path("<task>"),
        "migration_dimensions",
    )
    gold_hit = bool(set(selected) & set(gold))
    negative_hit = bool(set(selected[:5]) & set(negative))
    evidence_checks = [
        {
            "name": evidence,
            "satisfied": gold_hit and not negative_hit,
            "source": "deterministic-skill-selection",
        }
        for evidence in expected_evidence
    ]
    dimension_scores = {
        dimension: 1.0 if gold_hit and not negative_hit else 0.0
        for dimension in migration_dimensions
    }
    agent_success = gold_hit and not negative_hit
    failure_type = None
    failure_reason = None
    if not selected:
        failure_type = "no_skill_selected"
        failure_reason = "No skill guidance was injected into the simulated loop."
    elif not gold_hit:
        failure_type = "routing_miss"
        failure_reason = "Selected skill set did not include a gold migrated skill."
    elif negative_hit:
        failure_type = "negative_skill_selected"
        failure_reason = "Selected skill set included a task negative skill."

    task_id = str(task["id"])
    return {
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "trace_id": f"{run_label}:{task_id}",
        "task_id": task_id,
        "prompt": str(task["prompt"]),
        "execution_condition": condition,
        "source_router": source_router,
        "source_results_path": routes_path,
        "selected_skill_ids": selected,
        "injected_guidance": selected,
        "agent_status": "passed" if agent_success else "failed",
        "agent_success": agent_success,
        "migration_source": task.get("migration_source"),
        "expected_evidence": expected_evidence,
        "migration_dimensions": migration_dimensions,
        "evidence_checks": evidence_checks,
        "dimension_scores": dimension_scores,
        "failure_type": failure_type,
        "failure_reason": failure_reason,
        "loop_steps": _loop_steps(condition, selected, agent_success),
        "artifacts": [
            f"agent-traces.jsonl#{task_id}",
            f"results.jsonl#{task_id}",
        ],
        "warnings": _warnings(route, selected, gold, negative),
    }


def _result_record(
    trace: dict[str, object],
    route: dict[str, object],
    task: dict[str, object],
    selected: list[str],
    run_label: str,
) -> dict[str, object]:
    gold = _string_list(task["gold_skills"], Path("<task>"), "gold_skills")
    negative = _string_list(task["negative_skills"], Path("<task>"), "negative_skills")
    scores = route.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    return {
        "task_id": task["id"],
        "category": task["category"],
        "difficulty": task["difficulty"],
        "split": task["split"],
        "prompt": task["prompt"],
        "robustness_tags": task["robustness_tags"],
        "router": run_label,
        "selected_skill_ids": selected,
        "scores": scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": 0.0,
        "recall_at_1": recall_at_k(selected, gold, 1),
        "recall_at_3": recall_at_k(selected, gold, 3),
        "recall_at_5": recall_at_k(selected, gold, 5),
        "precision_at_5": precision_at_k(selected, gold, 5),
        "mrr": mean_reciprocal_rank(selected, gold),
        "ndcg_at_5": ndcg_at_k(selected, gold, 5),
        "negative_hit_rate": negative_hit_rate(selected, negative, 5),
        "accepted_count": accepted_count(selected),
        "coverage": coverage(selected),
        "selection_rate_at_5": selection_rate_at_k(selected, 5),
        "abstention_rate": abstention_rate(selected),
        "accepted_recall_at_5": accepted_recall_at_k(selected, gold, 5),
        "negative_accepted_rate": negative_accepted_rate(selected, negative, 5),
        "trace_schema_version": trace["trace_schema_version"],
        "trace_id": trace["trace_id"],
        "execution_condition": trace["execution_condition"],
        "source_router": trace["source_router"],
        "source_results_path": trace["source_results_path"],
        "agent_status": trace["agent_status"],
        "agent_success": trace["agent_success"],
        "migration_source": trace["migration_source"],
        "expected_evidence": trace["expected_evidence"],
        "migration_dimensions": trace["migration_dimensions"],
        "evidence_checks": trace["evidence_checks"],
        "dimension_scores": trace["dimension_scores"],
        "failure_type": trace["failure_type"],
        "failure_reason": trace["failure_reason"],
        "loop_steps": trace["loop_steps"],
        "artifacts": trace["artifacts"],
        "warnings": trace["warnings"],
    }


def _loop_steps(condition: str, selected: list[str], success: bool) -> list[dict[str, object]]:
    return [
        {
            "step": "read_task",
            "status": "completed",
            "detail": "Loaded migration task prompt and expected evidence.",
        },
        {
            "step": "inject_guidance",
            "status": "completed" if selected else "skipped",
            "detail": f"{condition}: {', '.join(selected) if selected else 'no skill'}",
        },
        {
            "step": "simulate_execution",
            "status": "completed",
            "detail": "Evaluated deterministic evidence gates from selected skills.",
        },
        {
            "step": "final_handoff",
            "status": "completed" if success else "failed",
            "detail": "Produced evidence-complete handoff." if success else "Handoff failed evidence gates.",
        },
    ]


def _summary(
    run_label: str,
    source_router: str,
    condition: str,
    records: list[dict[str, object]],
) -> dict[str, object]:
    task_count = len(records)
    success_count = sum(1 for record in records if record["agent_success"] is True)
    evidence_rates = [
        _evidence_completion(record["evidence_checks"])
        for record in records
    ]
    return {
        "artifact_type": "phase10-agent-loop-summary",
        "phase": "Phase 10",
        "run_label": run_label,
        "source_router": source_router,
        "execution_condition": condition,
        "task_count": task_count,
        "agent_success_count": success_count,
        "agent_success_rate": round(success_count / task_count, 3) if task_count else 0.0,
        "mean_evidence_completion": round(sum(evidence_rates) / task_count, 3)
        if task_count
        else 0.0,
    }


def _report(summary: dict[str, object], records: list[dict[str, object]]) -> str:
    lines = [
        "# Phase 10 Agent-in-the-loop Report",
        "",
        f"- Run: {summary['run_label']}",
        f"- Source router: {summary['source_router']}",
        f"- Execution condition: {summary['execution_condition']}",
        f"- Tasks: {summary['task_count']}",
        f"- Agent success rate: {summary['agent_success_rate']:.3f}",
        f"- Mean evidence completion: {summary['mean_evidence_completion']:.3f}",
        "",
        "## Task Results",
        "",
        "| Task ID | Success | Selected Skills | Failure Type |",
        "| --- | --- | --- | --- |",
    ]
    for record in records:
        selected = ", ".join(
            _string_list(record["selected_skill_ids"], Path("<record>"), "selected_skill_ids")
        )
        lines.append(
            f"| {record['task_id']} | {record['agent_success']} | "
            f"{selected} | {record['failure_type'] or ''} |"
        )
    return "\n".join(lines) + "\n"


def _selected_for_condition(
    route: dict[str, object],
    task: dict[str, object],
    condition: str,
) -> list[str]:
    if condition == "no-skill":
        return []
    if condition == "oracle-skill":
        return list(_string_list(task["gold_skills"], Path("<task>"), "gold_skills"))
    return _string_list(route.get("selected_skill_ids"), Path("<routes>"), "selected_skill_ids")


def _source_router(routes: list[dict[str, object]]) -> str:
    routers = {
        router
        for route in routes
        if isinstance((router := route.get("router")), str) and router.strip()
    }
    if not routers:
        raise ValueError("route records must include router")
    if len(routers) > 1:
        return "mixed"
    return next(iter(routers))


def _default_run_label(condition: str, source_router: str) -> str:
    if condition == "routed-skill":
        return f"agent-loop-{source_router}"
    return f"agent-loop-{condition}-{source_router}"


def _validate_selected_skills(
    selected: list[str],
    skills: Mapping[str, object],
    task_id: str,
) -> None:
    missing = sorted(skill_id for skill_id in selected if skill_id not in skills)
    if missing:
        raise ValueError(
            f"{task_id} selected skill(s) missing from skills index: {', '.join(missing)}"
        )


def _warnings(
    route: dict[str, object],
    selected: list[str],
    gold: list[str],
    negative: list[str],
) -> list[str]:
    warnings: list[str] = []
    if not selected:
        warnings.append("no-skill-guidance")
    if not set(selected) & set(gold):
        warnings.append("missing-gold-skill")
    if set(selected[:5]) & set(negative):
        warnings.append("negative-skill-selected")
    if route.get("selected_skill_ids") != selected:
        warnings.append("condition-overrode-route-selection")
    return warnings


def _evidence_completion(value: object) -> float:
    if not isinstance(value, list) or not value:
        return 0.0
    satisfied = [
        check
        for check in value
        if isinstance(check, dict) and check.get("satisfied") is True
    ]
    return len(satisfied) / len(value)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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


def _required_string(value: object, path: Path, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} field {field} must be a non-empty string")
    return value


def _string_field(record: dict[str, object], field: str, path: Path) -> str:
    return _required_string(record.get(field), path, field)


def _string_list(value: object, path: Path, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path} field {field} must be a list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{path} field {field} must be a list of strings")
    return list(value)
