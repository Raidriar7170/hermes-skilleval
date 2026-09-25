"""Reconstruct candidate in fresh qualified image; restore official test files."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET

P = Path(os.environ.get("NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"))
results_path = P / "candidate-verification-results.json"
results = json.loads(results_path.read_text()) if results_path.exists() else []
for ident, iid, image in [
    (
        "smoke-pyupgrade330",
        "asottile__pyupgrade-330",
        "swerebench/sweb.eval.x86_64.asottile_1776_pyupgrade-330",
    ),
    ("smoke-httpx386", "encode__httpx-386", "hermes-native-gap-httpx386:v1"),
]:
    if any(r["instance_id"] == iid for r in results):
        continue
    source = P / ident
    if not (source / "result.json").exists():
        continue
    task = json.loads((P / "trusted-targets" / (iid + ".json")).read_text())
    attempt = json.loads((source / "result.json").read_text())
    if not attempt.get("no_running_tool_confirmation"):
        raise RuntimeError("Cannot verify live candidate")
    out = P / "candidate-verification" / iid
    out.mkdir(parents=True, exist_ok=False)
    patch = (source / "candidate.patch").read_bytes()
    (out / "candidate.patch").write_bytes(patch)
    (out / "test.patch").write_text(task["test_patch"])
    files = sorted(
        {
            line[6:]
            for line in task["test_patch"].splitlines()
            if line.startswith("+++ b/")
        }
    )
    commands = [
        "set -e",
        "source /opt/miniconda3/bin/activate testbed",
        "cd /testbed",
        'test "$(git rev-parse HEAD)" = ' + shlex.quote(task["base_commit"]),
        "git apply --check /evidence/candidate.patch",
        "git apply /evidence/candidate.patch",
        "git checkout "
        + shlex.quote(task["base_commit"])
        + " -- "
        + " ".join(map(shlex.quote, files)),
        "git apply /evidence/test.patch",
        task["install_config"]["test_cmd"]
        + " "
        + " ".join(map(shlex.quote, files))
        + " --junitxml=/evidence/candidate.xml",
    ]
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "-v",
        str(out) + ":/evidence",
        "--entrypoint",
        "/bin/bash",
        image,
        "-lc",
        "\n".join(commands),
    ]
    started = time.monotonic()
    run = subprocess.run(command, capture_output=True, text=True, timeout=300)
    log = run.stdout + run.stderr
    (out / "candidate.log").write_text(log)
    xml = out / "candidate.xml"
    counts = None
    if xml.exists():
        suites = ET.parse(xml).getroot()
        counts = {
            k: sum(int(s.get(k, "0")) for s in suites.iter("testsuite"))
            for k in ["tests", "failures", "errors", "skipped"]
        }
    from author_parser import parse

    statuses = parse(log, P / "swebench-fork")
    labels = {
        k: {name: statuses.get(name, "UNKNOWN") for name in task[k]}
        for k in ["FAIL_TO_PASS", "PASS_TO_PASS"]
    }
    row = {
        "instance_id": iid,
        "candidate_sha256": hashlib.sha256(patch).hexdigest(),
        "returncode": run.returncode,
        "seconds": time.monotonic() - started,
        "junit_counts": counts,
        "author_label_checks": labels,
        "candidate_applied": xml.exists(),
        "functional_result": "PASS"
        if run.returncode == 0
        and all(v == "PASSED" for checks in labels.values() for v in checks.values())
        else (
            "FAIL"
            if counts
            and any(
                v == "FAILED" for checks in labels.values() for v in checks.values()
            )
            else "UNKNOWN"
        ),
        "command": command,
        "test_patch_sha256": hashlib.sha256(task["test_patch"].encode()).hexdigest(),
    }
    results.append(row)
    (P / "candidate-verification-results.json").write_text(
        json.dumps(results, indent=2)
    )
    print(iid, row["functional_result"], counts, flush=True)
