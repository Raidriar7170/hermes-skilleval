"""Pure-functional paired tails with immutable candidate and observable-state identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from .functional_outcomes import load_objective, outcomes
from .records import verify_artifacts
from .rollouts import GENERIC
from .session import dump, inventory
from .study import assets, read, run_once, check_once, verify_freeze


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def bind_checkpoint(path, payloads):
    path = Path(path)
    meta = read(path / "checkpoint.json")
    if not meta.get("no_running_tool_confirmation"):
        raise ValueError("unconfirmed checkpoint boundary")
    for scope in ("source", "scratch"):
        if inventory(path / scope) != meta["files"][scope]:
            raise ValueError("checkpoint content changed: " + scope)
    candidates = meta["candidates"]
    if not candidates or len(candidates) > 2 or len(candidates) != len(set(candidates)):
        raise ValueError("invalid common candidate list")
    binding = {
        "observable_state_sha256": digest(meta),
        "visible_prefix_sha256": meta["visible_prefix_sha256"],
        "source_sha256": digest(meta["files"]["source"]),
        "scratch_sha256": digest(meta["files"]["scratch"]),
        "initial_remaining": meta["remaining_seconds"],
        "candidates": [
            {
                "id": k,
                "payload": payloads[k],
                "payload_sha256": hashlib.sha256(payloads[k].encode()).hexdigest(),
            }
            for k in candidates
        ],
    }
    return {**binding, "binding_sha256": digest(binding)}


def verify_row(row):
    """Recompute outcome only after capture, reconstruction and verifier evidence checks."""
    integrity = "VERIFIED"
    try:
        if row.get("checkpoint"):
            cp = Path(row["checkpoint"])
            meta = read(cp / "checkpoint.json")
            binding = bind_checkpoint(
                cp, {p["id"]: p["payload"] for p in row["candidate_payloads"]}
            )
            if (
                binding["binding_sha256"] != row["binding_sha256"]
                or row["state"] != meta["state"]
                or row["candidates"] != meta["candidates"]
                or row["candidate_payloads"] != binding["candidates"]
            ):
                raise ValueError("row differs from frozen observable checkpoint")
            execution = row["execution"]
            if execution.get("thread_id"):
                if execution["initial_remaining"] != binding["initial_remaining"]:
                    raise ValueError("row tail budget differs from frozen checkpoint")
                if bool(execution["injected"]) != (row["action"] != "NO_INTERVENTION"):
                    raise ValueError("row action differs from executed intervention")
                if meta["thread_id"]:
                    fork = read(Path(row["run"]) / "fork.json")
                    if (
                        fork["parent_thread"] != meta["thread_id"]
                        or fork["boundary_id"] != meta["last_turn_id"]
                        or fork["expected_prefix_sha256"]
                        != meta["visible_prefix_sha256"]
                    ):
                        raise ValueError("fork differs from frozen checkpoint")
        verification = verify_artifacts({**row, "quality": None})
        if verification["status"] == "VERIFIED":
            run = Path(row["run"])
            checks_root = Path(
                row.get("checks_root", run.parent / (run.name + "-checks"))
            )
            if not read(checks_root / "acceptance.json").get("capture"):
                raise ValueError("missing complete candidate capture")
        if verification["status"] != "VERIFIED":
            integrity = verification["status"]
    except (ValueError, OSError) as exc:
        integrity = "INTEGRITY_UNKNOWN"
        verification = {"error": str(exc)}
    return {
        **row,
        **outcomes(row["execution"], row["checks"], integrity=integrity),
        "verification": verification,
    }


def collect(
    protocol_path,
    objective_path,
    tasks,
    output,
    skills,
    payloads,
    encoder_path,
    session_home,
    pilot_root,
    native_only=False,
):
    objective = load_objective(objective_path)
    protocol = read(protocol_path)
    if protocol["objective_sha256"] != objective["sha256"]:
        raise ValueError("collection objective identity mismatch")
    tasks, output, home, pilot_root = map(
        Path, (tasks, output, session_home, pilot_root)
    )
    verify_freeze(protocol, tasks, payloads, skills, encoder_path)
    output.mkdir(parents=True, exist_ok=True)
    identity = {
        "protocol_sha256": hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        "objective_sha256": objective["sha256"],
    }
    if (output / "identity.json").exists() and read(
        output / "identity.json"
    ) != identity:
        raise ValueError("collection resume identity changed")
    dump(output / "identity.json", identity)
    _, retriever, counts, manifest = assets(payloads, encoder_path)
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    if auth.exists():
        raise ValueError("session home in use; do not overlap collectors")
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    all_rows = []
    try:
        # Complete the registered native chains before branching. This continues
        # the ceiling probe across all categories without outcome selection.
        native_rows = []
        for info in protocol["tasks"]:
            if info["split"] == "test":
                continue
            tid = info["task_id"]
            root = output / tid
            root.mkdir(exist_ok=True)
            reuse = info.get("pilot_reuse")
            run = pilot_root / tid / "r1" if reuse else root / "native-chain"
            if reuse:
                if (
                    hashlib.sha256((run / "execution.json").read_bytes()).hexdigest()
                    != reuse["execution_sha256"]
                ):
                    raise ValueError("reused pilot execution changed")
                execution = read(run / "execution.json")
            else:
                print(json.dumps({"native_start": tid}), flush=True)
                execution = run_once(
                    tasks / tid,
                    run,
                    home,
                    skills,
                    total=protocol["total_seconds"],
                    retriever=retriever,
                )
            checks_root = run.parent / (run.name + "-checks")
            row = verify_row(
                {
                    "task_id": tid,
                    "family": info["family"],
                    "split": info["split"],
                    "action": "NO_INTERVENTION",
                    "run": str(run),
                    "checks_root": str(checks_root),
                    "execution": execution,
                    "checks": check_once(tasks / tid, run, checks_root, execution),
                }
            )
            native_rows.append(row)
            dump(
                output / "native-records.json",
                {
                    "identity": identity,
                    "planned": sum(x["split"] != "test" for x in protocol["tasks"]),
                    "rows": native_rows,
                },
            )
            print(
                json.dumps(
                    {
                        "native_complete": tid,
                        "y_functional": row["y_functional"],
                        "status": execution["status"],
                    }
                ),
                flush=True,
            )
        if native_only:
            return {"native_recorded": len(native_rows), "paired_tails": 0}
        for info in protocol["tasks"]:
            if info["split"] == "test":
                continue
            tid = info["task_id"]
            task = tasks / tid
            root = output / tid
            root.mkdir(exist_ok=True)
            if (root / "records.json").exists():
                all_rows.extend(read(root / "records.json")["rows"])
                continue
            reuse = info.get("pilot_reuse")
            if reuse:
                native_run = pilot_root / tid / "r1"
                native = read(native_run / "execution.json")
                if (
                    hashlib.sha256(
                        (native_run / "execution.json").read_bytes()
                    ).hexdigest()
                    != reuse["execution_sha256"]
                ):
                    raise ValueError("reused pilot execution changed")
            else:
                native_run = root / "native-chain"
                native = run_once(
                    task,
                    native_run,
                    home,
                    skills,
                    total=protocol["total_seconds"],
                    retriever=retriever,
                )
            dump(
                root / "native-binding.json",
                {"run": str(native_run), "reused": bool(reuse), "execution": native},
            )
            rows = []
            for checkpoint in native.get("checkpoints", []):
                cp = Path(checkpoint)
                meta = read(cp / "checkpoint.json")
                stage = meta["state"]["stage"]
                binding = bind_checkpoint(cp, retriever.skills)
                binding_path = root / (stage + "-common-state.json")
                if binding_path.exists() and read(binding_path) != binding:
                    raise ValueError("shared state binding changed")
                dump(binding_path, binding)
                repeats = 2 if tid + ":" + stage in protocol["repeat_states"] else 1
                actions = ["NO_INTERVENTION", *meta["candidates"], "GENERIC_REMINDER"]
                for repeat in range(1, repeats + 1):
                    offset = (
                        7170 + repeat - 1 + sum(tid.encode()) + ord(stage[-1])
                    ) % len(actions)
                    for action in actions[offset:] + actions[:offset]:
                        run = root / stage / f"r{repeat}" / action
                        payload = (
                            None
                            if action == "NO_INTERVENTION"
                            else GENERIC
                            if action == "GENERIC_REMINDER"
                            else retriever.skills[action]
                        )
                        tokens = (
                            0
                            if action == "NO_INTERVENTION"
                            else manifest["generic_tokens"]
                            if action == "GENERIC_REMINDER"
                            else counts[action]
                        )
                        sample = {
                            "task_id": tid,
                            "state_id": tid + ":" + stage,
                            "split": info["split"],
                            "family": info["family"],
                            "stage": stage,
                            "repeat": repeat,
                            "action": action,
                            "binding_sha256": binding["binding_sha256"],
                        }
                        print(json.dumps({"starting": sample}), flush=True)
                        dump(
                            run.parent / (run.name + "-intent.json"),
                            {
                                **sample,
                                "checkpoint": str(cp),
                                "initial_remaining": binding["initial_remaining"],
                                "payload_sha256": hashlib.sha256(
                                    (payload or "").encode()
                                ).hexdigest(),
                            },
                        )
                        execution = run_once(
                            task,
                            run,
                            home,
                            skills,
                            from_checkpoint=cp,
                            retriever=retriever,
                            payload=payload,
                            payload_tokens=tokens,
                        )
                        if (
                            execution.get("initial_remaining") is not None
                            and execution["initial_remaining"]
                            != binding["initial_remaining"]
                        ):
                            raise ValueError("unequal starting tail budget")
                        row = {
                            **sample,
                            "state": meta["state"],
                            "candidates": meta["candidates"],
                            "candidate_payloads": binding["candidates"],
                            "checkpoint": str(cp),
                            "run": str(run),
                            "execution": execution,
                            "payload_tokens": tokens,
                            "native_terminal_status": native["status"],
                        }
                        rows.append(row)
                        # Durable roster before hidden labels; no outcome-based replacement.
                        dump(root / "started-rows.json", {"rows": rows})
                        print(
                            json.dumps(
                                {
                                    "finished": sample,
                                    "execution_status": execution["status"],
                                }
                            ),
                            flush=True,
                        )
            # Task-level release only after all predetermined tails finish.
            for row in rows:
                run = Path(row["run"])
                checks_root = run.parent / (run.name + "-checks")
                row["checks_root"] = str(checks_root)
                row["checks"] = check_once(task, run, checks_root, row["execution"])
                row.update(verify_row(row))
            # No checkpoint is explicit missing evidence, never a fictitious zero label.
            dump(
                root / "records.json",
                {
                    "native_chain": native,
                    "missing_checkpoint_reason": None if rows else native["status"],
                    "unobserved_registered_states": [
                        {
                            "state_id": tid + ":" + stage,
                            "reason": "NATURAL_OPPORTUNITY_ABSENT"
                            if native["status"] == "COMPLETED"
                            else "UNCONFIRMED_NATIVE_CONTINUATION",
                        }
                        for stage in ("E0", "E1", "E2")
                        if stage not in {r["stage"] for r in rows}
                    ],
                    "rows": rows,
                },
            )
            all_rows.extend(rows)
            dump(
                output / "records.json",
                {
                    "identity": identity,
                    "rows": all_rows,
                    "completed_tasks": [
                        r["task_id"]
                        for r in protocol["tasks"]
                        if (output / r["task_id"] / "records.json").exists()
                    ],
                },
            )
            print(
                json.dumps(
                    {
                        "task_complete": tid,
                        "tails": len(rows),
                        "known": sum(r["y_functional"] is not None for r in rows),
                    }
                ),
                flush=True,
            )
    finally:
        auth.unlink(missing_ok=True)
    return {
        "recorded_tails": len(all_rows),
        "known_functional": sum(r["y_functional"] is not None for r in all_rows),
    }
