"""Recompute public qualification decisions from exported JUnit, without models."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def cases(path):
    rows = []
    for case in ET.parse(path).iter("testcase"):
        outcome = "passed"
        for tag, value in [
            ("failure", "failed"),
            ("error", "error"),
            ("skipped", "skipped"),
        ]:
            if case.find(tag) is not None:
                outcome = value
        rows.append(
            {
                "id": case.attrib["classname"] + "::" + case.attrib["name"],
                "outcome": outcome,
            }
        )
    return sorted(rows, key=lambda item: item["id"])


def recompute(index):
    data = json.loads(index.read_text())
    decisions = []
    for attempt in data["attempts"]:
        observed = {}
        for name, cell in attempt["cells"].items():
            path = index.parent / cell["junit"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != cell["junit_sha256"]:
                raise ValueError("JUnit digest mismatch: " + str(path))
            actual = cases(path)
            valid = (
                bool(actual)
                and [c["id"] for c in actual] == cell["collected_ids"]
                and all(c["outcome"] not in ("error", "skipped") for c in actual)
                and cell["installation_succeeded"]
                and cell["cli_canary_succeeded"]
            )
            passed = valid and all(c["outcome"] == "passed" for c in actual)
            if valid != cell["valid"] or passed != cell["passed"]:
                raise ValueError(
                    "Cell verdict mismatch: " + attempt["task_id"] + ":" + name
                )
            observed[name] = {
                "valid": valid,
                "passed": passed,
                "ids": [c["id"] for c in actual],
            }
        qualified = (
            all(c["valid"] for c in observed.values())
            and not observed["base-target"]["passed"]
            and all(
                observed[n]["passed"]
                for n in ["reference-target", "base-regression", "reference-regression"]
            )
            and all(
                observed["base-" + k]["ids"] == observed["reference-" + k]["ids"]
                for k in ["target", "regression"]
            )
        )
        if qualified != attempt["qualified"]:
            raise ValueError("Qualification verdict mismatch: " + attempt["task_id"])
        decisions.append(
            {
                "task_id": attempt["task_id"],
                "attempt": attempt["attempt"],
                "qualified": qualified,
                "active": attempt["active"],
            }
        )
    active = [row for row in decisions if row["active"]]
    result = {
        "candidate_families": len(active),
        "qualification_attempts": len(decisions),
        "qualified_families": sum(row["qualified"] for row in active),
        "decisions": decisions,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("artifacts/repo-aware-routing/task-qualification/index.json"),
    )
    args = parser.parse_args()
    print(json.dumps(recompute(args.index), indent=2))
