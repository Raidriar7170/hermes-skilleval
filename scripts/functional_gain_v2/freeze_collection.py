"""Freeze the complete qualified roster before new native chains and paired tails."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.intervention.session import dump, inventory
from hermes_skilleval.intervention.study import read, verify_freeze


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for k in (
        "private",
        "pool",
        "objective",
        "payloads",
        "skills",
        "encoder",
        "public",
    ):
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    protocol_path = a.private / "collection-protocol-v1.json"
    task_root = a.private / "collection-tasks-v1"
    if protocol_path.exists() or task_root.exists() or a.public.exists():
        raise ValueError("collection freeze already exists")
    objective = load_objective(a.objective)
    pool = read(a.pool)
    inherited = read(a.private / "pilot-protocol-v1.json")
    groups = [
        ("pilot-tasks-v1", "pilot-qualification-v2"),
        ("sqlite-training-tasks-v1", "sqlite-training-qualification-v1"),
        ("tabular-tasks-v2", "tabular-qualification-v2"),
        ("final-tasks-v2", "final-qualification-v2"),
    ]
    sources, qualifications = {}, {}
    for source, checks in groups:
        for row in read(a.private / checks / "qualification.json")["rows"]:
            if row["status"] != "BASE_RED_REFERENCE_GREEN":
                raise ValueError("unqualified task: " + row["task_id"])
            tid = row["task_id"]
            if tid in sources:
                raise ValueError("duplicate qualified task")
            sources[tid] = a.private / source / tid
            qualifications[tid] = sha(a.private / checks / "qualification.json")
    if set(sources) != {r["task_id"] for r in pool["rows"]}:
        raise ValueError("qualified roster mismatch")
    rows = []
    issue769 = {"8572d1e", "d9a0fd2", "7d86118", "60811e7"}
    for row in pool["rows"]:
        tid = row["task_id"]
        root = sources[tid]
        item = {
            **row,
            "qualification": "BASE_RED_REFERENCE_GREEN",
            "files": {k: inventory(root / k) for k in ("base", "trusted", "reference")},
            "profile_sha256": sha(root / "task.json"),
            "request_sha256": sha(root / "request.txt"),
            "qualification_sha256": qualifications[tid],
        }
        if tid.split("-")[-1] in issue769:
            item["source_family"] = item["family"]
            item["family"] = "sqlite-issue-769"
        if row["pilot"]:
            old = next(r for r in inherited["tasks"] if r["task_id"] == tid)
            for field in ("files", "profile_sha256", "request_sha256"):
                if item[field] != old[field]:
                    raise ValueError("pilot reuse task identity mismatch")
            execution_path = a.private / "pilot-runs-v1" / tid / "r1" / "execution.json"
            item["pilot_reuse"] = {"repeat": 1, "execution_sha256": sha(execution_path)}
        rows.append(item)
    families = {}
    for row in rows:
        families.setdefault(row["family"], set()).add(row["split"])
    if any(len(splits) > 1 for splits in families.values()):
        raise ValueError("family crosses splits")
    states = [
        r["task_id"] + ":" + stage
        for r in rows
        if r["split"] != "test"
        for stage in ("E0", "E1", "E2")
    ]
    protocol = {
        k: inherited[k]
        for k in (
            "agent",
            "representation",
            "payloads",
            "skills",
            "registry_sha256",
            "guidance",
            "resource_basis",
        )
    }
    protocol.update(
        version="functional-v2-collection-1",
        status="FROZEN",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        tasks=rows,
        objective_sha256=objective["sha256"],
        pool_sha256=sha(a.pool),
        total_seconds=600,
        planned_states=states,
        repeat_states=states[::4],
        maximum_tails=240,
        native_order="all registered train/dev chains first, then paired tails in roster order",
        repeat_selection="Every fourth registered task-stage slot starting at zero; no observed state/outcome selection",
        family_amendment="Public issue 769 shared provenance grouped together for cross-fitting; all remain train",
        missing_states="Preserve absent natural opportunities and infrastructure unknowns; never synthesize labels",
        final_execution="NOT_AUTHORIZED_BY_THIS_COLLECTION_COMMAND; separate model and policy freeze required",
    )
    task_root.mkdir()
    for tid, root in sources.items():
        (task_root / tid).symlink_to(root, target_is_directory=True)
    verify_freeze(protocol, task_root, a.payloads, a.skills, a.encoder)
    dump(protocol_path, protocol)
    dump(
        a.public,
        {
            **protocol,
            "tasks": [{k: v for k, v in r.items() if k != "files"} for r in rows],
            "private_protocol_sha256": sha(protocol_path),
        },
    )
    print(
        json.dumps(
            {
                "status": "COLLECTION_FROZEN",
                "tasks": len(rows),
                "planned_states": len(states),
                "repeat_states": len(states[::4]),
                "maximum_tails": 240,
            }
        )
    )


if __name__ == "__main__":
    main()
