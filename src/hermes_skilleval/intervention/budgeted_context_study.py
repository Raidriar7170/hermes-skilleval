"""Opt-in finite P/C study on the final content-admission index."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import time

from .anytime_acquisition import acquire
from .evidence_linked_state import analyze
from .linked_context_study import early_checkpoint, functional_label, load_pool, read
from .local_retrieval import retrieve
from .relation_store import atomic_json
from .repair_composer import CompleteEncoder, render_pack, select_mmr
from .repair_content_study import first_checkpoint, verify_checkpoint
from .repair_knowledge import token_count


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recover_outer_budget(budget, acquisition=None):
    import os
    from .anytime_acquisition import reconcile

    active = [s for s in budget.value["stages"] if s["status"] == "ACTIVE"]
    if not active:
        return
    for stage in active:
        try:
            os.kill(stage["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError("Previous preparation process still exists")
    if acquisition is not None and (acquisition / "active.json").exists():
        # Reconcile helper before outer accounting. Restore marker for core recovery.
        marker = read(acquisition / "active.json")
        reconcile(acquisition)
        atomic_json(acquisition / "active.json", marker)
    budget.recover(confirmed_stopped=True)


def compose(plan, tasks, output, encoder_path):
    """Persist independent baselines before A and retain all preparation costs."""
    from .value import Encoder
    from .method_budget import MethodBudget, boot_identity
    from .repair_knowledge import RepairKnowledgeUnit, render_units

    for task in plan["tasks"]:
        tid = task["instance_id"]
        root = output / "selection" / tid
        selection_path = root / "selection.json"
        if selection_path.exists() and read(selection_path)["status"] == "LOCKED":
            continue
        execution = read(output / "prefixes" / tid / "execution.json")
        cp = first_checkpoint(execution)
        if cp is None:
            atomic_json(
                selection_path,
                {"task_id": tid, "status": "NO_PREFIX", "checkpoint": None},
            )
            continue
        meta = verify_checkpoint(cp)
        initial = {
            "task_id": tid,
            "status": "N_READY",
            "checkpoint": str(cp),
            "checkpoint_sha256": sha(cp / "checkpoint.json"),
            "prefix_remaining_seconds": meta["remaining_seconds"],
            "messages": {"N": None},
            "costs": {"N": 0},
            "plan_digest": plan["plan_digest"],
        }
        if not selection_path.exists():
            atomic_json(selection_path, initial)
        identity = plan["plan_digest"] + initial["checkpoint_sha256"]
        local_budget = MethodBudget(
            root / "local-cost.json",
            meta["remaining_seconds"],
            identity=identity,
            host_clock=boot_identity(),
        )
        recover_outer_budget(local_budget)
        try:
            if not (root / "M.json").exists():
                with local_budget.stage("ledger_index_encoder_candidates_mmr"):
                    ledger = analyze(
                        meta["state"]["request"],
                        meta["visible_events"],
                        checkpoint_event_count=len(meta["visible_events"]),
                        initial_source_version=task["base_commit"],
                    )
                    atomic_json(root / "ledger.json", ledger)
                    index = read(
                        output / "public-knowledge" / task["base_commit"] / "index.json"
                    )
                    encoder = CompleteEncoder(Encoder(encoder_path))
                    pool, diag = retrieve(
                        index,
                        ledger,
                        encoder=encoder,
                        visible_text="\n".join(
                            o["output"] for o in ledger["observations"]
                        ),
                        read_symbols=tuple(
                            p
                            for o in ledger["observations"]
                            if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
                            for p in o["paths"]
                        ),
                    )
                    atomic_json(root / "pool.json", asdict(pool))
                    atomic_json(root / "retrieval.json", diag)
                    mmr = select_mmr(pool)
                    atomic_json(
                        root / "M.json",
                        {"pack": mmr.to_dict(), "message": render_pack(mmr)},
                    )
            local = local_budget.spent
            m = read(root / "M.json")
            state = read(selection_path)
            state.update(
                status="M_READY",
                messages={"N": None, "M": m["message"] or None},
                costs={"N": 0, "M": local},
            )
            atomic_json(selection_path, state)
        except (ValueError, RuntimeError, TimeoutError) as exc:
            state = read(selection_path)
            state["local_error"] = str(exc)
            atomic_json(selection_path, state)
            continue
        ledger, pool = read(root / "ledger.json"), load_pool(root / "pool.json")
        relation_limit = min(
            plan["relation_seconds_max"],
            plan["relation_fraction_of_postlocal_remaining"] * local_budget.remaining,
        )
        a_budget = MethodBudget(
            root / "A-cost.json",
            local_budget.remaining,
            identity=identity,
            host_clock=boot_identity(),
        )
        recover_outer_budget(a_budget, root / "A")
        try:
            with a_budget.stage("anytime_acquisition_and_render"):
                result = acquire(
                    ledger,
                    pool,
                    root / "A",
                    seconds=relation_limit,
                    pair_cap=plan["relation_unique_pair_cap"],
                    batch_size=plan["relation_batch_size"],
                    call_seconds=plan["helper_call_deadline_seconds"],
                )
                amessage = render_units(
                    [RepairKnowledgeUnit.from_dict(u) for u in result["pack"]["units"]]
                )
            state["messages"]["A"] = amessage or None
            state["costs"]["A"] = local + a_budget.spent
            state.update(
                A_status=result["status"],
                A_stop_reason=result["stop_reason"],
                A_relation_seconds=result["relation_seconds"],
                A_relation_limit=relation_limit,
                A_budget_overrun=result["budget_overrun"],
            )
        except (ValueError, RuntimeError, TimeoutError) as exc:
            state["A_error"] = str(exc)
            try:
                state["costs"]["A"] = local + a_budget.spent
                state["messages"]["A"] = m["message"] or None
                state["A_status"] = "MMR_FALLBACK"
            except ValueError:
                state["A_status"] = "UNKNOWN_COST"
        state["status"] = "LOCKED"
        atomic_json(selection_path, state)
        atomic_json(root / "core-lock.json", state)


def matrix(plan):
    rng = random.Random(plan["order_seed"])
    cells = []
    for task in plan["tasks"]:
        for protocol, arms in [("P", ["N", "M", "A"]), ("C", ["M", "A", "D"])]:
            for repeat in range(1, plan["tail_repeats"] + 1):
                order = list(arms)
                rng.shuffle(order)
                cells += [
                    dict(
                        task_id=task["instance_id"],
                        protocol=protocol,
                        arm=arm,
                        repeat=repeat,
                    )
                    for arm in order
                ]
    return cells


def cell_path(output, cell):
    return (
        output
        / "tails"
        / cell["task_id"]
        / f"{cell['protocol']}-{cell['arm']}-r{cell['repeat']}"
    )


def reconcile_runner(output, plan):
    """Keep interrupted original cells after proving their owned containers stopped."""
    import os
    import subprocess

    marker = output / "runner-active.json"
    record = read(marker)
    if "pid" not in record:
        raise ValueError("Legacy runner marker lacks verifiable process identity")
    try:
        os.kill(record["pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError("Previous runner process still exists")
    ids = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
    if ids:
        containers = json.loads(
            subprocess.check_output(["docker", "inspect", *ids], text=True)
        )
        root = str(output.resolve()) + "/"
        if any(
            m.get("Source", "").startswith(root)
            for c in containers
            for m in c.get("Mounts", [])
        ):
            raise ValueError("Owned study container still running")
    paths = [cell_path(output, c) for c in matrix(plan)]
    paths += [output / "prefixes" / t["instance_id"] for t in plan["tasks"]]
    for path in paths:
        if path.exists() and not (path / "execution.json").exists():
            atomic_json(
                path / "execution.json",
                {
                    "status": "UNKNOWN_INTERRUPTED_ATTEMPT",
                    "research_execution_started": True,
                    "no_running_tool_confirmation": True,
                    "recovery": "original_attempt_preserved_no_resampling",
                    "budget_status": "UNKNOWN",
                },
            )
    atomic_json(output / ("runner-recovery-" + str(time.time_ns()) + ".json"), record)
    marker.unlink()


def run(plan, tasks, skills, output, *, phase):
    from .diagnostic import home_auth
    from .study import run_once

    import os

    active = output / "runner-active.json"
    if active.exists():
        reconcile_runner(output, plan)
    with active.open("x") as f:
        json.dump({"phase": phase, "started": time.time(), "pid": os.getpid()}, f)
    auth = None
    try:
        home, auth = home_auth(output)
        if phase == "prefix":
            for task in plan["tasks"]:
                result = run_once(
                    tasks / task["instance_id"],
                    output / "prefixes" / task["instance_id"],
                    home,
                    skills,
                    total=600,
                    image=plan["image"],
                    public_docs=output / "public-knowledge" / task["base_commit"],
                    checkpoint_selector=early_checkpoint,
                    stop_at_checkpoint=True,
                )
                print(task["mechanism"], result["status"], flush=True)
        else:
            by_id = {t["instance_id"]: t for t in plan["tasks"]}
            for cell in matrix(plan):
                if phase in {"P", "C"} and cell["protocol"] != phase:
                    continue
                state = read(output / "selection" / cell["task_id"] / "selection.json")
                dest = cell_path(output, cell)
                if dest.exists():
                    continue
                core_path = output / "selection" / cell["task_id"] / "core-lock.json"
                if core_path.exists():
                    core = read(core_path)
                    for frozen_arm in ("N", "M", "A"):
                        if state.get("messages", {}).get(frozen_arm) != core.get(
                            "messages", {}
                        ).get(frozen_arm):
                            raise ValueError("Locked method message changed")
                        if state.get("costs", {}).get(frozen_arm) != core.get(
                            "costs", {}
                        ).get(frozen_arm):
                            raise ValueError("Locked method charge changed")
                arm = cell["arm"]
                if not state.get("checkpoint") or arm not in state.get("messages", {}):
                    atomic_json(
                        dest / "execution.json",
                        {
                            "status": "NOT_RUN_UNAVAILABLE",
                            "research_execution_started": False,
                        },
                    )
                    continue
                cp = Path(state["checkpoint"])
                if sha(cp / "checkpoint.json") != state["checkpoint_sha256"]:
                    raise ValueError("Changed common checkpoint")
                verify_checkpoint(cp)
                payload = state["messages"][arm]
                charge = state["costs"][arm] if cell["protocol"] == "P" else 0
                charge_path = (
                    output / "cell-budgets" / cell["task_id"] / (dest.name + ".json")
                )
                charge_record = {
                    **cell,
                    "charged_seconds": charge,
                    "preparation_seconds": state["costs"][arm],
                    "initial_remaining": state["prefix_remaining_seconds"],
                    "payload_sha256": hashlib.sha256(
                        (payload or "").encode()
                    ).hexdigest(),
                    "plan_digest": plan["plan_digest"],
                    "status": "STARTED",
                }
                atomic_json(charge_path, charge_record)
                result = run_once(
                    tasks / cell["task_id"],
                    dest,
                    home,
                    skills,
                    from_checkpoint=cp,
                    payload=payload,
                    payload_tokens=token_count(payload or ""),
                    initialization_seconds=charge,
                    image=plan["image"],
                    public_docs=output
                    / "public-knowledge"
                    / by_id[cell["task_id"]]["base_commit"],
                )
                charge_record.update(
                    status="FINISHED", execution_sha256=sha(dest / "execution.json")
                )
                atomic_json(charge_path, charge_record)
                print(cell, result["status"], flush=True)
    finally:
        if auth is not None:
            auth.unlink(missing_ok=True)
        active.unlink(missing_ok=True)


def evaluate(plan, tasks, output, overlays):
    from .repair_checks import accept_candidate

    cells = matrix(plan)
    if (output / "runner-active.json").exists():
        raise ValueError("Runner active; cannot release labels")
    if not all((cell_path(output, c) / "execution.json").exists() for c in cells):
        raise ValueError("All fixed attempts must finish before label release")
    results = []
    for cell in cells:
        root = cell_path(output, cell)
        execution = read(root / "execution.json")
        integrity, target, protected = "UNCONFIRMED", "UNKNOWN", "UNKNOWN"
        if execution["status"] in {"COMPLETED", "TIMEOUT"} and execution.get(
            "thread_id"
        ):
            accepted = accept_candidate(
                tasks / cell["task_id"],
                root,
                root / "acceptance",
                image=plan["image"],
                trusted_overlay=overlays / cell["task_id"],
            )
            integrity = (
                "CONFIRMED" if accepted["integrity"] == "VERIFIED" else "UNCONFIRMED"
            )

            def label(check):
                return (
                    ("PASS" if check["passed"] else "FAIL")
                    if check.get("valid") is True
                    else "UNKNOWN"
                )

            target = label(accepted["checks"]["target"])
            protected = label(accepted["checks"]["regression"])
            if execution.get("injected") and not execution.get("model_input_observed"):
                integrity = "UNCONFIRMED"
        results.append(
            {
                **cell,
                "integrity": integrity,
                "target": target,
                "protected": protected,
                "functional": functional_label(
                    integrity=integrity, target=target, protected=protected
                ),
                "execution_status": execution["status"],
            }
        )
        atomic_json(
            output / "functional-results.json", {"rows": results, "planned": len(cells)}
        )
    return results


def complete_states(plan, output):
    from .relation_reference import complete_reference
    from .repair_knowledge import RepairKnowledgeUnit, render_units

    for task in plan["tasks"]:
        root = output / "selection" / task["instance_id"]
        state = read(root / "selection.json")
        if not (root / "A/selection.json").exists():
            continue
        result = complete_reference(
            read(root / "ledger.json"),
            load_pool(root / "pool.json"),
            root / "A",
            root / "D",
            seconds=plan["dense_seconds_max"],
            batch_size=plan["relation_batch_size"],
        )
        state["D_reference_status"] = result["reference_status"]
        if result["reference_status"] == "COMPLETE_TRANSPORT":
            state["messages"]["D"] = (
                render_units(
                    [RepairKnowledgeUnit.from_dict(u) for u in result["pack"]["units"]]
                )
                or None
            )
            state["costs"]["D"] = state["costs"]["M"] + result["relation_seconds"]
        atomic_json(root / "selection.json", state)


def report(output):
    """Recompute saved functional and budget records, never acceptance or models."""
    from collections import Counter

    saved = read(output / "functional-results.json")
    rows = []
    for r in saved["rows"]:
        state = read(output / "selection" / r["task_id"] / "selection.json")
        cost = state.get("costs", {}).get(r["arm"])
        remaining = state.get("prefix_remaining_seconds")
        tail = (
            None
            if remaining is None or cost is None
            else max(0, remaining - (cost if r["protocol"] == "P" else 0))
        )
        execution_path = cell_path(output, r) / "execution.json"
        budget_path = (
            output
            / "cell-budgets"
            / r["task_id"]
            / (cell_path(output, r).name + ".json")
        )
        validity = "UNKNOWN"
        if budget_path.exists() and execution_path.exists():
            charged, execution = read(budget_path), read(execution_path)
            if (
                charged.get("status") == "FINISHED"
                and charged.get("execution_sha256") == sha(execution_path)
                and execution.get("policy_initialization_seconds")
                == charged["charged_seconds"]
                and execution.get("initial_remaining") == charged["initial_remaining"]
            ):
                actual = execution.get("tail_seconds")
                if isinstance(actual, (float, int)):
                    validity = (
                        "VALID"
                        if actual <= charged["initial_remaining"]
                        else "OVER_BUDGET"
                    )
        rows.append(
            {
                **r,
                "functional": functional_label(
                    integrity=r["integrity"],
                    target=r["target"],
                    protected=r["protected"],
                ),
                "charged_preparation_seconds": cost,
                "tail_budget_seconds": tail,
                "budget_status": validity,
                "strict_functional": functional_label(
                    integrity=r["integrity"],
                    target=r["target"],
                    protected=r["protected"],
                )
                if validity == "VALID"
                else "UNKNOWN",
                "A_status": state.get("A_status"),
                "A_relation_limit": state.get("A_relation_limit"),
                "A_relation_seconds": state.get("A_relation_seconds"),
            }
        )
    tables = {}
    for protocol in ("P", "C"):
        groups = {}
        for row in rows:
            if row["protocol"] != protocol:
                continue
            key = row["task_id"] + "/" + row["arm"]
            groups.setdefault(key, Counter())[row["functional"]] += 1
        tables[protocol] = {
            k: {
                "PASS": v["PASS"],
                "FAIL": v["FAIL"],
                "UNKNOWN": v["UNKNOWN"],
                "planned": sum(v.values()),
            }
            for k, v in groups.items()
        }
    return {
        "rows": rows,
        "tables": tables,
        "planned": saved["planned"],
        "scope": "exploratory_development_comparison",
        "default_policy": "UNCHANGED",
        "budget_scope": "warm-index; P charges reusable measured preparation per repeat; C preparation reported separately",
        "model_calls": 0,
        "acceptance_calls": 0,
    }


def main():
    import argparse
    from .budgeted_study_assets import prepare, freeze, verify
    from .relation_reference import complete_reference, replay_table

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=[
            "prepare",
            "freeze",
            "compose-anytime",
            "complete-reference",
            "run",
            "evaluate",
            "report",
            "replay",
        ],
    )
    for name in (
        "plan",
        "tasks",
        "skills",
        "output",
        "encoder",
        "overlays",
        "legacy-knowledge",
        "ledger",
        "pool",
        "source",
        "table",
    ):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--phase", choices=["prefix", "compose", "P", "C", "tails"])
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--batch-size", type=int, default=2)
    a = p.parse_args()
    if a.output is None:
        p.error("--output is required")
    if a.action == "compose-anytime":
        result = acquire(
            read(a.ledger),
            load_pool(a.pool),
            a.output,
            seconds=a.seconds,
            batch_size=a.batch_size,
        )
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in [
                        "status",
                        "stop_reason",
                        "unique_requested",
                        "relation_seconds",
                    ]
                }
            )
        )
    elif a.action == "complete-reference" and a.ledger:
        result = complete_reference(
            read(a.ledger),
            load_pool(a.pool),
            a.source,
            a.output,
            seconds=a.seconds,
            batch_size=a.batch_size,
        )
        print(result["reference_status"])
    elif a.action == "replay" and a.table:
        atomic_json(a.output, replay_table(read(a.ledger), load_pool(a.pool), a.table))
    elif a.action in {"report", "replay"}:
        atomic_json(a.output / "report.json", report(a.output))
    else:
        plan = read(a.plan)
        if a.action == "prepare":
            prepare(plan, a.tasks, a.legacy_knowledge, a.output)
        elif a.action == "freeze":
            freeze(a.plan, a.tasks, a.skills, a.output, a.encoder, a.overlays)
        else:
            verify(
                plan,
                a.tasks,
                a.skills,
                a.output,
                overlays=a.overlays,
                encoder=a.encoder,
            )
            if a.action == "complete-reference":
                complete_states(plan, a.output)
            elif a.action == "evaluate":
                evaluate(plan, a.tasks, a.output, a.overlays)
            elif a.phase == "compose":
                compose(plan, a.tasks, a.output, a.encoder)
            elif a.phase:
                run(plan, a.tasks, a.skills, a.output, phase=a.phase)
            else:
                p.error("--phase required for run")


if __name__ == "__main__":
    main()
