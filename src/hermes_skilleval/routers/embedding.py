from __future__ import annotations

import hashlib
import math
import re
import time
from collections.abc import Iterable

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class HashingEmbeddingModel:
    """Small deterministic embedding model for offline routing experiments."""

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def encode(self, text: str) -> dict[int, float]:
        vector: dict[int, float] = {}
        for feature in _features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] = vector.get(bucket, 0.0) + sign
        return _normalize(vector)


class EmbeddingRouter(SkillRouter):
    name = "embedding"

    def __init__(self, model: HashingEmbeddingModel | None = None) -> None:
        self.model = model or HashingEmbeddingModel()

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")

        started = time.perf_counter()
        query = self.model.encode(_task_text(task))
        scores = {
            skill.id: _cosine(query, self.model.encode(_skill_text(skill)))
            for skill in skills
        }
        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=[skill.id for skill in ranked[:top_k]],
            scores=scores,
            latency_ms=latency_ms,
        )


def _task_text(task: BenchmarkTask) -> str:
    return " ".join([task.id.replace("-", " "), task.category, task.prompt])


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


def _features(text: str) -> Iterable[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    for token in tokens:
        if len(token) >= 3:
            yield f"tok:{token}"
    for left, right in zip(tokens, tokens[1:], strict=False):
        if len(left) >= 3 and len(right) >= 3:
            yield f"bi:{left}:{right}"


def _normalize(vector: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return {}
    return {index: value / norm for index, value in vector.items()}


def _cosine(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(index, 0.0) for index, value in left.items())
