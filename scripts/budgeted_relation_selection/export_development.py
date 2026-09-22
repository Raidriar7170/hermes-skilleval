"""Export compact observed development evidence, without source corpora or sessions."""

import argparse
from pathlib import Path

from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.relation_store import atomic_json

p = argparse.ArgumentParser()
p.add_argument("--private", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
rows = []
for root in sorted(a.private.glob("development-*")):
    if not root.is_dir():
        continue
    calls = []
    for cost in sorted(root.glob("batch-*/cost.json")):
        d = read(cost)
        calls.append(
            {
                k: d.get(k)
                for k in [
                    "status",
                    "seconds",
                    "deadline_seconds",
                    "error",
                    "cancellation",
                    "no_running_tool_confirmation",
                ]
            }
        )
    result = root / "selection.json"
    if result.exists():
        d = read(result)
        rows.append(
            {
                "attempt": root.name,
                "calls": calls,
                **{
                    k: d.get(k)
                    for k in [
                        "status",
                        "stop_reason",
                        "unique_requested",
                        "relation_seconds",
                        "relation_limit",
                        "budget_overrun",
                        "input_identity",
                    ]
                },
                "relation_counts": d["relations"]["counts"],
                "pack_ids": [u["unit_id"] for u in d["pack"]["units"]],
            }
        )
    elif calls:
        rows.append({"attempt": root.name, "calls": calls})
atomic_json(
    a.output,
    {
        "study": "budgeted-relation-selection-v1",
        "scope": "DEVELOPMENT_ONLY",
        "attempts": rows,
        "research_prefixes": 0,
        "research_tails": 0,
        "legacy_import": read(a.private / "legacy-partial-import-v1/summary.json"),
        "overlay_preflight": read(a.private / "overlay-preflight-v1/result.json"),
        "functional_gain": "NOT_ESTABLISHED",
        "default_policy": "UNCHANGED",
    },
)
print(len(rows), "development attempts exported")
