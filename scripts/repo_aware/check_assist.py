"""Check the separate product smoke's public artifact and outcome bindings."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from recompute_execution import checked_file
from hermes_skilleval._maintenance.assist_checks import paired_results
from hermes_skilleval.repo_routing.gate import decide


def check_assist(root: Path):
    folder = root / "assist"
    record = json.loads((folder / "record.json").read_text())
    seal = json.loads((root / "gate/freeze.json").read_text())
    model = json.loads((root / "gate/model.json").read_text())
    launch = record["launch"]
    if not (
        launch["time"] > seal["frozen_at"]
        and launch["gate_sha256"] == seal["gate_sha256"]
        and record["r_version"] == launch["r_version"] == seal["r_version"]
    ):
        raise ValueError("Assist gate launch binding mismatch")
    result = record["result"]
    execution = record["execution"]
    if result["engineering"] == "COMPLETE" and not (
        execution["execution_status"] == "STARTED"
        and execution["exit_code"] == 0
        and execution["timed_out"] is False
        and execution["cleanup_confirmed"] is True
        and result["source_unchanged"] is True
        and result["policy_status"] == "ACCEPTED"
        and result["rebuild"] == "MATCHED_CAPTURE"
        and result["errors"] == []
    ):
        raise ValueError("Assist completion evidence mismatch")
    if result["resolved"] is not None:
        raise ValueError("Assist cannot claim historical resolution")
    routing = result["routing"]
    decision = decide(
        record["features"],
        model,
        record["r_version"],
        supported=record["context_supported"],
        resources=record["heavy_available"],
    )
    if decision != routing["decision"] or routing["action"] != decision["action"]:
        raise ValueError("Assist gate decision mismatch")
    if routing["action"] in ("N", "F") and any(routing["calls"].values()):
        raise ValueError("Assist cheap branch invoked heavy model")
    checked_file(folder, "candidate.patch", result["patch"]["sha256"])
    groups = {}
    for phase, items in record["check_evidence"].items():
        groups[phase] = {}
        for name, item in items.items():
            path = checked_file(folder, item["path"], item["sha256"])
            cases = []
            for case in ET.parse(path).iter("testcase"):
                outcome = next(
                    (
                        value
                        for tag, value in (
                            ("error", "error"),
                            ("failure", "failed"),
                            ("skipped", "skipped"),
                        )
                        if case.find(tag) is not None
                    ),
                    "passed",
                )
                cases.append(
                    {
                        "id": case.attrib["classname"] + "::" + case.attrib["name"],
                        "outcome": outcome,
                    }
                )
            actual = sorted(c["id"] for c in cases)
            valid = (
                bool(actual)
                and actual == sorted(item["collected_ids"])
                and all(c["outcome"] not in ("error", "skipped") for c in cases)
            )
            valid = valid and all(
                item[k] == 0
                for k in ("build_returncode", "cli_returncode", "collection_returncode")
            )
            passed = (
                valid
                and item["returncode"] == 0
                and all(c["outcome"] == "passed" for c in cases)
            )
            groups[phase][name] = {"cases": cases, "valid": valid, "passed": passed}
    paired = paired_results(
        record["checks_config"], groups["baseline"], groups["candidate"]
    )
    for key in ("checks", "requirements", "resolved"):
        if paired[key] != result[key]:
            raise ValueError("Assist public check result mismatch")
    if (
        record["execution"]["run_id"] != result["run_id"]
        or record["execution"]["arm"] != routing["action"]
    ):
        raise ValueError("Assist actual execution identity mismatch")
    return {
        "assist_checked": True,
        "resolved": None,
        "engineering": result["engineering"],
    }
