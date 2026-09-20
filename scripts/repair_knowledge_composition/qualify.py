"""Qualify fixed sources without new repair Agent samples."""

import argparse
import json
from pathlib import Path
from hermes_skilleval.intervention.repair_checks import check_source
from hermes_skilleval.intervention.session import dump

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("pool", "tasks", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    results = []
    for row in json.loads(a.pool.read_text())["rows"]:
        tid = row["instance_id"]
        task = a.tasks / tid
        variants = {
            v: check_source(task, task / v, a.output / tid / v)
            for v in ("base", "reference")
        }
        base, reference = variants["base"], variants["reference"]
        qualified = (
            all(c.get("valid") for v in variants.values() for c in v.values())
            and base["target"]["passed"] is False
            and base["regression"]["passed"] is True
            and all(c["passed"] for c in reference.values())
        )
        result = {
            "task_id": tid,
            "mechanism": row["mechanism"],
            "qualified": qualified,
            "variants": variants,
        }
        results.append(result)
        dump(a.output / "qualification.json", {"rows": results, "agent_calls": 0})
        print(
            json.dumps(
                {
                    "mechanism": row["mechanism"],
                    "qualified": qualified,
                    "base": {k: (v["valid"], v["passed"]) for k, v in base.items()},
                    "reference": {
                        k: (v["valid"], v["passed"]) for k, v in reference.items()
                    },
                }
            ),
            flush=True,
        )
