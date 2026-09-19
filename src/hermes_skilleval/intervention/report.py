"""Task-clustered descriptive diagnostics for the predeclared ASI comparison."""

from __future__ import annotations
from collections import Counter, defaultdict
import random


def interval(task_values, repeats=10000, seed=7170):
    """Task bootstrap: repetitions and shared native tails are not independent n."""
    values = list(task_values)
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choices(values, k=len(values))) / len(values) for _ in range(repeats)
    )
    return {
        "mean": sum(values) / len(values),
        "lower_95": means[int(0.025 * repeats)],
        "upper_95": means[int(0.975 * repeats)],
        "independent_tasks": len(values),
        "method": "paired task-cluster percentile bootstrap; small-n unstable",
    }


def final_comparisons(rows):
    by_run = {(r["task_id"], r["method"], r["repeat"]): r for r in rows}
    result = {}
    for baseline in ("N0", "S1", "R1", "H-myopic", "H-no-state"):
        paired = defaultdict(list)
        quality = defaultdict(list)
        missing = []
        for (task, method, repeat), full in by_run.items():
            if method != "H-full":
                continue
            base = by_run.get((task, baseline, repeat))
            if base is None or base["quality"] is None or full["quality"] is None:
                missing.append([task, repeat])
                continue
            paired[task].append(full["utility"] - base["utility"])
            quality[task].append(int(full["quality"]) - int(base["quality"]))
        result[baseline] = {
            "utility": interval([sum(v) / len(v) for v in paired.values()]),
            "success": interval([sum(v) / len(v) for v in quality.values()]),
            "paired_runs": sum(map(len, paired.values())),
            "unknown_pairs": missing,
        }
    return result


def collection_diagnostics(rows):
    baseline = {
        (r["state_id"], r["repeat"]): r
        for r in rows
        if r["action"] == "NO_INTERVENTION"
    }
    reminder = {
        (r["state_id"], r["repeat"]): r
        for r in rows
        if r["action"] == "GENERIC_REMINDER"
    }
    counts = Counter()
    by_stage = defaultdict(Counter)
    by_skill_stage = defaultdict(list)
    unknown = []
    skill_vs_reminder = defaultdict(list)
    for row in rows:
        if row["action"] in ("NO_INTERVENTION", "GENERIC_REMINDER"):
            continue
        base = baseline.get((row["state_id"], row["repeat"]))
        if base is None or base["quality"] is None or row["quality"] is None:
            unknown.append([row["state_id"], row["action"], row["repeat"]])
            continue
        label = (
            "rescue"
            if row["quality"] > base["quality"]
            else "damage"
            if row["quality"] < base["quality"]
            else "tie_success"
            if row["quality"]
            else "tie_failure"
        )
        counts[label] += 1
        by_stage[row["stage"]][label] += 1
        by_skill_stage[row["action"] + "@" + row["stage"]].append(
            row["utility"] - base["utility"]
        )
        generic = reminder.get((row["state_id"], row["repeat"]))
        if generic is not None and generic["quality"] is not None:
            skill_vs_reminder[row["task_id"]].append(
                row["utility"] - generic["utility"]
            )
    return {
        "paired_outcomes": dict(counts),
        "by_stage": {k: dict(v) for k, v in by_stage.items()},
        "skill_stage_delta": {
            k: {"pairs": len(v), "mean": sum(v) / len(v)}
            for k, v in by_skill_stage.items()
        },
        "unknown_pairs": unknown,
        "skill_vs_generic_task_cluster": interval(
            [sum(v) / len(v) for v in skill_vs_reminder.values()]
        ),
        "actual_states": len({r["state_id"] for r in rows}),
        "natural_stages": dict(
            Counter(s.split(":")[-1] for s in {r["state_id"] for r in rows})
        ),
        "counterfactual_collection_active_seconds": sum(
            r["execution"].get("tail_seconds") or 0 for r in rows
        ),
        "actual_api_tokens": None,
        "actual_dollar_bill": None,
    }
