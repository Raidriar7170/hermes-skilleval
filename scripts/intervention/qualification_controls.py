"""Behavioral negative controls for already-green bases; never training labels."""

import argparse
import json
import shutil
from pathlib import Path
from hermes_skilleval._maintenance.check import check
from hermes_skilleval.repository_profile import RepositoryProfile
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
mutations = [
    (
        "sqlite-utils-issue-234",
        "sqlite_utils/db.py",
        'if alter and (" column" in e.args[0]):',
        'if False and alter and (" column" in e.args[0]):',
    ),
    (
        "csvkit-issue-1264",
        "csvkit/utilities/csvcut.py",
        "    def main(self):",
        '    def main(self):\n        if self.args.columns and self.args.columns.endswith("-"):\n            self.args.columns = self.args.columns[:-1]',
    ),
    (
        "csvkit-issue-1263",
        "csvkit/utilities/csvgrep.py",
        "        patterns = {column_id: pattern for column_id in column_ids}",
        '        patterns = {column_id: "__absent_match__" if "-" in self.args.columns else pattern for column_id in column_ids}',
    ),
]
results = []
for tid, file, old, new in mutations:
    root = a.tasks / tid
    candidate = a.output / tid / "candidate"
    shutil.copytree(root / "base", candidate, symlinks=True)
    path = candidate / file
    s = path.read_text()
    assert old in s
    path.write_text(s.replace(old, new))
    m = json.loads((root / "task.json").read_text())
    result = check(
        candidate,
        root / "trusted",
        a.output / tid / "checks",
        "test_target or test_regression",
        profile=RepositoryProfile(**m["profile"]),
        test_file="test_behavior.py",
        timeout=120,
    )
    cases = result.get("cases", [])
    qualified = (
        result["valid"]
        and any("test_target" in c["id"] and c["outcome"] == "failed" for c in cases)
        and all(c["outcome"] == "passed" for c in cases if "test_regression" in c["id"])
    )
    results.append(
        {
            "task_id": tid,
            "mutation": {"file": file, "old": old, "new": new},
            "qualified_negative": qualified,
            "check": result,
        }
    )
    dump(a.output / "controls.json", results)
    print(tid, qualified, flush=True)
assert all(r["qualified_negative"] for r in results)
