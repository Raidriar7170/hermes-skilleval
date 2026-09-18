"""Independent records-only verification; no model, executor or external check calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from hermes_skilleval.repo_routing.advisory_capture import inventory


def read(path):
    return json.loads(Path(path).read_text())


def verify_artifacts(row):
    run = Path(row["run"])
    execution = row["execution"]
    if (run / "execution.json").exists() and read(run / "execution.json") != execution:
        raise ValueError("execution record mismatch: " + str(run))
    checks_root = run.parent / (run.name + "-checks")
    if not (checks_root / "acceptance.json").exists():
        if row["quality"] is not None:
            raise ValueError("label without acceptance record")
        return {"status": "UNKNOWN_NO_ACCEPTANCE", "artifacts_verified": 0}
    acceptance = read(checks_root / "acceptance.json")
    if acceptance["checks"] != row["checks"]:
        raise ValueError("acceptance record mismatch")
    capture = acceptance.get("capture")
    count = 0
    if capture:
        patch = checks_root / "capture/candidate.patch"
        if hashlib.sha256(patch.read_bytes()).hexdigest() != capture["patch_sha256"]:
            raise ValueError("candidate patch changed")
        for source in (
            run / "source",
            checks_root / "capture/snapshot",
            checks_root / "reconstructed",
        ):
            if inventory(source) != capture["after"]:
                raise ValueError(
                    "captured source or reconstructed candidate changed: " + str(source)
                )
        changed = sorted(
            k
            for k in capture["before"].keys() | capture["after"].keys()
            if capture["before"].get(k) != capture["after"].get(k)
        )
        if changed != capture["changed_files"]:
            raise ValueError("changed file list mismatch")
        count += 4
    for kind in ("target", "regression"):
        check = row["checks"].get(kind)
        if check is None:
            continue
        root = checks_root / kind
        if read(root / "result.json") != check:
            raise ValueError("external check record mismatch")
        for file, digest in check["evidence_sha256"].items():
            if hashlib.sha256((root / file).read_bytes()).hexdigest() != digest:
                raise ValueError("check artifact changed: " + file)
            count += 1
        if (root / "junit.xml").exists():
            cases = []
            for case in ET.parse(root / "junit.xml").iter("testcase"):
                outcome = (
                    "error"
                    if case.find("error") is not None
                    else "failed"
                    if case.find("failure") is not None
                    else "skipped"
                    if case.find("skipped") is not None
                    else "passed"
                )
                cases.append(
                    {
                        "id": case.attrib["classname"] + "::" + case.attrib["name"],
                        "outcome": outcome,
                    }
                )
            expected = read(root / "collected.json")
            valid = (
                bool(expected)
                and sorted(c["id"] for c in cases) == sorted(expected)
                and all(c["outcome"] not in ("error", "skipped") for c in cases)
            )
            passed = (
                valid
                and check["returncode"] == 0
                and all(c["outcome"] == "passed" for c in cases)
            )
            if (
                cases != check["cases"]
                or valid != check["valid"]
                or passed != check["passed"]
            ):
                raise ValueError("independent JUnit recomputation mismatch")
    fork_file = run / "fork.json"
    if fork_file.exists():
        fork = read(fork_file)
        if (
            not fork["matched"]
            or fork["visible_prefix_sha256"] != fork["expected_prefix_sha256"]
        ):
            raise ValueError("fork prefix mismatch")
    return {"status": "VERIFIED", "artifacts_verified": count}
