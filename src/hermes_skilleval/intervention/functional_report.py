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
    planned_actions = {
        (tid, r["repeat"], r["action"])
        for tid, lock in panel_locks
        for r in lock["action_roster"]
    }
    if not set(actions) <= planned_actions:
        raise ValueError("unregistered common-panel sample")
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
        "NOT_ESTABLISHED"
        if not panel_locks
        else "NOT_IDENTIFIABLE"
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
        "NOT_ESTABLISHED"
        if not panel_locks
        else "NOT_IDENTIFIABLE"
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


def summarize(
    protocol_path, objective_path, collection, evaluation, models, output, roster_path
):
    """Recompute claims from verified saved records; no model or Agent execution."""
    import hashlib
    from pathlib import Path
    from .functional_outcomes import load_objective
    from .functional_pairs import paired_records, signal_summary, verify_collection_roster
    from .functional_export import replay
    from .learning import model_identity
    from .session import dump
    from .study import read

    objective = load_objective(objective_path)
    protocol = read(protocol_path)
    if protocol["objective_sha256"] != objective["sha256"]:
        raise ValueError("report objective mismatch")
    collection, evaluation, models, output = map(
        Path, (collection, evaluation, models, output)
    )
    sources = {}

    def verified_rows(path):
        if not path.exists():
            return []
        sources[str(path)] = replay(path, objective_path)
        return read(path)["rows"]

    collected = verified_rows(collection / "records.json")
    matrix = verified_rows(evaluation / "matrix-records.json")
    panel = verified_rows(evaluation / "panel-records.json")
    delayed = verified_rows(evaluation / "delay-records.json")
    collection_bundle = (
        read(collection / "records.json")
        if (collection / "records.json").exists()
        else {}
    )
    expected_training = {
        r["task_id"] for r in protocol["tasks"] if r["split"] != "test"
    }
    collection_roster = verify_collection_roster(
        collected,
        read(roster_path),
        hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        require_complete=False,
    )
    collected_all = collection_roster["complete"] and (
        set(collection_bundle.get("completed_tasks", [])) == expected_training
    )
    signal = signal_summary(
        paired_records(collected), collection_complete=collected_all
    )
    finals = [r for r in protocol["tasks"] if r["split"] == "test"]
    roster = [
        {"task_id": r["task_id"], "method": m, "repeat": n}
        for r in finals
        for m in METHODS
        for n in (1, 2)
    ]
    families = {r["task_id"]: r["family"] for r in protocol["tasks"]}
    main = functional_main_table(matrix, roster, families)
    locks = []
    for task in finals:
        path = evaluation / task["task_id"] / "panel-lock.json"
        if path.exists():
            lock = read(path)
            if "lock_sha256" in lock:
                locks.append((task["task_id"], lock))
    registered = (
        read(evaluation / "delay-roster.json")["rows"]
        if (evaluation / "delay-roster.json").exists()
        else []
    )
    mechanism = mechanism_tables(panel, delayed, locks, families, registered)
    training = "NOT_RUN"
    if (models / "training.json").exists():
        training_report = read(models / "training.json")
        if training_report.get("status") == "PARTIAL_METHOD":
            training = "INSUFFICIENT_SIGNAL"
        elif (models / "independent-reload.json").exists():
            reload = read(models / "independent-reload.json")
            if all(
                reload.get(name, {}).get("match") is True
                and reload[name].get("model_identity") == model_identity(models / name)
                for name in ("full", "task-only")
            ):
                training = "TRAINED_AND_RELOADED"
    panel_planned = sum(len(lock["action_roster"]) for _, lock in locks)
    panel_complete = (
        len(locks) == len(finals)
        and len(panel) == panel_planned
        and all(r["y_functional"] is not None for r in panel)
    )
    delay_complete = (
        panel_complete
        and len(delayed) == len(registered)
        and all(r["y_functional"] is not None for r in delayed)
    )
    complete = (
        collected_all
        and training == "TRAINED_AND_RELOADED"
        and main["final_functional_evaluation"] == "COMPLETED"
        and panel_complete
        and delay_complete
    )
    truth = {
        "objective_alignment": "VERIFIED",
        "functional_signal": "VARIABLE"
        if signal["nonzero_skill_pairs"]
        else "CONSTANT"
        if signal["status"] == "FUNCTIONAL_SIGNAL_NOT_IDENTIFIABLE"
        else "UNKNOWN",
        "functional_gain_training": training,
        "final_functional_evaluation": main["final_functional_evaluation"],
        "same_state_representation": "COMPLETED"
        if panel_complete
        else "PARTIAL"
        if panel
        else "NOT_RUN",
        "waiting_counterfactuals": "NO_ELIGIBLE_OPPORTUNITY"
        if panel_complete and not registered
        else "COMPLETED"
        if delay_complete
        else "PARTIAL",
        "functional_gain_claim": main["functional_gain_claim"],
        "state_incremental_claim": mechanism["state_incremental_claim"],
        "waiting_incremental_claim": mechanism["waiting_incremental_claim"],
        "policy_metric_role": "SECONDARY_ONLY",
        "cost_metric_role": "SECONDARY_ONLY",
        "study_execution": "COMPLETE" if complete else "PARTIAL",
        "method_upgrade": "IMPLEMENTED_AND_EVALUATED" if complete else "PARTIAL_METHOD",
        "deployment": "KEEP_EXISTING_DEFAULT",
        "publication": "PENDING",
    }
    report = {
        "operation": "RECORDS_ONLY_SUMMARY",
        "objective_sha256": objective["sha256"],
        "collection_accounting": {
            **collection_roster,
            "planned_tasks": len(expected_training),
            "completed_tasks": len(collection_bundle.get("completed_tasks", [])),
            "maximum_tails": protocol["maximum_tails"],
            "scored_tails": len(collected),
            "uncompleted_tasks": sorted(
                expected_training - set(collection_bundle.get("completed_tasks", []))
            ),
        },
        "truth": truth,
        "functional_main": main,
        "same_state_mechanisms": mechanism,
        "collection_signal": signal,
        "secondary": secondary_table(matrix),
        "records_replay": sources,
        "final_repository_closure": "NOT_ASSESSED_BY_REPORTER",
        "legacy_results": "REQUIRES_FINAL_BASELINE_DIFF_AUDIT",
        "agent_calls": 0,
        "model_calls": 0,
    }
    dump(output, report)
    return truth
