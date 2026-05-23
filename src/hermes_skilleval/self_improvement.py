from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from hermes_skilleval.models import BenchmarkTask, Skill


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "behavior",
    "before",
    "from",
    "into",
    "tests",
    "through",
    "while",
    "with",
    "without",
    "write",
}
ACCEPTANCE_METRICS = (
    ("Recall@1", "recall_at_1", True),
    ("MRR", "mrr", True),
    ("NDCG@5", "ndcg_at_5", True),
    ("Negative Hit Rate", "negative_hit_rate", False),
)


@dataclass(frozen=True)
class SkillPatch:
    skill_id: str
    field: str
    before: list[str]
    after: list[str]
    reason: str
    source_task_ids: list[str]
    status: str = "proposed"


def propose_skill_patches(
    records: list[dict[str, Any]],
    skills: list[Skill],
    tasks: list[BenchmarkTask],
    *,
    max_terms_per_skill: int = 8,
) -> list[SkillPatch]:
    skill_by_id = {skill.id: skill for skill in skills}
    task_by_id = {task.id: task for task in tasks}
    terms_by_skill: dict[str, list[str]] = {}
    task_ids_by_skill: dict[str, list[str]] = {}

    for record in records:
        task_id = str(record["task_id"])
        task = task_by_id.get(task_id)
        if task is None:
            continue
        for skill_id in _target_gold_skills(record):
            skill = skill_by_id.get(skill_id)
            if skill is None:
                continue
            terms = terms_by_skill.setdefault(skill_id, [])
            for term in _prompt_terms(task, skill):
                if term not in terms:
                    terms.append(term)
                if len(terms) >= max_terms_per_skill:
                    break
            source_task_ids = task_ids_by_skill.setdefault(skill_id, [])
            if task_id not in source_task_ids:
                source_task_ids.append(task_id)

    patches = []
    for skill_id in sorted(terms_by_skill):
        skill = skill_by_id[skill_id]
        before = list(skill.trigger_terms)
        additions = [term for term in terms_by_skill[skill_id] if term not in before]
        if not additions:
            continue
        after = before + additions
        patches.append(
            SkillPatch(
                skill_id=skill_id,
                field="trigger_terms",
                before=before,
                after=after,
                reason=(
                    "Add prompt terms from failed routing task(s): "
                    + ", ".join(task_ids_by_skill[skill_id])
                ),
                source_task_ids=task_ids_by_skill[skill_id],
            )
        )
    return patches


def apply_skill_patches(skills: list[Skill], patches: list[SkillPatch]) -> list[Skill]:
    patch_by_skill = {patch.skill_id: patch for patch in patches}
    patched = []
    for skill in skills:
        patch = patch_by_skill.get(skill.id)
        if patch is None:
            patched.append(skill)
            continue
        if patch.field != "trigger_terms":
            raise ValueError(f"unsupported patch field: {patch.field}")
        patched.append(replace(skill, trigger_terms=list(patch.after)))
    return patched


def write_patches_json(patches: list[SkillPatch], output_path: Path | str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "patch_count": len(patches),
        "patches": [asdict(patch) for patch in patches],
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_patch_report(patches: list[SkillPatch], output_path: Path | str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Hermes SkillEval Self-Improvement Patches",
        "",
        f"- Patch count: {len(patches)}",
        "",
        "| Skill | Field | Status | Added Terms | Source Tasks |",
        "| --- | --- | --- | --- | --- |",
    ]
    if patches:
        for patch in patches:
            added = [term for term in patch.after if term not in patch.before]
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape(patch.skill_id),
                        _escape(patch.field),
                        _escape(patch.status),
                        _escape(", ".join(added)),
                        _escape(", ".join(patch.source_task_ids)),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| No patches |  |  |  |  |")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def write_acceptance_report(
    baseline_records: list[dict[str, Any]],
    candidate_records: list[dict[str, Any]],
    output_path: Path | str,
    *,
    baseline_name: str,
    candidate_name: str,
) -> str:
    status = _acceptance_status(baseline_records, candidate_records)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Hermes SkillEval Improvement Acceptance",
        "",
        f"- Baseline: `{baseline_name}`",
        f"- Candidate: `{candidate_name}`",
        f"- Status: {status}",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, field, higher_is_better in ACCEPTANCE_METRICS:
        baseline = _mean_metric(baseline_records, field)
        candidate = _mean_metric(candidate_records, field)
        delta = candidate - baseline
        if not higher_is_better:
            delta = -delta
        lines.append(
            f"| {label} | {_fmt(baseline)} | {_fmt(candidate)} | {_signed_fmt(delta)} |"
        )
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return status


def _acceptance_status(
    baseline_records: list[dict[str, Any]],
    candidate_records: list[dict[str, Any]],
) -> str:
    regressions = []
    improvements = []
    for _, field, higher_is_better in ACCEPTANCE_METRICS:
        baseline = _mean_metric(baseline_records, field)
        candidate = _mean_metric(candidate_records, field)
        if higher_is_better:
            regressions.append(candidate < baseline)
            improvements.append(candidate > baseline)
        else:
            regressions.append(candidate > baseline)
            improvements.append(candidate < baseline)
    return "accepted" if not any(regressions) and any(improvements) else "rejected"


def _mean_metric(records: list[dict[str, Any]], field: str) -> float:
    if not records:
        raise ValueError("records must not be empty")
    return sum(float(record[field]) for record in records) / len(records)


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def _signed_fmt(value: float) -> str:
    return f"{value:+.3f}"


def _target_gold_skills(record: dict[str, Any]) -> list[str]:
    selected = list(record["selected_skill_ids"])
    top5 = set(selected[:5])
    gold = list(record["gold_skills"])
    targets = []
    for skill_id in gold:
        top1_miss = not selected or selected[0] != skill_id
        missing_at_5 = skill_id not in top5
        if top1_miss or missing_at_5:
            targets.append(skill_id)
    return targets


def _prompt_terms(task: BenchmarkTask, skill: Skill) -> list[str]:
    existing = {term.casefold() for term in skill.trigger_terms}
    skill_tokens = set(_tokens(skill.id.replace("-", " ")))
    candidates = _tokens(f"{task.category} {task.id.replace('-', ' ')} {task.prompt}")
    terms = []
    for term in candidates:
        if term in STOPWORDS or term in existing or term in skill_tokens:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) >= 4
    ]


def _escape(value: object) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "\\|")
