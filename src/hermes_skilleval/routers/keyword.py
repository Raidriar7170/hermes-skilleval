from __future__ import annotations

import math
import re
import time
from collections import Counter

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.routers.base import SkillRouter


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class KeywordRouter(SkillRouter):
    name = "keyword"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")
        started = time.perf_counter()
        query_terms = _terms(router_query_text(task.prompt))
        scores = {skill.id: _score(query_terms, skill) for skill in skills}
        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        selected = [skill.id for skill in ranked[:top_k]]
        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=selected,
            scores=scores,
            latency_ms=latency_ms,
        )


def _terms(text: str) -> Counter[str]:
    return Counter(term.lower() for term in WORD_RE.findall(text) if len(term) >= 3)


def _score(query_terms: Counter[str], skill: Skill) -> float:
    skill_terms = _terms(
        " ".join(
            [
                skill.id.replace("-", " "),
                skill.name,
                skill.category or "",
                skill.description,
                " ".join(skill.trigger_terms),
                skill.body,
            ]
        )
    )
    if not query_terms or not skill_terms:
        return 0.0
    overlap = set(query_terms) & set(skill_terms)
    weighted_overlap = sum(
        query_terms[term] * (1.0 + math.log1p(skill_terms[term]))
        for term in sorted(overlap)
    )
    return weighted_overlap
