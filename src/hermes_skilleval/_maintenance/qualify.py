"""Run all four trusted qualification cells; no Agent or selector calls."""

import argparse
import json
from pathlib import Path
from hermes_skilleval.repository_profile import profile_for
from hermes_skilleval._maintenance.check import check
from hermes_skilleval._maintenance.finalize import binding
from hermes_skilleval.repository_maintenance import manifest

p = argparse.ArgumentParser()
p.add_argument("--task-root", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--oracle", nargs="+", required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
task = json.loads((a.task_root / "task.json").read_text())
cells = {}
for variant in ["base", "reference"]:
    for kind in ["target", "regression"]:
        cells[variant + "-" + kind] = check(
            a.task_root / variant,
            a.task_root / "trusted",
            a.output / (variant + "-" + kind),
            task[kind + "_selector"],
            test_file=task["trusted_test_file"],
            profile=profile_for(task),
        )
qualified = (
    all(c["valid"] for c in cells.values())
    and not cells["base-target"]["passed"]
    and all(
        cells[k]["passed"]
        for k in ["reference-target", "base-regression", "reference-regression"]
    )
)
for kind in ["target", "regression"]:
    qualified = qualified and sorted(
        c["id"] for c in cells["base-" + kind]["cases"]
    ) == sorted(c["id"] for c in cells["reference-" + kind]["cases"])
r = dict(
    task,
    qualification_binding=binding(a.task_root),
    qualified=qualified,
    base_manifest=manifest(a.task_root / "base"),
    oracle_ids=a.oracle,
    test_ids={
        n: sorted(c["id"] for c in cells["reference-" + n]["cases"])
        for n in ["target", "regression"]
    },
)
(a.output / "qualified.json").write_text(json.dumps(r, indent=2) + "\n")
print(
    json.dumps(
        {
            "qualified": qualified,
            "cells": {
                k: {
                    "valid": v["valid"],
                    "passed": v["passed"],
                    "tests": len(v["cases"]),
                }
                for k, v in cells.items()
            },
        },
        indent=2,
    )
)
