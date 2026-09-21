"""Executable opt-in evidence-linked research entry points; legacy stays immutable."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .evidence_linked_state import analyze
from .local_source_index import build_index
from .local_retrieval import retrieve
from .linked_composition import select
from .repair_composer import Candidate, CandidatePool, CompleteEncoder, Obligation
from .repair_knowledge import RepairKnowledgeUnit
from .session import dump
from .source_relation import propose_with_session, validate_relations


def read(path):
    return json.loads(Path(path).read_text())


def load_pool(path):
    data = read(path)
    return CandidatePool(
        tuple(
            Candidate(
                RepairKnowledgeUnit.from_dict(c["unit"]),
                c["relevance"],
                tuple(c["coverage"]),
                c["exposure"],
                c["retrieval"],
            )
            for c in data["candidates"]
        ),
        tuple(tuple(r) for r in data["overlap"]),
        tuple(Obligation(**o) for o in data["obligations"]),
        data["query"],
    )


def functional_label(*, integrity, target, protected):
    if integrity != "CONFIRMED":
        return "UNKNOWN"
    if "FAIL" in (target, protected):
        return "FAIL"
    if target == protected == "PASS":
        return "PASS"
    return "UNKNOWN"


def early_checkpoint(state, seen, events, done):
    """First completed turn with public request-related source/test observation."""
    import re
    from .state import FILE, is_test_command

    if state.completed_turn_index <= 0:
        return None
    terms = set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]{2,}", state.request.lower()))
    declared_paths = FILE.findall(state.request)
    declared_stems = {Path(p).stem.removeprefix("test_") for p in declared_paths}
    for event in events:
        if event.get("method") != "item/completed":
            continue
        item = event.get("params", {}).get("item", {})
        if item.get("type") != "commandExecution" or item.get("exitCode") is None:
            continue
        command = item.get("command", "")
        paths = FILE.findall(command)
        related = any(
            any(p.endswith(q) for q in declared_paths)
            or Path(p).stem.removeprefix("test_") in declared_stems
            or Path(p).stem.removeprefix("test_")
            in terms - {"__init__", "test", "tests", "main", "base", "utils", "common"}
            for p in paths
        )
        actual_read = (
            item.get("exitCode") == 0
            and any(
                a.get("type") in {"read", "search"}
                for a in item.get("commandActions", [])
            )
            and bool(item.get("aggregatedOutput"))
        )
        if related and (actual_read or is_test_command(command)):
            return "E1" if "E1" not in seen else None
    return "E2" if done and "E2" not in seen else None


def verify_frozen(plan, tasks, skills, output):
    import hashlib
    import subprocess
    from .session import inventory

    root = Path(__file__).resolve().parents[3]
    if plan["status"] != "FROZEN":
        raise ValueError("Unfrozen method")
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    if (
        hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        != plan["plan_digest"]
    ):
        raise ValueError("Frozen plan content changed")
    if (
        plan["model"] != "gpt-5.6-sol"
        or plan["effort"] != "medium"
        or plan["total_seconds"] != 600
    ):
        raise ValueError("Unsupported executor identity or budget")
    for name, expected in plan["algorithm_files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen algorithm changed: " + name)
    if inventory(skills) != plan["skills"]:
        raise ValueError("Shared skills changed")
    actual = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if actual != plan["image_id"]:
        raise ValueError("Executor image changed")
    for field, path in (
        ("defaults_sha256", "configs/evidence-linked-local-retrieval-v1/defaults.json"),
        (
            "selection_review_sha256",
            "configs/evidence-linked-local-retrieval-v1/selection-review.json",
        ),
    ):
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != plan[field]:
            raise ValueError("Frozen study configuration changed")
    for task in plan["tasks"]:
        if (
            inventory(output / "public-knowledge" / task["base_commit"])
            != task["public_knowledge_files"]
        ):
            raise ValueError("Shared public knowledge changed")
        if (
            hashlib.sha256(
                (tasks / task["instance_id"] / "task.json").read_bytes()
            ).hexdigest()
            != task["task_sha256"]
        ):
            raise ValueError("Task execution profile changed")
        for field in ("base", "evaluation"):
            actual = hashlib.sha256(
                json.dumps(
                    inventory(tasks / task["instance_id"] / field), sort_keys=True
                ).encode()
            ).hexdigest()
            if actual != task["files"][field]:
                raise ValueError("Frozen task changed: " + field)
        if (
            hashlib.sha256(
                (tasks / task["instance_id"] / "request.txt").read_bytes()
            ).hexdigest()
            != task["request_sha256"]
        ):
            raise ValueError("Public request changed")


def run_prefixes(plan, tasks, skills, output):
    from .diagnostic import home_auth
    from .study import run_once

    verify_frozen(plan, tasks, skills, output)
    home, auth = home_auth(output)
    try:
        for row in plan["tasks"]:
            tid = row["instance_id"]
            result = run_once(
                tasks / tid,
                output / "prefixes" / tid,
                home,
                skills,
                total=plan["total_seconds"],
                image=plan["image"],
                public_docs=output / "public-knowledge" / row["base_commit"],
                checkpoint_selector=early_checkpoint,
                stop_at_checkpoint=True,
            )
            print(
                json.dumps(
                    {"phase": "prefix", "task": tid, "status": result["status"]}
                ),
                flush=True,
            )
    finally:
        auth.unlink(missing_ok=True)


def preprocessing_unavailable(task_id, checkpoint, reason):
    """Retain every planned cell without inventing a relation or a repaired arm."""
    import hashlib

    return {
        "task_id": task_id,
        "status": "UNAVAILABLE_PREPROCESS_FAILURE",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(
            (checkpoint / "checkpoint.json").read_bytes()
        ).hexdigest(),
        "messages": {arm: None for arm in ("N", "M-local", "H-sim", "H-link")},
        "packs": {},
        "failure_reason": reason,
        "method_available": False,
        "common_charge_seconds": None,
        "remaining_after_common_charge": None,
        "cost_status": "known_helper_costs_retained; whole interrupted preprocessing duration unconfirmed",
        "validation_status": "REPAIRED_AFTER_FREEZE; no semantic or repair resampling",
    }


def compose_new_states(plan, tasks, skills, output, encoder_path):
    import hashlib
    import random
    import time
    from .value import Encoder
    from .repair_content_study import first_checkpoint, verify_checkpoint
    from .source_relation import compact_propose, propose_observation_links
    from .repair_composer import render_pack

    verify_frozen(plan, tasks, skills, output)
    for name, expected in plan["representation"]["files"].items():
        if hashlib.sha256((encoder_path / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen encoder changed")
    model_started = time.monotonic()
    encoder = CompleteEncoder(Encoder(encoder_path))
    model_load_seconds = time.monotonic() - model_started
    states = []
    for row in plan["tasks"]:
        tid = row["instance_id"]
        directory = output / "selection" / tid
        if (directory / "selection.json").exists():
            states.append(read(directory / "selection.json"))
            continue
        prefix = output / "prefixes" / tid
        execution = (
            read(prefix / "execution.json")
            if (prefix / "execution.json").exists()
            else {}
        )
        cp = first_checkpoint(execution)
        if cp is None:
            value = {
                "task_id": tid,
                "status": "NO_EXECUTABLE_PREFIX",
                "messages": {m: None for m in plan["arms"]},
                "checkpoint": None,
            }
            dump(directory / "selection.json", value)
            states.append(value)
            continue
        meta = verify_checkpoint(cp)
        if (directory / "semantic" / "error.json").exists():
            failure = read(directory / "semantic" / "error.json")
            value = preprocessing_unavailable(tid, cp, failure["error"])
            dump(directory / "selection.json", value)
            states.append(value)
            continue
        started = time.monotonic()
        ledger = analyze(
            meta["state"]["request"],
            meta["visible_events"],
            checkpoint_event_count=len(meta["visible_events"]),
            initial_source_version=row["base_commit"],
        )
        links = propose_observation_links(ledger, directory / "observation-links")
        ledger = analyze(
            meta["state"]["request"],
            meta["visible_events"],
            checkpoint_event_count=len(meta["visible_events"]),
            initial_source_version=row["base_commit"],
            links=links,
        )
        dump(directory / "ledger.json", ledger)
        index = read(output / "public-knowledge" / row["base_commit"] / "index.json")
        visible = "\n".join(o["output"] for o in ledger["observations"])
        read_symbols = tuple(
            p
            for o in ledger["observations"]
            if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
            for p in o["paths"]
        )
        pool, retrieval = retrieve(
            index,
            ledger,
            encoder=encoder,
            visible_text=visible,
            read_symbols=read_symbols,
        )
        dump(directory / "pool.json", asdict(pool))
        dump(directory / "retrieval.json", retrieval)
        try:
            relations = (
                compact_propose(ledger, pool, directory / "semantic")
                if pool.candidates and pool.obligations
                else []
            )
        except Exception as exc:
            value = preprocessing_unavailable(tid, cp, str(exc))
            value["known_preprocessing_seconds"] = (
                time.monotonic() - started + model_load_seconds
            )
            dump(directory / "selection.json", value)
            states.append(value)
            continue
        packs = {
            m: select(pool, ledger, method=m, relations=relations)
            for m in plan["arms"]
            if m != "N"
        }
        charged = (
            time.monotonic()
            - started
            + model_load_seconds
            + read(output / "public-knowledge" / row["base_commit"] / "cost.json")[
                "seconds"
            ]
        )
        value = {
            "task_id": tid,
            "status": "SELECTION_FROZEN",
            "checkpoint": str(cp),
            "checkpoint_sha256": hashlib.sha256(
                (cp / "checkpoint.json").read_bytes()
            ).hexdigest(),
            "packs": {k: v.to_dict() for k, v in packs.items()},
            "messages": {
                "N": None,
                **{k: render_pack(v) or None for k, v in packs.items()},
            },
            "common_charge_seconds": charged,
            "prefix_remaining_seconds": meta["remaining_seconds"],
            "remaining_after_common_charge": max(
                0, meta["remaining_seconds"] - charged
            ),
            "model_load_seconds": model_load_seconds,
            "source_relation_quality": "NOT_YET_INDEPENDENTLY_CHECKED",
            "no_supported_context": bool(relations)
            and not any(r["weight"] > 0 for r in relations),
        }
        dump(directory / "selection.json", value)
        states.append(value)
    cells = []
    rng = random.Random(plan["order_seed"])
    for row in plan["tasks"]:
        for repeat in range(1, plan["tail_repeats"] + 1):
            arms = list(plan["arms"])
            rng.shuffle(arms)
            cells.extend(
                {"task_id": row["instance_id"], "arm": arm, "repeat": repeat}
                for arm in arms
            )
    lock = {"states": states, "cells": cells, "plan_digest": plan["plan_digest"]}
    dump(output / "selection-lock.json", lock)
    return lock


def run_tails(plan, tasks, skills, output):
    import hashlib
    import os
    from .diagnostic import home_auth
    from .study import run_once
    from .repair_knowledge import token_count
    from .repair_content_study import verify_checkpoint

    verify_frozen(plan, tasks, skills, output)
    lock = read(output / "selection-lock.json")
    if lock["plan_digest"] != plan["plan_digest"]:
        raise ValueError("Selection plan mismatch")
    # Independent review must exist after predictions are locked. Its preference
    # cannot change source packs, weights or the planned denominator.
    review = read(output / "new-state-source-review.json")
    if (
        review["selection_lock_sha256"]
        != hashlib.sha256((output / "selection-lock.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Source review does not bind frozen predictions")
    active = output / "tail-runner-active.json"
    if active.exists():
        raise ValueError(
            "Existing tail runner marker requires stopped-runtime confirmation"
        )
    home, auth = home_auth(output)
    with active.open("x") as handle:
        json.dump({"pid": os.getpid(), "plan_digest": plan["plan_digest"]}, handle)
    states = {s["task_id"]: s for s in lock["states"]}
    tasks_by_id = {r["instance_id"]: r for r in plan["tasks"]}
    try:
        for cell in lock["cells"]:
            tid = cell["task_id"]
            state = states[tid]
            run = output / "tails" / tid / f"{cell['arm']}-r{cell['repeat']}"
            if state["status"] == "UNAVAILABLE_PREPROCESS_FAILURE":
                if not run.exists():
                    dump(
                        run / "execution.json",
                        {
                            "status": "UNKNOWN_PREPROCESS_FAILURE",
                            "research_execution_started": False,
                            "reason": state["failure_reason"],
                            "method_available": False,
                        },
                    )
                continue
            if (
                not state["checkpoint"]
                or state.get("remaining_after_common_charge", 0) <= 0
            ):
                if not run.exists():
                    dump(
                        run / "execution.json",
                        {
                            "status": "UNKNOWN_NO_PREFIX"
                            if not state["checkpoint"]
                            else "UNKNOWN_PREPROCESS_BUDGET_EXHAUSTED",
                            "research_execution_started": False,
                        },
                    )
                continue
            cp = Path(state["checkpoint"])
            verify_checkpoint(cp)
            if (
                hashlib.sha256((cp / "checkpoint.json").read_bytes()).hexdigest()
                != state["checkpoint_sha256"]
            ):
                raise ValueError("Checkpoint changed")
            payload = state["messages"][cell["arm"]]
            result = run_once(
                tasks / tid,
                run,
                home,
                skills,
                from_checkpoint=cp,
                payload=payload,
                payload_tokens=token_count(payload or ""),
                initialization_seconds=state["common_charge_seconds"],
                image=plan["image"],
                public_docs=output
                / "public-knowledge"
                / tasks_by_id[tid]["base_commit"],
            )
            print(
                json.dumps({"phase": "tail", **cell, "status": result["status"]}),
                flush=True,
            )
    finally:
        auth.unlink(missing_ok=True)
        active.unlink(missing_ok=True)


def evaluate_tails(plan, tasks, skills, output, overlays):
    from .repair_checks import accept_candidate

    verify_frozen(plan, tasks, skills, output)
    if (output / "tail-runner-active.json").exists():
        raise ValueError(
            "Research runner active or interrupted; confirm stopped before releasing labels"
        )
    lock = read(output / "selection-lock.json")
    if lock["plan_digest"] != plan["plan_digest"]:
        raise ValueError("Selection plan mismatch")
    from .session import inventory

    for task in plan.get("tasks", []):
        if inventory(overlays / task["instance_id"]) != task["trusted_overlay_files"]:
            raise ValueError("Trusted overlay differs from frozen qualification")
    cells = lock["cells"]
    paths = [
        output / "tails" / c["task_id"] / f"{c['arm']}-r{c['repeat']}" for c in cells
    ]
    if not all(
        (p / "execution.json").exists() or (p / "interrupted.json").exists()
        for p in paths
    ):
        raise ValueError("Do not release hidden checks before all planned attempts")
    for path in paths:
        record = (
            read(path / "execution.json")
            if (path / "execution.json").exists()
            else read(path / "interrupted.json")
        )
        if record.get("status") in {None, "RUNNING", "STARTED"}:
            raise ValueError("Active research cell cannot release hidden checks")
        if (path / "interrupted.json").exists() and record.get(
            "no_running_tool_confirmation"
        ) is not True:
            raise ValueError(
                "Interrupted research cell has no stopped-runtime evidence"
            )
    rows = []
    for cell, path in zip(cells, paths):
        execution = (
            read(path / "execution.json")
            if (path / "execution.json").exists()
            else {"status": "UNKNOWN_INTERRUPTED_ATTEMPT"}
        )
        target = protected = "UNKNOWN"
        integrity = "UNCONFIRMED"
        checks = {}
        if execution["status"] in {"COMPLETED", "TIMEOUT"} and execution.get(
            "thread_id"
        ):
            accepted = accept_candidate(
                tasks / cell["task_id"],
                path,
                path / "acceptance",
                image=plan["image"],
                trusted_overlay=overlays / cell["task_id"],
            )
            checks = accepted["checks"]
            integrity = (
                "CONFIRMED" if accepted["integrity"] == "VERIFIED" else "UNCONFIRMED"
            )

            def label(check):
                return (
                    ("PASS" if check["passed"] else "FAIL")
                    if check.get("valid") is True
                    else "UNKNOWN"
                )

            target = label(checks["target"])
            protected = label(checks["regression"])
            if execution.get("injected") and not execution.get("model_input_observed"):
                integrity = "UNCONFIRMED"
        rows.append(
            {
                **cell,
                "integrity": integrity,
                "target": target,
                "protected": protected,
                "functional": functional_label(
                    integrity=integrity, target=target, protected=protected
                ),
                "checks": checks,
                "execution_status": execution["status"],
            }
        )
        dump(
            output / "functional-results.json",
            {"rows": rows, "planned": len(cells), "plan_digest": plan["plan_digest"]},
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "index",
            "analyze",
            "retrieve",
            "inspect",
            "compose",
            "report",
            "replay",
            "run",
            "evaluate",
        ],
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--skills", type=Path)
    parser.add_argument("--overlays", type=Path)
    parser.add_argument("--phase", choices=["prefix", "compose", "tails"])
    parser.add_argument("--base", type=Path)
    parser.add_argument("--repository", default="ansible/ansible")
    parser.add_argument("--revision")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--pool", type=Path)
    parser.add_argument("--relations", type=Path)
    parser.add_argument("--encoder", type=Path)
    parser.add_argument("--no-expansion", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "run":
        plan = read(args.plan)
        if args.phase == "prefix":
            run_prefixes(plan, args.tasks, args.skills, args.output)
        elif args.phase == "compose":
            compose_new_states(plan, args.tasks, args.skills, args.output, args.encoder)
        elif args.phase == "tails":
            run_tails(plan, args.tasks, args.skills, args.output)
        else:
            raise ValueError("run requires --phase")
    elif args.action == "evaluate":
        evaluate_tails(
            read(args.plan), args.tasks, args.skills, args.output, args.overlays
        )
    elif args.action == "index":
        dump(
            args.output,
            build_index(args.base, repository=args.repository, revision=args.revision),
        )
    elif args.action == "analyze":
        cp = read(args.checkpoint)
        dump(
            args.output,
            analyze(
                cp["state"]["request"],
                cp["visible_events"],
                checkpoint_event_count=len(cp["visible_events"]),
            ),
        )
    elif args.action == "retrieve":
        from .value import Encoder

        ledger = read(args.ledger)
        visible = "\n".join(o["output"] for o in ledger["observations"])
        read_symbols = tuple(
            p
            for o in ledger["observations"]
            if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
            for p in o["paths"]
        )
        pool, diagnostic = retrieve(
            read(args.index),
            ledger,
            encoder=CompleteEncoder(Encoder(args.encoder)),
            visible_text=visible,
            read_symbols=read_symbols,
            expand=not args.no_expansion,
        )
        dump(args.output, asdict(pool))
        dump(args.output.with_suffix(".retrieval.json"), diagnostic)
    elif args.action == "inspect":
        propose_with_session(read(args.ledger), load_pool(args.pool), args.output)
    elif args.action == "compose":
        ledger, pool = read(args.ledger), load_pool(args.pool)
        relations = validate_relations(ledger, pool, read(args.relations))
        dump(
            args.output,
            {
                m: select(pool, ledger, method=m, relations=relations).to_dict()
                for m in ("M-local", "H-sim", "H-link")
            },
        )
    elif args.action in {"report", "replay", "run", "evaluate"}:
        # Records-only. This action cannot invoke an Agent or acceptance runner.
        rows = read(args.ledger)
        results = [
            {
                **r,
                "functional": functional_label(
                    integrity=r["integrity"],
                    target=r["target"],
                    protected=r["protected"],
                ),
            }
            for r in rows
        ]
        dump(
            args.output,
            {
                "rows": results,
                "research_executions": 0,
                "mode": "RECORDS_ONLY",
                "default_policy": "UNCHANGED",
            },
        )


if __name__ == "__main__":
    main()
