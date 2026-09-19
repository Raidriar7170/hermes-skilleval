"""Materialize preregistered tabular contracts without Agent calls."""

import argparse
import io
import json
from pathlib import Path
import tarfile

from prepare_pilot import git
from tabular_contracts import CONTRACTS
from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.repository_profile import SQLITE_UTILS, CSVKIT, RepositoryProfile
from hermes_skilleval.intervention.session import IMAGE


def main():
    p = argparse.ArgumentParser()
    for key in ("pool", "objective", "upstreams", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--final", action="store_true")
    a = p.parse_args()
    contracts = CONTRACTS
    if a.final:
        from final_contracts import CONTRACTS as contracts
    load_objective(a.objective)
    a.output.mkdir(parents=True, exist_ok=False)
    rows = [
        r
        for r in json.loads(a.pool.read_text())["rows"]
        if r["fix_commit"][:7] in contracts
    ]
    for row in rows:
        ref = row["fix_commit"]
        repo_name, request, code = contracts[ref[:7]]
        repo = a.upstreams / repo_name
        root = a.output / row["task_id"]
        root.mkdir()
        for scope, commit in [("base", row["base_commit"]), ("reference", ref)]:
            dest = root / scope
            dest.mkdir()
            with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", commit))) as tar:
                tar.extractall(dest, filter="data")
        trusted = root / "trusted"
        trusted.mkdir()
        (trusted / "pytest.ini").write_text("[pytest]\n")
        (trusted / "test_behavior.py").write_text(code + "\n")
        profile = (
            SQLITE_UTILS
            if repo_name == "sqlite-utils"
            else CSVKIT
            if repo_name == "csvkit"
            else RepositoryProfile(
                "simonw/csv-diff",
                {"csv_diff": "."},
                "csv_diff.cli",
                "cli",
                "csv-diff",
                IMAGE,
                ("csv_diff", "tests"),
            )
        ).to_dict()
        profile["image"] = IMAGE
        profile["file_policy"] = {
            "version": "operations-v1",
            "rules": [
                {
                    "path": r,
                    "operations": ["add", "modify", "delete"],
                    "max_bytes": 1000000,
                }
                for r in profile["writable_roots"]
            ],
        }
        meta = {
            **row,
            "profile": profile,
            "trusted_test_file": "test_behavior.py",
            "target_selector": "test_target",
            "regression_selector": "test_regression",
            "reference_commit": ref,
            "request_ref": row["source"],
        }
        (root / "task.json").write_text(json.dumps(meta, indent=2) + "\n")
        (root / "request.txt").write_text(request + "\n")
        row["request"] = request
        row["coverage"] = {
            "source": row["source"],
            "target": "test_target",
            "protected_regression": "test_regression",
            "known_omissions": "Scoped public behavior; not complete upstream suite.",
        }
    (a.output / "candidate-roster.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"prepared": len(rows), "agent_calls": 0}))


if __name__ == "__main__":
    main()
