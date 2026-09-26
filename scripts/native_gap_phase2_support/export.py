"""Export saved public events/costs; no models, selection, or acceptance calls."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
P = Path("/tmp/hermes-native-gap-phase2-private")
C = ROOT / "configs/native-gap-phase2-same-library-v1"
A = ROOT / "artifacts/native-gap-phase2-same-library-v1"
sys.path.insert(0, str(ROOT / "scripts"))
from native_gap_phase1 import public_only  # noqa: E402


def compact(value):
    if isinstance(value, list):
        return [compact(v) for v in value]
    if isinstance(value, dict):
        result = {k: compact(v) for k, v in value.items()}
        output = result.get("aggregatedOutput")
        if isinstance(output, str) and len(output) > 2500:
            result["aggregatedOutput_sha256"] = hashlib.sha256(
                output.encode()
            ).hexdigest()
            result["aggregatedOutput_original_characters"] = len(output)
            result["aggregatedOutput"] = (
                output[:1800] + "\n[public excerpt truncated]\n" + output[-700:]
            )
        return result
    return value


def save(path, value):
    text = json.dumps(compact(public_only(value)), indent=2, ensure_ascii=False)
    for old in [str(P), "/private" + str(P)]:
        text = text.replace(old, "$PRIVATE")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n")


def extract(root):
    parent = json.loads((root / "result.json").read_text())
    worker = parent.get("worker", parent.get("recovered_manifest.json", {}))
    events = worker.get(
        "public_events", parent.get("recovered_public-events-live.json", [])
    )
    usage = None
    for event in reversed(events):
        if event.get("method") == "thread/tokenUsage/updated":
            usage = event["params"]["tokenUsage"]["total"]
            break
    commands = [
        e["params"]["item"]
        for e in events
        if e.get("params", {}).get("item", {}).get("type") == "commandExecution"
    ]
    reads = [
        c
        for c in commands
        if c.get("exitCode") == 0
        and re.search(
            r"\b(cat|sed|head|tail|awk|rg)\b|read_text|read_bytes|open\(",
            c.get("command", ""),
        )
    ]
    observations = {
        "catalog_read_observed": any(
            "catalog.md" in c.get("command", "") for c in reads
        ),
        "explicit_body_read_observed": any(
            "SKILL.md" in c.get("command", "") for c in reads
        ),
        "references_read_observed": any(
            "/references/" in c.get("command", "") for c in reads
        ),
        "automatic_body_context": "UNKNOWN_INITIAL_CONTEXT_NOT_EXPOSED",
        "body_non_read_is_not_unused_proof": True,
    }
    row = {
        k: parent.get(k)
        for k in [
            "t0",
            "t1",
            "elapsed_seconds",
            "budget_valid",
            "model_started",
            "model_start_requested",
            "tool_action_observed",
            "parent_status",
            "parent_cleanup",
            "parent_cleanup_error",
        ]
    }
    row.update(
        id=root.name,
        terminal=worker.get("terminal", "UNKNOWN"),
        usage=usage,
        observations=observations,
        input_bindings_verified=worker.get("input_bindings_verified", False),
        discovery_identity_verified=worker.get("discovery_identity_verified", False),
        original_project_skills=worker.get("original_project_skills", []),
        navigation=worker.get("navigation"),
        navigation_seconds=worker.get("navigation_seconds", 0),
        navigation_fallback=worker.get("navigation_fallback", False),
        navigation_error=worker.get("navigation_error"),
        prompt=worker.get("prompt"),
        thread_id=worker.get("thread_id"),
        public_events=events,
        money=None,
        memory_scope="SKILLS_ONLY_NO_GENERATION_NO_USE",
    )
    return row


def preflights():
    for ident in ["preflight-1", "preflight-2"]:
        save(A / "preflight" / f"{ident}.json", extract(P / ident))


def results():
    plan = json.loads((C / "plan.json").read_text())
    checks = {r["id"]: r for r in json.loads((P / "trusted-results.json").read_text())}
    rows = []
    for item in plan["order"]:
        row = extract(P / "runs" / item["id"])
        check = checks[item["id"]]
        row.update({k: item[k] for k in ["instance_id", "arm", "repeat"]})
        row["functional_result"] = check["functional_result"]
        row["protocol_validity"] = (
            "VERIFIED"
            if row["input_bindings_verified"]
            and row["discovery_identity_verified"]
            and row["budget_valid"]
            and (row.get("parent_cleanup") or {}).get("no_running_tool_confirmation")
            else "LIMITED_OR_UNKNOWN"
        )
        save(A / "runs" / item["id"] / "result.json", row)
        candidate = P / "runs" / item["id"] / "candidate.patch"
        if candidate.exists():
            shutil.copyfile(candidate, A / "runs" / item["id"] / "candidate.patch")
        save(A / "checks" / item["id"] / "result.json", check)
        xml = P / "checks" / item["id"] / "candidate.xml"
        if xml.exists():
            shutil.copyfile(xml, A / "checks" / item["id"] / "candidate.xml")
        row.pop("public_events")
        row.pop("prompt")
        rows.append(row)
    grouped = []
    for iid in sorted({r["instance_id"] for r in rows}):
        arms = {
            a: [
                r["functional_result"]
                for r in rows
                if r["instance_id"] == iid and r["arm"] == a
            ]
            for a in ["NATIVE", "ASSIST"]
        }
        n, a = arms["NATIVE"], arms["ASSIST"]
        assert len(n) == len(a) == 2
        unknown = "UNKNOWN" in n + a
        grouped.append(
            {
                "instance_id": iid,
                "raw_results": arms,
                "delta": None if unknown else (a.count("PASS") - n.count("PASS")) / 2,
                "missing_bound_low": (
                    a.count("PASS") - n.count("PASS") - n.count("UNKNOWN")
                )
                / 2,
                "missing_bound_high": (
                    a.count("PASS") + a.count("UNKNOWN") - n.count("PASS")
                )
                / 2,
            }
        )
    value = {
        "rows": rows,
        "tasks": grouped,
        "task_equal_delta": None
        if any(g["delta"] is None for g in grouped)
        else sum(g["delta"] for g in grouped) / len(grouped),
        "unknown_bound": [
            sum(g[k] for g in grouped) / len(grouped)
            for k in ["missing_bound_low", "missing_bound_high"]
        ],
        "bounds_are_not_confidence_intervals": True,
        "independent_task_units": len(grouped),
    }
    save(A / "results.json", value)
    save(
        A / "usage-costs.json",
        {
            "online_runs": [
                {
                    k: r[k]
                    for k in [
                        "id",
                        "arm",
                        "elapsed_seconds",
                        "budget_valid",
                        "navigation_seconds",
                        "usage",
                        "money",
                    ]
                }
                for r in rows
            ],
            "offline_preparation": "See preparation/*.json; Docker actual transfer bytes remain UNKNOWN; no Phase1 cost reconstruction.",
        },
    )
    print("exported", len(rows), "rows; task-equal delta", value["task_equal_delta"])


if __name__ == "__main__":
    if sys.argv[1:] == ["preflights"]:
        preflights()
    elif sys.argv[1:] == ["results"]:
        results()
    else:
        raise SystemExit("Use preflights or results; no implicit model/acceptance call")
