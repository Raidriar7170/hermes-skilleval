"""Small resumable acquisition loop. Baseline is saved before any helper call."""

import json
import os
from pathlib import Path
import time

from .anytime_relation_selector import ExactSelector
from .budgeted_relation_session import BATCH_PROMPT, call_batch
from .method_budget import MethodBudget
from .relation_store import RelationStore, atomic_json
from .repair_composer import select_mmr
from .repair_knowledge import token_count


def reconcile(output):
    """Recover only a dead local owner and positively confirmed stopped helpers."""
    import subprocess

    active = output / "active.json"
    old = json.loads(active.read_text())
    try:
        os.kill(old["pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError("Previous acquisition process still exists")
    for batch in output.glob("batch-*"):
        cost = batch / "cost.json"
        if cost.exists() and json.loads(cost.read_text()).get(
            "no_running_tool_confirmation"
        ):
            continue
        saved = json.loads((batch / "input.json").read_text())
        name = saved.get("container_name")
        if not name:
            raise ValueError("Unconfirmed interrupted helper identity")
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip() == "false":
            continue
        if result.returncode != 0 and "No such object" in result.stderr:
            continue
        raise ValueError("Previous helper has not been confirmed stopped")
    active.unlink()


def acquire(
    ledger,
    pool,
    output,
    *,
    seconds=60,
    pair_cap=48,
    batch_size=8,
    call_seconds=20,
    strategy="A",
    count_tokens=token_count,
    helper=call_batch,
    seed_store=None,
):
    from dataclasses import asdict
    from .method_budget import boot_identity
    from .source_relation import identity

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    contract = identity(
        {
            "ledger": ledger,
            "pool": asdict(pool),
            "seconds": seconds,
            "pair_cap": pair_cap,
            "batch_size": batch_size,
            "call_seconds": call_seconds,
            "strategy": strategy,
            "seed_store": seed_store,
            "tokenizer": count_tokens.__module__ + "." + count_tokens.__name__,
            "prompt": BATCH_PROMPT,
            "algorithm": "budgeted-acquisition-v1",
        }
    )
    contract_path = output / "contract.json"
    if (
        contract_path.exists()
        and json.loads(contract_path.read_text())["identity"] != contract
    ):
        raise ValueError("Changed acquisition contract")
    active = output / "active.json"
    recovered = active.exists()
    if recovered:
        reconcile(output)
    with active.open("x") as f:
        json.dump({"pid": os.getpid(), "started_timestamp": time.time()}, f)
    try:
        atomic_json(contract_path, {"identity": contract})
        if (output / "selection.json").exists():
            return json.loads((output / "selection.json").read_text())
        budget = MethodBudget(
            output / "budget.json",
            seconds,
            identity=contract,
            host_clock=boot_identity(),
        )
        if recovered:
            budget.recover(confirmed_stopped=True)
        remaining = budget.remaining
        deadline = time.monotonic() + remaining
        trace = (
            json.loads((output / "trace.json").read_text())
            if (output / "trace.json").exists()
            else []
        )
        queried = {tuple(p) for step in trace for p in step["requested"]}
        # Existing baseline is available even when recovery conservatively consumed the budget.
        from contextlib import nullcontext

        with budget.stage("store_and_baseline") if remaining > 0 else nullcontext():
            store = RelationStore(
                output / "relations.json", ledger, pool, prompt=BATCH_PROMPT
            )
            if seed_store is not None and not trace:
                if seed_store["input_identity"] != store.digest:
                    raise ValueError("Dense seed relation identity differs")
                seeded = {tuple(r["pair"]): r["record"] for r in seed_store["records"]}
                if set(seeded) != set(store.pairs):
                    raise ValueError("Dense seed domain differs")
                from .relation_store import TERMINAL

                for pair, row in seeded.items():
                    if row["state"] in TERMINAL:
                        store.records[pair] = row
                store.save()
            mmr = select_mmr(pool, count_tokens=count_tokens)
            atomic_json(output / "mmr.json", mmr.to_dict())
        pack = mmr
        state = {
            "status": "MMR_FALLBACK",
            "lower": None,
            "upper": None,
            "stable": False,
        }
        current_path = output / "current-pack.json"
        if current_path.exists():
            from .repair_composer import KnowledgePack
            from .repair_knowledge import RepairKnowledgeUnit

            saved = json.loads(current_path.read_text())
            p = saved["pack"]
            pack = KnowledgePack(
                p["method"],
                tuple(p["indices"]),
                tuple(RepairKnowledgeUnit.from_dict(u) for u in p["units"]),
                p["tokens"],
                p["scores"],
                tuple(p["decisions"]),
            )
            state = saved["state"]
        reason = "TIME_BUDGET"
        if budget.remaining > 0:
            with budget.stage("acquisition"):
                try:
                    solver = ExactSelector(
                        pool, ledger, count_tokens=count_tokens, deadline=deadline - 1
                    )
                    pack, state = solver.solve(store, deadline=deadline - 1)
                    atomic_json(current_path, {"pack": pack.to_dict(), "state": state})
                    while time.monotonic() < deadline - 5:
                        if state["stable"] and strategy != "D":
                            reason = "RELATION_OBJECTIVE_STABLE"
                            break
                        pending = store.pending()
                        if not pending:
                            reason = "ALL_REQUESTABLE_COMPLETE"
                            break
                        available_new = pair_cap - len(queried)
                        elapsed = sum(t.get("elapsed", 0) for t in trace)
                        lengths = sum(t.get("input_characters", 0) for t in trace)
                        rate = elapsed / lengths if elapsed and lengths else None
                        reqs = {
                            r["requirement_id"]: r["expected_text"]
                            for r in ledger["requirements"]
                        }
                        units = {
                            c.unit.unit_id: c.unit.statement for c in pool.candidates
                        }
                        sizes = {
                            p: len(reqs[p[0]]) + len(units[p[1]]) + 200 for p in pending
                        }
                        costs = (
                            {p: max(0.001, sizes[p] * rate) for p in pending}
                            if rate
                            else None
                        )
                        proposed = solver.requests(
                            store,
                            state,
                            size=len(pending),
                            strategy="S" if strategy == "D" else strategy,
                            costs=costs,
                            offset=sum(len(t["requested"]) for t in trace),
                        )
                        batch = []
                        for pair in proposed:
                            if pair not in queried and available_new <= 0:
                                continue
                            batch.append(pair)
                            if pair not in queried:
                                available_new -= 1
                            if len(batch) == batch_size:
                                break
                        if not batch:
                            reason = "UNIQUE_PAIR_CAP"
                            break
                        limit = min(call_seconds, deadline - time.monotonic() - 5)
                        if limit <= 0:
                            break
                        step = {
                            "requested": batch,
                            "seconds_limit": limit,
                            "ordinal": len(trace),
                            "before": state,
                            "strategy": strategy,
                            "status": "STARTED",
                            "input_characters": sum(sizes[p] for p in batch),
                            "query_basis": [
                                {
                                    "pair": p,
                                    "requirement_weight": ledger["weights"][p[0]],
                                    "bounds": store.bounds(p),
                                    "estimated_cost": costs[p] if costs else 1.0,
                                    "reason": "requirement_round_robin"
                                    if (sum(len(t["requested"]) for t in trace) + k + 1)
                                    % 3
                                    == 0
                                    else "decision_priority",
                                }
                                for k, p in enumerate(batch)
                            ],
                        }
                        trace.append(step)
                        atomic_json(output / "trace.json", trace)
                        queried.update(batch)
                        store.ingest(batch, {})
                        started = time.monotonic()
                        try:
                            value = helper(
                                ledger,
                                pool,
                                batch,
                                output / f"batch-{len(trace):04}",
                                seconds=limit,
                            )
                            store.ingest(
                                batch, value, late=time.monotonic() >= deadline
                            )
                            step["status"] = "COMPLETED"
                        except (
                            RuntimeError,
                            TimeoutError,
                            ValueError,
                            IndexError,
                        ) as exc:
                            step["status"], step["error"] = "ERROR", str(exc)
                            reason = "HELPER_UNAVAILABLE"
                        finally:
                            step["elapsed"] = time.monotonic() - started
                            atomic_json(output / "trace.json", trace)
                        if step["status"] == "ERROR":
                            break
                        pack, state = solver.solve(store, deadline=deadline - 1)
                        atomic_json(
                            current_path, {"pack": pack.to_dict(), "state": state}
                        )
                        if len(queried) >= pair_cap:
                            reason = "UNIQUE_PAIR_CAP"
                            break
                except TimeoutError:
                    reason = "TIME_BUDGET"
        if not store.pairs:
            reason = "EMPTY_DOMAIN"
        result = {
            "pack": pack.to_dict(),
            **state,
            "stop_reason": reason,
            "unique_requested": len(queried),
            "relation_seconds": budget.spent,
            "relation_limit": seconds,
            "budget_overrun": budget.spent > seconds,
            "relations": store.summary(),
            "input_identity": store.digest,
            "acquisition_identity": contract,
        }
        atomic_json(output / "selection.json", result)
        return json.loads((output / "selection.json").read_text())
    finally:
        active.unlink(missing_ok=True)
