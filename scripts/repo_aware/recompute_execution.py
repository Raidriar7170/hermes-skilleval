"""Recompute bounded five-arm outcomes from public patch/JUnit evidence only."""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

POLICIES = ("native", "fixed", "strong", "repo-aware", "auto")


def numeric(value):
    return (
        value
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
        else None
    )


def mean(values):
    observed = [value for value in values if value is not None]
    return statistics.mean(observed) if observed else None


def checked_file(root, relative, digest):
    if not isinstance(relative, str):
        raise ValueError("Missing artifact path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing or unsafe public artifact")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Public artifact SHA-256 mismatch")
    return path


def quality(cell, root, locked):
    reasons = []
    if cell.get("parse_errors"):
        reasons.append("malformed_private_metadata")
    if not locked:
        reasons.append("protocol_lock_missing_or_changed")
    if cell.get("execution_status") != "STARTED":
        reasons.append("not_started")
    binding = cell.get("binding", {})
    required = (
        "single_launch",
        "launch_protocol_matches",
        "task_and_base_match",
        "qualification_matches",
        "registry_matches",
        "policy_matches",
        "r_version_present",
        "patch_applies",
        "finalize_no_error",
    )
    reasons.extend("binding_" + key for key in required if binding.get(key) is not True)
    patch = cell.get("patch") or {}
    if (
        patch.get("status") != "EXPORTED"
        or patch.get("run_binding_matches") is not True
    ):
        reasons.append("patch_missing_withheld_or_unbound")
    else:
        checked_file(root, patch.get("path"), patch.get("sha256"))
    outcomes = []
    for kind in ("target", "regression"):
        check = cell.get("checks", {}).get(kind, {})
        if check.get("status") != "EXPORTED":
            reasons.append(kind + "_missing")
            continue
        path = checked_file(root, check.get("junit"), check.get("junit_sha256"))
        cases = list(ET.parse(path).iter("testcase"))
        ids = sorted(
            case.attrib["classname"] + "::" + case.attrib["name"] for case in cases
        )
        conditions = (
            "build_ok",
            "canary_ok",
            "collection_ok",
            "image_matches",
            "candidate_import_isolated",
            "run_hashes_match",
        )
        valid = (
            bool(cases)
            and ids == check.get("expected_ids")
            and len(ids) == len(set(ids))
            and all(check.get(key) is True for key in conditions)
            and type(check.get("returncode")) is int
            and check.get("returncode") in (0, 1)
            and all(
                case.find("error") is None and case.find("skipped") is None
                for case in cases
            )
        )
        if not valid:
            reasons.append(kind + "_invalid")
        passed = all(case.find("failure") is None for case in cases)
        if valid and (passed != (check.get("returncode") == 0)):
            reasons.append(kind + "_exit_outcome_mismatch")
        outcomes.append(passed)
    return (int(all(outcomes)) if not reasons and len(outcomes) == 2 else None), reasons


def recompute(index):
    data = json.loads(index.read_text())
    if data.get("schema") != "repo-aware-public-execution-v1":
        raise ValueError("Unsupported execution evidence schema")
    rows = []
    ids = set()
    for cell in data["cells"]:
        if cell["run_id"] in ids:
            raise ValueError("Duplicate run record")
        ids.add(cell["run_id"])
        launches = [
            event
            for event in data.get("events", [])
            if event.get("run_id") == cell["run_id"] and event.get("event") == "launch"
        ]
        ledger_consistent = (
            len(launches) == 1
            and launches[0].get("protocol_sha256") == data["protocol_sha256"]
        )
        score, reasons = quality(
            cell,
            index.parent,
            data.get("protocol_lock_matches") is True and ledger_consistent,
        )
        usage = cell.get("usage") or {}
        input_tokens, output_tokens = (
            numeric(usage.get("input_tokens")),
            numeric(usage.get("output_tokens")),
        )
        cached = numeric(usage.get("cached_input_tokens"))
        if cached is not None and (input_tokens is None or cached > input_tokens):
            cached = None
        elapsed = numeric(cell.get("timing", {}).get("pipeline_wall_seconds"))
        events = [
            event
            for event in data.get("events", [])
            if event.get("run_id") == cell["run_id"]
        ]
        rows.append(
            {
                "run_id": cell["run_id"],
                "task_id": cell["task_id"],
                "family_id": cell["family_id"],
                "policy": cell["policy"],
                "quality": score,
                "unknown_reasons": reasons,
                "execution_status": cell["execution_status"],
                "exit_code": cell.get("exit_code"),
                "timed_out": cell.get("timed_out"),
                "elapsed_seconds": elapsed,
                "execution_seconds": numeric(
                    cell.get("timing", {}).get("execution_seconds")
                ),
                "input_tokens": input_tokens,
                "cached_input_tokens": cached,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
                if input_tokens is not None and output_tokens is not None
                else None,
                "dollars": None,
                "attempt_events": events,
            }
        )
    groups = defaultdict(list)
    for row in rows:
        groups[(row["family_id"], row["policy"])].append(row)
    families = []
    for (family, policy), cells in sorted(groups.items()):
        values = [row["quality"] for row in cells]
        known = [value for value in values if value is not None]
        successes, unknown = sum(known), len(values) - len(known)
        families.append(
            {
                "family_id": family,
                "policy": policy,
                "planned_attempts": len(values),
                "known": len(known),
                "unknown": unknown,
                "successes": successes,
                "quality": mean(values) if not unknown else None,
                "known_only_quality": mean(values),
                "quality_lower": successes / len(values),
                "quality_upper": (successes + unknown) / len(values),
                "elapsed_seconds": mean([c["elapsed_seconds"] for c in cells]),
                "elapsed_observed": sum(
                    c["elapsed_seconds"] is not None for c in cells
                ),
                "total_tokens": mean([c["total_tokens"] for c in cells]),
                "tokens_observed": sum(c["total_tokens"] is not None for c in cells),
            }
        )
    summary = {}
    for policy in (*POLICIES, *sorted({row["policy"] for row in rows} - set(POLICIES))):
        group = [row for row in families if row["policy"] == policy]
        summary[policy] = {
            "families": len(group),
            "planned_attempts": sum(row["planned_attempts"] for row in group),
            "known_attempts": sum(row["known"] for row in group),
            "unknown_attempts": sum(row["unknown"] for row in group),
            "family_quality": mean([row["quality"] for row in group]),
            "complete_families": sum(row["quality"] is not None for row in group),
            "quality_lower": mean([row["quality_lower"] for row in group]),
            "quality_upper": mean([row["quality_upper"] for row in group]),
            "family_mean_elapsed_seconds": mean(
                [row["elapsed_seconds"] for row in group]
            ),
            "elapsed_families_observed": sum(
                row["elapsed_seconds"] is not None for row in group
            ),
            "family_mean_total_tokens": mean([row["total_tokens"] for row in group]),
            "token_families_observed": sum(
                row["total_tokens"] is not None for row in group
            ),
            "dollars": None,
        }
    paired = {}
    family_ids = sorted(
        {row["family_id"] for row in families if row["policy"] in POLICIES}
    )
    lookup = {(row["family_id"], row["policy"]): row for row in families}
    for policy in POLICIES[:-1]:
        counts = {"win": 0, "loss": 0, "tie": 0, "unknown": 0}
        for family in family_ids:
            h = lookup.get((family, "auto"), {}).get("quality")
            b = lookup.get((family, policy), {}).get("quality")
            outcome = (
                "unknown"
                if h is None or b is None
                else "win"
                if h > b
                else "loss"
                if h < b
                else "tie"
            )
            counts[outcome] += 1
        paired[policy] = counts
    versions = {
        key: sorted({cell[key] for cell in data["cells"] if cell.get(key)})
        for key in ("r_version", "registry_id")
    }
    return {
        "schema": "repo-aware-recomputed-execution-v1",
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "protocol_sha256": data["protocol_sha256"],
        "planned_cells": len(rows),
        "all_events": data.get("events", []),
        "rows": rows,
        "families": families,
        "five_arm_summary": summary,
        "h_paired_family_comparison": paired,
        "versions": versions,
        "mixed_versions": any(len(values) > 1 for values in versions.values()),
        "five_arm_complete_plan": all(
            (family, policy) in lookup for family in family_ids for policy in POLICIES
        )
        if family_ids
        else False,
        "cost_semantics": "Family-weighted observed means with missing counts; input includes cached subset; reasoning is not added to output; dollars unavailable. Unknown bounds include every planned attempt; repeated runs do not add independent families.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = recompute(args.index)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
