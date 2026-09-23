"""Records-only compact export: original patches, verifier artifacts and three tables."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from hermes_skilleval.intervention.budgeted_context_study import (
    cell_path,
    matrix,
    report,
)
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.relation_store import atomic_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compressed(source, destination):
    raw = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(raw, mtime=0))
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "gzip_sha256": sha(destination),
        "uncompressed_bytes": len(raw),
    }


def export(study, plan, output):
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if plan.get("status") != "FROZEN" or digest != plan.get("plan_digest"):
        raise ValueError("Frozen plan identity changed")
    for task in plan["tasks"]:
        root = study / "selection" / task["instance_id"]
        for name in ["selection.json", "core-lock.json"]:
            path = root / name
            if path.exists():
                state = read(path)
                if (
                    state.get("status") != "NO_PREFIX"
                    and state.get("plan_digest") != digest
                ):
                    raise ValueError(f"Selection belongs to another plan: {path}")
    for path in (study / "cell-budgets").glob("*/*.json"):
        if read(path).get("plan_digest") != digest:
            raise ValueError(f"Execution charge belongs to another plan: {path}")
    outcome = report(study)
    expected = matrix(plan)

    def key(r):
        return (r["task_id"], r["protocol"], r["arm"], r["repeat"])

    if Counter(map(key, outcome["rows"])) != Counter(map(key, expected)):
        raise ValueError("Planned ledger incomplete or duplicated")
    names = {t["instance_id"]: t["mechanism"] for t in plan["tasks"]}
    public = []
    evidence = []
    for row in outcome["rows"]:
        run = cell_path(study, row)
        dest = output / "functional" / names[row["task_id"]] / run.name
        dest.mkdir(parents=True, exist_ok=True)
        value = {
            **row,
            "mechanism": names[row["task_id"]],
            "execution_sha256": sha(run / "execution.json"),
        }
        acceptance = run / "acceptance/acceptance.json"
        if acceptance.exists():
            accepted = read(acceptance)
            capture = accepted["capture"]
            patch = run / "acceptance/capture/candidate.patch"
            if sha(patch) != capture["patch_sha256"]:
                raise ValueError(f"Verified candidate patch changed: {patch}")
            patch_dest = dest / "candidate.patch.gz"
            value["candidate"] = {
                **compressed(patch, patch_dest),
                "path": str(patch_dest.relative_to(output)),
                "integrity": accepted["integrity"],
                "captured_patch_sha256": capture["patch_sha256"],
                "changed_files": capture["changed_files"],
                "before_inventory_sha256": hashlib.sha256(
                    json.dumps(capture["before"], sort_keys=True).encode()
                ).hexdigest(),
                "after_inventory_sha256": hashlib.sha256(
                    json.dumps(capture["after"], sort_keys=True).encode()
                ).hexdigest(),
            }
            value["checks"] = {
                kind: {k: v for k, v in check.items() if k != "error"}
                for kind, check in accepted["checks"].items()
            }
            value["reconstruction_version"] = accepted.get(
                "reconstruction_version", "frozen-original-patch-v1"
            )
            if "metadata_sidecar_path" in accepted:
                sidecar = run / "acceptance" / accepted["metadata_sidecar_path"]
                metadata = read(sidecar)
                if (
                    sha(sidecar) != accepted["metadata_sidecar_sha256"]
                    or metadata["patch_sha256"] != capture["patch_sha256"]
                    or metadata["original_inventory_sha256"]
                    != value["candidate"]["after_inventory_sha256"]
                    or accepted["execution_sha256"] != value["execution_sha256"]
                ):
                    raise ValueError("Reconstruction sidecar identity changed")
                atomic_json(dest / "reconstruction-metadata.json", metadata)
                value["candidate"]["metadata_sidecar"] = str(
                    (dest / "reconstruction-metadata.json").relative_to(output)
                )
                value["candidate"]["metadata_sidecar_sha256"] = sha(sidecar)
            # Only explicit verifier evidence, never reconstructed source trees or sessions.
            check_root = (
                run / "acceptance" / accepted.get("check_evidence_directory", "checks")
            )
            check_files = [check_root / "test-overlay.json"] + [
                check_root / kind / filename
                for kind in ["target", "regression"]
                for filename in ["junit.xml", "collected.json"]
            ]
            for source in check_files:
                if source.is_file() and source.name in {
                    "junit.xml",
                    "collected.json",
                    "test-overlay.json",
                }:
                    relative = source.relative_to(check_root)
                    target = (
                        dest
                        / "checks"
                        / str(relative)
                        .replace(".xml", ".xml.gz")
                        .replace(".json", ".json.gz")
                    )
                    entry = compressed(source, target)
                    evidence.append({"path": str(target.relative_to(output)), **entry})
        atomic_json(dest / "result.json", value)
        public.append(value)
    tables = []
    contrasts = []
    for protocol, arms in [("P", ["N", "M", "A"]), ("C", ["M", "A", "D"])]:
        for task in plan["tasks"]:
            groups = {}
            for arm in arms:
                group = [
                    r
                    for r in public
                    if r["task_id"] == task["instance_id"]
                    and r["protocol"] == protocol
                    and r["arm"] == arm
                ]
                if len(group) != plan["tail_repeats"]:
                    raise ValueError("Missing planned repeat")
                counts = Counter(r["functional"] for r in group)
                strict = Counter(r["strict_functional"] for r in group)
                groups[arm] = strict if protocol == "P" else counts
                tables.append(
                    {
                        "protocol": protocol,
                        "mechanism": task["mechanism"],
                        "arm": arm,
                        "planned": len(group),
                        "functional": {
                            k: counts[k] for k in ["PASS", "FAIL", "UNKNOWN"]
                        },
                        "strict_budget_functional": {
                            k: strict[k] for k in ["PASS", "FAIL", "UNKNOWN"]
                        },
                        "budget_states": dict(
                            Counter(r["budget_status"] for r in group)
                        ),
                        "tail_budget_seconds": [
                            r["tail_budget_seconds"] for r in group
                        ],
                        "A_states": dict(Counter(r.get("A_status") for r in group)),
                    }
                )
            for comparator in ["M", "N"] if protocol == "P" else ["D", "M"]:
                left, right = groups["A"], groups[comparator]
                n = plan["tail_repeats"]
                contrasts.append(
                    {
                        "protocol": protocol,
                        "mechanism": task["mechanism"],
                        "contrast": "A_minus_" + comparator,
                        "lower": (left["PASS"] - right["PASS"] - right["UNKNOWN"]) / n,
                        "upper": (left["PASS"] + left["UNKNOWN"] - right["PASS"]) / n,
                        "interpretation": "missing-outcome bounds, not confidence interval",
                    }
                )
    acquisition = []
    for task in plan["tasks"]:
        root = study / "selection" / task["instance_id"]
        state = read(root / "selection.json")
        for arm in ["A", "D"]:
            result = root / arm / ("reference.json" if arm == "D" else "selection.json")
            if not result.exists():
                acquisition.append(
                    {"mechanism": task["mechanism"], "arm": arm, "status": "NOT_RUN"}
                )
                continue
            d = read(result)
            acquisition.append(
                {
                    "mechanism": task["mechanism"],
                    "arm": arm,
                    "mode": "ONLINE_HELPER_ACQUISITION",
                    "unique_requested_scope": "this acquisition only; D inherits accepted A rows",
                    **{
                        k: d.get(k)
                        for k in [
                            "status",
                            "stop_reason",
                            "unique_requested",
                            "relation_seconds",
                            "relation_limit",
                            "reference_status",
                            "semantic_unknown",
                            "lower",
                            "upper",
                        ]
                    },
                    "counts": d["relations"]["counts"],
                    "pack_ids": [u["unit_id"] for u in d["pack"]["units"]],
                    "M_A_identical_bytes": state["messages"].get("M")
                    == state["messages"].get("A"),
                }
            )
        if (root / "A/trace.json").exists():
            atomic_json(
                output / "traces" / task["mechanism"] / "A.json",
                read(root / "A/trace.json"),
            )
        # Produced by the frozen replay CLI only after D is locked. Keep the
        # offline table separate from online latency and functional outcomes.
        replay_path = root / "offline-replay.json"
        if not replay_path.exists():
            if (root / "D/reference.json").exists():
                raise ValueError(f"Missing final-state offline replay: {replay_path}")
            acquisition.append(
                {
                    "mechanism": task["mechanism"],
                    "mode": "OFFLINE_HIDDEN_TABLE_REPLAY",
                    "status": "NOT_RUN",
                    "reason": "D reference unavailable; P/C records retained",
                }
            )
            continue
        replay = read(replay_path)
        if (
            replay["mode"] != "OFFLINE_HIDDEN_TABLE_REPLAY"
            or replay["model_calls"] != 0
            or replay["repair_executions"] != 0
        ):
            raise ValueError("Not a records-only hidden-table replay")
        atomic_json(
            output / "traces" / task["mechanism"] / "offline-replay.json", replay
        )
        for row in replay["rows"]:
            acquisition.append(
                {
                    "mechanism": task["mechanism"],
                    "arm": row["strategy"],
                    "mode": replay["mode"],
                    "progress_point": row["progress_point"],
                    "unique_requested": row["requested"],
                    "counts": row["relations"]["counts"],
                    "pack_ids": row["package_ids"],
                    "same_pack_as_reference": row["same_pack_as_reference"],
                    "reference_objective_lower": row["reference_objective_lower"],
                    "reference_objective_upper": row["reference_objective_upper"],
                    "state": row["state"],
                    "relation_seconds": None,
                    "latency_claim": "NONE",
                }
            )
    atomic_json(
        output / "functional-results.json",
        {
            "plan_digest": plan["plan_digest"],
            "execution_code_commit": plan["execution_commit"],
            "rows": public,
            "planned": len(expected),
            "tables": tables,
            "contrasts": contrasts,
            "default_policy": "UNCHANGED",
            "scope": "exploratory_development_comparison",
        },
    )
    atomic_json(
        output / "acquisition.json",
        {
            "rows": acquisition,
            "dense_scope": "same-matrix posthoc model reference, not oracle",
        },
    )
    from hermes_skilleval.intervention.usage import reported_usage

    costs = {
        "scenario": "warm_index",
        "charging": "physical shared preparation charged per method/repeat; C reported separately",
        "offline_index": [],
        "executions": [],
        "helper_calls": [],
        "component_limit": "Local ledger/index/encoder/retrieval/MMR aggregate measured together; finer split unavailable for this execution version",
    }
    for task in plan["tasks"]:
        costs["offline_index"].append(
            {
                "mechanism": task["mechanism"],
                **read(study / "public-knowledge" / task["base_commit"] / "cost.json"),
            }
        )
    for phase in ["prefixes", "tails"]:
        for path in sorted((study / phase).rglob("execution.json")):
            d = read(path)
            try:
                usage = reported_usage(path.parent)
            except ValueError as exc:
                usage = {"status": "UNAVAILABLE_INVALID_USAGE", "reason": str(exc)}
            costs["executions"].append(
                {
                    "attempt": str(path.parent.relative_to(study)),
                    **{
                        k: d.get(k)
                        for k in [
                            "status",
                            "initial_remaining",
                            "tail_seconds",
                            "preparation_seconds",
                            "policy_initialization_seconds",
                            "prefix_seconds",
                            "payload_tokens",
                            "model_input_observed",
                        ]
                    },
                    "actual_thread_started": bool(d.get("thread_id")),
                    "reported_usage": usage,
                }
            )
    for batch in sorted((study / "selection").glob("*/*/batch-*")):
        if not batch.is_dir():
            continue
        path = batch / "cost.json"
        d = read(path) if path.exists() else {"status": "UNKNOWN_MISSING_COST"}
        events = batch / "server/events.jsonl"
        updates = []
        usage_status = "NOT_REPORTED"
        if events.exists():
            try:
                for line in events.read_text().splitlines():
                    event = json.loads(line)
                    if event.get("method") == "thread/tokenUsage/updated":
                        updates.append(event["params"]["tokenUsage"])
                usage_status = "REPORTED" if updates else "NOT_REPORTED"
            except (ValueError, KeyError, TypeError):
                updates = []
                usage_status = "UNAVAILABLE_INVALID_EVENTS"
        costs["helper_calls"].append(
            {
                "attempt": str(batch.relative_to(study)),
                "cost_sha256": sha(path) if path.exists() else None,
                "events_sha256": sha(events) if events.exists() else None,
                "usage_status": usage_status,
                **{
                    k: d.get(k)
                    for k in [
                        "status",
                        "seconds",
                        "deadline_seconds",
                        "cancellation",
                        "no_running_tool_confirmation",
                    ]
                },
                "usage": updates[-1] if updates else None,
                "usage_scope": "fresh single helper thread; counters retained separately, cached/reasoning subsets not added to totals",
            }
        )
    atomic_json(output / "costs.json", costs)
    atomic_json(output / "compressed-evidence.json", {"files": evidence})
    return tables


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ["study", "plan", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(export(a.study, read(a.plan), a.output), indent=2))
