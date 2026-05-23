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
        contrastive_selective: bool = False,
        contrastive_margin: float = 6.0,
        min_evidence: float = 2.0,
    ) -> None:
        if candidate_pool_size <= 0:
            raise ValueError("candidate_pool_size must be positive")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if contrastive_margin < 0.0:
            raise ValueError("contrastive_margin must be non-negative")
        if min_evidence < 0.0:
            raise ValueError("min_evidence must be non-negative")
        self.base_router = base_router or EmbeddingRouter()
        self.candidate_pool_size = candidate_pool_size
        self.selective = selective
        self.min_confidence = min_confidence
        self.contrastive_selective = contrastive_selective
        self.contrastive_margin = contrastive_margin
        self.min_evidence = min_evidence

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
            ranked_candidates = _select_candidates(
                task,
                ranked_candidates,
                scores,
                min_confidence=self.min_confidence,
                contrastive_selective=self.contrastive_selective,
                contrastive_margin=self.contrastive_margin,
                min_evidence=self.min_evidence,
            )

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


def _select_candidates(
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
        if _confidence(scores[skill.id]) < min_confidence:
            continue
        if contrastive_selective and accepted and _same_category(task, skill):
            evidence = _prompt_evidence_score(task, skill)
            same_category_evidence = [
                accepted_evidence[accepted_skill.id]
                for accepted_skill in accepted
                if _same_category(task, accepted_skill)
            ]
            if same_category_evidence:
                best_evidence = max(same_category_evidence)
                if evidence < min_evidence:
                    continue
                if best_evidence - evidence > contrastive_margin:
                    continue
        accepted.append(skill)
        accepted_evidence[skill.id] = _prompt_evidence_score(task, skill)
    return accepted


def _prompt_evidence_score(task: BenchmarkTask, skill: Skill) -> float:
    query_terms = _terms(task.prompt)
    skill_terms = _terms(_skill_text(skill))
    lexical_score = _weighted_overlap(query_terms, skill_terms)
    exact_id_score = 3.0 if _prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return lexical_score + exact_id_score


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
