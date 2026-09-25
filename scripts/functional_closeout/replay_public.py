"""Recompute exported functional counts from raw JUnit without private resources."""

import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from hermes_skilleval.intervention.functional_closeout import STUDY, summarize_rows
from hermes_skilleval.intervention.linked_context_study import functional_label, read


def replay(repo):
    root = repo / "artifacts" / STUDY
    plan = read(repo / "configs" / STUDY / "plan.json")
    saved = read(root / "functional.json")
    names = {t["instance_id"]: t["mechanism"] for t in plan["tasks"]}
    rows = []
    for row in saved["rows"]:
        folder = (
            root
            / "functional"
            / names[row["task_id"]]
            / f"{row['arm']}-r{row['repeat']}"
        )
        result = read(folder / "result.json")
        patch = gzip.decompress((folder / "candidate.patch.gz").read_bytes())
        assert hashlib.sha256(patch).hexdigest() == result["patch_sha256"]
        labels = {}
        for kind in ("target", "regression"):
            check = result["checks"][kind]
            xml = ET.fromstring(
                gzip.decompress(
                    (folder / "checks" / kind / "junit.xml.gz").read_bytes()
                )
            )
            cases = list(xml.iter("testcase"))
            failures = sum(c.find("failure") is not None for c in cases)
            errors = sum(c.find("error") is not None for c in cases)
            skips = sum(c.find("skipped") is not None for c in cases)
            assert (len(cases), failures, errors, skips) == (
                check["cases"],
                check["failures"],
                check["errors"],
                check["skipped"],
            )
            labels[kind] = (
                "UNKNOWN"
                if not check["valid"]
                else "FAIL"
                if failures or errors
                else "PASS"
                if check["passed"]
                else "UNKNOWN"
            )
        label = functional_label(
            integrity="CONFIRMED"
            if result["integrity"] == "VERIFIED"
            else "UNCONFIRMED",
            target=labels["target"],
            protected=labels["regression"],
        )
        assert label == row["functional"]
        rows.append({**row, "functional": label})
    table, contrasts = summarize_rows(plan["tasks"], rows)
    assert table == saved["table"]
    for name, contrast in contrasts.items():
        assert all(saved["contrasts"][name][k] == v for k, v in contrast.items())
    costs = read(root / "costs.json")
    status = read(root / "status.json")
    assert (
        sum(
            c["budget_status"] == "VALID" and c["protocol_deviation"] is None
            for c in costs
        )
        == status["repair_tails_budget_protocol_valid"]
    )
    assert all(
        c["budget_status"] == "UNKNOWN_PREPARATION_COST"
        for c in costs
        if c["arm"] in {"M", "R"}
    )
    assert status["integration"] == "PARTIAL"
    assert (
        status["functional_gain_over_M"]
        == status["functional_gain_over_N"]
        == "UNKNOWN"
    )
    print(
        json.dumps(
            {
                "planned": len(rows),
                "counts": {
                    arm: {
                        label: sum(
                            r["arm"] == arm and r["functional"] == label for r in rows
                        )
                        for label in ("PASS", "FAIL", "UNKNOWN")
                    }
                    for arm in ("N", "M", "R")
                },
                "contrasts": contrasts,
                "model_calls": 0,
                "acceptance_calls": 0,
                "boundary": "Export consistency; does not independently rerun reconstruction or recover missing cost",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    replay(Path.cwd())
