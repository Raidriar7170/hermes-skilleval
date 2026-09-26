"""Phase 2 worker: same native public protocol with precise skill read exception."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import time
from native_gap_phase1 import RPC, MODEL, EFFORT, dump, fresh_base


def native_attempt(root, descriptor, deadline):
    """One full native turn in a task-only Linux sandbox, plus candidate capture."""
    # Called only by the already-timed parent. All descriptor/input I/O is online.
    started = time.monotonic()
    desc = json.loads(Path(descriptor).read_text())
    ident = desc["id"]
    for entry in desc.get("bindings", []):
        actual = hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError("frozen input changed: " + entry["name"])
    task = json.loads(Path(desc["public_task"]).read_text())
    allowed = {"instance_id", "repo", "base_commit", "problem_statement", "language"}
    if set(task) - allowed:
        raise ValueError("non-public task fields in repair input")
    skills = Path(desc["skills"])
    image = desc["image"]
    binary_dir = Path(desc["binary_dir"])
    seccomp = Path(desc["seccomp"])
    preflight = desc.get("canary_only", False)
    source, state, home, scratch = (
        root / n for n in ["repo", "state", "home", "scratch"]
    )
    result = {
        "id": ident,
        "model": MODEL,
        "effort": EFFORT,
        "budget_seconds": desc.get("budget_seconds", 900),
        "condition": desc.get("arm", "NATIVE"),
        "started_unix": time.time(),
        "task": task,
        "image": image,
        "phase": "preparing",
        "input_bindings_verified": True,
    }
    rpc = None
    name = "hermes-native-phase2-" + ident

    def remaining():
        value = deadline - 15 - time.monotonic()
        if value <= 0:
            raise TimeoutError("outer activity budget exhausted")
        return value

    try:
        if desc.get("fixture_dir"):
            shutil.copytree(desc["fixture_dir"], source)
            result["base_export"] = {"fixture": True, "head": task["base_commit"]}
        else:
            result["base_export"] = fresh_base(
                image, task["base_commit"], source, remaining
            )
        shutil.copytree(source / ".git", root / "capture-git")
        for p in [state, home, scratch]:
            p.mkdir()
        shutil.copytree(skills, home / ".agents/skills")
        auth = (
            Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            / "auth.json"
        )
        shutil.copyfile(auth, state / "auth.json")
        (state / "auth.json").chmod(0o600)
        roots = {
            ":root": "deny",
            ":minimal": "read",
            "/testbed": "write",
            "/workspace/scratch": "write",
            "/home/native/.agents/skills": "read",
            "/native": "read",
            "/usr": "read",
            "/lib": "read",
            "/bin": "read",
            "/etc": "read",
            "/opt": "read",
            "/state/skills": "read",
        }
        mapping = ", ".join(
            json.dumps(k) + "=" + json.dumps(v) for k, v in roots.items()
        )
        config = 'default_permissions="native-task"\nweb_search="disabled"\n'
        config += (
            "[permissions.native-task]\nfilesystem={"
            + mapping
            + "}\nnetwork.enabled=false\n"
        )
        config += "[features]\nmemories=false\n[memories]\ngenerate_memories=false\nuse_memories=false\n"
        config += '[shell_environment_policy]\ninherit="none"\nset={PATH="/opt/conda/envs/testbed/bin:/usr/local/bin:/usr/bin:/bin",HOME="/home/native",TMPDIR="/workspace/scratch",PYTHONDONTWRITEBYTECODE="1",PYTHONPATH="/testbed"}\n'
        (state / "config.toml").write_text(config)
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=512m",
            "--security-opt",
            "seccomp=" + str(seccomp),
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--memory",
            "4g",
            "--cpus",
            "2",
            "-v",
            str(source) + ":/testbed",
            "-v",
            str(state) + ":/state",
            "-v",
            str(home) + ":/home/native",
            "-v",
            str(scratch) + ":/workspace/scratch",
            "-v",
            str(binary_dir) + ":/native:ro",
            "-e",
            "HOME=/home/native",
            "-e",
            "CODEX_HOME=/state",
            "-w",
            "/testbed",
            "--entrypoint",
            "/native/bin/codex",
            image,
            "app-server",
        ]
        result["command"] = command
        rpc = RPC(command, dict(os.environ), str(root), root / "stderr.log")
        rpc.call(
            "initialize",
            {
                "clientInfo": {"name": "native-gap-recon", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
            timeout=min(45, remaining()),
        )
        result["skills_list"] = rpc.call(
            "skills/list",
            {"cwds": ["/testbed"], "forceReload": True},
            timeout=min(45, remaining()),
        )
        result["effective_config"] = rpc.call(
            "config/read", {"includeLayers": False}, timeout=min(45, remaining())
        )
        effective = result["effective_config"]["config"]
        if effective.get("features", {}).get("memories") is not False or any(
            effective.get("memories", {}).get(k) is not False
            for k in ("generate_memories", "use_memories")
        ):
            raise ValueError("effective memory configuration is not skills-only")
        entries = [
            s for group in result["skills_list"]["data"] for s in group["skills"]
        ]
        names = [s["name"] for s in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate native skill names")
        expected_names = set(desc.get("expected_skill_names", []))
        if expected_names and not expected_names.issubset(names):
            raise ValueError("native discovery lacks frozen library entries")
        extras = [s for s in entries if s["name"] not in expected_names]
        if expected_names and any(
            not s["path"].startswith("/testbed/") for s in extras
        ):
            raise ValueError("unexpected non-project skill scope")
        result["original_project_skills"] = extras if expected_names else []
        by_name = {entry["name"]: entry for entry in entries}
        for expected in desc.get("expected_skill_metadata", []):
            actual = by_name[expected["name"]]
            if any(actual.get(k) != expected[k] for k in ("description", "path")):
                raise ValueError("native metadata differs from frozen catalog")
        result["discovery_identity_verified"] = bool(
            desc.get("expected_skill_metadata")
        )
        for entry in desc.get("system_assets", []):
            actual = hashlib.sha256(
                (state / "skills" / entry["path"]).read_bytes()
            ).hexdigest()
            if actual != entry["sha256"]:
                raise ValueError("system skill asset changed: " + entry["path"])
        thread = rpc.call(
            "thread/start",
            {
                "cwd": "/testbed",
                "model": MODEL,
                "approvalPolicy": "never",
                "ephemeral": False,
            },
            timeout=min(45, remaining()),
        )
        result["thread_id"] = thread["thread"]["id"]
        result["thread_identity"] = {
            k: thread.get(k)
            for k in ["model", "modelProvider", "cwd", "approvalPolicy", "sandbox"]
        }
        if preflight:
            entries = [
                s for group in result["skills_list"]["data"] for s in group["skills"]
            ]
            names = [s["name"] for s in entries]
            if len(names) != len(set(names)):
                raise ValueError("duplicate native skill names")
            paths = [s["path"] for s in entries]
            canary = "import pathlib, socket\npaths=" + repr(paths) + "\n"
            canary += "for path in paths:\n p=pathlib.Path(path); print('BODY_READ',path,len(p.read_bytes()))\n"
            canary += "for p in pathlib.Path('/state/skills').rglob('*'):\n if p.is_file(): print('ASSET_READ',str(p),len(p.read_bytes()))\n"
            canary += "for path in ['/state/canary-secret', '/state/auth.json']:\n try:\n  f=open(path); f.close(); raise RuntimeError('credential path opened')\n except (PermissionError,FileNotFoundError): print('DENIED_OR_MASKED',path)\n"
            canary += "try:\n socket.create_connection(('1.1.1.1',443),timeout=2); raise RuntimeError('network allowed')\nexcept OSError: print('NETWORK_DENIED')\n"
            (state / "canary-secret").write_text("harmless sandbox canary")
            checked = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "/native/bin/codex",
                    "sandbox",
                    "-P",
                    "native-task",
                    "--",
                    "/opt/conda/envs/testbed/bin/python",
                    "-c",
                    canary,
                ],
                capture_output=True,
                text=True,
                timeout=min(60, remaining()),
            )
            result["preflight"] = {
                "returncode": checked.returncode,
                "stdout": checked.stdout,
                "stderr": checked.stderr,
            }
            result["terminal"] = (
                "PREFLIGHT_COMPLETE" if checked.returncode == 0 else "PREFLIGHT_FAILED"
            )
            return result
        prompt = (
            task["problem_statement"]
            + "\n\nThe repository is /testbed at the repair-before base. Python and dependencies are installed in /opt/conda/envs/testbed; use its python/pytest. Scratch is /workspace/scratch. Historical skills may be useful references but are not mandatory; current requirements and actual source take priority. Make the requested repair and run relevant available tests. Network access is unavailable in this preconfigured repository maintenance environment."
        )
        if desc.get("fixture_prompt"):
            prompt = desc["fixture_prompt"]
        prompt = (
            f"Repository: {task['repo']}\nLanguage: {task.get('language', 'Python')}\n\n"
            + prompt
        )
        prompt += "\nThe full experience catalog is /home/native/.agents/skills/catalog.md. All entries and references are optional and available."
        if desc.get("arm") == "ASSIST":
            from native_gap_phase2_support.navigation import navigate

            retrieval_start = time.monotonic()
            try:
                nav = navigate(desc, task)
                prompt += "\n\n" + nav["block"]
                result["navigation"] = nav
                result["navigation_fallback"] = False
            except Exception as exc:
                result["navigation_fallback"] = True
                result["navigation_error"] = str(exc)
            result["navigation_seconds"] = time.monotonic() - retrieval_start
        remaining()
        result["prompt"] = prompt
        result["phase"] = "agent_started"
        dump(root / "manifest.json", result)
        turn = rpc.call(
            "turn/start",
            {
                "threadId": result["thread_id"],
                "effort": EFFORT,
                "input": [{"type": "text", "text": prompt}],
            },
            timeout=min(45, remaining()),
        )
        result["turn_start_acknowledged"] = True
        dump(root / "manifest.json", result)
        while time.monotonic() < deadline - 15:
            event = rpc.next(deadline - 15 - time.monotonic())
            dump(root / "public-events-live.json", rpc.events)
            if event.get("method") == "turn/completed":
                result["terminal"] = event["params"]["turn"]["status"]
                break
        else:
            result["terminal"] = "TIMEOUT"
    except queue.Empty:
        result["terminal"] = "TIMEOUT"
    except Exception as exc:
        result["terminal"] = "ERROR"
        result["error"] = str(exc)
    finally:
        if rpc:
            if result.get("terminal") in ("TIMEOUT", "ERROR") and result.get(
                "thread_id"
            ):
                try:
                    rpc.call(
                        "turn/interrupt",
                        {"threadId": result["thread_id"], "turnId": turn["turn"]["id"]},
                        timeout=10,
                    )
                except Exception:
                    pass
            # A cleanup failure invalidates capture but must not erase the attempt.
            try:
                stopped = subprocess.run(
                    ["docker", "stop", "-t", "3", name], capture_output=True, timeout=20
                )
                remaining = subprocess.run(
                    ["docker", "ps", "-q", "--filter", "name=^/" + name + "$"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                result["no_running_tool_confirmation"] = (
                    remaining.returncode == 0 and not remaining.stdout.strip()
                )
                result["container_stop_returncode"] = stopped.returncode
            except Exception as exc:
                result["no_running_tool_confirmation"] = False
                result["cleanup_error"] = str(exc)
            try:
                rpc.close()
            except Exception as exc:
                result["client_cleanup_error"] = str(exc)
            result["public_events"] = rpc.events
        else:
            result["no_running_tool_confirmation"] = True
        try:
            if (source / ".git").exists() and result["no_running_tool_confirmation"]:
                from native_gap_phase2 import capture_candidate

                identity = capture_candidate(root, task["base_commit"])
                result["candidate_identity"] = identity
                result["candidate_bytes"] = identity["bytes"]
            else:
                result["candidate_capture_status"] = "UNAVAILABLE"
        except Exception as exc:
            result["candidate_capture_status"] = "ERROR"
            result["capture_error"] = str(exc)
        result["worker_elapsed_seconds"] = time.monotonic() - started
        dump(root / "worker-result.json", result)
    return result
