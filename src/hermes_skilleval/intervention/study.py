"""Bounded real study coordinator. Research records are immutable once attempted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .session import dump, inventory
from .rollouts import execute, accept, GENERIC, utility
from .state import State
from .value import Encoder, Retriever


def read(path):
    return json.loads(Path(path).read_text())


def assets(payload_dir, encoder_path):
    manifest = read(Path(payload_dir) / "manifest.json")
    payloads = {
        r["skill_id"]: (Path(payload_dir) / r["path"]).read_text()
        for r in manifest["skills"]
    }
    for row in manifest["skills"]:
        if (
            hashlib.sha256(payloads[row["skill_id"]].encode()).hexdigest()
            != row["payload_sha256"]
        ):
            raise ValueError("frozen payload changed")
    encoder = Encoder(encoder_path)
    registry = read(Path(payload_dir) / manifest["registry_relative_path"])
    full_bodies = {r["id"]: r["body"] for r in registry["skills"]}
    for row in manifest["skills"]:
        if (
            hashlib.sha256(full_bodies[row["skill_id"]].encode()).hexdigest()
            != row["source_body_sha256"]
        ):
            raise ValueError("original skill body changed")
    if registry["registry_id"] != manifest["registry_id"]:
        raise ValueError("registry changed")
    return (
        encoder,
        Retriever(encoder, payloads, full_bodies),
        {r["skill_id"]: r["tokens"] for r in manifest["skills"]},
        manifest,
    )


def verify_freeze(protocol, tasks, payload_dir, skill_dir, encoder_path):
    if protocol["status"] != "FROZEN":
        raise ValueError("study protocol is not frozen")
    for field, root in (("payloads", payload_dir), ("skills", skill_dir)):
        if inventory(Path(root)) != protocol[field]:
            raise ValueError("frozen " + field + " changed")
    for name, digest in protocol["representation"]["files"].items():
        if (
            hashlib.sha256((Path(encoder_path) / name).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("frozen encoder changed")
    manifest = read(Path(payload_dir) / "manifest.json")
    registry = Path(payload_dir) / manifest["registry_relative_path"]
    if hashlib.sha256(registry.read_bytes()).hexdigest() != protocol["registry_sha256"]:
        raise ValueError("frozen registry changed")
    image_id = subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            protocol["agent"]["image"],
            "--format",
            "{{.Id}}",
        ],
        text=True,
    ).strip()
    if image_id != protocol["agent"]["image_id"]:
        raise ValueError("frozen executor image changed")
    for row in protocol["tasks"]:
        root = Path(tasks) / row["task_id"]
        for scope in ["base", "trusted", "reference"]:
            if inventory(root / scope) != row["files"][scope]:
                raise ValueError("frozen " + scope + " changed: " + row["task_id"])
        if (
            hashlib.sha256((root / "task.json").read_bytes()).hexdigest()
            != row["profile_sha256"]
        ):
            raise ValueError("frozen task profile changed")
        if (
            hashlib.sha256((root / "request.txt").read_bytes()).hexdigest()
            != row["request_sha256"]
        ):
            raise ValueError("frozen request changed")


def qualify_quality(execution, checks):
    if execution["status"] not in ("COMPLETED", "TIMEOUT") or not execution.get(
        "thread_id"
    ):
        return None
    if execution.get("injected") and not execution.get("model_input_observed"):
        return None
    if not {"target", "regression", "policy"} <= checks.keys():
        return None
    if not all(
        r.get("valid") is True and isinstance(r.get("passed"), bool)
        for r in checks.values()
    ):
        return None
    return all(r.get("passed") for r in checks.values())


def run_once(task, run, home, skill_dir, **kwargs):
    if (run / "execution.json").exists():
        return read(run / "execution.json")
    if run.exists():
        # A process died after reserving this sample. Never silently draw a replacement.
        return {
            "status": "UNKNOWN_INTERRUPTED_ATTEMPT",
            "thread_id": None,
            "tail_seconds": None,
        }
    return execute(task, run, home, skill_dir, **kwargs)


def check_once(task, run, out, execution):
    if execution["status"] not in ("COMPLETED", "TIMEOUT"):
        return {
            "execution": {
                "valid": False,
                "passed": False,
                "reason": execution["status"],
            }
        }
    if (out / "acceptance.json").exists():
        return read(out / "acceptance.json")["checks"]
    if out.exists():
        return {
            "acceptance": {
                "valid": False,
                "passed": False,
                "reason": "INTERRUPTED_VERIFIER",
            }
        }
    try:
        return accept(task, run, out)
    except Exception as exc:
        out.mkdir(parents=True, exist_ok=True)
        result = {"acceptance": {"valid": False, "passed": False, "reason": str(exc)}}
        dump(out / "acceptance.json", {"checks": result})
        return result


def collect(protocol_path, tasks, output, skill_dir, payload_dir, encoder_path):
    protocol = read(protocol_path)
    tasks = Path(tasks)
    output = Path(output)
    verify_freeze(protocol, tasks, payload_dir, skill_dir, encoder_path)
    output.mkdir(parents=True, exist_ok=True)
    encoder, retriever, counts, manifest = assets(payload_dir, encoder_path)
    home = output / "session-home"
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    try:
        for task_info in protocol["tasks"]:
            if task_info["split"] == "test":
                continue
            tid = task_info["task_id"]
            task = tasks / tid
            root = output / tid
            if (root / "records.json").exists():
                continue
            root.mkdir(exist_ok=True)
            native = run_once(
                task,
                root / "native-chain",
                home,
                skill_dir,
                total=protocol["total_seconds"],
                retriever=retriever,
            )
            cp_paths = native.get("checkpoints", [])
            runs = []
            for cp_path in cp_paths:
                cp = Path(cp_path)
                meta = read(cp / "checkpoint.json")
                stage = meta["state"]["stage"]
                repeats = 2 if tid + ":" + stage in protocol["repeat_states"] else 1
                actions = ["NO_INTERVENTION", *meta["candidates"], "GENERIC_REMINDER"]
                for repeat in range(repeats):
                    # Rotated fixed ordering, fixed before outcomes, preserves all arms.
                    offset = (
                        protocol["order_seed"]
                        + repeat
                        + sum(tid.encode())
                        + ord(stage[-1])
                    ) % len(actions)
                    ordered = actions[offset:] + actions[:offset]
                    for action in ordered:
                        run = root / stage / f"r{repeat + 1}" / action
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
                        result = run_once(
                            task,
                            run,
                            home,
                            skill_dir,
                            from_checkpoint=cp,
                            retriever=retriever,
                            payload=payload,
                            payload_tokens=tokens,
                        )
                        runs.append(
                            {
                                "task_id": tid,
                                "split": task_info["split"],
                                "stage": stage,
                                "state_id": tid + ":" + stage,
                                "state": meta["state"],
                                "candidates": meta["candidates"],
                                "repeat": repeat + 1,
                                "action": action,
                                "run": str(run),
                                "execution": result,
                                "payload_tokens": tokens,
                            }
                        )
                        print(
                            json.dumps(
                                {
                                    "task": tid,
                                    "stage": stage,
                                    "repeat": repeat + 1,
                                    "action": action,
                                    "status": result["status"],
                                }
                            ),
                            flush=True,
                        )
            # Hidden target checks only after ALL tails for the task have ended.
            for row in runs:
                run = Path(row["run"])
                checks = check_once(
                    task, run, run.parent / (run.name + "-checks"), row["execution"]
                )
                quality = qualify_quality(row["execution"], checks)
                elapsed = row["execution"].get("tail_seconds")
                cost = (
                    None
                    if elapsed is None
                    else elapsed + row["execution"].get("prefix_seconds", 0)
                )
                row.update(
                    checks=checks,
                    quality=quality,
                    utility=utility(
                        quality, protocol["total_seconds"], cost, row["payload_tokens"]
                    )
                    if cost is not None
                    else None,
                )
            dump(root / "records.json", {"native_chain": native, "rows": runs})
            print(
                json.dumps(
                    {
                        "task_complete": tid,
                        "states": len(cp_paths),
                        "tails": len(runs),
                        "valid_labels": sum(r["quality"] is not None for r in runs),
                    }
                ),
                flush=True,
            )
    finally:
        auth.unlink(missing_ok=True)
    rows = []
    for t in protocol["tasks"]:
        p = output / t["task_id"] / "records.json"
        if p.exists():
            rows.extend(read(p)["rows"])
    dump(
        output / "records.json",
        {
            "protocol_sha256": hashlib.sha256(
                Path(protocol_path).read_bytes()
            ).hexdigest(),
            "rows": rows,
        },
    )
    return {"rows": len(rows), "valid": sum(r["quality"] is not None for r in rows)}


def paired_rows(
    records, encoder, retriever, *, split, no_state=False, native_status=None
):
    rows = []
    chains = {}
    missing = []
    source = [r for r in records if r["split"] == split]
    for row in source:
        if row["action"] == "NO_INTERVENTION":
            continue
        base = next(
            (
                r
                for r in source
                if r["state_id"] == row["state_id"]
                and r["repeat"] == row["repeat"]
                and r["action"] == "NO_INTERVENTION"
            ),
            None,
        )
        if base is None or base["utility"] is None or row["utility"] is None:
            missing.append((row["state_id"], row["action"], row["repeat"]))
            continue
        state = State(**row["state"])
        x = encoder.features(state, no_state=no_state)
        body = (
            GENERIC
            if row["action"] == "GENERIC_REMINDER"
            else retriever.full_bodies[row["action"]]
        )
        rows.append(
            {
                "task_id": row["task_id"],
                "state_id": row["state_id"],
                "stage": row["stage"],
                "action": row["action"],
                "x": x,
                "k": encoder.encode(body),
                "delta": row["utility"] - base["utility"],
                "delta_quality": float(row["quality"]) - float(base["quality"]),
                "baseline_run": base["run"],
            }
        )
    for row in source:
        tid = row["task_id"]
        chain = chains.setdefault(tid, {})
        if row["state_id"] in chain:
            continue
        state = State(**row["state"])
        candidates = (
            retriever.rank(state.request + "\n" + state.repo_facts)[:2]
            if no_state
            else row["candidates"]
        )
        chain[row["state_id"]] = {
            "state_id": row["state_id"],
            "stage": row["stage"],
            "terminal_confirmed": row["stage"] == "E2",
            "x": encoder.features(state, no_state=no_state),
            "candidate_ids": candidates,
            "candidates": [
                encoder.encode(retriever.full_bodies[k]) for k in candidates
            ],
        }
    ordered = {
        t: sorted(c.values(), key=lambda r: r["stage"]) for t, c in chains.items() if c
    }
    for task, chain in ordered.items():
        chain[-1]["terminal_confirmed"] = chain[-1]["terminal_confirmed"] or (
            native_status or {}
        ).get(task) in ("COMPLETED", "TIMEOUT")
    return rows, ordered, missing
