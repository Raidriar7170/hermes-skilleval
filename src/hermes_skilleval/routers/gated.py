from __future__ import annotations

import math
import re
import time
from collections import Counter

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.embedding import EmbeddingRouter


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class VerificationGatedRouter(SkillRouter):
    """Rerank embedding candidates with lightweight verifier-style evidence."""

    name = "gated"

    def __init__(
        self,
        base_router: SkillRouter | None = None,
        candidate_pool_size: int = 10,
        selective: bool = False,
        min_confidence: float = 0.5,
    ) -> None:
        if candidate_pool_size <= 0:
            raise ValueError("candidate_pool_size must be positive")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        self.base_router = base_router or EmbeddingRouter()
        self.candidate_pool_size = candidate_pool_size
        self.selective = selective
        self.min_confidence = min_confidence

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")

        started = time.perf_counter()
        candidate_k = min(len(skills), max(top_k, self.candidate_pool_size))
        base_result = self.base_router.route(task, skills, candidate_k)
        skill_by_id = {skill.id: skill for skill in skills}
        candidate_ids = [
            skill_id
            for skill_id in base_result.selected_skill_ids
            if skill_id in skill_by_id
        ]
        if not candidate_ids:
            candidate_ids = [skill.id for skill in skills[:candidate_k]]

        base_rank = {skill_id: index for index, skill_id in enumerate(candidate_ids)}
        scores = {
            skill.id: _verification_score(
                task,
                skill,
                float(base_result.scores.get(skill.id, 0.0)),
            )
            for skill in skills
        }
        ranked_candidates = sorted(
            (skill_by_id[skill_id] for skill_id in candidate_ids),
            key=lambda skill: (
                -scores[skill.id],
                base_rank[skill.id],
                skill.id,
            ),
        )
        if self.selective:
            ranked_candidates = [
                skill
                for skill in ranked_candidates
                if _confidence(scores[skill.id]) >= self.min_confidence
            ]

        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=[skill.id for skill in ranked_candidates[:top_k]],
            scores=scores,
            latency_ms=latency_ms,
        )


def _verification_score(
    task: BenchmarkTask,
    skill: Skill,
    base_score: float,
) -> float:
    query_terms = _terms(f"{task.category} {task.prompt}")
    skill_terms = _terms(_skill_text(skill))
    lexical_score = _weighted_overlap(query_terms, skill_terms)
    category_score = 100.0 if _same_category(task, skill) else 0.0
    exact_id_score = 3.0 if _prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return category_score + exact_id_score + lexical_score + base_score


def _confidence(score: float) -> float:
    return max(0.0, min(1.0, score / 100.0))


def _terms(text: str) -> Counter[str]:
    return Counter(term.lower() for term in WORD_RE.findall(text) if len(term) >= 3)


def _weighted_overlap(
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


def _skill_text(skill: Skill) -> str:
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


def _same_category(task: BenchmarkTask, skill: Skill) -> bool:
    return (skill.category or "").casefold() == task.category.casefold()


def _prompt_mentions_skill_id(prompt: str, skill_id: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(skill_id)}(?![A-Za-z0-9_-])"
    return re.search(pattern, prompt, flags=re.IGNORECASE) is not None
