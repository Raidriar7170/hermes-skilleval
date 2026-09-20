"""Freeze qualified sources and uniform accessible documentation before sampling."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.diagnostic import inventory_digest as inventory


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private", type=Path, required=True)
    a = p.parse_args()
    root = Path.cwd()
    private = a.private
    plan_path = root / "configs/task-skill-failure-diagnostic-v1/plan.json"
    plan = json.loads(plan_path.read_text())
    if plan["status"] == "FROZEN":
        raise ValueError("already frozen")
    final = private / "tasks-frozen"
    final.mkdir()
    first = json.loads((private / "qualification-v1/qualification.json").read_text())[
        "rows"
    ]
    repair = json.loads((private / "qualification-v2/qualification.json").read_text())[
        "rows"
    ]
    bom = json.loads((private / "qualification-v3/qualification.json").read_text())[
        "rows"
    ]
    qualifiers = {r["task_id"]: r for r in first}
    qualifiers.update({r["task_id"]: r for r in repair + bom})
    pool = json.loads(
        (root / "configs/task-skill-failure-diagnostic-v1/source-pool.json").read_text()
    )
    tasks = []
    for row in pool["rows"]:
        if row["qualification"] == "SOURCE_EXCLUDED":
            continue
        q = qualifiers[row["task_id"]]
        if q["status"] != "BASE_RED_REFERENCE_GREEN":
            continue
        source = (
            private
            / (
                "qualification-repair-tasks"
                if row["fix_commit"].startswith("80437fd")
                else "qualification-bom-tasks"
                if row["fix_commit"].startswith("19810a3")
                else "tasks-v1"
            )
            / row["task_id"]
        )
        task = final / row["task_id"]
        shutil.copytree(source, task)
        docs = task / "public-docs"
        docs.mkdir()
        for name in ("docs", "README.md", "README.rst"):
            f = task / "base" / name
            if f.is_dir():
                shutil.copytree(f, docs / name)
            elif f.is_file():
                shutil.copyfile(f, docs / name)
        request = task / "request.txt"
        request.write_text(
            request.read_text()
            + "\nThe checked-out base documentation is also available read-only at /workspace/public-docs. Use the same normal tools and native skills as usual.\n"
        )
        tasks.append(
            {
                **row,
                "qualification": "BASE_RED_REFERENCE_GREEN",
                "files": {
                    s: inventory(task / s)
                    for s in ("base", "trusted", "reference", "public-docs")
                },
                "request_sha256": sha(request),
                "task_sha256": sha(task / "task.json"),
            }
        )
    plan.update(
        status="FROZEN",
        tasks=tasks,
        assets={
            "skills": inventory(root / "configs/conditional-applicability-v1/skills"),
            "payloads": inventory(
                root / "configs/adaptive-skill-intervention-v1/payloads"
            ),
        },
        image="hermes-asi-executor:v1",
        image_id=subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                "hermes-asi-executor:v1",
                "--format",
                "{{.Id}}",
            ],
            text=True,
        ).strip(),
        checkpoint_rule="First completed boundary with task-mechanism-matched public functional failure; else first delivery E2. No budget-threshold E2. E0 recorded as origin only, not included in main panel.",
        source_preparation_model_calls=0,
    )
    dump(plan_path, plan)
    public = root / "artifacts/task-skill-failure-diagnostic-v1"
    dump(
        public / "qualification.json",
        {
            "attempt_1": first,
            "attempt_2": repair,
            "attempt_3": bom,
            "pre_sampling_repair": "csvkit 80437fd: correct excluded_columns parameter; numeric reverse range replaced by three-part date-like invalid identifier. Preserve both qualification attempts.",
            "admitted": [r["task_id"] for r in tasks],
        },
    )
    print(
        json.dumps(
            {
                "frozen_tasks": len(tasks),
                "native_planned": 2 * len(tasks),
                "plan_sha256": sha(plan_path),
            }
        )
    )


if __name__ == "__main__":
    main()
