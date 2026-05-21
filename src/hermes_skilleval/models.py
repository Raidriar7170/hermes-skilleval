from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    path: str
    category: str | None
    description: str
    body: str
    trigger_terms: list[str]
    token_count_estimate: int


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    category: str
    difficulty: str
    prompt: str
    gold_skills: list[str]
    negative_skills: list[str]
    verifier: str


@dataclass(frozen=True)
class RouteResult:
    task_id: str
    router: str
    selected_skill_ids: list[str]
    scores: dict[str, float]
    latency_ms: float


@dataclass(frozen=True)
class EvalRun:
    task: BenchmarkTask
    result: RouteResult
    warnings: list[str]


@dataclass(frozen=True)
class MetricSummary:
    router: str
    task_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_5: float
    mrr: float
    ndcg_at_5: float
    negative_hit_rate: float
    average_latency_ms: float
