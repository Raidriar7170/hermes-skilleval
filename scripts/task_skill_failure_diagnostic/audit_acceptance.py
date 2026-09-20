"""Preserve raw labels and publish a conservative, records-only selection gate."""

import argparse
from pathlib import Path

from hermes_skilleval.intervention.diagnostic import (
    acceptance_audit,
    read,
    select_panel,
    sha,
)
from hermes_skilleval.intervention.session import dump


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    a = p.parse_args()
    plan = read(a.plan)
    if read(a.native / "identity.json") != {"plan_sha256": sha(a.plan)}:
        raise ValueError("native plan identity mismatch")
    bundle = read(a.native / "records.json")
    rows, audits = [], []
    for row in bundle["rows"]:
        audit = acceptance_audit(row)
        audits.append({"task_id": row["task_id"], "repeat": row["repeat"], **audit})
        rows.append({**row, "y_functional": audit["interpretable_y_functional"]})
    if len(rows) != 2 * len(plan["tasks"]):
        raise ValueError("finish the fixed native roster before selection audit")
    audit_path = a.native / "acceptance-audit.json"
    dump(
        audit_path,
        {
            "records_sha256": sha(a.native / "records.json"),
            "rows": audits,
            "new_model_calls": 0,
            "new_checker_executions": 0,
            "rule": "Raw labels retained. Wording-only mismatch in known overconstrained assertions is UNKNOWN; never promoted to PASS. Other independently failed assertions remain failures.",
        },
    )
    panel = select_panel(plan["tasks"], rows, plan["min_remaining_seconds"])
    if not any(r["y_functional"] == 0 for r in rows) and any(
        r["y_functional"] is None for r in rows
    ):
        panel = {
            "status": "NATIVE_DIFFICULTY_UNKNOWN",
            "states": [],
            "reason": "No independently supported native failure; unknowns prevent an all-pass conclusion. Do not run success-only tails.",
        }
    panel["acceptance_audit_sha256"] = sha(audit_path)
    raw_path = a.native / "panel-raw.json"
    if not raw_path.exists():
        dump(raw_path, read(a.native / "panel.json"))
    dump(a.native / "panel.json", panel)
    print(panel)


if __name__ == "__main__":
    main()
