"""Fixed native pilot on registered training mechanisms, retaining all attempts."""

import hashlib
import json
from pathlib import Path
import shutil

from .functional_outcomes import load_objective, outcomes
from .records import verify_artifacts
from .session import dump
from .study import assets, read, run_once, check_once, verify_freeze


def pilot(protocol_path, objective_path, tasks, output, skills, payloads, encoder):
    objective = load_objective(objective_path)
    protocol = read(protocol_path)
    if protocol["objective_sha256"] != objective["sha256"]:
        raise ValueError("pilot objective identity mismatch")
    if (
        protocol["agent"]["model"] != "gpt-5.6-sol"
        or protocol["agent"]["effort"] != "medium"
    ):
        raise ValueError("inherited executor model/effort mismatch")
    tasks, output = Path(tasks), Path(output)
    verify_freeze(protocol, tasks, payloads, skills, encoder)
    output.mkdir(parents=True, exist_ok=True)
    identity = {
        "protocol_sha256": hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        "objective_sha256": objective["sha256"],
    }
    if (output / "identity.json").exists() and read(
        output / "identity.json"
    ) != identity:
        raise ValueError("pilot resume identity changed")
    dump(output / "identity.json", identity)
    _, retriever, _, _ = assets(payloads, encoder)
    home = output / "session-home"
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    rows = []
    try:
        for info in protocol["tasks"]:
            if info["split"] != "train":
                raise ValueError("pilot must use training mechanisms")
            task = tasks / info["task_id"]
            for repeat in range(1, protocol["repeats"] + 1):
                run = output / info["task_id"] / f"r{repeat}"
                print(
                    json.dumps({"starting": info["task_id"], "repeat": repeat}),
                    flush=True,
                )
                execution = run_once(
                    task,
                    run,
                    home,
                    skills,
                    total=protocol["total_seconds"],
                    retriever=retriever,
                )
                checks_root = run.parent / (run.name + "-checks")
                checks = check_once(task, run, checks_root, execution)
                integrity = "VERIFIED"
                evidence = {
                    "run": str(run),
                    "checks_root": str(checks_root),
                    "execution": execution,
                    "checks": checks,
                    "quality": None,
                }
                try:
                    verification = verify_artifacts(evidence)
                    if verification["status"] != "VERIFIED":
                        integrity = verification["status"]
                except (ValueError, OSError) as exc:
                    integrity = "INTEGRITY_UNKNOWN"
                    verification = {"error": str(exc)}
                label = outcomes(execution, checks, integrity=integrity)
                row = {
                    **evidence,
                    **label,
                    "task_id": info["task_id"],
                    "family": info["family"],
                    "split": "train",
                    "repeat": repeat,
                    "verification": verification,
                    "action": "NO_INTERVENTION",
                    "pilot": True,
                }
                rows.append(row)
                dump(
                    output / "records.json",
                    {
                        "identity": identity,
                        "planned": len(protocol["tasks"]) * protocol["repeats"],
                        "rows": rows,
                    },
                )
                print(
                    json.dumps(
                        {"completed": info["task_id"], "repeat": repeat, **label}
                    ),
                    flush=True,
                )
    finally:
        auth.unlink(missing_ok=True)
    return {
        "planned": len(protocol["tasks"]) * protocol["repeats"],
        "recorded": len(rows),
        "functional_pass": sum(r["y_functional"] == 1 for r in rows),
        "functional_fail": sum(r["y_functional"] == 0 for r in rows),
        "unknown": sum(r["y_functional"] is None for r in rows),
    }
