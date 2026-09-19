"""Functional-first tables with fixed denominators and family-cluster intervals."""

from collections import Counter, defaultdict

from .functional_policy import METHODS
from .report import interval


def indexed(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in fields)
        if key in result:
            raise ValueError("duplicate experimental sample")
        result[key] = row
    return result


def family_interval(task_values, families):
    grouped = defaultdict(list)
    for tid, value in task_values.items():
        grouped[families[tid]].append(value)
    result = interval([sum(v) / len(v) for v in grouped.values()])
    if result is not None:
        result["independent_families"] = result.pop("independent_tasks")
        result["contributing_tasks"] = len(task_values)
        result["method"] = (
            "paired family-cluster percentile bootstrap, seed 7170, 10000 draws; small-n unstable"
        )
    return result


def claim_from_effect(effect, *, complete):
    if not complete or effect is None:
        return "INCONCLUSIVE"
    if effect["mean"] <= 0:
        return "NOT_ESTABLISHED"
    if effect["independent_families"] >= 2 and effect["lower_95"] > 0:
        return "OBSERVED_WITH_LIMITATIONS"
    return "INCONCLUSIVE"


def functional_main_table(rows, roster, families):
    by_key = indexed(rows, ("task_id", "method", "repeat"))
    planned = indexed(roster, ("task_id", "method", "repeat"))
    if not set(by_key) <= set(planned):
        raise ValueError("unregistered final sample")
    table = {}
    for method in METHODS:
        keys = [k for k in planned if k[1] == method]
        outcomes = [by_key.get(k, {}).get("y_functional") for k in keys]
        known = [v for v in outcomes if v is not None]
        passed = sum(v == 1 for v in known)
        unknown = len(keys) - len(known)
        table[method] = {
            "planned": len(keys),
            "recorded": sum(k in by_key for k in keys),
            "functional_pass": passed,
            "functional_fail": len(known) - passed,
            "unknown_or_missing": unknown,
            "observed_known_pass_rate": passed / len(known) if known else None,
            "planned_success_rate_bounds": [
                passed / len(keys),
                (passed + unknown) / len(keys),
            ]
            if keys
            else None,
        }
    comparisons = {}
    for baseline in METHODS[:-1]:
        tasks = sorted({k[0] for k in planned if k[1] == "H-full-v2"})
        values, missing = {}, []
        for tid in tasks:
            repeats = [k[2] for k in planned if k[:2] == (tid, "H-full-v2")]
            deltas = []
            for repeat in repeats:
                full = by_key.get((tid, "H-full-v2", repeat), {}).get("y_functional")
                base = by_key.get((tid, baseline, repeat), {}).get("y_functional")
                if full is None or base is None:
                    missing.append([tid, repeat])
                else:
                    deltas.append(full - base)
            # Do not favor tasks by averaging only their successful observed repeat.
            if len(deltas) == len(repeats) and repeats:
                values[tid] = sum(deltas) / len(deltas)
        effect = family_interval(values, families)
        complete = bool(tasks) and not missing
        comparisons[baseline] = {
            "effect": effect,
            "task_means": values,
            "unknown_pairs": missing,
            "planned_tasks": len(tasks),
            "complete_paired_tasks": len(values),
            "claim": claim_from_effect(effect, complete=complete),
        }
    all_complete = bool(planned) and all(
        t["unknown_or_missing"] == 0 for t in table.values()
    )
    return {
        "primary_outcome": "y_functional",
        "table": table,
        "comparisons": comparisons,
        "final_functional_evaluation": "COMPLETED"
        if all_complete
        else "PARTIAL"
        if rows
        else "NOT_RUN",
        "functional_gain_claim": comparisons["N0-v2"]["claim"],
        "policy_metric_role": "SECONDARY_ONLY",
        "cost_metric_role": "SECONDARY_ONLY",
    }


def secondary_table(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)
    return {
        method: {
            "file_policy_status": dict(
                Counter(r.get("file_policy_status", "UNKNOWN") for r in items)
            ),
            "qualified_delivery": dict(
                Counter(str(r.get("qualified_delivery")) for r in items)
            ),
            "execution_status": dict(
                Counter(r.get("execution_status", "UNKNOWN") for r in items)
            ),
            "observed_active_seconds": sum(
                r["execution"]["tail_seconds"]
                for r in items
                if r["execution"].get("tail_seconds") is not None
            ),
            "active_seconds_unknown": sum(
                r["execution"].get("tail_seconds") is None for r in items
            ),
            "billing": "UNKNOWN; not inferred from seconds or model list pricing",
        }
        for method, items in grouped.items()
    }


def mechanism_tables(panel_rows, delay_rows, panel_locks, families, registered_delays):
    actions = indexed(panel_rows, ("task_id", "repeat", "action"))
    delayed = indexed(delay_rows, ("task_id", "repeat", "action"))
    planned_delays = indexed(registered_delays, ("task_id", "repeat", "action"))
    if not set(delayed) <= set(planned_delays):
        raise ValueError("unregistered delayed sample")
    representation = []
    delay_table = []
    reminders = []
    for tid, lock in panel_locks:
        repeats = sorted({r["repeat"] for r in lock["action_roster"]})
        choices = {m: p["immediate_gain_action"] for m, p in lock["methods"].items()}
        for repeat in repeats:
            observed = {
                m: actions.get((tid, repeat, a), {}).get("y_functional")
                for m, a in choices.items()
            }
            full, task = observed["H-full-v2"], observed["H-task-fixedC-v2"]
            representation.append(
                {
                    "task_id": tid,
                    "repeat": repeat,
                    "stage": lock["state"]["stage"],
                    "representation_identifiable": lock["representation_identifiable"],
                    "choices": choices,
                    "observed_functional": observed,
                    "action_disagreement": choices["H-full-v2"]
                    != choices["H-task-fixedC-v2"],
                    "full_minus_task": None
                    if full is None or task is None
                    else full - task,
                    "scope": "prelocked gain-only choices, not the unobserved outcome of a WAIT policy",
                }
            )
            generic = actions.get((tid, repeat, "GENERIC_REMINDER"), {}).get(
                "y_functional"
            )
            noop = actions.get((tid, repeat, "NO_INTERVENTION"), {}).get("y_functional")
            for candidate in lock["binding"]["candidates"]:
                skill = actions.get((tid, repeat, candidate["id"]), {}).get(
                    "y_functional"
                )
                reminders.append(
                    {
                        "task_id": tid,
                        "repeat": repeat,
                        "skill_id": candidate["id"],
                        "skill_minus_reminder": None
                        if skill is None or generic is None
                        else skill - generic,
                        "skill_minus_noop": None
                        if skill is None or noop is None
                        else skill - noop,
                    }
                )
            now = actions.get((tid, repeat, lock["now_skill"]), {}).get("y_functional")
            for mode in ("DEFER_SAME-v2", "WAIT_THEN_FULL-v2"):
                key = (tid, repeat, mode)
                if key not in planned_delays:
                    continue
                row = delayed.get(key, {})
                y = row.get("y_functional")
                delay_table.append(
                    {
                        "task_id": tid,
                        "repeat": repeat,
                        "mode": mode,
                        "wait_sensitive": lock["wait_sensitive"],
                        "now_skill": lock["now_skill"],
                        "now": now,
                        "never": noop,
                        "delayed": y,
                        "delayed_minus_now": None
                        if y is None or now is None
                        else y - now,
                        "delayed_minus_never": None
                        if y is None or noop is None
                        else y - noop,
                        "actual_injected": row.get("execution", {}).get("injected"),
                        "actual_decision_stages": [
                            d["stage"]
                            for d in row.get("execution", {}).get("decisions", [])
                        ],
                    }
                )

    def effect(rows, field):
        by_task = defaultdict(list)
        for row in rows:
            by_task[row["task_id"]].append(row[field])
        complete = {
            t: sum(values) / len(values)
            for t, values in by_task.items()
            if all(v is not None for v in values)
        }
        return {
            "effect": family_interval(complete, families),
            "planned_tasks": len(by_task),
            "complete_tasks": len(complete),
            "unknown_pairs": sum(r[field] is None for r in rows),
        }

    eligible_rep = [r for r in representation if r["representation_identifiable"]]
    rep_effect = effect(eligible_rep, "full_minus_task")
    rep_claim = (
        "NOT_IDENTIFIABLE"
        if not eligible_rep
        else claim_from_effect(
            rep_effect["effect"], complete=rep_effect["unknown_pairs"] == 0
        )
    )
    timing = {}
    for mode in ("DEFER_SAME-v2", "WAIT_THEN_FULL-v2"):
        selected = [r for r in delay_table if r["mode"] == mode]
        sensitive = [r for r in selected if r["wait_sensitive"]]
        timing[mode] = {
            "all_selected": effect(selected, "delayed_minus_now"),
            "wait_sensitive": effect(sensitive, "delayed_minus_now"),
            "sensitive_pairs": len(sensitive),
        }
    sensitive = timing["WAIT_THEN_FULL-v2"]["wait_sensitive"]
    wait_claim = (
        "NOT_IDENTIFIABLE"
        if not timing["WAIT_THEN_FULL-v2"]["sensitive_pairs"]
        else claim_from_effect(
            sensitive["effect"], complete=sensitive["unknown_pairs"] == 0
        )
    )
    return {
        "representation_rows": representation,
        "representation_effect": rep_effect,
        "state_incremental_claim": rep_claim,
        "representation_scope": "same candidate immediate-gain decisions; causal generalization limited by noisy paired tails",
        "delay_rows": delay_table,
        "timing_effects": timing,
        "waiting_incremental_claim": wait_claim,
        "wait_effect_marker": "WAIT_EFFECT_NOT_IDENTIFIABLE_IN_OBSERVED_STATES"
        if wait_claim == "NOT_IDENTIFIABLE"
        else wait_claim,
        "skill_vs_reminder_rows": reminders,
        "policy_metric_role": "SECONDARY_ONLY",
        "cost_metric_role": "SECONDARY_ONLY",
    }
