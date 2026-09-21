"""Same-pool MMR, similarity coverage and independently proposed relation coverage."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations

from .repair_composer import KnowledgePack, render_pack, select_mmr
from .repair_knowledge import render_units, token_count


def objective(pool, indices, weights, coverage):
    cov = sum(
        weights.get(o.id, 0) * max((coverage[i][j] for i in indices), default=0)
        for j, o in enumerate(pool.obligations)
    )
    rel = 0.10 * sum(pool.candidates[i].relevance for i in indices)
    redundancy = 0.10 * sum(pool.overlap[i][j] for i, j in combinations(indices, 2))
    exposure = 0.05 * sum(pool.candidates[i].exposure or 0 for i in indices)
    return {
        "coverage": cov,
        "relevance": rel,
        "redundancy_penalty": redundancy,
        "exposure_penalty": exposure,
        "total": cov + rel - redundancy - exposure,
    }


def select(
    pool, ledger, *, method, relations=(), token_budget=1200, count_tokens=token_count
):
    if method not in {"M-local", "H-sim", "H-link"}:
        raise ValueError("Unknown selector")
    if method == "M-local" or not pool.obligations:
        p = select_mmr(pool, token_budget=token_budget, count_tokens=count_tokens)
        return replace(
            p, method=method if pool.obligations else method + "-fallback-M-local"
        )
    if method == "H-link":
        matrix = {(r["requirement_id"], r["unit_id"]): r["weight"] for r in relations}
        if len(matrix) != len(pool.obligations) * len(pool.candidates):
            raise ValueError("Missing semantic relations")
        coverage = tuple(
            tuple(matrix[(o.id, c.unit.unit_id)] for o in pool.obligations)
            for c in pool.candidates
        )
        if not any(v > 0 for row in coverage for v in row):
            return KnowledgePack(
                "NO_SUPPORTED_LOCAL_CONTEXT",
                (),
                (),
                0,
                {"total": 0},
                ({"reason": "No positive grounded source relationship"},),
            )
    else:
        coverage = tuple(c.coverage for c in pool.candidates)
    weights = ledger["weights"]

    def score(ids):
        return objective(pool, ids, weights, coverage)

    def tokens(ids):
        return count_tokens(render_units([pool.candidates[i].unit for i in ids]))

    selected = []
    decisions = []
    while len(selected) < 4:
        available = [
            i
            for i in range(len(pool.candidates))
            if i not in selected and tokens(selected + [i]) <= token_budget
        ]
        if not available:
            break
        base = score(selected)["total"]
        marginal = {i: score(selected + [i])["total"] - base for i in available}
        best = min(
            available,
            key=lambda i: (
                -marginal[i] / max(1, tokens(selected + [i]) - tokens(selected)),
                pool.candidates[i].unit.unit_id,
            ),
        )
        if marginal[best] <= 0:
            break
        selected.append(best)
        decisions.append(
            {"unit_id": pool.candidates[best].unit.unit_id, "marginal": marginal[best]}
        )
    singles = [i for i in range(len(pool.candidates)) if tokens([i]) <= token_budget]
    if singles:
        best = min(
            singles,
            key=lambda i: (-score([i])["total"], pool.candidates[i].unit.unit_id),
        )
        if score([best])["total"] > score(selected)["total"]:
            selected = [best]
            decisions.append({"best_singleton": pool.candidates[best].unit.unit_id})
    pack = KnowledgePack(
        method,
        tuple(selected),
        tuple(pool.candidates[i].unit for i in selected),
        tokens(selected),
        score(selected),
        tuple(decisions),
    )
    if count_tokens(render_pack(pack)) > token_budget:
        raise AssertionError("Full serialized payload exceeds budget")
    return pack
