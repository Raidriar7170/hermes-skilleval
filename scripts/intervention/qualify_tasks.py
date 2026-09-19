"""Run controller-owned source-grounded checks on base/reference candidates."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from hermes_skilleval._maintenance.check import check
from hermes_skilleval.repository_profile import RepositoryProfile
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--only", nargs="*")
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
roster = json.loads((a.tasks / "candidate-roster.json").read_text())
if a.only:
    roster = [r for r in roster if r["task_id"] in a.only]


def one(t):
    tid = t["task_id"]
    root = a.tasks / tid
    m = json.loads((root / "task.json").read_text())
    out = {}
    for variant in ["base", "reference"]:
        r = check(
            root / variant,
            root / "trusted",
            a.output / tid / variant,
            "test_target or test_regression",
            profile=RepositoryProfile(**m["profile"]),
            test_file="test_behavior.py",
            timeout=120,
        )
        out[variant] = {
            k: r.get(k) for k in ["valid", "passed", "cases", "error", "seconds"]
        }
    print(json.dumps({"task_id": tid, **out}), flush=True)
    return {"task_id": tid, **out}


with ThreadPoolExecutor(max_workers=2) as pool:
    result = list(pool.map(one, roster))
dump(a.output / "qualification.json", result)
