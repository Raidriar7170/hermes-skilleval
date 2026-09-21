"""Records-only planned-denominator aggregation; never starts research execution."""

import argparse
from collections import Counter
from pathlib import Path
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--study", type=Path, required=True)
p.add_argument("--plan", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
plan = read(a.plan)
raw = read(a.study / "functional-results.json")
rows = raw["rows"]
if len(rows) != len(plan["tasks"]) * len(plan["arms"]) * plan["tail_repeats"]:
    raise ValueError("Incomplete planned result ledger")
summary = []
for task in plan["tasks"]:
    for arm in plan["arms"]:
        group = [
            r for r in rows if r["task_id"] == task["instance_id"] and r["arm"] == arm
        ]
        if len(group) != plan["tail_repeats"]:
            raise ValueError("Missing planned cell")
        counts = Counter(r["functional"] for r in group)
        summary.append(
            {
                "mechanism": task["mechanism"],
                "task_id": task["instance_id"],
                "arm": arm,
                "planned": len(group),
                "PASS": counts["PASS"],
                "FAIL": counts["FAIL"],
                "UNKNOWN": counts["UNKNOWN"],
                "target": dict(Counter(r["target"] for r in group)),
                "protected": dict(Counter(r["protected"] for r in group)),
                "lower": counts["PASS"] / len(group),
                "upper": (counts["PASS"] + counts["UNKNOWN"]) / len(group),
            }
        )
means = {
    arm: {
        k: sum(r[k] for r in summary if r["arm"] == arm) / len(plan["tasks"])
        for k in ["lower", "upper"]
    }
    for arm in plan["arms"]
}
differences = {
    f"{left}_minus_{right}": {
        "lower": means[left]["lower"] - means[right]["upper"],
        "upper": means[left]["upper"] - means[right]["lower"],
    }
    for left, right in [("H-link", "M-local"), ("H-link", "H-sim"), ("M-local", "N")]
}
executions = []
for phase in ["prefixes", "tails"]:
    for path in sorted((a.study / phase).rglob("execution.json")):
        value = read(path)
        executions.append(
            {
                "attempt": str(path.parent.relative_to(a.study)),
                "status": value["status"],
                "actual_thread_started": bool(value.get("thread_id")),
                "tail_seconds": value.get("tail_seconds"),
                "charged_initialization_seconds": value.get(
                    "policy_initialization_seconds"
                ),
                "model_input_observed": value.get("model_input_observed"),
            }
        )
semantic = []
for path in sorted((a.study / "selection").rglob("cost.json")):
    semantic.append({"attempt": str(path.parent.relative_to(a.study)), **read(path)})
dump(
    a.output,
    {
        "study": plan["study"],
        "plan_digest": plan["plan_digest"],
        "mechanism_results": summary,
        "mechanism_equal_weight_bounds": means,
        "difference_bounds": differences,
        "execution_ledger": executions,
        "semantic_costs": semantic,
        "planned_research_executions": plan["max_research_executions"],
        "actual_research_threads": sum(r["actual_thread_started"] for r in executions),
        "functional_gain_over_mmr": "OBSERVED_WITH_LIMITATIONS"
        if differences["H-link_minus_M-local"]["lower"] > 0
        else "UNKNOWN"
        if any(r["UNKNOWN"] for r in summary)
        else "NOT_ESTABLISHED",
        "relation_gain_over_similarity": "OBSERVED_WITH_LIMITATIONS"
        if differences["H-link_minus_H-sim"]["lower"] > 0
        else "UNKNOWN"
        if any(r["UNKNOWN"] for r in summary)
        else "NOT_ESTABLISHED",
        "default_policy": "UNCHANGED",
        "neural_training": "NOT_IN_SCOPE",
        "legacy_results": "PRESERVED",
        "aggregation_mode": "RECORDS_ONLY",
    },
)
print(
    {
        "mechanisms": len(plan["tasks"]),
        "planned_tails": len(rows),
        "actual_threads": sum(r["actual_thread_started"] for r in executions),
        "difference_bounds": differences,
    }
)
