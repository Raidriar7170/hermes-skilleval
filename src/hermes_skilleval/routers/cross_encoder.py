from __future__ import annotations

import math
import time
from collections.abc import Iterable
from typing import Protocol

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.embedding import EmbeddingDependencyError, EmbeddingRouter
from hermes_skilleval.routers.verification import (
    select_candidates,
    skill_text,
    task_text,
)


class CrossEncoderModel(Protocol):
    cache_key: str

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        raise NotImplementedError


class SentenceTransformerCrossEncoderModel:
    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        if batch_size <= 0:
            raise ValueError("cross_encoder_batch_size must be positive")
        try:
            from sentence_transformers import CrossEncoder
        except (ImportError, ModuleNotFoundError) as exc:
            raise EmbeddingDependencyError(
                "sentence-transformers cross-encoder backend requires optional "
                "dependency; install with: python -m pip install -e "
                '".[embedding]"'
            ) from exc

        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_key = f"sentence-transformers-cross-encoder:{model_name}"
        self.model = CrossEncoder(model_name)

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        pair_list = list(pairs)
        scores = self.model.predict(pair_list, batch_size=self.batch_size)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        return [float(score) for score in scores]


class StaticCrossEncoderModel:
    def __init__(
        self,
        scores: dict[tuple[str, str], float] | None = None,
        default_score: float = 0.0,
    ) -> None:
        self.scores = scores or {}
        self.default_score = default_score
        self.cache_key = "static-cross-encoder"

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        return [float(self.scores.get(pair, self.default_score)) for pair in pairs]


class CrossEncoderReranker(SkillRouter):
    name = "cross-encoder"

    def __init__(
        self,
        base_router: SkillRouter | None = None,
        model: CrossEncoderModel | None = None,
        candidate_pool_size: int = 10,
        selective: bool = False,
        min_confidence: float = 0.5,
        contrastive_selective: bool = False,
        contrastive_margin: float = 6.0,
        min_evidence: float = 2.0,
        cross_encoder_batch_size: int = 16,
    ) -> None:
        if candidate_pool_size <= 0:
            raise ValueError("candidate_pool_size must be positive")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if contrastive_margin < 0.0:
            raise ValueError("contrastive_margin must be non-negative")
        if min_evidence < 0.0:
            raise ValueError("min_evidence must be non-negative")
        if cross_encoder_batch_size <= 0:
            raise ValueError("cross_encoder_batch_size must be positive")

        self.base_router = base_router or EmbeddingRouter()
        self.model = model or SentenceTransformerCrossEncoderModel(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            batch_size=cross_encoder_batch_size,
        )
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

        candidates = [skill_by_id[skill_id] for skill_id in candidate_ids]
        query_text = task_text(task)
        pair_scores = self.model.score_pairs(
            (query_text, skill_text(skill)) for skill in candidates
        )
        if len(pair_scores) != len(candidates):
            raise ValueError("cross-encoder returned a mismatched number of scores")

        scores = {skill.id: -1_000_000.0 for skill in skills}
        for skill, score in zip(candidates, pair_scores, strict=True):
            scores[skill.id] = float(score)

        base_rank = {skill_id: index for index, skill_id in enumerate(candidate_ids)}
        ranked_candidates = sorted(
            candidates,
            key=lambda skill: (-scores[skill.id], base_rank[skill.id], skill.id),
        )
        if self.selective:
            ranked_candidates = select_candidates(
                task,
                ranked_candidates,
                _acceptance_scores(scores),
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


def _acceptance_scores(scores: dict[str, float]) -> dict[str, float]:
    return {skill_id: _sigmoid(score) * 100.0 for skill_id, score in scores.items()}


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)
