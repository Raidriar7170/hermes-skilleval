"""Recover the four existing repair assets into an independent study namespace."""

import argparse
import ast
import hashlib
import json
import shutil
from pathlib import Path

from hermes_skilleval.repo_routing.advisory_capture import inventory
from hermes_skilleval.repository_profile import SQLITE_UTILS, CSVKIT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--image", required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    project = a.project.resolve()
    records = json.loads(
        (project / "artifacts/frozen-independent-validation-v1/tasks.json").read_text()
    )
    ids = [
        "sqlite-utils-issue-344",
        "sqlite-utils-issue-400",
        "sqlite-utils-issue-368",
        "csvkit-issue-1225",
    ]
    oldq = json.loads(
        (
            project
            / "artifacts/frozen-independent-validation-v1/repair-qualification.json"
        ).read_text()
    )
    new = []
    for tid in ids:
        t = next(t for t in records if t["task_id"] == tid)
        root = a.output / tid
        root.mkdir()
        source = a.previous / "snapshots" / tid
        shutil.copytree(source, root / "base")
        shutil.copytree(
            a.previous / "qualification" / tid / "reference", root / "reference"
        )
        check = a.previous / "qualification" / tid / "check.py"
        expected = next(
            r["check_sha256"] for r in oldq["records"] if r["task_id"] == tid
        )
        assert hashlib.sha256(check.read_bytes()).hexdigest() == expected
        # Retain original target/regression statements; only substitute child launch
        # and immutable fixture paths so candidate imports cannot resolve to old code.
        snippets = [
            n.args[0].value
            for n in ast.walk(ast.parse(check.read_text()))
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "exec"
        ]
        assert len(snippets) == 2
        trusted = root / "trusted"
        trusted.mkdir()
        (trusted / "pytest.ini").write_text("[pytest]\n")
        bootstrap = """import importlib.abc,importlib.machinery,sys,runpy
class Candidate(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('sqlite_utils','csvkit'):
   spec=importlib.machinery.PathFinder.find_spec(fullname,['/input'])
   if spec is None:raise ImportError(fullname)
   return spec
sys.meta_path.insert(0,Candidate())
"""
        helper = (
            "import subprocess,sys,json,pytest\nBOOTSTRAP=" + repr(bootstrap) + "\n"
        )
        helper += """def candidate_run(args, **kwargs):
    tail = args[3:] if args[:3] == [sys.executable, '-m', 'sqlite_utils'] else args[1:]
    if args[0] == 'in2csv':
        body = "from csvkit.utilities.in2csv import launch_new_instance; launch_new_instance()"
    elif args[0] == 'sqlite-utils':
        body = "from sqlite_utils.cli import cli; cli()"
    else:
        body = "runpy.run_module('sqlite_utils',run_name='__main__')"
    code = BOOTSTRAP + '\\nsys.argv=' + repr([args[0],*tail]) + '\\n' + body
    return subprocess.run([sys.executable,'-I','-c',code], **kwargs)
"""
        for kind, code in zip(["target", "regression"], snippets):
            code = code.replace("subprocess.run(", "candidate_run(").replace(
                "/opt/source/examples/dummy.xlsx", "/trusted/dummy.xlsx"
            )
            helper += (
                "\ndef test_"
                + kind
                + "(tmp_path, monkeypatch):\n    monkeypatch.chdir(tmp_path)\n    try:\n        exec("
                + repr(code)
                + ", globals(), {})\n    except Exception as exc:\n        pytest.fail(str(exc))\n"
            )
        (trusted / "test_behavior.py").write_text(helper)
        if tid.startswith("csvkit"):
            shutil.copy2(root / "base/examples/dummy.xlsx", trusted / "dummy.xlsx")
        profile = (CSVKIT if tid.startswith("csvkit") else SQLITE_UTILS).to_dict()
        profile["image"] = a.image
        profile["file_policy"] = {
            "version": "operations-v1",
            "rules": [
                {
                    "path": s,
                    "operations": ["add", "modify", "delete"],
                    "max_bytes": 1000000,
                }
                for s in profile["writable_roots"]
            ],
        }
        task = {
            "task_id": tid,
            "repository": t["repository"],
            "split": "exploratory",
            "base_commit": t["source_revision"],
            "public_request_sha256": t["request_sha256"],
            "profile": profile,
            "trusted_test_file": "test_behavior.py",
            "target_selector": "test_target",
            "regression_selector": "test_regression",
            "legacy_check_sha256": expected,
            "check_wrapper": "same statements with candidate-only child imports and controller-owned XLSX fixture",
        }
        (root / "task.json").write_text(json.dumps(task, indent=2) + "\n")
        (root / "request.txt").write_text(t["request"])
        assert (
            hashlib.sha256((root / "request.txt").read_bytes()).hexdigest()
            == t["request_sha256"]
        )
        new.append(
            {
                "task_id": tid,
                "request": t["request"],
                "context": t["context"],
                "repository": t["repository"],
                "source_revision": t["source_revision"],
                "source_manifest": inventory(root / "base"),
                "old_check_sha256": expected,
                "wrapper_sha256": hashlib.sha256(
                    (trusted / "test_behavior.py").read_bytes()
                ).hexdigest(),
            }
        )
    (a.output / "public-tasks.json").write_text(json.dumps(new, indent=2) + "\n")
    print(json.dumps({"tasks": ids, "image": a.image}))


if __name__ == "__main__":
    main()
