"""Execute declared target/regression selectors separately; no Agent calls."""

import argparse
import json
from pathlib import Path

from hermes_skilleval._maintenance.check import check
from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.repository_profile import RepositoryProfile


def main():
    p = argparse.ArgumentParser()
    for key in ("tasks", "output", "objective"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    objective = load_objective(a.objective)
    a.output.mkdir(parents=True, exist_ok=False)
    roster = json.loads((a.tasks / "candidate-roster.json").read_text())
    results = []
    for row in roster:
        tid = row["task_id"]
        task = a.tasks / tid
        meta = json.loads((task / "task.json").read_text())
        variants = {}
        for variant in ("base", "reference"):
            variants[variant] = {}
            for kind in ("target", "regression"):
                result = check(
                    task / variant,
                    task / "trusted",
                    a.output / tid / variant / kind,
                    meta[kind + "_selector"],
                    profile=RepositoryProfile(**meta["profile"]),
                    test_file=meta["trusted_test_file"],
                    timeout=120,
                )
                variants[variant][kind] = {
                    k: result.get(k)
                    for k in ("valid", "passed", "cases", "error", "seconds")
                }
        base, ref = variants["base"], variants["reference"]
        qualified = (
            all(r["valid"] for v in variants.values() for r in v.values())
            and base["target"]["passed"] is False
            and base["regression"]["passed"] is True
            and all(r["passed"] for r in ref.values())
        )
        result = {
            "task_id": tid,
            "status": "BASE_RED_REFERENCE_GREEN" if qualified else "NOT_QUALIFIED",
            **variants,
        }
        results.append(result)
        print(json.dumps(result), flush=True)
        (a.output / "qualification.json").write_text(
            json.dumps(
                {"objective_sha256": objective["sha256"], "rows": results}, indent=2
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
