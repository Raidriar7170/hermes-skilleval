"""Verify trusted overlay installation after ordinary candidate test edits."""

import argparse
from pathlib import Path
import shutil

from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.relation_store import atomic_json
from hermes_skilleval.intervention.repair_checks import install_test_overlay

p = argparse.ArgumentParser()
for name in ("plan", "tasks", "overlays", "output"):
    p.add_argument("--" + name, type=Path, required=True)
a = p.parse_args()
rows = []
for task in read(a.plan)["tasks"]:
    tid = task["instance_id"]
    out = a.output / tid
    if out.exists():
        raise ValueError("Preflight exists; preserve original evidence")
    source = out / "candidate"
    shutil.copytree(a.tasks / tid / "base", source, symlinks=True)
    manifest = read(a.overlays / tid / "manifest.json")
    for name in manifest["files"]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        path.write_text("# Candidate replaced a test during maintenance.\n")
    install_test_overlay(
        source,
        a.overlays / tid,
        out,
        expected_patch=a.tasks / tid / "evaluation/test.patch",
    )
    evidence = read(out / "test-overlay.json")
    rows.append(
        {
            "task_id": tid,
            "outside_overlay_unchanged": evidence["outside_overlay_unchanged"],
            "status": "INSTALL_VERIFIED",
            "functional_assertions": "NOT_RUN",
        }
    )
atomic_json(a.output / "result.json", {"rows": rows, "repair_executions": 0})
print(rows)
