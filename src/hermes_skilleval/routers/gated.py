from __future__ import annotations

import time

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.embedding import EmbeddingRouter
from hermes_skilleval.routers.verification import (
    select_candidates,
    verification_score,
)


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
            skill.id: verification_score(
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
            ranked_candidates = select_candidates(
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
