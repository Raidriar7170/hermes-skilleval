"""Qualification-only normalization of source parser-truncated pytest node IDs."""

import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
from hermes_skilleval._maintenance.check import isolated
from hermes_skilleval.intervention.repair_checks import IMAGE
from hermes_skilleval.intervention.session import dump


def normalize(raw):
    return re.sub(r"/+", "/", raw.removeprefix("/app/"))


def resolve(raws, collected):
    result = set()
    mapping = {}
    for raw in raws:
        raw = normalize(raw)
        matches = (
            [raw]
            if raw in collected
            else [n for n in collected if normalize(n).startswith(raw)]
        )
        if not matches:
            raise ValueError("unresolved selector: " + raw)
        mapping[raw] = matches
        result.update(matches)
    return sorted(result), mapping


def prepare(task, output):
    meta = json.loads((task / "task.json").read_text())
    if (task / "evaluation/selectors.json").exists():
        return
    output.mkdir(parents=True, exist_ok=False)
    candidate = output / "reference-overlay"
    shutil.copytree(task / "reference", candidate, symlinks=True)
    subprocess.run(
        ["git", "apply", str((task / "evaluation/test.patch").resolve())],
        cwd=candidate,
        check=True,
        capture_output=True,
    )
    target = meta["fail_to_pass"]
    regression = meta["pass_to_pass"]
    if not regression:
        regression = [
            "test/units/plugins/strategy/test_strategy.py",
            "test/units/plugins/strategy/test_linear.py",
        ]
    files = sorted({normalize(x).split("::")[0] for x in target + regression})
    dump(output / "files.json", files)
    (output / "collect.py").write_text("""import os, shutil, json
shutil.copytree('/candidate','/tmp/repo',symlinks=True)
os.chdir('/tmp/repo')
os.environ['HOME']='/tmp'
os.environ['ANSIBLE_DEVEL_WARNING']='false'
import sys
sys.path[:0]=['/tmp/repo/lib','/tmp/repo/test/lib','/tmp/repo']
import pytest
class Capture:
 def pytest_collection_finish(self,session):
  json.dump([i.nodeid for i in session.items],open('/out/nodeids.json','w'))
raise SystemExit(pytest.main(['--collect-only','-q','-o','addopts=','-p','no:cacheprovider',*json.load(open('/out/files.json'))],plugins=[Capture()]))
""")
    rc, _ = isolated(
        IMAGE,
        [(candidate, "/candidate", "ro"), (output, "/out", "rw")],
        ["python", "/out/collect.py"],
        output,
        "collect",
    )
    if rc:
        raise ValueError("reference collection failed")
    collected = json.loads((output / "nodeids.json").read_text())
    target_ids, target_map = resolve(target, collected)
    if meta["pass_to_pass"]:
        regression_ids, regression_map = resolve(regression, collected)
    else:
        regression_ids = [
            n
            for n in collected
            if any(n.startswith(file + "::") for file in regression)
        ]
        regression_map = {"supplementary_general_regression": regression_ids}
    if not target_ids or not regression_ids or set(target_ids) & set(regression_ids):
        raise ValueError("empty or overlapping source selector groups")
    dump(
        task / "evaluation/selectors.json",
        {
            "target": target_ids,
            "regression": regression_ids,
            "source_mapping": {"target": target_map, "regression": regression_map},
            "rule": "exact nodeid else all matching full nodeid prefixes; no omitted source IDs",
            "supplementary_regression": not bool(meta["pass_to_pass"]),
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("pool", "tasks", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    for row in json.loads(a.pool.read_text())["rows"]:
        try:
            prepare(a.tasks / row["instance_id"], a.output / row["instance_id"])
            print(row["mechanism"], "RESOLVED", flush=True)
        except Exception as exc:
            print(row["mechanism"], type(exc).__name__, str(exc), flush=True)
