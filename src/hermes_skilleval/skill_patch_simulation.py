from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

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
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.skill_index import save_skill_index


METRIC_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
    "selection_rate_at_5",
)
ALIGNMENT_FIELDS = (
    "gold_skills",
    "negative_skills",
    "category",
    "difficulty",
    "split",
    "robustness_tags",
)


def read_ranked_patches(path: Path | str) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return sorted(records, key=lambda record: int(record.get("rank") or 10**9))


def apply_ranked_patch_candidates(
    skills: list[Skill],
    candidates: list[dict[str, Any]],
    *,
    max_patches: int | None = None,
) -> tuple[list[Skill], list[dict[str, Any]]]:
    by_id = {skill.id: _copy_skill(skill) for skill in skills}
    applied: list[dict[str, Any]] = []
    limit = len(candidates) if max_patches is None else max_patches
    for candidate in sorted(
        candidates,
        key=lambda record: int(record.get("rank") or 10**9),
    ):
        if len(applied) >= limit:
            break
        if candidate.get("status", "proposed") != "proposed":
            continue
        skill_id = str(candidate["target_skill_id"])
        if skill_id not in by_id:
            raise ValueError(f"patch target skill not found: {skill_id}")
        patched_skill = _apply_candidate(by_id[skill_id], candidate)
        if patched_skill == by_id[skill_id]:
            continue
        by_id[skill_id] = patched_skill
        applied.append(dict(candidate))
    return [by_id[skill.id] for skill in skills], applied


def _copy_skill(skill: Skill) -> Skill:
    return replace(skill, trigger_terms=list(skill.trigger_terms))


def _apply_candidate(skill: Skill, candidate: dict[str, Any]) -> Skill:
    field = str(candidate["patch_field"])
    operation = str(candidate["operation"])
    if field == "trigger_terms" and operation == "append_terms":
        terms = list(skill.trigger_terms)
        for term in candidate.get("added_terms", []):
            value = str(term)
            if value and value not in terms:
                terms.append(value)
        return replace(skill, trigger_terms=terms)
    if field == "description" and operation == "append_sentence":
        text = str(candidate.get("added_text") or "").strip()
        return replace(skill, description=_append_text(skill.description, text))
    if field == "body" and operation == "append_section_note":
        text = str(candidate.get("added_text") or "").strip()
        return replace(skill, body=_append_text(skill.body, text))
    raise ValueError(f"unsupported patch candidate: {field}/{operation}")


def _append_text(before: str, addition: str) -> str:
    if not addition or addition in before:
        return before
    return f"{before.rstrip()} {addition}".strip()


def compare_route_records(
    baseline_records: list[dict[str, Any]],
    shadow_records: list[dict[str, Any]],
    *,
    applied_by_task: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    _reject_duplicate_task_ids(baseline_records, "baseline")
    _reject_duplicate_task_ids(shadow_records, "shadow")
    baseline_by_task = {str(record["task_id"]): record for record in baseline_records}
    shadow_by_task = {str(record["task_id"]): record for record in shadow_records}
    if set(baseline_by_task) != set(shadow_by_task):
        missing = sorted(set(baseline_by_task) ^ set(shadow_by_task))
        raise ValueError(f"baseline and shadow task ids differ: {', '.join(missing)}")
    applied_by_task = applied_by_task or {}
    return [
        _route_diff(
            baseline_by_task[task_id],
            shadow_by_task[task_id],
            applied_by_task.get(task_id, []),
        )
        for task_id in sorted(baseline_by_task)
    ]


def _reject_duplicate_task_ids(records: list[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        task_id = str(record["task_id"])
        if task_id in seen and task_id not in duplicates:
            duplicates.append(task_id)
        seen.add(task_id)
    if duplicates:
        raise ValueError(
            f"{label} records contain duplicate task ids: {', '.join(duplicates)}"
        )


def _route_diff(
    baseline: dict[str, Any],
    shadow: dict[str, Any],
    applied_candidate_ids: list[str],
) -> dict[str, Any]:
    _validate_alignment(baseline, shadow)
    before_metrics = {field: float(baseline[field]) for field in METRIC_FIELDS}
    after_metrics = {field: float(shadow[field]) for field in METRIC_FIELDS}
    metric_deltas = {
        field: round(after_metrics[field] - before_metrics[field], 6)
        for field in METRIC_FIELDS
    }
    before_selected = list(baseline["selected_skill_ids"])
    after_selected = list(shadow["selected_skill_ids"])
    negative = set(baseline["negative_skills"])
    before_negative = set(before_selected) & negative
    after_negative = set(after_selected) & negative
    regressions = []
    improvements = []
    for field in ("recall_at_5", "mrr", "ndcg_at_5"):
        if after_metrics[field] < before_metrics[field]:
            regressions.append(f"{field}_decreased")
        if after_metrics[field] > before_metrics[field]:
            improvements.append(f"{field}_increased")
    for field in ("negative_hit_rate", "negative_accepted_rate"):
        if after_metrics[field] > before_metrics[field]:
            regressions.append(f"{field}_increased")
        if after_metrics[field] < before_metrics[field]:
            improvements.append(f"{field}_decreased")
    if after_negative - before_negative:
        regressions.append("new_negative_skill_selected")
    if before_negative - after_negative:
        improvements.append("removed_negative_skill")
    return {
        "task_id": baseline["task_id"],
        "before_selected_skill_ids": before_selected,
        "after_selected_skill_ids": after_selected,
        "gold_skills": list(baseline["gold_skills"]),
        "negative_skills": list(baseline["negative_skills"]),
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "metric_deltas": metric_deltas,
        "selection_changed": before_selected != after_selected,
        "regression_flags": regressions,
        "improvement_flags": improvements,
        "applied_candidate_ids": applied_candidate_ids,
    }


def _validate_alignment(baseline: dict[str, Any], shadow: dict[str, Any]) -> None:
    task_id = str(baseline["task_id"])
    for field in ALIGNMENT_FIELDS:
        if field not in baseline or field not in shadow:
            raise ValueError(f"baseline and shadow records must include {field}")
        if baseline.get(field) != shadow.get(field):
            raise ValueError(f"baseline and shadow {field} differ for task {task_id}")


def simulate_skill_patches(
    *,
    ranked_patches: list[dict[str, Any]],
    baseline_records_path: Path | str,
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    router: SkillRouter,
    router_label: str,
    top_k: int,
    output_dir: Path | str,
    max_patches: int | None = None,
    input_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if max_patches is not None and max_patches <= 0:
        raise ValueError("max_patches must be positive")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    shadow_skills, applied = apply_ranked_patch_candidates(
        skills,
        ranked_patches,
        max_patches=max_patches,
    )
    baseline_records = _read_jsonl(baseline_records_path)
    shadow_records = [
        _route_record(task, router.route(task, shadow_skills, top_k), router_label)
        for task in tasks
    ]
    diffs = compare_route_records(
        baseline_records,
        shadow_records,
        applied_by_task=_applied_by_task(applied),
    )
    summary = _summary(
        baseline_records,
        shadow_records,
        diffs,
        applied,
        router_label=router_label,
        top_k=top_k,
        input_paths=input_paths or {},
    )

    save_skill_index(shadow_skills, output / "shadow-skills.json")
    _write_jsonl(output / "shadow-results.jsonl", shadow_records)
    _write_jsonl(output / "route-diffs.jsonl", diffs)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "regression-report.md").write_text(
        _report(summary, diffs),
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


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _route_record(
    task: BenchmarkTask,
    result: RouteResult,
    router_label: str,
) -> dict[str, Any]:
    selected = result.selected_skill_ids
    gold = task.gold_skills
    negative = task.negative_skills
    return {
        "task_id": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "split": task.split,
        "robustness_tags": task.robustness_tags,
        "router": router_label,
        "selected_skill_ids": selected,
        "scores": result.scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": result.latency_ms,
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
    }


def _applied_by_task(applied: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_task: dict[str, list[str]] = {}
    for candidate in applied:
        task_id = str(candidate.get("source_task_id", ""))
        if not task_id:
            continue
        by_task.setdefault(task_id, []).append(str(candidate["candidate_id"]))
    return by_task


def _summary(
    baseline_records: list[dict[str, Any]],
    shadow_records: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
    applied: list[dict[str, Any]],
    *,
    router_label: str,
    top_k: int,
    input_paths: dict[str, str],
) -> dict[str, Any]:
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    selection_changed_count = sum(1 for diff in diffs if diff["selection_changed"])
    baseline_metrics = _mean_metrics(baseline_records)
    shadow_metrics = _mean_metrics(shadow_records)
    metric_deltas = {
        field: round(shadow_metrics[field] - baseline_metrics[field], 6)
        for field in METRIC_FIELDS
    }
    patched_skill_ids = sorted(
        {str(candidate["target_skill_id"]) for candidate in applied}
    )
    applied_candidate_ids = [str(candidate["candidate_id"]) for candidate in applied]
    return {
        "phase": "Phase 13",
        "artifact_type": "phase13-patch-simulation",
        "router_label": router_label,
        "top_k": top_k,
        "task_count": len(shadow_records),
        "applied_candidate_count": len(applied),
        "applied_candidate_ids": applied_candidate_ids,
        "patched_skill_ids": patched_skill_ids,
        "selection_changed_count": selection_changed_count,
        "regression_count": regression_count,
        "improvement_count": improvement_count,
        "guard_status": "PASS" if regression_count == 0 else "REVIEW_REQUIRED",
        "baseline_mean_metrics": baseline_metrics,
        "shadow_mean_metrics": shadow_metrics,
        "metric_deltas": metric_deltas,
        "input_paths": input_paths,
        "source_mutation": "none; source SKILL.md files are not modified",
        "original_skills_index_mutation": "none; original skills.json is not overwritten",
    }


def _mean_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    if not records:
        return {field: 0.0 for field in METRIC_FIELDS}
    return {
        field: round(
            sum(float(record[field]) for record in records) / len(records),
            6,
        )
        for field in METRIC_FIELDS
    }


def _report(summary: dict[str, Any], diffs: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 13 Patch Simulation",
        "",
        "Offline deterministic patch simulation applies ranked metadata candidates "
        "to a shadow skill index and compares routing results against a baseline.",
        "",
        "## Guard Summary",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Guard status | {summary['guard_status']} |",
        f"| Tasks | {summary['task_count']} |",
        f"| Applied candidates | {summary['applied_candidate_count']} |",
        f"| Patched skills | {', '.join(summary['patched_skill_ids']) or '-'} |",
        f"| Selection changes | {summary['selection_changed_count']} |",
        f"| Tasks with regressions | {summary['regression_count']} |",
        f"| Tasks with improvements | {summary['improvement_count']} |",
        "",
        "## Mean Metric Deltas",
        "",
        "| Metric | Baseline | Shadow | Delta |",
        "|---|---:|---:|---:|",
    ]
    for field in METRIC_FIELDS:
        lines.append(
            "| "
            f"{field} | "
            f"{summary['baseline_mean_metrics'][field]:.6f} | "
            f"{summary['shadow_mean_metrics'][field]:.6f} | "
            f"{summary['metric_deltas'][field]:+.6f} |"
        )

    flagged = [
        diff
        for diff in diffs
        if diff["regression_flags"] or diff["improvement_flags"] or diff["selection_changed"]
    ]
    lines.extend(["", "## Route Diffs", ""])
    if not flagged:
        lines.append("No route changes or guard flags were observed.")
    else:
        lines.extend(
            [
                "| Task | Selection Changed | Regression Flags | Improvement Flags | "
                "Before Selected | After Selected | Applied Candidates |",
                "|---|:-:|---|---|---|---|---|",
            ]
        )
        for diff in flagged:
            regression_flags = ", ".join(diff["regression_flags"]) or "-"
            improvement_flags = ", ".join(diff["improvement_flags"]) or "-"
            before_selected = ", ".join(diff["before_selected_skill_ids"]) or "-"
            after_selected = ", ".join(diff["after_selected_skill_ids"]) or "-"
            applied_candidates = ", ".join(diff["applied_candidate_ids"]) or "-"
            lines.append(
                "| "
                f"{diff['task_id']} | "
                f"{diff['selection_changed']} | "
                f"{regression_flags} | "
                f"{improvement_flags} | "
                f"{before_selected} | "
                f"{after_selected} | "
                f"{applied_candidates} |"
            )

    lines.extend(
        [
            "",
            "## Mutation Boundary",
            "",
            "- Source `SKILL.md` files are not modified.",
            "- The original `skills.json` input is not overwritten.",
            "- `after_excerpt` is display-only and is not used as patch source.",
            "",
        ]
    )
    return "\n".join(lines)
