from __future__ import annotations

from abc import ABC, abstractmethod

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill


class SkillRouter(ABC):
    name: str

    @abstractmethod
    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        raise NotImplementedError
