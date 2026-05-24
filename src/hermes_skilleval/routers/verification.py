from __future__ import annotations

import math
import re
from collections import Counter

from hermes_skilleval.models import BenchmarkTask, Skill


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def verification_score(task: BenchmarkTask, skill: Skill, base_score: float) -> float:
    query_terms = terms(f"{task.category} {task.prompt}")
    skill_terms = terms(skill_text(skill))
    lexical_score = weighted_overlap(query_terms, skill_terms)
    category_score = 100.0 if same_category(task, skill) else 0.0
    exact_id_score = 3.0 if prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return category_score + exact_id_score + lexical_score + base_score


def select_candidates(
    task: BenchmarkTask,
    ranked_candidates: list[Skill],
    scores: dict[str, float],
    *,
    min_confidence: float,
    contrastive_selective: bool,
    contrastive_margin: float,
    min_evidence: float,
) -> list[Skill]:
    accepted: list[Skill] = []
    accepted_evidence: dict[str, float] = {}
    for skill in ranked_candidates:
        if confidence(scores[skill.id]) < min_confidence:
            continue
        if contrastive_selective and accepted and same_category(task, skill):
            evidence = prompt_evidence_score(task, skill)
            same_category_evidence = [
                accepted_evidence[accepted_skill.id]
                for accepted_skill in accepted
                if same_category(task, accepted_skill)
            ]
            if same_category_evidence:
                best_evidence = max(same_category_evidence)
                if evidence < min_evidence:
                    continue
                if best_evidence - evidence > contrastive_margin:
                    continue
        accepted.append(skill)
        accepted_evidence[skill.id] = prompt_evidence_score(task, skill)
    return accepted


def prompt_evidence_score(task: BenchmarkTask, skill: Skill) -> float:
    query_terms = terms(task.prompt)
    skill_terms = terms(skill_text(skill))
    lexical_score = weighted_overlap(query_terms, skill_terms)
    exact_id_score = 3.0 if prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return lexical_score + exact_id_score


def confidence(score: float) -> float:
    return max(0.0, min(1.0, score / 100.0))


def task_text(task: BenchmarkTask) -> str:
    return " ".join([task.id.replace("-", " "), task.category, task.prompt])


def skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )


def terms(text: str) -> Counter[str]:
    return Counter(term.lower() for term in WORD_RE.findall(text) if len(term) >= 3)


def weighted_overlap(
    query_terms: Counter[str],
    skill_terms: Counter[str],
) -> float:
    if not query_terms or not skill_terms:
        return 0.0
    overlap = set(query_terms) & set(skill_terms)
    return sum(
        query_terms[term] * (1.0 + math.log1p(skill_terms[term]))
        for term in sorted(overlap)
    )


def same_category(task: BenchmarkTask, skill: Skill) -> bool:
    return (skill.category or "").casefold() == task.category.casefold()


def prompt_mentions_skill_id(prompt: str, skill_id: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(skill_id)}(?![A-Za-z0-9_-])"
    return re.search(pattern, prompt, flags=re.IGNORECASE) is not None
