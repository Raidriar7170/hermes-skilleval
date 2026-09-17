"""Exact finite-pool proxy optimization; no monotone approximation claim."""

import math
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Budget:
    tokens: int = 4000
    max_k: int = 4
    alpha: float = 0.25
    beta: float = 0.2
    gamma: float = 0.1

    def __post_init__(self):
        if self.tokens <= 0 or not 0 <= self.max_k <= 6:
            raise ValueError("invalid selection budget")
        if any(
            not math.isfinite(v) or v < 0 for v in (self.alpha, self.beta, self.gamma)
        ):
            raise ValueError("invalid objective weights")


def objective(subset, weights, budget):
    coverage = sum(
        w * max((s["support"][j] for s in subset), default=0)
        for j, w in enumerate(weights)
    )
    relevance = budget.alpha * sum(s["relevance"] for s in subset)
    # Only explicit byte-equivalence/substitution families incur this penalty.
    redundancy = budget.beta * sum(
        bool(a.get("equivalent_family"))
        and a.get("equivalent_family") == b.get("equivalent_family")
        for a, b in combinations(subset, 2)
    )
    cost = budget.gamma * sum(s["tokens"] for s in subset) / budget.tokens
    return {
        "coverage": coverage,
        "relevance": relevance,
        "redundancy": redundancy,
        "cost": cost,
        "score": coverage + relevance - redundancy - cost,
    }


def select(candidates, weights, budget=None, *, exact_k=None):
    budget = budget or Budget()
    if len(candidates) > 20 or len({s["id"] for s in candidates}) != len(candidates):
        raise ValueError("unique pool of at most 20 required")
    if any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError("invalid requirement weights")
    for s in candidates:
        if (
            s["tokens"] < 0
            or len(s["support"]) != len(weights)
            or any(
                not math.isfinite(v) or not 0 <= v <= 1
                for v in [s["relevance"], *s["support"]]
            )
        ):
            raise ValueError("invalid bounded candidate values")
        if s.get("support_state") != "SUPPORTED_BY_TEXT" and any(s["support"]):
            raise ValueError("unknown support cannot count as coverage")
    pool = sorted(
        (s for s in candidates if s.get("compatible") is True and any(s["support"])),
        key=lambda s: s["id"],
    )
    best, score, evaluated = (), 0.0, 0
    found = exact_k is None
    for k in range(min(budget.max_k, len(pool)) + 1):
        if exact_k is not None and k != exact_k:
            continue
        for subset in combinations(pool, k):
            if sum(s["tokens"] for s in subset) > budget.tokens:
                continue
            evaluated += 1
            value = objective(subset, weights, budget)["score"]
            if not found or value > score + 1e-12:
                best, score, found = subset, value, True
    return {
        "skill_ids": [s["id"] for s in best],
        "objective": objective(best, weights, budget),
        "potential_load_tokens": sum(s["tokens"] for s in best),
        "evaluated_subsets": evaluated,
        "fallback_reason": None if best else "no_positive_feasible_supported_set",
        "candidate_pool_only": True,
        "exact_k": exact_k,
    }
