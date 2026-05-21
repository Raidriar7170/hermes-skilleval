from __future__ import annotations

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter


class EmbeddingRouter(SkillRouter):
    name = "embedding"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        raise RuntimeError(
            "embedding router requires optional embedding dependencies; use keyword or hybrid for the offline MVP"
        )
