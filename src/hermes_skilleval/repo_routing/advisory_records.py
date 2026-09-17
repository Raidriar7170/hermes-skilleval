"""Zero-model recomputation of the public advisory replay evidence package."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def recompute(root):
    index = read(root / "evidence-index.json")
    for name, value in index["files"].items():
        p = root / name
        if not p.resolve().is_relative_to(root.resolve()) or sha(p) != value:
            raise ValueError("evidence changed: " + name)
    required = {"protocol.json", "runs.json", "qualification.json"}
    if not required <= set(index["files"]):
        raise ValueError("required evidence missing from index")
    protocol = read(root / "protocol.json")
    rows = read(root / "runs.json")
    qual = read(root / "qualification.json")
    expected = {r["run_id"]: r for r in protocol["schedule"]}
    if len(rows) != 32 or {r["run_id"] for r in rows} != set(expected):
        raise ValueError("full plan denominator changed")
    tests = {r["task_id"]: r["test_ids"] for r in qual["tasks"]}
    for r in rows:
        if r["result"] not in {
            "SUCCESS",
            "FUNCTIONAL_FAILURE",
            "POLICY_FAILURE",
            "TIMEOUT",
            "UNKNOWN",
            "NOT_RUN",
        }:
            raise ValueError("unknown result classification")
        if r["result"] == "TIMEOUT" and r.get("timed_out") is not True:
            raise ValueError("timeout classification lacks observed timeout")
        if r["result"] == "FUNCTIONAL_FAILURE" and r.get("provider_error_events"):
            raise ValueError("provider error is not a functional negative")
        cell = expected[r["run_id"]]
        if any(r[k] != cell[k] for k in ("task_id", "arm", "repeat", "timeout")):
            raise ValueError("cell changed")
        if (
            r.get("patch_sha256")
            and sha(root / "patches" / (r["run_id"] + ".patch")) != r["patch_sha256"]
        ):
            raise ValueError("patch mismatch")
        if r["result"] in ("SUCCESS", "FUNCTIONAL_FAILURE", "TIMEOUT"):
            required_reports = {
                "checks/" + r["run_id"] + "/" + kind + ".xml"
                for kind in ("target", "regression")
            }
            if not r.get("patch_sha256") or not required_reports <= set(index["files"]):
                raise ValueError("accepted chain lacks indexed patch/report evidence")
            if (
                r["execution_status"] != "STARTED"
                or r["patch_status"] != "RECONSTRUCTED"
                or r["policy_status"] != "PASS"
            ):
                raise ValueError("invalid acceptance chain")
            all_pass = True
            for kind in ("target", "regression"):
                cases = []
                for c in ET.parse(root / "checks" / r["run_id"] / (kind + ".xml")).iter(
                    "testcase"
                ):
                    outcome = (
                        "error"
                        if c.find("error") is not None
                        else "failed"
                        if c.find("failure") is not None
                        else "skipped"
                        if c.find("skipped") is not None
                        else "passed"
                    )
                    cases.append(
                        {
                            "id": c.attrib["classname"] + "::" + c.attrib["name"],
                            "outcome": outcome,
                        }
                    )
                if (
                    not cases
                    or sorted(c["id"] for c in cases) != tests[r["task_id"]][kind]
                    or any(c["outcome"] in ("error", "skipped") for c in cases)
                ):
                    raise ValueError("empty/incomplete trusted report")
                if cases != r["checks"][kind]["cases"]:
                    raise ValueError("report differs from result")
                all_pass &= all(c["outcome"] == "passed" for c in cases)
            if (r["result"] == "SUCCESS") != all_pass:
                raise ValueError("outcome differs from JUnit")
    counts = {
        arm: dict(Counter(r["result"] for r in rows if r["arm"] == arm))
        for arm in ("N", "F2", "T2", "J2")
    }
    paired = {}
    for tid in tests:
        values = {}
        for arm in counts:
            rs = [r for r in rows if r["task_id"] == tid and r["arm"] == arm]
            values[arm] = (
                None
                if any(r["result"] in ("UNKNOWN", "NOT_RUN") for r in rs)
                else sum(r["result"] == "SUCCESS" for r in rs) / 2
            )
        comparisons = {
            arm: "UNKNOWN"
            if values["J2"] is None or values[arm] is None
            else "WIN"
            if values["J2"] > values[arm]
            else "LOSS"
            if values["J2"] < values[arm]
            else "TIE"
            for arm in ("N", "F2", "T2")
        }
        paired[tid] = {"two_repeat_success_mean": values, "J2_comparisons": comparisons}
    usage = {}
    for arm in counts:
        rs = [
            r
            for r in rows
            if r["arm"] == arm and r.get("execution_status") == "STARTED"
        ]
        usage[arm] = {
            k: sum(r["usage"][k] for r in rs)
            if rs
            and all(
                r.get("usage") is not None and r["usage"].get(k) is not None for r in rs
            )
            else None
            for k in ("input_tokens", "cached_input_tokens", "output_tokens")
        }
        usage[arm]["agent_seconds_sum"] = sum(r.get("execution_seconds", 0) for r in rs)
        for key in (
            "package_prepare_seconds",
            "verification_seconds_sum",
            "post_agent_seconds_derived_from_mtime",
        ):
            usage[arm][key] = (
                sum(r[key] for r in rs)
                if rs and all(r.get(key) is not None for r in rs)
                else None
            )
    result = {
        "records": "MATCHED",
        "model_calls": 0,
        "planned": 32,
        "counts": counts,
        "paired": paired,
        "usage": usage,
        "independent_tasks": 4,
        "support_certification": "NOT_CLAIMED",
        "deployment_recommendation": "KEEP_NATIVE",
        "boundary": "Recomputes hash-bound public raw patches and JUnit case outcomes. Does not rerun candidate execution or prove adversarial judge isolation.",
    }
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output", type=Path, required=True, help="public evidence directory"
    )
    a = p.parse_args(argv)
    print(json.dumps(recompute(a.output), indent=2))


if __name__ == "__main__":
    main()
