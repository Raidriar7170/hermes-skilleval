"""Isolated acceptance-only qualification; no output is consumed by retrieval."""

import argparse
import runpy
from pathlib import Path
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.repair_checks import check_source
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--overlays", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
plan = read("configs/repair-knowledge-composition-v1/plan.json")
build_overlay = runpy.run_path("scripts/repair_knowledge_composition/revalidate.py")[
    "build_overlay"
]
rows = []
for task in sorted(
    (t for t in plan["tasks"] if t["split"] == "confirmation"),
    key=lambda t: t["source_order"],
):
    tid = task["instance_id"]
    root = a.tasks / tid
    overlay = a.overlays / tid
    build_overlay(root, overlay)
    variants = {}
    for variant in ("base", "reference"):
        variants[variant] = check_source(
            root,
            root / variant,
            a.output / tid / variant,
            image=plan["image"],
            trusted_overlay=overlay,
        )
    qualified = (
        all(c.get("valid") for v in variants.values() for c in v.values())
        and variants["base"]["target"]["passed"] is False
        and variants["base"]["regression"]["passed"] is True
        and all(c["passed"] for c in variants["reference"].values())
    )
    row = {
        "task_id": tid,
        "mechanism": task["mechanism"],
        "source_order": task["source_order"],
        "mechanically_qualified": qualified,
        "variants": variants,
    }
    rows.append(row)
    dump(a.output / "qualification.json", {"rows": rows, "research_executions": 0})
    print(
        {"mechanism": task["mechanism"], "mechanically_qualified": qualified},
        flush=True,
    )
