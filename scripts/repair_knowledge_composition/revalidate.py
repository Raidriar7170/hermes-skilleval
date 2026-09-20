"""Symmetric posthoc test-install repair. No new Agent or altered candidate."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from hermes_skilleval.intervention.functional_outcomes import outcomes
from hermes_skilleval.intervention.repair_checks import (
    accept_candidate,
    check_source,
    frozen_test_paths,
)
from hermes_skilleval.intervention.repair_content_study import verify_plan
from hermes_skilleval.intervention.session import dump, inventory


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_overlay(task, output):
    if (output / "manifest.json").exists():
        return
    output.mkdir(parents=True, exist_ok=False)
    patch = task / "evaluation/test.patch"
    names = frozen_test_paths(patch)
    trusted = output / "trusted-base"
    shutil.copytree(task / "base", trusted, symlinks=True)
    before = inventory(trusted)
    subprocess.run(["git", "apply", str(patch.resolve())], cwd=trusted, check=True)
    after = inventory(trusted)
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    if not changed <= set(names):
        raise ValueError("test patch contains undeclared changes")
    modes = {}
    for name in names:
        source = trusted / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(
                "deletions, links and renames are unsupported in this bounded adapter"
            )
        if any((trusted / parent).is_symlink() for parent in Path(name).parents):
            raise ValueError("unsafe trusted test parent")
        destination = output / "files" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        modes[name] = source.stat().st_mode & 0o777
    dump(
        output / "manifest.json",
        {
            "status": "POSTHOC_ACCEPTANCE_REVALIDATION",
            "test_patch_sha256": sha(patch),
            "files": inventory(output / "files"),
            "modes": modes,
            "scope": "Exact frozen test.patch paths only; production and other candidate files retained",
        },
    )


def run(private, plan):
    tasks = private / "tasks"
    verify_plan(plan, tasks, private / "knowledge")
    root = private / "study-v1"
    overlay_root = private / "test-overlays-v2"
    qualification = []
    for task in plan["tasks"]:
        if task["split"] != "dev":
            continue
        tid = task["instance_id"]
        overlay = overlay_root / tid
        build_overlay(tasks / tid, overlay)
        checks = {}
        for variant in ["base", "reference"]:
            checks[variant] = check_source(
                tasks / tid,
                tasks / tid / variant,
                private / "qualification-overlay-v2" / tid / variant,
                image=plan["image"],
                trusted_overlay=overlay,
            )
        qualified = (
            checks["base"]["target"]["valid"]
            and not checks["base"]["target"]["passed"]
            and checks["reference"]["target"]["passed"]
            and all(checks[v]["regression"]["passed"] for v in checks)
        )
        qualification.append(
            {"task_id": tid, "qualified": qualified, "variants": checks}
        )
        dump(private / "qualification-overlay-v2/results.json", {"rows": qualification})
        if not qualified:
            raise ValueError("posthoc test-install qualification failed")
    for phase in ["native", "pilot"]:
        source = root / (phase + "-results.json")
        preserved = root / (phase + "-results-v1.json")
        if not preserved.exists():
            shutil.copyfile(source, preserved)
        original = read(preserved)
        lock = read(root / "pilot-lock.json")
        if (
            original["plan_digest"] != plan["plan_digest"]
            or lock["plan_digest"] != plan["plan_digest"]
        ):
            raise ValueError("revalidation plan mismatch")
        expected = (
            {
                (t["instance_id"], "N", i)
                for t in plan["tasks"]
                if t["split"] == "dev"
                for i in (1, 2)
            }
            if phase == "native"
            else {(c["task_id"], c["arm"], c["repeat"]) for c in lock["cells"]}
        )
        actual = [(r["task_id"], r["arm"], r["repeat"]) for r in original["rows"]]
        if (
            len(actual) != len(expected)
            or set(actual) != expected
            or original["planned"] != len(expected)
        ):
            raise ValueError("original acceptance phase unfinished")
        rows = []
        for row in original["rows"]:
            tid, arm, repeat = row["task_id"], row["arm"], row["repeat"]
            cell = f"r{repeat}" if phase == "native" else f"{arm}-r{repeat}"
            run = root / phase / tid / cell
            accepted = accept_candidate(
                tasks / tid,
                run,
                run / "acceptance-v2",
                image=plan["image"],
                trusted_overlay=overlay_root / tid,
            )
            if sha(run / "acceptance/capture/candidate.patch") != sha(
                run / "acceptance-v2/capture/candidate.patch"
            ):
                raise ValueError("original candidate changed")
            result = {
                **{
                    k: row[k]
                    for k in ["task_id", "arm", "repeat", "phase", "execution"]
                },
                "checks": accepted["checks"],
                **outcomes(
                    row["execution"],
                    accepted["checks"],
                    integrity=accepted["integrity"],
                ),
            }
            rows.append(result)
            dump(
                root / (phase + "-results-v2.json"),
                {
                    "rows": rows,
                    "planned": original["planned"],
                    "plan_digest": original["plan_digest"],
                    "acceptance_version": "v2",
                    "status": "POSTHOC_ACCEPTANCE_REVALIDATION",
                    "original_results_sha256": sha(preserved),
                    "new_agent_calls": 0,
                },
            )
            print(
                json.dumps(
                    {
                        "phase": phase,
                        "revalidated": len(rows),
                        "planned": original["planned"],
                    }
                ),
                flush=True,
            )
    # Publish current acceptance only after all original candidates were rechecked.
    for phase in ["native", "pilot"]:
        shutil.copyfile(
            root / (phase + "-results-v2.json"), root / (phase + "-results.json")
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    args = p.parse_args()
    plan = read(args.plan)
    plan["plan_digest"] = sha(args.plan)
    run(args.private, plan)
