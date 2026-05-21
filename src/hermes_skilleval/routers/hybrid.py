from __future__ import annotations

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.keyword import KeywordRouter


class HybridRouter(KeywordRouter):
    name = "hybrid"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        result = super().route(task, skills, top_k)
        scores = dict(result.scores)
        for skill in skills:
            if skill.category == task.category:
                scores[skill.id] += 1.0
            if skill.id in task.prompt:
                scores[skill.id] += 2.0

        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        selected = [skill.id for skill in ranked[:top_k]]
        return RouteResult(
            task_id=result.task_id,
            router=self.name,
            selected_skill_ids=selected,
            scores=scores,
            latency_ms=result.latency_ms,
        )
