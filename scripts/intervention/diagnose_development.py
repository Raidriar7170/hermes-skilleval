"""Predeclared offline E2 forced-injection and generic-message diagnostics."""

import argparse
from collections import defaultdict
from pathlib import Path
import torch
from hermes_skilleval.intervention.study import read, assets
from hermes_skilleval.intervention.state import State
from hermes_skilleval.intervention.learning import Predictor
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.report import collection_diagnostics, interval

p = argparse.ArgumentParser()
for key in ("records", "models", "payloads", "encoder", "output"):
    p.add_argument("--" + key, type=Path, required=True)
a = p.parse_args()
torch.set_num_threads(2)
rows = [r for r in read(a.records)["rows"] if r["split"] == "dev"]
encoder, retriever, _, _ = assets(a.payloads, a.encoder)
predict = Predictor(a.models, "H-full", encoder, retriever)
groups = defaultdict(list)
for row in rows:
    if row["stage"] == "E2":
        groups[row["state_id"], row["repeat"]].append(row)
results = []
for (state_id, repeat), group in sorted(groups.items()):
    state = State(**group[0]["state"])
    candidates = group[0]["candidates"]
    gains, _ = predict(state, candidates)
    chosen = min(candidates, key=lambda k: (-gains[k], k))
    forced = next(r for r in group if r["action"] == chosen)
    native = next(r for r in group if r["action"] == "NO_INTERVENTION")
    allowed = forced if gains[chosen] > 0 else native
    valid = forced["utility"] is not None and allowed["utility"] is not None
    results.append(
        {
            "state_id": state_id,
            "task_id": forced["task_id"],
            "repeat": repeat,
            "gains": gains,
            "forced_action": chosen,
            "allowed_action": allowed["action"],
            "forced_utility": forced["utility"],
            "allowed_utility": allowed["utility"],
            "allowed_minus_forced": allowed["utility"] - forced["utility"]
            if valid
            else None,
        }
    )
by_task = defaultdict(list)
for r in results:
    if r["allowed_minus_forced"] is not None:
        by_task[r["task_id"]].append(r["allowed_minus_forced"])
report = {
    "scope": "OFFLINE_DEVELOPMENT_E2_OBSERVED_ACTIONS_ONLY; not an end-to-end policy estimate",
    "forced_injection": results,
    "allowed_minus_forced": interval([sum(v) / len(v) for v in by_task.values()]),
    "generic_and_damage_controls": collection_diagnostics(rows),
    "full_policy_uncertainty": "WAIT trajectories cannot be valued by choosing the best observed future branch",
}
dump(a.output, report)
print(
    {
        "development_E2_pairs": len(results),
        "qualified": sum(r["allowed_minus_forced"] is not None for r in results),
    }
)
