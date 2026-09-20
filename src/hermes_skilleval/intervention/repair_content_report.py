"""Functional study report; coverage, policy and cost are never success inputs."""

from __future__ import annotations
from collections import defaultdict


def counts(rows, planned=2):
    values = [r.get("y_functional") for r in rows]
    if len(values) > planned:
        raise ValueError("too many study cells")
    passed = sum(v == 1 for v in values)
    failed = sum(v == 0 for v in values)
    unknown = planned - passed - failed
    return {
        "pass": passed,
        "fail": failed,
        "unknown": unknown,
        "planned": planned,
        "mean": passed / planned if planned and not unknown else None,
        "bounds": [passed / planned, (passed + unknown) / planned] if planned else None,
    }


def summarize(rows, lock):
    grouped = defaultdict(list)
    seen = set()
    roster = {(c["task_id"], c["arm"], c["repeat"]) for c in lock["cells"]}
    for row in rows:
        key = (row["task_id"], row["arm"], row["repeat"])
        if key in seen or key not in roster:
            raise ValueError("duplicate or unplanned outcome")
        seen.add(key)
        grouped[key[:2]].append(row)
    states = []
    for state in lock["states"]:
        tid = state["task_id"]
        arms = sorted({c["arm"] for c in lock["cells"] if c["task_id"] == tid})
        table = {a: counts(grouped[tid, a]) for a in arms}
        contrasts = {}
        for a, b in [
            ("H", "M"),
            ("M", "L"),
            ("M", "N"),
            ("H", "G"),
            ("H", "N"),
            ("H", "H-no-gap"),
            ("H", "H-no-exposure"),
        ]:
            if a in table and b in table:
                av, bv = table[a]["mean"], table[b]["mean"]
                contrasts[a + "-" + b] = (
                    av - bv if av is not None and bv is not None else None
                )
        states.append(
            {
                "task_id": tid,
                "mechanism": state["mechanism"],
                "arms": table,
                "contrasts": contrasts,
            }
        )
    signals = []
    for state in states:
        table = state["arms"]
        if not all(
            a in table and table[a]["mean"] is not None
            for a in ["N", "G", "L", "M", "H"]
        ):
            continue
        threshold = max(table[a]["mean"] for a in ["N", "G", "L"])
        if max(table[a]["mean"] for a in ["M", "H"]) > threshold:
            signals.append(state["mechanism"])
    complete = len(seen) == len(roster) and all(
        r.get("y_functional") is not None for r in rows
    )
    triggered = complete and len(set(signals)) >= 2
    primary = [s["contrasts"].get("H-M") for s in states]
    return {
        "states": states,
        "planned": len(roster),
        "recorded": len(seen),
        "functional_evidence_complete": complete,
        "mechanism_mean_H_minus_M": sum(primary) / len(primary)
        if primary and all(x is not None for x in primary)
        else None,
        "content_route_signal_mechanisms": sorted(set(signals)),
        "confirmation_decision": "TRIGGERED"
        if triggered
        else "NOT_TRIGGERED"
        if complete
        else "UNRESOLVED",
        "continuation_rule": "At least two distinct mechanisms where M or H mean exceeds every N/G/L mean; complete scheduled pilot and ablation labels required. Frozen before sampling.",
        "default_policy": "UNCHANGED",
        "new_gain_wait_training": "NOT_IN_SCOPE",
    }
