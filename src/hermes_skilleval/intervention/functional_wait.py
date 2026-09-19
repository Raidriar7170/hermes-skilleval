"""Nested mechanism-family-held-out functional continuation targets."""

from .value import fit_gain, fit_wait


def cross_fitted_targets(rows, chains, *, epochs=160):
    import torch

    family = {tid: chain[0]["family"] for tid, chain in chains.items() if chain}
    families = sorted(set(family.values()))
    if len(families) < 3:
        raise ValueError("need at least three independent training families")
    gain_cache = {}

    def gain_without(excluded):
        key = tuple(sorted(excluded))
        if key not in gain_cache:
            data = [r for r in rows if r["family"] not in excluded]
            if not data:
                raise ValueError("no known functional labels outside held families")
            gain_cache[key] = fit_gain(data, epochs=epochs)[0]
        return gain_cache[key]

    def value(gain, wait, state):
        with torch.no_grad():
            gains = [
                float(gain(state["x"][None], k[None])[0]) for k in state["candidates"]
            ]
            waiting = 0.0 if wait is None else float(wait(state["x"][None])[0, 0])
        return max(0.0, waiting, *gains)

    result, provenance = [], []
    for held in families:
        outside = [tid for tid in chains if family[tid] != held]
        intermediate = []
        inner_folds = []
        for tid in outside:
            excluded = {held, family[tid]}
            gain = gain_without(excluded)
            chain = chains[tid]
            for i, state in enumerate(chain):
                if state["stage"] != "E1":
                    continue
                if i + 1 < len(chain):
                    target = value(gain, None, chain[i + 1])
                elif state["terminal_confirmed"]:
                    target = 0.0
                else:
                    continue
                intermediate.append({**state, "target": target})
            inner_folds.append(
                {
                    "target_task": tid,
                    "excluded_families": sorted(excluded),
                    "gain_training_tasks": sorted(
                        {r["task_id"] for r in rows if r["family"] not in excluded}
                    ),
                }
            )
        wait = fit_wait(intermediate, epochs=epochs)[0] if intermediate else None
        gain = gain_without({held})
        unknown = []
        target_tasks = [tid for tid in chains if family[tid] == held]
        for tid in target_tasks:
            chain = chains[tid]
            for i, state in enumerate(chain):
                if i == len(chain) - 1:
                    if not state["terminal_confirmed"]:
                        unknown.append(
                            {
                                "state_id": state["state_id"],
                                "reason": "UNCONFIRMED_NATIVE_TERMINATION",
                            }
                        )
                        continue
                    target = 0.0
                else:
                    nxt = chain[i + 1]
                    needs_wait = nxt["stage"] == "E1" and not nxt["terminal_confirmed"]
                    if needs_wait and wait is None:
                        unknown.append(
                            {
                                "state_id": state["state_id"],
                                "reason": "NO_OUT_OF_FAMILY_WAIT_TARGETS",
                            }
                        )
                        continue
                    target = value(gain, wait if needs_wait else None, nxt)
                result.append({**state, "target": target})
        provenance.append(
            {
                "excluded_family": held,
                "target_tasks": target_tasks,
                "gain_training_tasks": sorted(
                    {r["task_id"] for r in rows if r["family"] != held}
                ),
                "wait_training_tasks": sorted({r["task_id"] for r in intermediate}),
                "inner_folds": inner_folds,
                "unknown_wait_targets": unknown,
            }
        )
    return result, provenance
