"""Materialize qualified task candidates without calling an Agent or scoring policies."""

import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from task_contracts import (
    TRAIN,
    DEV,
    TEST,
    CLARIFY,
    TARGET,
    CSV_DIFF_TARGET,
    CSVKIT_TARGET,
    REGRESSION,
)
from hermes_skilleval.repository_profile import SQLITE_UTILS, CSVKIT, RepositoryProfile
from hermes_skilleval.intervention.session import dump, IMAGE

p = argparse.ArgumentParser()
p.add_argument("--previous", type=Path, required=True)
p.add_argument("--project", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
old = a.previous / "conditional-applicability-v1"
new = a.previous / "frozen-independent-validation-v1"
records = {}
for name, private in [
    ("conditional-applicability-v1", old),
    ("frozen-independent-validation-v1", new),
]:
    for t in json.loads((a.project / "artifacts" / name / "tasks.json").read_text()):
        records[t["task_id"]] = (t, private)
public = []
for split, ids in [("train", TRAIN), ("dev", DEV), ("test", TEST)]:
    for tid in ids:
        root = a.output / tid
        if tid in DEV:
            shutil.copytree(
                a.previous / "advisory-utility-replay-v1/tasks-v2" / tid, root
            )
            m = json.loads((root / "task.json").read_text())
            m["split"] = split
        else:
            t, private = records[tid]
            root.mkdir()
            shutil.copytree(private / "snapshots" / tid, root / "base", symlinks=True)
            repo = tid.split("-issue-")[0]
            number = int(tid.split("-issue-")[1])
            upstream = old / "upstreams" / repo
            ref = subprocess.check_output(
                ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
            ).strip()
            archive = subprocess.check_output(
                ["git", "-C", str(upstream), "archive", ref]
            )
            (root / "reference").mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(root / "reference", filter="data")
            if repo == "sqlite-utils":
                profile = SQLITE_UTILS.to_dict()
                target = TARGET[number]
            elif repo == "csvkit":
                profile = CSVKIT.to_dict()
                target = CSVKIT_TARGET[number]
            else:
                profile = RepositoryProfile(
                    "simonw/csv-diff",
                    {"csv_diff": "."},
                    "csv_diff.cli",
                    "cli",
                    "csv-diff",
                    IMAGE,
                    ("csv_diff", "tests"),
                ).to_dict()
                target = CSV_DIFF_TARGET[number]
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
            m = {
                "task_id": tid,
                "repository": t["repository"],
                "split": split,
                "base_commit": t["source_revision"],
                "reference_commit": ref,
                "profile": profile,
                "trusted_test_file": "test_behavior.py",
                "target_selector": "test_target",
                "regression_selector": "test_regression",
                "request_ref": t["request_ref"],
                "mechanism": t.get("repair_group_id"),
            }
            trusted = root / "trusted"
            trusted.mkdir()
            (trusted / "pytest.ini").write_text("[pytest]\n")
            code = "import pytest\n\ndef test_target(tmp_path):\n" + "".join(
                "    " + line + "\n" for line in target.strip().splitlines()
            )
            code += "\ndef test_regression(tmp_path):\n" + "".join(
                "    " + line + "\n" for line in REGRESSION[repo].strip().splitlines()
            )
            (trusted / "test_behavior.py").write_text(code)
            (root / "request.txt").write_text(t["request"])
        if tid in CLARIFY:
            with (root / "request.txt").open("a") as f:
                f.write(
                    "\n\nASI task scope clarification (public, frozen before execution):\n"
                    + CLARIFY[tid]
                    + "\n"
                )
        dump(root / "task.json", m)
        public.append(
            {
                "task_id": tid,
                "split": split,
                "request": (root / "request.txt").read_text(),
                "base_commit": m["base_commit"],
                "mechanism": m.get("mechanism"),
                "source": m.get("request_ref"),
                "qualification": "PENDING",
            }
        )
dump(a.output / "candidate-roster.json", public)
print(
    json.dumps(
        {
            "train": len(TRAIN),
            "dev": len(DEV),
            "test": len(TEST),
            "status": "QUALIFICATION_PENDING",
        }
    )
)
