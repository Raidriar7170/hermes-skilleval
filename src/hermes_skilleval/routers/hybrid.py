from __future__ import annotations

import re
import time

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.routers.keyword import KeywordRouter


class HybridRouter(KeywordRouter):
    name = "hybrid"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        started = time.perf_counter()
        result = super().route(task, skills, top_k)
        scores = dict(result.scores)
        query_text = router_query_text(task.prompt)
        for skill in skills:
            if _prompt_mentions_skill_id(query_text, skill.id):
                scores[skill.id] += 2.0

        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        selected = [skill.id for skill in ranked[:top_k]]
        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=result.task_id,
            router=self.name,
            selected_skill_ids=selected,
            scores=scores,
            latency_ms=latency_ms,
        )


def _prompt_mentions_skill_id(prompt: str, skill_id: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(skill_id)}(?![A-Za-z0-9_-])"
    return re.search(pattern, prompt, flags=re.IGNORECASE) is not None
