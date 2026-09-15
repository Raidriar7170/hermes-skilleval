"""Independently verify an explicit saved patch; no Agent execution."""

import argparse
import hashlib
import json
from pathlib import Path
from hermes_skilleval.repository_profile import profile_for, validate_changes
from hermes_skilleval._maintenance.check import check
from hermes_skilleval._maintenance.finalize import binding
from hermes_skilleval.repository_maintenance import manifest, rebuild, mode_manifest

p = argparse.ArgumentParser()
p.add_argument("--task-root", type=Path, required=True)
p.add_argument("--qualification", type=Path, required=True)
p.add_argument("--patch", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError("preserve old verification")
task = json.loads((a.task_root / "task.json").read_text())
q = json.loads(a.qualification.read_text())
if (
    not q["qualified"]
    or q["qualification_binding"] != binding(a.task_root)
    or manifest(a.task_root / "base") != q["base_manifest"]
):
    raise ValueError("qualification mismatch")
if any(task[k] != q[k] for k in ["task_id", "base_commit"]):
    raise ValueError("task mismatch")
a.output.mkdir(parents=True)
r = {
    "task_id": task["task_id"],
    "base_commit": task["base_commit"],
    "patch_sha256": hashlib.sha256(a.patch.read_bytes()).hexdigest(),
    "patch_applies": False,
    "verifier_valid": False,
    "resolved": None,
}
try:
    rebuild(a.task_root / "base", a.patch, a.output / "rebuilt")
    r["patch_applies"] = True
    if task.get("profile"):
        before = manifest(a.task_root / "base")
        after = manifest(a.output / "rebuilt")
        before_modes = mode_manifest(a.task_root / "base", before)
        after_modes = mode_manifest(a.output / "rebuilt", after)
        validate_changes(
            profile_for(task),
            [
                k
                for k in before.keys() | after.keys()
                if before.get(k) != after.get(k)
                or before_modes.get(k) != after_modes.get(k)
            ],
        )
    cells = {
        kind: check(
            a.output / "rebuilt",
            a.task_root / "trusted",
            a.output / kind,
            task[kind + "_selector"],
            test_file=task["trusted_test_file"],
            profile=profile_for(task),
        )
        for kind in ["target", "regression"]
    }
    r["verifier_valid"] = all(
        v["valid"] and sorted(x["id"] for x in v["cases"]) == q["test_ids"][k]
        for k, v in cells.items()
    )
    r["resolved"] = (
        all(v["passed"] for v in cells.values()) if r["verifier_valid"] else None
    )
except Exception as exc:
    r["error"] = str(exc)
(a.output / "result.json").write_text(json.dumps(r, indent=2) + "\n")
print(json.dumps(r, indent=2))
