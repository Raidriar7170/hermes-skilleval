"""Outer process clock for each Phase 2 attempt, before worker/input preparation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def supervise(root, command_factory, seconds, cleanup=None):
    # root and budget are the minimal attempt descriptor; no task data read yet.
    t0 = time.monotonic()
    started_unix = time.time()
    deadline = t0 + seconds
    process = None
    record = {
        "t0": t0,
        "started_unix": started_unix,
        "deadline": deadline,
        "budget_seconds": seconds,
        "model_started": False,
        "tool_action_observed": False,
        "parent_status": "PREPARING",
    }
    root.mkdir(parents=True, exist_ok=False)  # refusal protects existing attempts
    try:
        command = command_factory(deadline)
        with (root / "worker-stdout.log").open("w") as out:
            process = subprocess.Popen(
                command, stdout=out, stderr=subprocess.STDOUT, start_new_session=True
            )
            record["worker_pid"] = process.pid
            (root / "parent-live.json").write_text(json.dumps(record, indent=2))
            try:
                code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
                record.update(parent_status="WORKER_EXIT", worker_exitcode=code)
            except subprocess.TimeoutExpired:
                record["parent_status"] = "TIMEOUT"
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    except Exception as exc:
        record.update(parent_status="ERROR", error=str(exc))
    finally:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired) as exc:
                record["worker_termination_error"] = str(exc)
        if cleanup:
            try:
                record["parent_cleanup"] = cleanup()
            except Exception as exc:
                record["parent_cleanup_error"] = str(exc)
        worker = root / "worker-result.json"
        if worker.exists():
            try:
                data = json.loads(worker.read_text())
                record["worker"] = data
                events = data.get("public_events", [])
                requested = data.get("phase") == "agent_started"
                record["model_start_requested"] = requested
                record["model_started"] = "UNKNOWN" if requested else False
                if any(
                    e.get("params", {}).get("item", {}).get("type")
                    in ("agentMessage", "commandExecution", "fileChange", "mcpToolCall")
                    for e in events
                ):
                    record["model_started"] = True
                record["tool_action_observed"] = any(
                    e.get("params", {}).get("item", {}).get("type")
                    in ("commandExecution", "fileChange", "mcpToolCall")
                    for e in events
                )
            except Exception as exc:
                record["worker_read_error"] = str(exc)
        if "worker" not in record and process is not None:
            record["model_started"] = "UNKNOWN"
            record["tool_action_observed"] = "UNKNOWN"
            for filename in ["manifest.json", "public-events-live.json"]:
                try:
                    value = json.loads((root / filename).read_text())
                    record["recovered_" + filename] = value
                    if (
                        filename == "manifest.json"
                        and value.get("phase") == "agent_started"
                    ):
                        record["model_start_requested"] = True
                    if filename == "public-events-live.json":
                        if any(
                            e.get("params", {}).get("item", {}).get("type")
                            in ("commandExecution", "fileChange", "mcpToolCall")
                            for e in value
                        ):
                            record["tool_action_observed"] = True
                except (OSError, ValueError):
                    pass
        # This finally remains authoritative even if preparation or worker failed.
        t1 = time.monotonic()
        record.update(t1=t1, elapsed_seconds=t1 - t0, budget_valid=t1 <= deadline)
        (root / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def capture_candidate(root, base):
    """Use pre-agent Git metadata, never the task's mutable local/global config."""
    git_dir = root / "capture-git"
    if not git_dir.exists():
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    git = [
        "git",
        "--git-dir",
        str(git_dir),
        "--work-tree",
        str(root / "repo"),
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=" + os.devnull,
    ]
    subprocess.run(
        git + ["add", "-N", "."], check=True, capture_output=True, timeout=10, env=env
    )
    patch = subprocess.check_output(
        git + ["diff", "--no-ext-diff", "--no-textconv", "--binary", base],
        timeout=10,
        env=env,
    )
    temp = root / "candidate.patch.tmp"
    temp.write_bytes(patch)
    temp.replace(root / "candidate.patch")
    return {"bytes": len(patch), "sha256": hashlib.sha256(patch).hexdigest()}


def run_descriptor(descriptor, root, seconds=900, expected_descriptor_sha256=None):

    if sys.version_info < (3, 11):
        raise RuntimeError("Python >=3.11 required for shared monotonic clock")

    def command(deadline):
        if (
            expected_descriptor_sha256 is not None
            and hashlib.sha256(Path(descriptor).read_bytes()).hexdigest()
            != expected_descriptor_sha256
        ):
            raise ValueError("frozen attempt descriptor changed")
        return [
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            "--descriptor",
            descriptor,
            "--root",
            str(root),
            "--deadline",
            str(deadline),
        ]

    def cleanup():
        # Descriptor read occurs after t0; never traverse unrelated containers.
        desc = json.loads(Path(descriptor).read_text())
        name = "hermes-native-phase2-" + desc["id"]
        live = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=^/" + name + "$"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        if live.stdout.strip():
            subprocess.run(
                ["docker", "stop", "-t", "3", name],
                capture_output=True,
                timeout=10,
                check=True,
            )
        live = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=^/" + name + "$"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        if live.stdout.strip():
            raise RuntimeError("owned task container still running; capture withheld")
        task = json.loads(Path(desc["public_task"]).read_text())
        captured = capture_candidate(root, task["base_commit"])
        return {
            "no_running_tool_confirmation": True,
            "candidate_captured": captured is not None,
            "candidate_identity": captured,
        }

    result = supervise(root, command, seconds, cleanup)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["run", "worker"])
    ap.add_argument("--descriptor", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=900)
    ap.add_argument("--deadline", type=float)
    args = ap.parse_args()
    if sys.version_info < (3, 11):
        ap.error("Python >=3.11 required: shared cross-process monotonic clock")
    if args.action == "worker":
        from native_gap_phase2_support.runtime import native_attempt

        native_attempt(args.root, args.descriptor, args.deadline)
    else:
        result = run_descriptor(args.descriptor, args.root, args.seconds)
        print(json.dumps({k: v for k, v in result.items() if k != "worker"}))


if __name__ == "__main__":
    main()
