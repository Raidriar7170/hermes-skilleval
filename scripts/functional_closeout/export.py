"""Export bounded functional evidence without raw sessions or full source indexes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

from hermes_skilleval.intervention.functional_closeout import STUDY, cell_path, matrix
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.relation_store import atomic_json
from hermes_skilleval.intervention.rollouts import task_complete


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def compressed(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(source.read_bytes(), mtime=0))
    return sha_bytes(source.read_bytes())


def clean(value):
    if isinstance(value, dict):
        return {
            k: clean(v)
            for k, v in value.items()
            if k not in {"pid", "host_clock", "thread_id", "thread_ids", "last_turn_id"}
        }
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(Path.home()), "${USER_HOME}")
    return value


def export(repo, private):
    plan = read(repo / "configs" / STUDY / "plan.json")
    report = read(private / "report.json")
    dest = repo / "artifacts" / STUDY
    atomic_json(
        dest / "functional.json",
        {
            "rows": clean(read(private / "functional-results.json")["rows"]),
            "table": report["functional_table"],
            "contrasts": report["contrasts"],
        },
    )
    atomic_json(dest / "costs.json", report["cost_table"])
    atomic_json(dest / "status.json", report["terminal"])
    packs, bindings, cases, manifests = {}, [], [], []
    tasks = {t["instance_id"]: t for t in plan["tasks"]}
    for case in report["knowledge_behavior_table"]:
        payload = case.pop("actual_payload")
        units = case.pop("units")
        key = sha_bytes((payload or "").encode())
        if payload:
            packs[key] = {"payload": payload, "units": units}
        cases.append(clean({**case, "pack_sha256": key if payload else None}))
    atomic_json(dest / "packages.json", packs)
    atomic_json(dest / "knowledge-behavior.json", cases)
    for cell in matrix(plan["tasks"]):
        source = cell_path(private, cell)
        target = dest / "functional" / tasks[cell["task_id"]]["mechanism"] / source.name
        execution = read(source / "execution.json")
        # Exact private record hash plus bounded public runtime fields.
        evidence = {
            **cell,
            "execution_sha256": sha_bytes((source / "execution.json").read_bytes()),
            "execution": clean(
                {
                    k: execution.get(k)
                    for k in [
                        "status",
                        "turns",
                        "total_seconds",
                        "initial_remaining",
                        "tail_seconds",
                        "preparation_seconds",
                        "policy_initialization_seconds",
                        "prefix_seconds",
                        "model_input_observed",
                        "injected",
                        "payload_tokens",
                    ]
                }
            ),
        }
        binding_path = (
            private / "cell-budgets" / cell["task_id"] / (source.name + ".json")
        )
        if binding_path.exists():
            evidence["budget_binding"] = read(binding_path)
        accepted_path = source / "acceptance/acceptance.json"
        if accepted_path.exists():
            accepted = read(accepted_path)
            evidence["integrity"] = accepted["integrity"]
            evidence["changed_files"] = accepted["capture"]["changed_files"]
            evidence["checks"] = accepted["checks"]
            checkroot = (
                source
                / "acceptance"
                / accepted.get("check_evidence_directory", "checks")
            )
            for kind in ("target", "regression"):
                for name in ("junit.xml", "collected.json"):
                    path = checkroot / kind / name
                    if path.exists():
                        compressed(path, target / "checks" / kind / (name + ".gz"))
            if accepted.get("metadata_sidecar_path"):
                atomic_json(
                    target / "permission-sidecar.json",
                    read(source / "acceptance" / accepted["metadata_sidecar_path"]),
                )
        patch = source / "acceptance/capture/candidate.patch"
        if patch.exists():
            evidence["patch_sha256"] = compressed(patch, target / "candidate.patch.gz")
        for filename in ("reconstruction-error.json", "capture/capture.json"):
            path = source / "acceptance" / filename
            if path.exists():
                atomic_json(target / Path(filename).name, clean(read(path)))
        atomic_json(target / "result.json", clean(evidence))
    for tid, task in tasks.items():
        root = private / "selection" / tid
        target = dest / "selection" / task["mechanism"]
        common = read(root / "common.json")
        bindings.append(
            {
                "task_id": tid,
                "mechanism": task["mechanism"],
                "checkpoint_sha256": common.get("checkpoint_sha256"),
                "prefix_seconds": common.get("prefix_seconds"),
                "remaining_seconds": common.get("prefix_remaining_seconds"),
                "terminal_at_boundary": task_complete(
                    read(Path(common["checkpoint"]) / "checkpoint.json")[
                        "visible_events"
                    ]
                )
                if common.get("checkpoint")
                else None,
            }
        )
        for name in ("common-cost.json", "pool.json", "retrieval.json"):
            if (root / name).exists():
                content = (
                    json.dumps(clean(read(root / name)), sort_keys=True, indent=2)
                    + "\n"
                ).encode()
                target.mkdir(parents=True, exist_ok=True)
                (target / (name + ".gz")).write_bytes(gzip.compress(content, mtime=0))
        if (root / "ledger.json").exists():
            ledger = read(root / "ledger.json")
            atomic_json(
                target / "ledger.json",
                clean({k: v for k, v in ledger.items() if k != "observations"}),
            )
        for repeat in (1, 2):
            r = root / f"R-r{repeat}"
            if (r / "store.json").exists():
                compressed(r / "store.json", target / f"R-r{repeat}-relations.json.gz")
            trajectory = r / "trajectory.json"
            if trajectory.exists():
                rows = [
                    {k: v for k, v in row.items() if k != "pack"}
                    for row in read(trajectory)
                ]
                atomic_json(target / f"R-r{repeat}-trajectory.json", clean(rows))
            lock = read(root / f"R-r{repeat}.json")
            message = lock.pop("message", None)
            lock.pop("pack", None)
            lock["payload_sha256"] = sha_bytes((message or "").encode())
            atomic_json(target / f"R-r{repeat}.json", clean(lock))
            cost = root / f"R-r{repeat}-cost.json"
            if cost.exists():
                atomic_json(target / f"R-r{repeat}-cost.json", clean(read(cost)))
        manifests.append(
            {
                "task_id": tid,
                "index_sha256": task["public_knowledge_inventory"]["index.json"],
                "offline_index": read(
                    private / "public-knowledge" / task["base_commit"] / "cost.json"
                ),
                "qualification": next(
                    r
                    for r in read(private / "qualification-summary.json")["rows"]
                    if r["instance_id"] == tid
                ),
            }
        )
    atomic_json(dest / "prefix-bindings.json", bindings)
    atomic_json(dest / "asset-summary.json", clean(manifests))
    atomic_json(dest / "preflight.json", clean(read(private / "preflight/result.json")))
    atomic_json(dest / "cost-model.json", clean(read(private / "cost-model.json")))
    notice = repo / "artifacts/relation-applicability-query-v1"
    for name in ("SOURCE-NOTICE.md", "ANSIBLE-COPYING"):
        shutil.copyfile(notice / name, dest / name)
    print(
        json.dumps(
            {
                "files": sum(p.is_file() for p in dest.rglob("*")),
                "model_calls": 0,
                "acceptance_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--private", type=Path, required=True)
    args = parser.parse_args()
    export(args.repo, args.private)
