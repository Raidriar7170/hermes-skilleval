"""Fixed-time, one-injection repair-content study. No gain/wait training."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time

from .diagnostic import home_auth, visible_opportunity
from .functional_outcomes import outcomes
from .repair_checks import accept_candidate
from .repair_composer import (
    CompleteEncoder,
    extract_obligations,
    retrieve_common,
    select_gap_cover,
    select_mmr,
    render_pack,
    words,
)
from .repair_knowledge import RepairKnowledgeUnit, token_count
from .rollouts import GENERIC
from .session import Session, dump, inventory
from .state import State
from .study import read, run_once, assets


def identity(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_plan(
    plan, tasks, knowledge, *, skills=None, payloads=None, encoder_path=None
):
    if plan["model"] != "gpt-5.6-sol" or plan["effort"] != "medium":
        raise ValueError("unsupported executor identity")
    if plan["status"] != "FROZEN":
        raise ValueError("unfrozen study")
    repository = Path(__file__).resolve().parents[3]
    for filename, expected in plan["algorithm_files"].items():
        if identity(repository / filename) != expected:
            raise ValueError("frozen algorithm changed: " + filename)
    for field, directory in (
        (
            "skills",
            skills or repository / "configs/conditional-applicability-v1/skills",
        ),
        (
            "payloads",
            payloads or repository / "configs/adaptive-skill-intervention-v1/payloads",
        ),
    ):
        if inventory(Path(directory)) != plan[field]:
            raise ValueError("frozen " + field + " changed")
    actual_image = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if actual_image != plan["image_id"]:
        raise ValueError("executor image changed")
    if encoder_path is not None:
        for filename, expected in plan["representation"]["files"].items():
            if identity(Path(encoder_path) / filename) != expected:
                raise ValueError("encoder changed")
    for r in plan["tasks"]:
        task = tasks / r["instance_id"]
        for name in ["base", "evaluation"]:
            if (
                hashlib.sha256(
                    json.dumps(inventory(task / name), sort_keys=True).encode()
                ).hexdigest()
                != r["files"][name]
            ):
                raise ValueError("changed " + name)
        if identity(task / "request.txt") != r["request_sha256"]:
            raise ValueError("changed public request")
        if identity(task / "task.json") != r["task_sha256"]:
            raise ValueError("changed profile")
        if (
            identity(knowledge / r["base_commit"] / "units.json")
            != r["knowledge_sha256"]
        ):
            raise ValueError("changed units")
        if inventory(knowledge / r["base_commit"]) != r["public_knowledge_files"]:
            raise ValueError("changed public knowledge directory")


def verify_checkpoint(cp):
    meta = read(cp / "checkpoint.json")
    for scope in ("source", "scratch"):
        if inventory(cp / scope) != meta["files"][scope]:
            raise ValueError("checkpoint " + scope + " changed")
    return meta


def first_checkpoint(execution):
    # Repeat one only. Earliest E1 preferred, else earliest E2; never inspect labels.
    for stage in ("E1", "E2"):
        for raw in execution.get("checkpoints", []):
            path = Path(raw)
            meta = read(path / "checkpoint.json")
            if (
                meta["state"]["stage"] == stage
                and meta.get("thread_id")
                and meta.get("last_turn_id")
            ):
                return path
    return None


def checkpoint_selector(state, seen, events, done):
    terms = tuple(sorted({w for w in words(state.request) if len(w) > 5}))
    return visible_opportunity(state, seen, events, done, terms)


def preflight(plan, tasks, skills, output):
    output.mkdir(parents=True, exist_ok=False)
    home, auth = home_auth(output)
    try:
        task = tasks / plan["tasks"][0]["instance_id"]
        with Session(
            task / "base",
            output / "scratch",
            home,
            skills,
            output / "server",
            image=plan["image"],
        ) as session:
            models = session.rpc("model/list", {"includeHidden": True}).get("data", [])
            advertised = any(
                (r.get("model") or r.get("id")) == plan["model"] for r in models
            )
        result = {
            "model": plan["model"],
            "advertised": advertised,
            "research_executions": 0,
        }
        dump(output / "preflight.json", result)
        if not advertised:
            raise ValueError("required model unavailable")
        return result
    finally:
        auth.unlink(missing_ok=True)


def require_confirmation(plan, output):
    from .repair_content_report import summarize

    review = output / "contract-review.json"
    if review.exists():
        finding = read(review)
        if finding["plan_digest"] != plan["plan_digest"]:
            raise ValueError("contract review plan mismatch")
        if finding["status"] == "PUBLIC_CONTRACT_CLASSIFICATION_AMBIGUITY":
            raise ValueError(
                "confirmation unavailable: unresolved public acceptance contract"
            )
    lock = read(output / "pilot-lock.json")
    results = read(output / "pilot-results.json")
    if (
        lock["plan_digest"] != plan["plan_digest"]
        or results["plan_digest"] != plan["plan_digest"]
    ):
        raise ValueError("confirmation plan mismatch")
    rows = results["rows"]
    decision = summarize(rows, lock)
    dump(output / "continuation-decision.json", decision)
    if decision["confirmation_decision"] != "TRIGGERED":
        raise ValueError("confirmation continuation rule not met")


def native(plan, tasks, knowledge, skills, output, *, confirmation=False):
    verify_plan(plan, tasks, knowledge, skills=skills)
    if confirmation:
        require_confirmation(plan, output)
    phase = "confirmation-prefixes" if confirmation else "native"
    root = output / phase
    root.mkdir(parents=True, exist_ok=True)
    home, auth = home_auth(output)
    selected = [
        r
        for r in plan["tasks"]
        if r["split"] == ("confirmation" if confirmation else "dev")
    ]
    try:
        for row in selected:
            tid = row["instance_id"]
            task = tasks / tid
            for repeat in (1,) if confirmation else (1, 2):
                run = root / tid / f"r{repeat}"
                prior = run.exists()
                print(
                    json.dumps({"start": phase, "task": tid, "repeat": repeat}),
                    flush=True,
                )
                result = run_once(
                    task,
                    run,
                    home,
                    skills,
                    total=plan["total_seconds"],
                    image=plan["image"],
                    public_docs=knowledge / row["base_commit"],
                    checkpoint_selector=checkpoint_selector,
                    stop_at_checkpoint=confirmation,
                )
                print(
                    json.dumps(
                        {
                            "end": phase,
                            "task": tid,
                            "repeat": repeat,
                            "status": result["status"],
                        }
                    ),
                    flush=True,
                )
                if not prior and result["status"] not in (
                    "COMPLETED",
                    "TIMEOUT",
                    "PREFIX_SAVED",
                ):
                    return {"status": "PARTIAL", "reason": result["status"]}
    finally:
        auth.unlink(missing_ok=True)
    return {"status": "COMPLETE", "phase": phase}


def compose(
    plan,
    tasks,
    knowledge,
    skills,
    payloads,
    encoder_path,
    output,
    *,
    confirmation=False,
):
    verify_plan(
        plan,
        tasks,
        knowledge,
        skills=skills,
        payloads=payloads,
        encoder_path=encoder_path,
    )
    if confirmation:
        require_confirmation(plan, output)
    phase = "confirm" if confirmation else "pilot"
    lock = output / (phase + "-lock.json")
    if lock.exists():
        return read(lock)
    encoder, legacy, _, _ = assets(payloads, encoder_path)
    complete = CompleteEncoder(encoder)
    states = []
    for row in plan["tasks"]:
        if row["split"] != ("confirmation" if confirmation else "dev"):
            continue
        native_root = (
            output
            / ("confirmation-prefixes" if confirmation else "native")
            / row["instance_id"]
            / "r1"
        )
        execution = (
            read(native_root / "execution.json")
            if (native_root / "execution.json").exists()
            else {}
        )
        cp = first_checkpoint(execution)
        if cp is None:
            continue
        meta = verify_checkpoint(cp)
        state = State(**meta["state"])
        started = time.monotonic()
        obligations = extract_obligations(state)
        units = [
            RepairKnowledgeUnit.from_dict(v)
            for v in read(knowledge / row["base_commit"] / "units.json")
        ]
        visible = "\n".join(
            e.get("params", {}).get("item", {}).get("aggregatedOutput") or ""
            for e in meta["visible_events"]
        )
        pool = retrieve_common(
            state,
            obligations,
            units,
            encoder=complete,
            repository=row["repo"],
            revision=row["base_commit"],
            visible_text=visible,
        )
        shared = time.monotonic() - started
        packs = {}
        costs = {}
        for method, selector, options in [
            ("M", select_mmr, {}),
            ("H", select_gap_cover, {}),
            ("H-no-gap", select_gap_cover, {"no_gap": True}),
            ("H-no-exposure", select_gap_cover, {"no_exposure": True}),
        ]:
            started = time.monotonic()
            pack = selector(pool, token_budget=1200, **options)
            costs[method] = time.monotonic() - started
            packs[method] = {"payload": render_pack(pack), "pack": pack.to_dict()}
        skill = legacy.dynamic_top(state)
        messages = {
            "N": None,
            "G": GENERIC,
            "L": legacy.skills[skill],
            **{k: v["payload"] for k, v in packs.items()},
        }
        # Identical start budget after shared preprocessing; actual per-method
        # overhead is separately retained and never enters functional labels.
        charge = shared + max(costs.values(), default=0)
        entry = {
            "task_id": row["instance_id"],
            "mechanism": row["mechanism"],
            "checkpoint": str(cp),
            "checkpoint_sha256": identity(cp / "checkpoint.json"),
            "state": meta["state"],
            "obligations": [asdict(o) for o in obligations],
            "pool": asdict(pool),
            "packs": packs,
            "messages": messages,
            "legacy_skill": skill,
            "shared_seconds": shared,
            "selection_seconds": costs,
            "common_charge_seconds": charge,
        }
        states.append(entry)
    cells = []
    for index, state in enumerate(states):
        arms = ["N", "M", "H"] if confirmation else ["N", "G", "L", "M", "H"]
        if not confirmation and index < 2:
            arms += ["H-no-gap", "H-no-exposure"]
        block = [
            {"task_id": state["task_id"], "arm": arm, "repeat": r}
            for arm in arms
            for r in (1, 2)
        ]
        random.Random(plan["order_seed"] + index).shuffle(block)
        cells += block
    result = {
        "phase": phase,
        "states": states,
        "cells": cells,
        "plan_digest": plan["plan_digest"],
        "encoding": "complete chunked frozen MiniLM; no truncated source unit",
        "status": "LOCKED_BEFORE_TAILS",
    }
    dump(lock, result)
    return result


def tails(plan, tasks, knowledge, skills, output, *, confirmation=False):
    verify_plan(plan, tasks, knowledge, skills=skills)
    if confirmation:
        require_confirmation(plan, output)
    phase = "confirm" if confirmation else "pilot"
    lock = read(output / (phase + "-lock.json"))
    if lock["plan_digest"] != plan["plan_digest"]:
        raise ValueError("plan changed")
    states = {r["task_id"]: r for r in lock["states"]}
    for state in states.values():
        verify_checkpoint(Path(state["checkpoint"]))
    lookup = {r["instance_id"]: r for r in plan["tasks"]}
    home, auth = home_auth(output)
    try:
        for cell in lock["cells"]:
            tid = cell["task_id"]
            state = states[tid]
            arm = cell["arm"]
            cp = Path(state["checkpoint"])
            if identity(cp / "checkpoint.json") != state["checkpoint_sha256"]:
                raise ValueError("checkpoint changed")
            payload = state["messages"][arm]
            run = output / phase / tid / f"{arm}-r{cell['repeat']}"
            prior = run.exists()
            print(json.dumps({"start": phase, **cell}), flush=True)
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
                public_docs=knowledge / lookup[tid]["base_commit"],
            )
            print(
                json.dumps({"end": phase, **cell, "status": result["status"]}),
                flush=True,
            )
            if not prior and result["status"] not in ("COMPLETED", "TIMEOUT"):
                return {"status": "PARTIAL", "reason": result["status"]}
    finally:
        auth.unlink(missing_ok=True)
    return {"status": "COMPLETE", "cells": len(lock["cells"])}


def evaluate(plan, tasks, knowledge, skills, output, phase):
    verify_plan(plan, tasks, knowledge, skills=skills)
    # Labels released only once all the phase's planned runs have been attempted.
    if phase == "native":
        cells = [
            {"task_id": r["instance_id"], "arm": "N", "repeat": i}
            for r in plan["tasks"]
            if r["split"] == "dev"
            for i in (1, 2)
        ]
    else:
        cells = read(output / (phase + "-lock.json"))["cells"]
    rows = []
    for cell in cells:
        path = (
            output
            / phase
            / cell["task_id"]
            / (
                f"r{cell['repeat']}"
                if phase == "native"
                else f"{cell['arm']}-r{cell['repeat']}"
            )
        )
        if not path.exists():
            raise ValueError(
                "phase has unattempted cells; do not release hidden labels"
            )
    for cell in cells:
        path = (
            output
            / phase
            / cell["task_id"]
            / (
                f"r{cell['repeat']}"
                if phase == "native"
                else f"{cell['arm']}-r{cell['repeat']}"
            )
        )
        execution = (
            read(path / "execution.json")
            if (path / "execution.json").exists()
            else {"status": "UNKNOWN_INTERRUPTED_ATTEMPT"}
        )
        checks = {}
        integrity = "UNAVAILABLE"
        if execution["status"] in ("COMPLETED", "TIMEOUT"):
            accepted = accept_candidate(
                tasks / cell["task_id"], path, path / "acceptance", image=plan["image"]
            )
            checks = accepted["checks"]
            integrity = accepted["integrity"]
        row = {
            **cell,
            "phase": phase,
            "execution": execution,
            "checks": checks,
            **outcomes(execution, checks, integrity=integrity),
        }
        rows.append(row)
        dump(
            output / (phase + "-results.json"),
            {"rows": rows, "planned": len(cells), "plan_digest": plan["plan_digest"]},
        )
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=[
            "preflight",
            "native",
            "compose",
            "pilot",
            "evaluate",
            "confirm-prefix",
            "confirm-compose",
            "confirm",
        ],
    )
    for key in ["plan", "tasks", "knowledge", "skills", "output"]:
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--payloads", type=Path)
    p.add_argument("--encoder", type=Path)
    p.add_argument("--phase", choices=["native", "pilot", "confirm"], default="pilot")
    a = p.parse_args()
    plan = read(a.plan)
    plan["plan_digest"] = identity(a.plan)
    if a.command == "preflight":
        result = preflight(plan, a.tasks, a.skills, a.output)
    elif a.command in ("native", "confirm-prefix"):
        result = native(
            plan,
            a.tasks,
            a.knowledge,
            a.skills,
            a.output,
            confirmation=a.command == "confirm-prefix",
        )
    elif a.command in ("compose", "confirm-compose"):
        result = compose(
            plan,
            a.tasks,
            a.knowledge,
            a.skills,
            a.payloads,
            a.encoder,
            a.output,
            confirmation=a.command == "confirm-compose",
        )
    elif a.command in ("pilot", "confirm"):
        result = tails(
            plan,
            a.tasks,
            a.knowledge,
            a.skills,
            a.output,
            confirmation=a.command == "confirm",
        )
    else:
        result = evaluate(plan, a.tasks, a.knowledge, a.skills, a.output, a.phase)
    print(
        json.dumps(
            {
                "command": a.command,
                "result": result
                if isinstance(result, dict) and "states" not in result
                else "saved",
            }
        )
    )


if __name__ == "__main__":
    main()
