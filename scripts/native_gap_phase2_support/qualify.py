"""Trusted base/reference qualification. Never send solutions to repair contexts."""

from __future__ import annotations
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
P = Path("/tmp/hermes-native-gap-phase2-private")
OLD = Path("/tmp/hermes-native-gap-phase1-private")
sys.path.insert(0, str(ROOT / "scripts/native_gap_phase1_support"))
from author_parser import parse  # noqa: E402


def qualify(iid, *, adapter="editable"):
    task = json.loads((P / "trusted-targets" / f"{iid}.json").read_text())
    out = (
        P
        / ("qualification" if adapter == "editable" else "qualification-pythonpath")
        / iid
    )
    out.mkdir(parents=True, exist_ok=True)
    if (out / "result.json").exists():
        return json.loads((out / "result.json").read_text())
    (out / "reference.patch").write_text(task["patch"])
    (out / "test.patch").write_text(task["test_patch"])
    files = sorted(
        {x[6:] for x in task["test_patch"].splitlines() if x.startswith("+++ b/")}
    )
    rows = []
    for mode in ["base", "reference"]:
        package = "pyupgrade" if "pyupgrade" in iid else "httpx"
        commands = [
            "set -e",
            "source /opt/miniconda3/bin/activate testbed",
            "cd /testbed",
            'test "$(git rev-parse HEAD)" = ' + shlex.quote(task["base_commit"]),
            (
                "python -m pip install --no-deps --no-build-isolation -e ."
                if adapter == "editable"
                else "export PYTHONPATH=/testbed"
            ),
        ]
        if mode == "reference":
            commands += ["git apply /evidence/reference.patch"]
        commands += [
            "git apply /evidence/test.patch",
            "python -c "
            + shlex.quote(
                f'import {package}; assert {package}.__file__.startswith("/testbed/"); print("IMPORT_FROM_TASK_VERIFIED")'
            ),
            task["install_config"]["test_cmd"]
            + " "
            + " ".join(map(shlex.quote, files))
            + " --maxfail=0 --junitxml=/evidence/"
            + mode
            + ".xml",
        ]
        name = "hermes-phase2-qualify-" + iid + "-" + mode
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--cpus",
            "2",
            "--memory",
            "4g",
            "-v",
            str(out) + ":/evidence",
            "--entrypoint",
            "/bin/bash",
            task["docker_image"],
            "-lc",
            "\n".join(commands),
        ]
        started = time.monotonic()
        error = None
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=300)
            log = run.stdout + run.stderr
            code = run.returncode
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ["docker", "stop", "-t", "3", name], capture_output=True, timeout=15
            )
            log = str(exc)
            code = None
            error = "QUALIFICATION_TIMEOUT"
        (out / (mode + ".log")).write_text(log)
        statuses = parse(log, OLD / "swebench-fork")
        labels = {
            k: {n: statuses.get(n, "UNKNOWN") for n in task[k]}
            for k in ["FAIL_TO_PASS", "PASS_TO_PASS"]
        }
        xml = out / (mode + ".xml")
        counts = None
        if xml.exists():
            counts = {
                k: sum(
                    int(s.get(k, "0"))
                    for s in ET.parse(xml).getroot().iter("testsuite")
                )
                for k in ["tests", "failures", "errors", "skipped"]
            }
        rows.append(
            {
                "mode": mode,
                "returncode": code,
                "error": error,
                "seconds": time.monotonic() - started,
                "command": command,
                "import_verified": "IMPORT_FROM_TASK_VERIFIED" in log,
                "author_checks": labels,
                "junit_counts": counts,
            }
        )
        (out / "progress.json").write_text(json.dumps(rows, indent=2))
    base, reference = rows
    ok = (
        base["import_verified"]
        and reference["import_verified"]
        and any(v == "FAILED" for v in base["author_checks"]["FAIL_TO_PASS"].values())
        and all(v == "PASSED" for v in base["author_checks"]["PASS_TO_PASS"].values())
        and reference["returncode"] == 0
        and all(
            v == "PASSED"
            for checks in reference["author_checks"].values()
            for v in checks.values()
        )
    )
    result = {
        "instance_id": iid,
        "qualified": ok,
        "checks": rows,
        "base_commit": task["base_commit"],
        "image": task["docker_image"],
        "adaptation": adapter
        + "; maxfail=0 to retain complete author label denominator",
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    print(
        iid,
        "QUALIFIED" if ok else "UNQUALIFIED",
        [r["junit_counts"] for r in rows],
        flush=True,
    )
    return result


if __name__ == "__main__":
    for iid in sys.argv[1:]:
        qualify(iid, adapter="pythonpath" if "2523" in iid else "editable")
