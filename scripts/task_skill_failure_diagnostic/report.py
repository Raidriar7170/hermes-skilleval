"""Compact exports and records-only replay, never a new behavioral execution."""

import argparse
import hashlib
import json
from pathlib import Path

from hermes_skilleval.intervention.diagnostic import (
    acceptance_audit,
    compare_state,
    counts,
)
from hermes_skilleval.intervention.functional_costs import cost_ledger
from hermes_skilleval.intervention.functional_export import export, replay
from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.intervention.session import dump


def read(p):
    return json.loads(p.read_text())


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def aggregate(states):
    """Repeat means first, then equal mechanism weights; strata never pooled."""
    result = {}
    for stratum in ("native_failure", "native_success_control"):
        selected = [s for s in states if s["stratum"] == stratum]
        result[stratum] = {"mechanisms": len(selected)}
        for contrast in ("K_minus_N", "K_minus_G"):
            valid = [
                s["comparison"][contrast]
                for s in selected
                if "difference_bounds" in s["comparison"][contrast]
            ]
            result[stratum][contrast] = {
                "tested_mechanisms": len(valid),
                "difference_bounds": [
                    sum(x["difference_bounds"][i] for x in valid) / len(valid)
                    for i in (0, 1)
                ]
                if valid
                else None,
                "observed_difference": sum(x["observed_difference"] for x in valid)
                / len(valid)
                if valid and all(x["observed_difference"] is not None for x in valid)
                else None,
            }
    return result


def replay_diagnostic(output):
    """Recompute validity overlays and comparison summaries from public JUnit."""
    groups = {}
    for name in ("native", "tails"):
        path = output / name / "records.json"
        if not path.exists():
            continue
        rows = read(path)["rows"]
        for row in rows:
            audit = acceptance_audit(
                row, output / name / row["evidence_path"] / "target-junit.xml"
            )
            if audit != row["acceptance_validity"]:
                raise ValueError("acceptance validity overlay mismatch")
        groups[name] = rows
    for task in read(output / "native-difficulty.json")["tasks"]:
        rows = [r for r in groups.get("native", []) if r["task_id"] == task["task_id"]]
        if task["native"] != counts(
            [r["acceptance_validity"]["interpretable_y_functional"] for r in rows], 2
        ):
            raise ValueError("native difficulty summary mismatch")
        if task["native_raw"] != counts([r["y_functional"] for r in rows], 2):
            raise ValueError("raw native summary mismatch")
    paired = read(output / "paired-comparisons.json")
    for state in paired["states"]:
        rows = [r for r in groups.get("tails", []) if r["task_id"] == state["task_id"]]
        has_skill = bool(state["choice"].get("skill_id"))
        actual = compare_state(
            [
                {
                    **r,
                    "y_functional": r["acceptance_validity"][
                        "interpretable_y_functional"
                    ],
                }
                for r in rows
            ],
            has_skill=has_skill,
        )
        if (
            actual != state["comparison"]
            or compare_state(rows, has_skill=has_skill) != state["raw_comparison"]
        ):
            raise ValueError("paired summary mismatch")
    if aggregate(paired["states"]) != paired["equal_mechanism_aggregation"]:
        raise ValueError("mechanism aggregate mismatch")
    return {
        "status": "OVERLAY_AND_FUNCTIONAL_SUMMARIES_RECOMPUTED",
        "model_calls": 0,
        "new_checker_executions": 0,
        "scope": "Public saved JUnit/raw functional labels, validity overlay, difficulty counts, paired and equal-mechanism summaries. Prefix/source replay and panel eligibility are separately evidenced, not re-executed.",
    }


def build(private, output, plan_path, objective_path):
    plan = read(plan_path)
    objective = load_objective(objective_path)
    output.mkdir(parents=True, exist_ok=True)
    groups = {}
    for name, path in [
        ("native", private / "native-v1"),
        ("tails", private / "tails-v1"),
    ]:
        if not (path / "records.json").exists():
            continue
        bundle = read(path / "records.json")
        # Explicitly inherit only the existing functional evaluator. The old
        # learning/matrix contrast in objective-lock is not this study's claim.
        bundle["objective_sha256"] = objective["sha256"]
        derived = private / (name + "-export-records.json")
        dump(derived, bundle)
        export(derived, objective_path, output / name, group=name)
        groups[name] = bundle["rows"]
        dest = output / name / "records.json"
        public = read(dest)
        for source, row in zip(bundle["rows"], public["rows"]):
            row["acceptance_validity"] = acceptance_audit(source)
            row.update(
                {
                    k: source[k]
                    for k in ("arm", "phase", "stratum", "state_id")
                    if k in source
                }
            )
        dump(dest, public)
    ledger = cost_ledger(groups)
    ledger["host_orchestration_usage"] = (
        "UNAVAILABLE; not included in research Agent totals"
    )
    ledger["source_preparation_and_qualification"] = (
        "Preparation/qualification scripts make zero repair-Agent model calls. Host authoring and review assistance are separate and unavailable, not zero."
    )
    ledger["skill_selection_assistance"] = {
        "status": "TRIGGERED_SEE_INPUT_OUTPUT_RECEIPTS"
        if (private / "selection.json").exists()
        else "NOT_TRIGGERED",
        "contexts": 1 if (private / "selection.json").exists() else 0,
        "tokens": None if (private / "selection.json").exists() else 0,
    }
    ledger["independent_readonly_review"] = {
        "status": "PERFORMED",
        "tokens": None,
        "scope": "Separate reviewer and follow-ups; unavailable usage is not included in research-Agent totals and is not zero.",
    }
    dump(output / "costs.json", ledger)
    native = groups.get("native", [])
    table = []
    for task in plan["tasks"]:
        rows = [r for r in native if r["task_id"] == task["task_id"]]
        cps = []
        for row in rows:
            for name in row["execution"].get("checkpoints", []):
                cp = Path(name)
                m = read(cp / "checkpoint.json")
                s = m["state"]
                cps.append(
                    {
                        "repeat": row["repeat"],
                        "stage": s["stage"],
                        "completed_turn_index": s["completed_turn_index"],
                        "remaining_seconds": m["remaining_seconds"],
                        "legal_main_tail": s["stage"] != "E0"
                        and m["remaining_seconds"] >= plan["min_remaining_seconds"]
                        and bool(m.get("last_turn_id")),
                        "prefix_sha256": m.get("visible_prefix_sha256"),
                        "checkpoint_sha256": digest(cp / "checkpoint.json"),
                        "public_test_command": s.get("public_test_command"),
                        "failure_text": s.get("failure_text"),
                        "observed_skill_reads": s.get("observed_skill_reads"),
                        "state_role": "task_origin_control"
                        if s["stage"] == "E0"
                        else "public_failure_boundary"
                        if s["stage"] == "E1"
                        else "first_delivery_boundary",
                    }
                )
        table.append(
            {
                "task_id": task["task_id"],
                "mechanism": task["mechanism"],
                "qualification": task["qualification"],
                "native_raw": counts([r["y_functional"] for r in rows], 2),
                "native": counts(
                    [acceptance_audit(r)["interpretable_y_functional"] for r in rows], 2
                ),
                "repeats": [
                    {
                        "repeat": r["repeat"],
                        "y_target": r["y_target"],
                        "y_regression": r["y_regression"],
                        "y_functional": r["y_functional"],
                        "acceptance_validity": acceptance_audit(r),
                    }
                    for r in rows
                ],
                "checkpoints": cps,
            }
        )
    dump(output / "native-difficulty.json", {"tasks": table})
    selected_path = private / "selection.json"
    states = []
    if selected_path.exists():
        selected = read(selected_path)
        for entry in selected["states"]:
            cp = Path(entry["checkpoint"])
            meta = read(cp / "checkpoint.json")
            rows = [
                r for r in groups.get("tails", []) if r["task_id"] == entry["task_id"]
            ]
            receipts = []
            for row in rows:
                run = Path(row["run"])
                started = read(run / "started.json")
                if (
                    started["initial_files"] != meta["files"]["source"]
                    or started["initial_remaining"] != meta["remaining_seconds"]
                ):
                    raise ValueError("different actual starting files/budget")
                fork = read(run / "fork.json") if (run / "fork.json").exists() else None
                if fork and (
                    fork["parent_thread"] != meta["thread_id"]
                    or fork["boundary_id"] != meta["last_turn_id"]
                    or fork["expected_prefix_sha256"] != meta["visible_prefix_sha256"]
                ):
                    raise ValueError("different actual fork")
                guidance = (
                    None
                    if row["arm"] == "N"
                    else selected["generic"]
                    if row["arm"] == "G"
                    else entry["payload"]
                )
                receipts.append(
                    {
                        "arm": row["arm"],
                        "repeat": row["repeat"],
                        "initial_remaining": started["initial_remaining"],
                        "source_identity_matches": True,
                        "prefix_sha256": meta["visible_prefix_sha256"],
                        "fork_matched": fork["matched"] if fork else None,
                        "guidance_sha256": hashlib.sha256(guidance.encode()).hexdigest()
                        if guidance
                        else None,
                        "actual_guidance_observed": row["execution"].get(
                            "model_input_observed"
                        ),
                        "execution_status": row["execution"]["status"],
                    }
                )
            states.append(
                {
                    "task_id": entry["task_id"],
                    "stratum": entry["stratum"],
                    "choice": entry["choice"],
                    "comparison": compare_state(
                        [
                            {
                                **r,
                                "y_functional": acceptance_audit(r)[
                                    "interpretable_y_functional"
                                ],
                            }
                            for r in rows
                        ],
                        has_skill=bool(entry["skill_id"]),
                    ),
                    "raw_comparison": compare_state(
                        rows, has_skill=bool(entry["skill_id"])
                    ),
                    "receipts": receipts,
                }
            )
    dump(
        output / "paired-comparisons.json",
        {
            "states": states,
            "equal_mechanism_aggregation": aggregate(states),
            "mechanism_unit": "one state per source mechanism; repeats are stochastic executions, not independent tasks",
            "learned_policy_gain": "NOT_TESTED",
            "default_policy": "UNCHANGED",
        },
    )
    return {
        "native_rows": len(native),
        "tail_rows": len(groups.get("tails", [])),
        "model_calls": 0,
        "new_verifier_executions": 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["export", "replay"])
    p.add_argument("--private", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--plan",
        type=Path,
        default=Path("configs/task-skill-failure-diagnostic-v1/plan.json"),
    )
    p.add_argument(
        "--objective",
        type=Path,
        default=Path("configs/functional-gain-v2/objective-lock.json"),
    )
    a = p.parse_args()
    if a.command == "export":
        result = build(a.private, a.output, a.plan, a.objective)
    else:
        result = {
            name: replay(
                a.output / name / "records.json",
                a.objective,
                public_root=a.output / name,
            )
            for name in ("native", "tails")
            if (a.output / name / "records.json").exists()
        }
        result["diagnostic"] = replay_diagnostic(a.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
