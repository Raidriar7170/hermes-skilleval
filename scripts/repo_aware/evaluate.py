"""Sequential resumable real replay matrix; every started attempt is retained."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--protocol", type=Path, required=True)
p.add_argument("--resume", action="store_true")
a = p.parse_args()
c = json.loads(a.protocol.read_text())
root = Path(c["output"])
root.mkdir(parents=True, exist_ok=True)
identity = hashlib.sha256(a.protocol.read_bytes()).hexdigest()
gate_binding = {}
if any(cell["policy"] == "auto" for cell in c["cells"]):
    routing_path = Path(c["routing_config"])
    routing = json.loads(routing_path.read_text())
    gate_path = Path(routing["gate"])
    if not gate_path.is_absolute():
        gate_path = routing_path.parent / gate_path
    seal = json.loads(gate_path.with_suffix(".freeze.json").read_text())
    gate_binding = {
        "gate_sha256": hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        "routing_config_sha256": hashlib.sha256(routing_path.read_bytes()).hexdigest(),
        "r_version": routing["r_version"],
    }
    if (
        gate_binding["gate_sha256"] != seal["gate_sha256"]
        or routing["r_version"] != seal["r_version"]
    ):
        raise ValueError("gate/config freeze mismatch before launch")
locked = root / "protocol-sha256.txt"
if locked.exists() and locked.read_text().strip() != identity:
    raise ValueError("protocol changed")
locked.write_text(identity + "\n")
for cell in c["cells"]:
    run_id = cell["run_id"]
    out = root / run_id
    if (out / "run.json").exists() or (out / "executor.json").exists():
        if not a.resume:
            raise ValueError("prior attempt exists")
        continue
    if out.exists():
        raise ValueError("incomplete attempt needs explicit diagnosis; never overwrite")
    task = Path(c["tasks"]) / cell["task_id"]
    cmd = [
        sys.executable,
        "-m",
        "hermes_skilleval._maintenance.execute",
        "--task-root",
        str(task),
        "--registry",
        c["registry"],
        "--skill-assets",
        c["skill_assets"],
        "--output",
        str(out),
        "--workspace-root",
        c["workspace"],
        "--private-root",
        c["private"],
        "--canary",
        c["canary"],
        "--qualification",
        str(Path(c["qualification"]) / cell["task_id"] / "qualified.json"),
        "--public-request",
        str(task / "public.md"),
        "--run-id",
        run_id,
        "--timeout",
        str(c["timeout"]),
    ]
    if cell["policy"] == "native-minus":
        cmd += ["--arm", "N"]
    else:
        cmd += ["--policy", cell["policy"], "--routing-config", c["routing_config"]]
    if gate_binding:
        if (
            hashlib.sha256(gate_path.read_bytes()).hexdigest()
            != gate_binding["gate_sha256"]
            or hashlib.sha256(routing_path.read_bytes()).hexdigest()
            != gate_binding["routing_config_sha256"]
        ):
            raise ValueError("frozen policy changed between final launches")
    with (root / "attempts.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "event": "launch",
                    "run_id": run_id,
                    "time": time.time(),
                    "protocol_sha256": identity,
                    **gate_binding,
                }
            )
            + "\n"
        )
    with (root / (run_id + ".log")).open("x") as log:
        result = subprocess.run(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=c["timeout"] + 600,
        )
    with (root / "attempts.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "event": "exit",
                    "run_id": run_id,
                    "exit_code": result.returncode,
                    "time": time.time(),
                }
            )
            + "\n"
        )
    print(json.dumps({"run_id": run_id, "exit_code": result.returncode}), flush=True)
    if not (out / "executor.json").exists():
        raise RuntimeError("prelaunch failure; diagnose before continuing")
