"""Frozen functional final matrix. No policy receives hidden outcome feedback."""

import hashlib
import json
from pathlib import Path
import random
import shutil
import time

from .functional_collection import verify_row, bind_checkpoint, digest
from .functional_outcomes import load_objective
from .functional_panel import select_checkpoint, lock_panel, delay_roster
from .functional_policy import METHODS, FunctionalController, FunctionalPredictor
from .learning import model_identity
from .session import dump
from .rollouts import GENERIC
from .study import assets, read, run_once, check_once, verify_freeze


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(protocol_path, objective_path, models):
    objective = load_objective(objective_path)
    protocol = read(protocol_path)
    models = Path(models)
    if objective["sha256"] != protocol["objective_sha256"]:
        raise ValueError("final objective mismatch")
    reload = read(models / "independent-reload.json")
    identities, records = {}, set()
    for name in ("full", "task-only"):
        identities[name] = model_identity(models / name)
        if (
            reload[name].get("model_identity") != identities[name]
            or reload[name].get("match") is not True
        ):
            raise ValueError("current functional model lacks independent reload")
        meta = read(models / name / "model.json")
        if meta.get("no_state") is not (name == "task-only"):
            raise ValueError("model representation role mismatch")
        binding = meta["data_binding"]
        if (
            binding["protocol_sha256"] != sha(protocol_path)
            or binding["objective_sha256"] != objective["sha256"]
            or binding["encoder_files"] != protocol["representation"]["files"]
            or binding["payload_files"] != protocol["payloads"]
            or binding["registry_sha256"] != protocol["registry_sha256"]
        ):
            raise ValueError("final model/source asset mismatch")
        records.add(binding["records_sha256"])
    if len(records) != 1:
        raise ValueError("representation models use different collections")
    roster = []
    for task in protocol["tasks"]:
        if task["split"] != "test":
            continue
        pairs = [(m, r) for m in METHODS for r in (1, 2) if (m, r) != ("N0-v2", 1)]
        random.Random(7170 + sum(task["task_id"].encode())).shuffle(pairs)
        roster.extend(
            {"task_id": task["task_id"], "method": m, "repeat": r}
            for m, r in [("N0-v2", 1), *pairs]
        )
    names = (
        "rollouts.py",
        "session.py",
        "state.py",
        "value.py",
        "functional_policy.py",
        "functional_panel.py",
        "functional_evaluate.py",
    )
    return {
        "protocol_sha256": sha(protocol_path),
        "objective_sha256": objective["sha256"],
        "models": identities,
        "training_sha256": sha(models / "training.json"),
        "independent_reload_sha256": sha(models / "independent-reload.json"),
        "runtime_code": {name: sha(Path(__file__).parent / name) for name in names},
        "roster": roster,
        "planned_matrix": len(roster),
        "panel_repeats": 2,
        "maximum_panel_tails": 64,
        "maximum_delay_tails": 16,
        "same_state_selector": "first E1, else E2, else E0 from N0 first repeat",
        "delay_selector": "first four nonterminal common panels in registered task order",
        "tie_rule": "candidate order",
        "margin": 0.0,
        "default_changed": False,
    }


def matrix(
    protocol_path, objective_path, tasks, output, skills, payloads, encoder_path, models
):
    protocol = read(protocol_path)
    tasks, output, models = map(Path, (tasks, output, models))
    verify_freeze(protocol, tasks, payloads, skills, encoder_path)
    frozen = freeze(protocol_path, objective_path, models)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "policy-freeze.json"
    if lock.exists() and read(lock) != frozen:
        raise ValueError("final policy freeze changed")
    dump(lock, frozen)
    setup_started = time.monotonic()
    encoder, retriever, counts, _ = assets(payloads, encoder_path)
    with (output / "shared-setup.jsonl").open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "seconds": time.monotonic() - setup_started,
                    "scope": "shared frozen encoder/catalog loading; per-state encoding/prediction and head loading charged to trajectory",
                }
            )
            + "\n"
        )
    home = output / "session-home"
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    if auth.exists():
        raise ValueError("final session home already in use")
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    all_rows = []
    try:
        for info in protocol["tasks"]:
            if info["split"] != "test":
                continue
            tid = info["task_id"]
            task, root = tasks / tid, output / tid
            root.mkdir(exist_ok=True)
            if (root / "matrix-records.json").exists():
                all_rows.extend(read(root / "matrix-records.json")["rows"])
                continue
            rows = []
            for sample in [r for r in frozen["roster"] if r["task_id"] == tid]:
                method, repeat = sample["method"], sample["repeat"]
                run = root / (method + f"-r{repeat}")
                init = time.monotonic()
                predictor = (
                    FunctionalPredictor(models, method, encoder, retriever)
                    if method not in ("N0-v2", "S1-v2")
                    else None
                )
                controller = FunctionalController(method)
                seconds = time.monotonic() - init
                dump(root / (run.name + "-intent.json"), sample)
                print(json.dumps({"starting": sample}), flush=True)
                already_reserved = run.exists()
                execution = run_once(
                    task,
                    run,
                    home,
                    skills,
                    total=protocol["total_seconds"],
                    retriever=retriever,
                    controller=controller,
                    predict=predictor,
                    token_counts=counts,
                    initialization_seconds=seconds,
                )
                calls_path = root / (run.name + "-model-calls.json")
                if not already_reserved:
                    dump(
                        calls_path,
                        {
                            "gain_calls": predictor.gain_calls if predictor else 0,
                            "wait_calls": predictor.wait_calls if predictor else 0,
                            "method": method,
                            "gain_artifact": frozen["models"].get(
                                "task-only" if method == "H-task-fixedC-v2" else "full"
                            )
                            if method.startswith("H-")
                            else None,
                        },
                    )
                row = {
                    "model_calls": read(calls_path)
                    if calls_path.exists()
                    else {"status": "UNKNOWN_INTERRUPTED_RECEIPT"},
                    **sample,
                    "family": info["family"],
                    "split": "test",
                    "run": str(run),
                    "execution": execution,
                }
                rows.append(row)
                dump(root / "matrix-started-rows.json", {"rows": rows})
                if method == "N0-v2" and repeat == 1:
                    panel_path = root / "panel-lock.json"
                    # Freeze the observation and predictions before any hidden check.
                    if not panel_path.exists():
                        cp = select_checkpoint(execution)
                        if cp is None:
                            dump(
                                panel_path,
                                {
                                    "status": "NO_OBSERVED_CHECKPOINT",
                                    "execution_status": execution["status"],
                                },
                            )
                        else:
                            measured = time.monotonic()
                            predictors = {
                                m: FunctionalPredictor(models, m, encoder, retriever)
                                for m in ("H-full-v2", "H-task-fixedC-v2", "P1-v2")
                            }
                            panel = lock_panel(cp, retriever.skills, predictors)
                            panel["common_prediction_seconds"] = (
                                time.monotonic() - measured
                            )
                            panel["lock_sha256"] = digest(
                                {k: v for k, v in panel.items() if k != "lock_sha256"}
                            )
                            dump(panel_path, panel)
                print(
                    json.dumps({"finished": sample, "status": execution["status"]}),
                    flush=True,
                )
            for row in rows:
                run = Path(row["run"])
                check_root = root / (run.name + "-checks")
                row["checks_root"] = str(check_root)
                row["checks"] = check_once(task, run, check_root, row["execution"])
                row.update(verify_row(row))
            dump(root / "matrix-records.json", {"rows": rows})
            all_rows.extend(rows)
            dump(
                output / "matrix-records.json",
                {
                    "policy_freeze": frozen,
                    "planned": frozen["planned_matrix"],
                    "rows": all_rows,
                },
            )
    finally:
        auth.unlink(missing_ok=True)
    dump(
        output / "matrix-records.json",
        {
            "policy_freeze": frozen,
            "planned": frozen["planned_matrix"],
            "rows": all_rows,
        },
    )
    panels = []
    for info in protocol["tasks"]:
        path = output / info["task_id"] / "panel-lock.json"
        if info["split"] == "test" and path.exists():
            panel = read(path)
            if "lock_sha256" in panel:
                panels.append((info["task_id"], panel))
    dump(
        output / "delay-roster.json",
        {
            "rows": delay_roster(panels),
            "selection": "registered order of available nonterminal states",
        },
    )
    return {
        "matrix_recorded": len(all_rows),
        "matrix_planned": frozen["planned_matrix"],
        "panel_states": len(panels),
        "paired_panel_tails": 0,
    }


def panels(
    protocol_path,
    objective_path,
    tasks,
    output,
    skills,
    payloads,
    encoder_path,
    models,
    *,
    delayed=False,
):
    """Run prelocked common actions or genuine branch-local delayed policies."""
    protocol = read(protocol_path)
    tasks, output, models = map(Path, (tasks, output, models))
    verify_freeze(protocol, tasks, payloads, skills, encoder_path)
    frozen = freeze(protocol_path, objective_path, models)
    if read(output / "policy-freeze.json") != frozen:
        raise ValueError("final freeze mismatch")
    matrix_rows = read(output / "matrix-records.json")["rows"]
    expected = {(r["task_id"], r["method"], r["repeat"]) for r in frozen["roster"]}
    if {(r["task_id"], r["method"], r["repeat"]) for r in matrix_rows} != expected:
        raise ValueError("matrix incomplete before common action panel phase")
    encoder, retriever, counts, manifest = assets(payloads, encoder_path)
    panel_locks = []
    for info in protocol["tasks"]:
        if info["split"] == "test":
            lock = read(output / info["task_id"] / "panel-lock.json")
            if "lock_sha256" in lock:
                if (
                    digest({k: v for k, v in lock.items() if k != "lock_sha256"})
                    != lock["lock_sha256"]
                ):
                    raise ValueError("prospective panel lock changed")
                if (
                    bind_checkpoint(lock["checkpoint"], retriever.skills)
                    != lock["binding"]
                ):
                    raise ValueError("common panel checkpoint changed")
                panel_locks.append((info["task_id"], lock))
    registered_delays = delay_roster(panel_locks)
    if read(output / "delay-roster.json")["rows"] != registered_delays:
        raise ValueError("delay roster changed")
    kind = "delay" if delayed else "panel"
    if delayed:
        for tid, _ in panel_locks:
            if not (output / tid / "panel-records.json").exists():
                raise ValueError(
                    "common action references incomplete before delay phase"
                )
    home = output / "session-home"
    auth = home / "auth.json"
    if auth.exists():
        raise ValueError("final session home already in use")
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    all_rows = []
    try:
        for tid, lock in panel_locks:
            root, task = output / tid, tasks / tid
            info = next(r for r in protocol["tasks"] if r["task_id"] == tid)
            samples = (
                [r for r in registered_delays if r["task_id"] == tid]
                if delayed
                else lock["action_roster"]
            )
            target = root / (kind + "-records.json")
            if target.exists():
                all_rows.extend(read(target)["rows"])
                continue
            rows = []
            for sample in samples:
                action, repeat = sample["action"], sample["repeat"]
                run = root / kind / f"r{repeat}" / action
                init = time.monotonic()
                predictor = controller = None
                payload = None
                tokens = 0
                if delayed:
                    controller = FunctionalController(
                        action, fixed_skill=sample["fixed_skill"]
                    )
                    if action == "WAIT_THEN_FULL-v2":
                        predictor = FunctionalPredictor(
                            models, "H-full-v2", encoder, retriever
                        )
                elif action != "NO_INTERVENTION":
                    payload = (
                        GENERIC
                        if action == "GENERIC_REMINDER"
                        else retriever.skills[action]
                    )
                    tokens = (
                        manifest["generic_tokens"]
                        if action == "GENERIC_REMINDER"
                        else counts[action]
                    )
                seconds = time.monotonic() - init + lock["common_prediction_seconds"]
                dump(
                    run.parent / (run.name + "-intent.json"),
                    {
                        **sample,
                        "panel_lock_sha256": lock["lock_sha256"],
                        "charged_initialization_seconds": seconds,
                    },
                )
                print(
                    json.dumps({"starting": kind, "task": tid, "sample": sample}),
                    flush=True,
                )
                execution = run_once(
                    task,
                    run,
                    home,
                    skills,
                    from_checkpoint=lock["checkpoint"],
                    retriever=retriever,
                    controller=controller,
                    predict=predictor,
                    payload=payload,
                    payload_tokens=tokens,
                    token_counts=counts,
                    initialization_seconds=seconds,
                )
                row = {
                    "task_id": tid,
                    "family": info["family"],
                    "split": "test",
                    "state_id": tid + ":" + lock["state"]["stage"],
                    "stage": lock["state"]["stage"],
                    "state": lock["state"],
                    "repeat": repeat,
                    "action": action,
                    "intervention_mode": "CONTINGENT_DELAY"
                    if delayed
                    else "IMMEDIATE_ACTION",
                    "checkpoint": lock["checkpoint"],
                    "binding_sha256": lock["binding"]["binding_sha256"],
                    "candidates": [p["id"] for p in lock["binding"]["candidates"]],
                    "candidate_payloads": lock["binding"]["candidates"],
                    "panel_lock_sha256": lock["lock_sha256"],
                    "run": str(run),
                    "execution": execution,
                    "payload_tokens": execution.get("payload_tokens"),
                    "reference_samples": {
                        "NEVER": "NO_INTERVENTION",
                        "NOW": lock["now_skill"],
                        "repeat": repeat,
                    }
                    if delayed
                    else None,
                }
                rows.append(row)
                dump(root / (kind + "-started-rows.json"), {"rows": rows})
            for row in rows:
                run = Path(row["run"])
                checks = run.parent / (run.name + "-checks")
                row["checks_root"] = str(checks)
                row["checks"] = check_once(task, run, checks, row["execution"])
                row.update(verify_row(row))
            dump(
                target,
                {
                    "panel_lock_sha256": lock["lock_sha256"],
                    "planned": len(samples),
                    "rows": rows,
                },
            )
            all_rows.extend(rows)
            dump(
                output / (kind + "-records.json"),
                {
                    "policy_freeze": frozen,
                    "planned": len(registered_delays)
                    if delayed
                    else sum(len(lock["action_roster"]) for _, lock in panel_locks),
                    "rows": all_rows,
                },
            )
    finally:
        auth.unlink(missing_ok=True)
    dump(
        output / (kind + "-records.json"),
        {
            "policy_freeze": frozen,
            "planned": len(registered_delays)
            if delayed
            else sum(len(lock["action_roster"]) for _, lock in panel_locks),
            "rows": all_rows,
        },
    )
    return {
        "kind": kind,
        "recorded": len(all_rows),
        "known_functional": sum(r["y_functional"] is not None for r in all_rows),
    }
