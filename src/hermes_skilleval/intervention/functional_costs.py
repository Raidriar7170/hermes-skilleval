"""Secondary records-only costs, with execution reuse excluded from totals."""

import hashlib
import json
from pathlib import Path

from .usage import reported_usage


def observed_sum(values):
    known = [v for v in values if v is not None]
    return {
        "observed_sum": sum(known),
        "known": len(known),
        "unknown": len(values) - len(known),
    }


def cost_ledger(groups, *, usage_reader=reported_usage):
    seen = {}
    result = {}
    for category, rows in groups.items():
        unique, reused = [], 0
        for row in rows:
            run = Path(row["run"]).resolve()
            execution = row["execution"]
            if run in seen:
                if seen[run] != execution:
                    raise ValueError("reused execution has conflicting cost evidence")
                reused += 1
                continue
            seen[run] = execution
            usage = usage_reader(run)
            unique.append((execution, usage))
        token_fields = (
            "inputTokens",
            "cachedInputTokens",
            "cacheWriteInputTokens",
            "outputTokens",
            "reasoningOutputTokens",
            "totalTokens",
        )
        result[category] = {
            "record_references": len(rows),
            "unique_executions_charged": len(unique),
            "reused_execution_references_excluded": reused,
            "tokens": {
                key: observed_sum([(u.get("tokens") or {}).get(key) for _, u in unique])
                for key in token_fields
            },
            "active_seconds": observed_sum([e.get("tail_seconds") for e, _ in unique]),
            "preparation_seconds": observed_sum(
                [e.get("preparation_seconds") for e, _ in unique]
            ),
            "online_decision_budget_charges": {
                "policy_initialization_seconds": observed_sum(
                    [e.get("policy_initialization_seconds") for e, _ in unique]
                ),
                "controller_overhead_seconds": {
                    key: observed_sum(
                        [
                            (e.get("controller_overhead_seconds") or {}).get(key)
                            for e, _ in unique
                        ]
                    )
                    for key in ("state", "retrieval", "checkpoint", "decision")
                },
            },
            "executions_with_complete_usage_notifications": sum(
                u.get("all_started_turns_completed_with_usage") is True
                for _, u in unique
            ),
        }
    return {
        "operation": "RECORDS_ONLY_SECONDARY_COST_LEDGER",
        "scope": "provided saved records only; active/unreleased attempts and unsupplied sources excluded",
        "metric_role": "SECONDARY_ONLY",
        "deduplication": "one resolved execution directory counted once globally; first listed category owns reused cost",
        "timing_semantics": "active time excludes inherited prefix_seconds; decision charges are components, not additive totals, and may include amortized shared prediction charges",
        "token_semantics": "input includes cached input; output includes reasoning output; subset fields must not be added again",
        "groups": result,
        "unique_executions": len(seen),
        "billing_usd": None,
        "billing_status": "UNKNOWN_NOT_INFERRED",
        "agent_calls": 0,
        "model_calls": 0,
    }


def from_files(sources, training=None):
    groups = {}
    identities = []
    for category, source in sources:
        path = Path(source)
        raw = path.read_bytes()
        groups.setdefault(category, []).extend(json.loads(raw)["rows"])
        identities.append(
            {"category": category, "records_sha256": hashlib.sha256(raw).hexdigest()}
        )
    report = cost_ledger(groups)
    report["record_sources"] = identities
    report["training"] = {"status": "NOT_SUPPLIED", "wall_seconds": None}
    if training is not None:
        raw = Path(training).read_bytes()
        value = json.loads(raw)
        report["training"] = {
            "status": value["status"],
            "wall_seconds": value.get("wall_seconds"),
            "report_sha256": hashlib.sha256(raw).hexdigest(),
            "scope": "saved training coordinator wall time; not GPU-hours or billing",
        }
    return report
