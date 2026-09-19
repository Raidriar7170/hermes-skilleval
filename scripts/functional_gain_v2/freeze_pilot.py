"""Freeze qualified pilot sources and inherited runtime, before Agent samples."""

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.intervention.session import inventory, dump
from hermes_skilleval.intervention.study import verify_freeze


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in (
        "tasks",
        "qualification",
        "objective",
        "pool",
        "inherited",
        "payloads",
        "skills",
        "encoder",
        "output",
        "public",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.public.exists():
        raise ValueError("immutable pilot freeze already exists")
    objective = load_objective(a.objective)
    qualified = json.loads(a.qualification.read_text())["rows"]
    roster = json.loads((a.tasks / "candidate-roster.json").read_text())
    if [r["task_id"] for r in qualified] != [r["task_id"] for r in roster] or not all(
        r["status"] == "BASE_RED_REFERENCE_GREEN" for r in qualified
    ):
        raise ValueError("pilot qualification incomplete")
    inherited = json.loads(a.inherited.read_text())
    rows = []
    for row in roster:
        root = a.tasks / row["task_id"]
        rows.append(
            {
                **row,
                "files": {
                    scope: inventory(root / scope)
                    for scope in ("base", "trusted", "reference")
                },
                "profile_sha256": sha(root / "task.json"),
                "request_sha256": sha(root / "request.txt"),
            }
        )
    protocol = {
        k: inherited[k]
        for k in (
            "agent",
            "representation",
            "payloads",
            "skills",
            "registry_sha256",
            "guidance",
        )
    }
    protocol.update(
        version="functional-v2-pilot-1",
        status="FROZEN",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        tasks=rows,
        total_seconds=600,
        repeats=2,
        objective_sha256=objective["sha256"],
        pool_sha256=sha(a.pool),
        qualification_sha256=sha(a.qualification),
        resource_basis={
            "weekly_remaining_percent_observed": 50,
            "capacity_guaranteed": False,
            "old_tail_mean_seconds": 95.87040568993676,
            "416_execution_estimate_hours_excluding_prefixes": 11.08,
            "billing": "UNKNOWN",
            "new_resource_purchase": False,
        },
    )
    verify_freeze(protocol, a.tasks, a.payloads, a.skills, a.encoder)
    dump(a.output, protocol)
    dump(
        a.public,
        {
            **protocol,
            "tasks": [{k: v for k, v in r.items() if k != "files"} for r in rows],
            "private_protocol_sha256": sha(a.output),
        },
    )
    print(
        json.dumps(
            {
                "status": "PILOT_FROZEN",
                "tasks": len(rows),
                "native_samples": len(rows) * 2,
                "agent_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
