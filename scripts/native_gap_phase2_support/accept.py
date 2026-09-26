"""Post-matrix trusted acceptance of original captured candidates only."""

from __future__ import annotations
import hashlib
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
C = ROOT / "configs/native-gap-phase2-same-library-v1"
sys.path.insert(0, str(ROOT / "scripts/native_gap_phase1_support"))
from author_parser import parse  # noqa: E402


def accept(item):
    ident = item["id"]
    source = P / "runs" / ident
    out = P / "checks" / ident
    out.mkdir(parents=True, exist_ok=True)
    if (out / "result.json").exists():
        return json.loads((out / "result.json").read_text())
    row = {
        "id": ident,
        "instance_id": item["instance_id"],
        "functional_result": "UNKNOWN",
    }
    attempt = json.loads((source / "result.json").read_text())
    capture = attempt.get("parent_cleanup", {})
    if not capture.get("no_running_tool_confirmation") or not capture.get(
        "candidate_captured"
    ):
        row["reason"] = "candidate not captured after confirmed stop"
        (out / "result.json").write_text(json.dumps(row, indent=2))
        return row
    patch = (source / "candidate.patch").read_bytes()
    if attempt.get("model_started") is not True and not patch:
        row["reason"] = (
            "No positively observed generation and no changed candidate; not an agent functional failure"
        )
        (out / "result.json").write_text(json.dumps(row, indent=2))
        return row
    identity = hashlib.sha256(patch).hexdigest()
    assert identity == capture["candidate_identity"]["sha256"], (
        "candidate identity changed"
    )
    task = json.loads(
        (P / "trusted-targets" / f"{item['instance_id']}.json").read_text()
    )
    (out / "candidate.patch").write_bytes(patch)
    (out / "test.patch").write_text(task["test_patch"])
    files = sorted(
        {x[6:] for x in task["test_patch"].splitlines() if x.startswith("+++ b/")}
    )
    for f in files:
        assert not Path(f).is_absolute() and ".." not in Path(f).parts
    package = "pyupgrade" if "pyupgrade" in item["instance_id"] else "httpx"
    commands = [
        "set -e",
        "source /opt/miniconda3/bin/activate testbed",
        "export PYTHONPATH=/testbed",
        "cd /testbed",
        'test "$(git rev-parse HEAD)" = ' + shlex.quote(task["base_commit"]),
    ]
    if patch:
        commands += [
            "git apply --check /evidence/candidate.patch",
            "git apply /evidence/candidate.patch",
        ]
    for f in files:
        ref = shlex.quote(task["base_commit"] + ":" + f)
        commands.append(
            "if git cat-file -e "
            + ref
            + " 2>/dev/null; then git checkout "
            + shlex.quote(task["base_commit"])
            + " -- "
            + shlex.quote(f)
            + "; else rm -f -- "
            + shlex.quote(f)
            + "; fi"
        )
    commands += [
        "git apply /evidence/test.patch",
        "python -c "
        + shlex.quote(
            f'import {package}; assert {package}.__file__.startswith("/testbed/"); print("IMPORT_FROM_TASK_VERIFIED")'
        ),
        task["install_config"]["test_cmd"]
        + " "
        + " ".join(map(shlex.quote, files))
        + " --maxfail=0 --junitxml=/evidence/candidate.xml",
    ]
    name = "hermes-phase2-check-" + ident.lower()
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
        "--memory",
        "4g",
        "--cpus",
        "2",
        "-v",
        str(out) + ":/evidence",
        "--entrypoint",
        "/bin/bash",
        item["image_id"],
        "-lc",
        "\n".join(commands),
    ]
    started = time.monotonic()
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
    (out / "candidate.log").write_text(log)
    statuses = parse(log, OLD / "swebench-fork")
    labels = {
        k: {n: statuses.get(n, "UNKNOWN") for n in task[k]}
        for k in ["FAIL_TO_PASS", "PASS_TO_PASS"]
    }
    xml = out / "candidate.xml"
    counts = None
    if xml.exists():
        counts = {
            k: sum(
                int(s.get(k, "0")) for s in ET.parse(xml).getroot().iter("testsuite")
            )
            for k in ["tests", "failures", "errors", "skipped"]
        }
    valid_scope = counts is not None and "IMPORT_FROM_TASK_VERIFIED" in log
    if valid_scope and any(
        v == "FAILED" for checks in labels.values() for v in checks.values()
    ):
        result = "FAIL"
    elif (
        valid_scope
        and code == 0
        and all(v == "PASSED" for checks in labels.values() for v in checks.values())
    ):
        result = "PASS"
    else:
        result = "UNKNOWN"
    row.update(
        functional_result=result,
        candidate_sha256=identity,
        candidate_bytes=len(patch),
        returncode=code,
        offline_seconds=time.monotonic() - started,
        author_label_checks=labels,
        junit_counts=counts,
        import_verified="IMPORT_FROM_TASK_VERIFIED" in log,
        command=command,
        test_patch_sha256=hashlib.sha256(task["test_patch"].encode()).hexdigest(),
    )
    (out / "result.json").write_text(json.dumps(row, indent=2) + "\n")
    print(ident, result, counts, flush=True)
    return row


def main():
    from integrity import verify_private_assets

    verify_private_assets(json.loads((C / "freeze.json").read_text()))
    plan = json.loads((C / "plan.json").read_text())
    terminal = json.loads((P / "all-repair-calls-terminal.json").read_text())
    assert terminal["ids"] == [i["id"] for i in plan["order"]]
    # Refuse hidden feedback before all registered repair supervisors have ended.
    for item in plan["order"]:
        result = json.loads((P / "runs" / item["id"] / "result.json").read_text())
        assert result.get("parent_cleanup", {}).get("no_running_tool_confirmation")
    rows = [accept(item) for item in plan["order"]]
    (P / "trusted-results.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
