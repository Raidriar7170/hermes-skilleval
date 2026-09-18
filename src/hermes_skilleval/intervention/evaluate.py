"""Frozen six-arm actual trajectories and zero-model outcome recomputation."""

from __future__ import annotations

import hashlib
import random
import shutil
from pathlib import Path

from .controller import Controller, METHODS
from .learning import Predictor, model_identity
from .session import dump
from .study import read, assets, verify_freeze, run_once, check_once, qualify_quality
from .rollouts import utility


def evaluate(
    protocol_path, tasks, output, skill_dir, payload_dir, encoder_path, models
):
    protocol = read(protocol_path)
    tasks = Path(tasks)
    output = Path(output)
    models = Path(models)
    verify_freeze(protocol, tasks, payload_dir, skill_dir, encoder_path)
    if not (models / "independent-reload.json").exists():
        raise ValueError("independent reload required")
    protocol_digest = hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest()
    reload_record = read(models / "independent-reload.json")
    training_records = set()
    for name in ("full", "no-state"):
        if reload_record[name].get("model_identity") != model_identity(
            models / name
        ) or not reload_record[name].get("match"):
            raise ValueError("reload record does not bind the current model")
        binding = read(models / name / "model.json")["data_binding"]
        training_records.add(binding["records_sha256"])
        if (
            binding["protocol_sha256"] != protocol_digest
            or binding["encoder_files"] != protocol["representation"]["files"]
            or binding["payload_files"] != protocol["payloads"]
            or binding["registry_sha256"] != protocol["registry_sha256"]
        ):
            raise ValueError(
                "trained model and evaluation assets/protocol do not match"
            )
    if len(training_records) != 1:
        raise ValueError("policy models were trained on different record sets")
    output.mkdir(parents=True, exist_ok=True)
    identity = {
        str(p.relative_to(models)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in models.rglob("*")
        if p.is_file()
        and p.name
        in ("weights.pt", "model.json", "training.json", "independent-reload.json")
    }
    lock = output / "policy-freeze.json"
    if lock.exists():
        frozen = read(lock)
        if (
            frozen["models"] != identity
            or frozen["protocol_sha256"] != protocol_digest
            or frozen["methods"] != list(METHODS)
        ):
            raise ValueError("models changed after final policy freeze")
    else:
        dump(
            lock,
            {
                "models": identity,
                "methods": list(METHODS),
                "protocol_sha256": hashlib.sha256(
                    Path(protocol_path).read_bytes()
                ).hexdigest(),
            },
        )
    encoder, retriever, counts, _ = assets(payload_dir, encoder_path)
    home = output / "session-home"
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    try:
        for task_info in protocol["tasks"]:
            if task_info["split"] != "test":
                continue
            tid = task_info["task_id"]
            task = tasks / tid
            root = output / tid
            if (root / "records.json").exists():
                continue
            root.mkdir(exist_ok=True)
            order = [
                (method, repeat)
                for method in METHODS
                for repeat in range(1, protocol["final_repeats"] + 1)
            ]
            random.Random(protocol["order_seed"] + sum(tid.encode())).shuffle(order)
            rows = []
            for method, repeat in order:
                predictor = (
                    Predictor(models, method, encoder, retriever)
                    if method.startswith("H-")
                    else None
                )
                run = root / (method + f"-r{repeat}")
                result = run_once(
                    task,
                    run,
                    home,
                    skill_dir,
                    total=protocol["total_seconds"],
                    retriever=retriever,
                    controller=Controller(method),
                    predict=predictor,
                    token_counts=counts,
                )
                rows.append(
                    {
                        "task_id": tid,
                        "method": method,
                        "repeat": repeat,
                        "run": str(run),
                        "execution": result,
                        "gain_model_calls": sum(
                            d.get("gains") is not None
                            for d in result.get("decisions", [])
                        )
                        if predictor
                        else 0,
                        "wait_model_calls": sum(
                            d.get("waiting_value") is not None and d["stage"] != "E2"
                            for d in result.get("decisions", [])
                        )
                        if predictor and predictor.use_wait
                        else 0,
                    }
                )
                print(
                    {
                        "task": tid,
                        "method": method,
                        "repeat": repeat,
                        "status": result["status"],
                    },
                    flush=True,
                )
            # Hidden checks remain outside every policy/Agent and start after the task matrix.
            for row in rows:
                run = Path(row["run"])
                checks = check_once(
                    task, run, root / (run.name + "-checks"), row["execution"]
                )
                quality = qualify_quality(row["execution"], checks)
                e = row["execution"]
                row.update(
                    checks=checks,
                    quality=quality,
                    utility=utility(
                        quality,
                        protocol["total_seconds"],
                        e["tail_seconds"],
                        e["payload_tokens"],
                    )
                    if e.get("tail_seconds") is not None
                    else None,
                )
            dump(root / "records.json", {"rows": rows})
            print(
                {
                    "test_task_complete": tid,
                    "valid": sum(r["quality"] is not None for r in rows),
                    "runs": len(rows),
                },
                flush=True,
            )
    finally:
        auth.unlink(missing_ok=True)
    rows = []
    for t in protocol["tasks"]:
        p = output / t["task_id"] / "records.json"
        if t["split"] == "test" and p.exists():
            rows.extend(read(p)["rows"])
    dump(output / "records.json", {"rows": rows, "policy_freeze": read(lock)})
    return summarize_rows(rows)


def summarize_rows(rows):
    results = {}
    for method in METHODS:
        selected = [r for r in rows if r["method"] == method]
        valid = [r for r in selected if r["quality"] is not None]
        decisions = [d for r in selected for d in r["execution"].get("decisions", [])]
        results[method] = {
            "runs": len(selected),
            "valid": len(valid),
            "successes": sum(r["quality"] for r in valid),
            "unknown": len(selected) - len(valid),
            "failure": sum(not r["quality"] for r in valid),
            "mean_utility": sum(r["utility"] for r in valid) / len(valid)
            if valid
            else None,
            "injections": sum(r["execution"].get("injected", False) for r in selected),
            "waiting_decisions": sum(
                d["reason"] == "WAIT_MODEL_DECISION" for d in decisions
            ),
            "noops": sum(d["reason"] == "NOOP_MODEL_DECISION" for d in decisions),
            "mean_active_seconds": sum(
                r["execution"].get("tail_seconds") or 0 for r in selected
            )
            / len(selected)
            if selected
            else None,
        }
    return results


def replay(records_path):
    """Records only: imports no torch/models and never runs Docker or an Agent."""
    from .records import verify_artifacts, verify_public_artifacts

    bundle = read(records_path)
    rows = bundle["rows"]
    for row in rows:
        if bundle.get("format") == "asi-public-v1":
            verify_public_artifacts(row, Path(records_path).parent)
        else:
            verify_artifacts(row)
        execution = row["execution"]
        checks = row["checks"]
        quality = qualify_quality(execution, checks)
        if quality != row["quality"]:
            raise ValueError("quality mismatch")
        if quality is not None:
            expected = utility(
                quality,
                execution["total_seconds"],
                execution["tail_seconds"] + execution.get("prefix_seconds", 0),
                row.get("payload_tokens", execution["payload_tokens"]),
            )
            if abs(expected - row["utility"]) > 1e-9:
                raise ValueError("utility mismatch")
    return (
        summarize_rows(rows)
        if rows and "method" in rows[0]
        else {"rows": len(rows), "valid": sum(r["quality"] is not None for r in rows)}
    )
