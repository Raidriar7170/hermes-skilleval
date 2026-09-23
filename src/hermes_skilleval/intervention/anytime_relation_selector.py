"""Finite-domain relation objective bounds, not confidence or repair guarantees."""

from __future__ import annotations

from itertools import combinations
import time

from .linked_composition import objective
from .repair_composer import KnowledgePack, select_mmr
from .repair_knowledge import render_units, token_count


class ExactSelector:
    def __init__(
        self,
        pool,
        ledger,
        *,
        token_budget=1200,
        max_units=4,
        count_tokens=token_count,
        deadline=None,
    ):
        if len(pool.candidates) > 24 or not 0 <= max_units <= 4:
            raise ValueError("Outside frozen enumeration domain")
        ids = [r["requirement_id"] for r in ledger["requirements"]]
        if set(ids) != {o.id for o in pool.obligations} or len(ids) != len(
            pool.obligations
        ):
            raise ValueError(
                "Complete requirement domain differs from candidate obligations"
            )
        if set(ledger["weights"]) != set(ids):
            raise ValueError("Complete requirement weight domain differs")
        if max_units != 4:
            raise ValueError(
                "This frozen method requires four-unit MMR and relation domain"
            )
        self.pool, self.ledger = pool, ledger
        self.mmr = select_mmr(
            pool, token_budget=token_budget, count_tokens=count_tokens
        )
        self.feasible = {}
        order = sorted(
            range(len(pool.candidates)), key=lambda i: pool.candidates[i].unit.unit_id
        )
        for k in range(min(max_units, len(order)) + 1):
            for ids in combinations(order, k):
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("Feasible-set enumeration deadline")
                tokens = count_tokens(
                    render_units([pool.candidates[i].unit for i in ids])
                )
                if tokens <= token_budget:
                    self.feasible[ids] = tokens
        if not self.feasible:
            raise ValueError("Empty serialization exceeds budget")

    def solve(self, store, *, deadline=None):
        pool = self.pool
        bounds = [
            [store.bounds((o.id, c.unit.unit_id)) for o in pool.obligations]
            for c in pool.candidates
        ]
        lower = [[b[0] for b in row] for row in bounds]
        upper = [[b[1] for b in row] for row in bounds]
        weights = self.ledger["weights"]
        scores = {}
        for ids in self.feasible:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Relation objective solve deadline")
            scores[ids] = (
                objective(pool, ids, weights, lower)["total"],
                objective(pool, ids, weights, upper)["total"],
            )

        def tie(ids):
            return tuple(pool.candidates[i].unit.unit_id for i in ids)

        lo = min(scores, key=lambda ids: (-scores[ids][0], tie(ids)))
        hi = min(scores, key=lambda ids: (-scores[ids][1], tie(ids)))
        baseline = objective(pool, self.mmr.indices, weights, lower)["total"]
        positive = any(
            lower[i][j] > 0 for i in lo for j in range(len(pool.obligations))
        )
        pack = self.mmr
        state = "MMR_FALLBACK"
        if positive and scores[lo][0] > baseline:
            pack = KnowledgePack(
                "A",
                lo,
                tuple(pool.candidates[i].unit for i in lo),
                self.feasible[lo],
                objective(pool, lo, weights, lower),
                (),
            )
            state = "PROVISIONAL_RELATION_PACK"
        if set(pack.indices) == set(self.mmr.indices) and positive:
            state = "UNCHANGED_MMR_PACK"
        rival_upper = max(
            (v[1] for ids, v in scores.items() if ids != lo), default=float("-inf")
        )
        return pack, {
            "status": state,
            "lower_indices": list(lo),
            "upper_indices": list(hi),
            "lower": scores[lo][0],
            "upper": scores[hi][1],
            "mmr_lower": baseline,
            "stable": rival_upper <= scores[lo][0] + 1e-12,
            "feasible_sets": len(scores),
            "bound_scope": "fixed_model_labels_and_candidate_domain_not_semantic_truth",
        }

    def requests(
        self, store, result, *, size=8, strategy="A", costs=None, offset=0, excluded=()
    ):
        pending = [p for p in store.pending() if p not in excluded]
        if strategy == "S":
            return pending[:size]
        if strategy != "A":
            raise ValueError("Unknown query strategy")
        costs = costs or {}
        pool = self.pool
        selected = [
            set(self.mmr.indices),
            set(result["lower_indices"]),
            set(result["upper_indices"]),
        ]
        index = {c.unit.unit_id: i for i, c in enumerate(pool.candidates)}
        weights = self.ledger["weights"]
        counts = {
            o.id: sum(
                store.records[p]["state"] != "NOT_ANALYZED"
                for p in store.pairs
                if p[0] == o.id
            )
            for o in pool.obligations
        }

        def priority(p):
            low, high = store.bounds(p)
            return (
                weights[p[0]]
                * (high - low)
                * (1 + sum(index[p[1]] in s for s in selected))
                / max(1e-9, costs.get(p, 1.0))
            )

        batch = []
        while pending and len(batch) < size:
            eligible = pending
            if (offset + len(batch) + 1) % 3 == 0:
                # Prefer least-analyzed requirements, weight and ID resolve ties.
                rid = min(
                    {p[0] for p in pending}, key=lambda r: (counts[r], -weights[r], r)
                )
                eligible = [p for p in pending if p[0] == rid]
            chosen = min(eligible, key=lambda p: (-priority(p), p))
            batch.append(chosen)
            pending.remove(chosen)
            counts[chosen[0]] += 1
        return batch
