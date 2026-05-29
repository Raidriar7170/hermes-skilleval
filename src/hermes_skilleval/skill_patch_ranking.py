from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.models import Skill
from hermes_skilleval.skill_index import load_skill_index


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SCORING_WEIGHTS = {
    "gold_boost": 0.35,
    "negative_separation": 0.25,
    "minimality": 0.15,
    "field_safety": 0.10,
    "source_support": 0.15,
}
FIELD_SAFETY = {"trigger_terms": 1.0, "description": 0.75, "body": 0.55}


def rank_skill_patches(
    *,
    judge_results_path: Path | str,
    routes_path: Path | str,
    tasks_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
) -> dict[str, object]:
    judge_records = _read_jsonl(Path(judge_results_path))
    routes = {str(record["task_id"]): record for record in _read_jsonl(Path(routes_path))}
    tasks = _load_tasks(Path(tasks_path))
    skills = {skill.id: skill for skill in load_skill_index(skills_index_path)}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    failures = [
        _failure_input(record, routes, tasks, skills)
        for record in judge_records
        if record.get("judge_pass") is not True
    ]
    candidates: list[dict[str, object]] = []
    for failure in failures:
        candidates.extend(_candidates_for_failure(failure))
    ranked = _rank_candidates(candidates)

    _write_jsonl(output / "patch-candidates.jsonl", candidates)
    _write_jsonl(output / "ranked-patches.jsonl", ranked)
    summary = _summary(
        failures=failures,
        candidates=ranked,
        judge_results_path=str(judge_results_path),
        routes_path=str(routes_path),
        tasks_path=str(tasks_path),
        skills_index_path=str(skills_index_path),
    )
    (output / "ranking-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "ranked-patches.md").write_text(_report(summary, ranked), encoding="utf-8")
    return summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _load_tasks(root: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for task_yaml in sorted(root.glob("*/task.yaml")):
        payload = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"task metadata must be an object: {task_yaml}")
        task_id = str(payload.get("id") or task_yaml.parent.name)
        prompt_path = task_yaml.parent / "prompt.md"
        tasks[task_id] = {
            "id": task_id,
            "gold_skills": list(payload.get("gold_skills", [])),
            "negative_skills": list(payload.get("negative_skills", [])),
            "expected_evidence": list(payload.get("expected_evidence", [])),
            "migration_dimensions": list(payload.get("migration_dimensions", [])),
            "prompt": prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "",
        }
    return tasks


def _failure_input(
    record: dict[str, Any],
    routes: dict[str, dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    skills: dict[str, Skill],
) -> dict[str, Any]:
    task_id = str(record.get("task_id"))
    if task_id not in routes:
        raise ValueError(f"missing Phase 9 route for failed task: {task_id}")
    if task_id not in tasks:
        raise ValueError(f"missing migration task metadata for failed task: {task_id}")

    route = routes[task_id]
    task = tasks[task_id]
    gold_skills = list(route.get("gold_skills") or task.get("gold_skills") or [])
    negative_skills = list(route.get("negative_skills") or task.get("negative_skills") or [])
    selected_skills = list(route.get("selected_skill_ids", []))
    missing_skills = [skill_id for skill_id in gold_skills if skill_id not in skills]
    if missing_skills:
        raise ValueError(
            f"missing migrated skill index entries for {task_id}: "
            f"{', '.join(missing_skills)}"
        )

    demote_skill_ids = [
        skill_id for skill_id in selected_skills if skill_id in set(negative_skills)
    ]
    return {
        "judge_record": record,
        "route": route,
        "task": task,
        "skills": skills,
        "task_id": task_id,
        "gold_skill_ids": gold_skills,
        "negative_skill_ids": negative_skills,
        "selected_skill_ids": selected_skills,
        "demote_skill_ids": demote_skill_ids,
        "failure_type": record.get("failure_type"),
        "expected_evidence": list(
            record.get("expected_evidence") or task.get("expected_evidence") or []
        ),
    }


def _candidates_for_failure(failure: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    terms = _source_terms(failure)
    evidence_text = ", ".join(failure["expected_evidence"])  # type: ignore[index]
    dimensions_text = ", ".join(failure["task"]["migration_dimensions"])  # type: ignore[index]
    for skill_id in failure["gold_skill_ids"]:  # type: ignore[index]
        candidates.append(
            _candidate(
                failure,
                str(skill_id),
                "trigger_terms",
                "append_terms",
                terms[:6],
                "",
            )
        )
        candidates.append(
            _candidate(
                failure,
                str(skill_id),
                "description",
                "append_sentence",
                terms[:4],
                f"Strengthen metadata for {evidence_text} evidence on this task family.",
            )
        )
        candidates.append(
            _candidate(
                failure,
                str(skill_id),
                "body",
                "append_section_note",
                terms[:4],
                "Offline patch note: emphasize "
                f"{evidence_text} from {dimensions_text or 'migration evidence'}.",
            )
        )
    return candidates


def _candidate(
    failure: dict[str, Any],
    skill_id: str,
    patch_field: str,
    operation: str,
    added_terms: list[str],
    added_text: str,
) -> dict[str, Any]:
    skill = failure["skills"][skill_id]
    before = _field_excerpt(skill, patch_field)
    after = _after_excerpt(before, patch_field, added_terms, added_text)
    candidate = {
        "candidate_id": (
            f"{failure['task_id']}::{skill_id}::{patch_field}::{operation}"
        ),
        "source_task_id": failure["task_id"],
        "target_skill_id": skill_id,
        "patch_field": patch_field,
        "operation": operation,
        "before_excerpt": before,
        "after_excerpt": after,
        "added_terms": added_terms,
        "added_text": added_text,
        "demote_skill_ids": failure["demote_skill_ids"],
        "rationale": (
            "Offline deterministic metadata patch candidate for a "
            f"{failure['failure_type']} judge failure."
        ),
        "evidence_inputs": {
            "trace_id": failure["judge_record"].get("trace_id"),
            "expected_evidence": failure["expected_evidence"],
            "migration_dimensions": failure["task"]["migration_dimensions"],
            "prompt_terms": _tokens(str(failure["task"]["prompt"]))[:12],
            "route_score": failure["route"].get("scores", {}).get(skill_id),
        },
        "deterministic_scores": {},
        "total_score": 0.0,
        "rank": None,
        "status": "proposed",
    }
    scores = _score_candidate(candidate, failure)
    candidate["deterministic_scores"] = scores
    candidate["total_score"] = round(
        sum(scores[name] * weight for name, weight in SCORING_WEIGHTS.items()),
        6,
    )
    return candidate


def _rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        (dict(candidate) for candidate in candidates),
        key=lambda candidate: (
            -float(candidate["total_score"]),
            str(candidate["source_task_id"]),
            str(candidate["target_skill_id"]),
            str(candidate["patch_field"]),
        ),
    )
    for index, candidate in enumerate(ranked, start=1):
        candidate["rank"] = index
    return ranked


def _score_candidate(
    candidate: dict[str, Any],
    failure: dict[str, Any],
) -> dict[str, float]:
    added_terms = list(candidate["added_terms"])
    prompt_terms = set(_tokens(str(failure["task"]["prompt"])))
    evidence_terms = set(
        _tokens(" ".join(str(item) for item in failure["expected_evidence"]))
    )
    source_terms = prompt_terms | evidence_terms
    support_hits = sum(1 for term in added_terms if term in source_terms)
    selected = set(failure["selected_skill_ids"])
    demoted = set(failure["demote_skill_ids"])
    gold_boost = 1.0 if candidate["target_skill_id"] in selected else 0.75
    negative_separation = min(1.0, len(demoted) / max(1, len(selected)))
    minimality = 1.0 - min(0.8, max(0, len(added_terms) - 4) * 0.1)
    return {
        "gold_boost": gold_boost,
        "negative_separation": negative_separation,
        "minimality": minimality,
        "field_safety": FIELD_SAFETY[str(candidate["patch_field"])],
        "source_support": support_hits / max(1, len(added_terms)),
    }


def _tokens(text: str) -> list[str]:
    seen = set()
    terms = []
    for match in TOKEN_RE.finditer(text.lower()):
        token = match.group(0).strip("_-")
        if len(token) < 4 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _summary(
    *,
    failures: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judge_results_path: str,
    routes_path: str,
    tasks_path: str,
    skills_index_path: str,
) -> dict[str, object]:
    return {
        "phase": "Phase 12",
        "artifact_type": "phase12-skill-patch-ranking",
        "method": "offline deterministic metadata patch ranking",
        "failed_task_count": len(failures),
        "failure_types": sorted(
            {str(failure["failure_type"]) for failure in failures if failure["failure_type"]}
        ),
        "candidate_count": len(candidates),
        "top_candidate_ids": [
            str(candidate["candidate_id"]) for candidate in candidates[:5]
        ],
        "input_paths": {
            "judge_results": judge_results_path,
            "routes": routes_path,
            "tasks": tasks_path,
            "skills_index": skills_index_path,
        },
        "scoring_weights": SCORING_WEIGHTS,
        "source_mutation": "none; source SKILL.md files are not modified",
    }


def _report(summary: dict[str, object], ranked: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 12 Skill Patch Ranking",
        "",
        "This report ranks offline deterministic metadata patch candidates.",
        "It does not modify source SKILL.md files or write a patched skills index.",
        "",
        "| Rank | Candidate | Task | Target Skill | Field | Score | Demote Skills |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for candidate in ranked:
        demote = ", ".join(str(item) for item in candidate["demote_skill_ids"])
        lines.append(
            "| {rank} | `{candidate_id}` | {task} | `{skill}` | {field} | "
            "{score:.6f} | {demote} |".format(
                rank=candidate["rank"],
                candidate_id=candidate["candidate_id"],
                task=candidate["source_task_id"],
                skill=candidate["target_skill_id"],
                field=candidate["patch_field"],
                score=float(candidate["total_score"]),
                demote=demote,
            )
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Failed tasks: {summary['failed_task_count']}",
            f"- Candidates: {summary['candidate_count']}",
            "- Source mutation: none",
            "",
        ]
    )
    return "\n".join(lines)


def _source_terms(failure: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(failure["task"]["prompt"]),
            " ".join(str(item) for item in failure["expected_evidence"]),
            " ".join(str(item) for item in failure["task"]["migration_dimensions"]),
        ]
    )
    return _tokens(text)


def _field_excerpt(skill: Skill, patch_field: str) -> str:
    if patch_field == "trigger_terms":
        return ", ".join(skill.trigger_terms[:12])
    return str(getattr(skill, patch_field))[:240]


def _after_excerpt(
    before: str,
    patch_field: str,
    added_terms: list[str],
    added_text: str,
) -> str:
    if patch_field == "trigger_terms":
        additions = ", ".join(term for term in added_terms if term not in before)
        return ", ".join(part for part in [before, additions] if part)
    return " ".join(part for part in [before, added_text] if part)[:360]
