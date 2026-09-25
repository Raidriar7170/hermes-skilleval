"""Bounded Phase 1 native public-protocol probes; no research turn protocol."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

MODEL = "gpt-6-sol"
EFFORT = "high"


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def public_only(value):
    if isinstance(value, dict):
        if value.get("type") == "reasoning":
            return None
        return {k: public_only(v) for k, v in value.items()}
    if isinstance(value, list):
        return [
            public_only(v)
            for v in value
            if not (isinstance(v, dict) and v.get("type") == "reasoning")
        ]
    return value


class RPC:
    def __init__(self, command, env, cwd, log):
        self.err = log.open("w")
        self.p = subprocess.Popen(
            command,
            env=env,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.err,
            text=True,
        )
        self.q = queue.Queue()
        self.events = []
        self.seq = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            # Never retain hidden reasoning messages/items, even in private event logs.
            if "reasoning" in obj.get("method", "").lower() or obj.get(
                "method", ""
            ).startswith("codex/event/"):
                continue
            if obj.get("params", {}).get("item", {}).get("type") == "reasoning":
                continue
            self.q.put(public_only(obj))

    def send(self, method, params):
        self.seq += 1
        self.p.stdin.write(
            json.dumps({"id": self.seq, "method": method, "params": params}) + "\n"
        )
        self.p.stdin.flush()
        return self.seq

    def next(self, timeout):
        d = self.q.get(timeout=max(0.01, timeout))
        # Only observable events are persisted; RPC results separately selected.
        if d.get("method") in [
            "item/completed",
            "turn/completed",
            "thread/tokenUsage/updated",
            "error",
            "model/rerouted",
            "configWarning",
        ]:
            self.events.append(d)
        return d

    def call(self, method, params, timeout=45):
        ident = self.send(method, params)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            d = self.next(end - time.monotonic())
            if d.get("id") == ident:
                if "error" in d:
                    raise RuntimeError(d["error"])
                return d.get("result")
        raise TimeoutError(method)

    def close(self):
        self.p.terminate()
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
        self.err.close()


SKILLS = [
    (
        "table-field-inventory",
        "Inspect CSV column names, record counts and empty cells in a small tabular file.",
        "Read the CSV with Python csv.DictReader. Report columns, row count and empty cells. Begin the report with FIELD_LEDGER_V1. Do not modify input data.",
    ),
    (
        "python-test-entry",
        "Find Python test entry points and pytest configuration for a small Python project.",
        "Read pyproject.toml and inspect tests filenames. Identify pytest testpaths and the command to run the suite. Begin the report with TEST_ENTRY_V1. Do not execute tests or change code.",
    ),
    (
        "package-notes-check",
        "Check package distribution documentation for license and installation instructions.",
        "Read README.md and LICENSE if present. Report which installation and licensing information is provided or missing. Begin the report with PACKAGE_NOTES_V1. Do not alter package files.",
    ),
]
PROMPTS = [
    "Use $table-field-inventory to inspect records.csv and report its fields, record count and empty cells.",
    "Inspect records.csv and tell me its column names, number of records, and which fields have empty cells.",
    "Find the Python test entry points and pytest configuration in this project. Tell me which command would run its test suite; do not run it.",
    "What is 19 multiplied by 23? Give the number.",
]


def probe(private, output, ident, binary):
    started = time.monotonic()  # before state, input and client preparation
    root = private / ident
    root.mkdir(parents=True, exist_ok=False)
    home, state, fixture = (root / n for n in ["home", "state", "fixture"])
    for p in [home, state, fixture]:
        p.mkdir()
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    shutil.copyfile(auth, state / "auth.json")
    (state / "auth.json").chmod(0o600)
    (state / "config.toml").write_text(
        'web_search="disabled"\n[features]\nmemories=false\n'
    )
    for name, desc, body in SKILLS:
        p = home / ".agents/skills" / name / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n")
    (fixture / "records.csv").write_text("name,city\nAda,London\nLin,\n")
    (fixture / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    )
    (fixture / "tests").mkdir()
    (fixture / "tests/test_example.py").write_text(
        "def test_sum():\n    assert 1+1 == 2\n"
    )
    (fixture / "README.md").write_text("Install using pip install .\n")
    (fixture / "AGENTS.md").write_text(
        "For reports about local project files, include their filenames.\n"
    )
    env = dict(os.environ, HOME=str(home.resolve()), CODEX_HOME=str(state.resolve()))
    command = [binary, "app-server"]
    result = {
        "id": ident,
        "model": MODEL,
        "effort": EFFORT,
        "command": command,
        "prompt": PROMPTS[int(ident[1:]) - 1],
        "budget_seconds": 180,
        "new_thread": True,
        "memory": "DISABLED",
        "started_unix": time.time(),
        "home": str(home),
        "codex_home": str(state),
        "cwd": str(fixture),
        "progressive_loading_observable": "PARTIAL_INITIAL_CONTEXT_NOT_EXPOSED",
    }
    rpc = None
    try:
        rpc = RPC(command, env, str(fixture), root / "stderr.log")
        rpc.call(
            "initialize",
            {
                "clientInfo": {"name": "native-gap-recon", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        result["skills"] = rpc.call(
            "skills/list", {"cwds": [str(fixture)], "forceReload": True}
        )
        result["models"] = rpc.call("model/list", {})
        thread = rpc.call(
            "thread/start",
            {
                "cwd": str(fixture),
                "model": MODEL,
                "approvalPolicy": "never",
                "sandbox": "workspace-write",
                "ephemeral": False,
            },
        )
        result["thread_id"] = thread["thread"]["id"]
        turn = rpc.call(
            "turn/start",
            {
                "threadId": result["thread_id"],
                "effort": EFFORT,
                "input": [{"type": "text", "text": result["prompt"]}],
            },
        )
        end = started + 180
        while time.monotonic() < end:
            d = rpc.next(end - time.monotonic())
            if d.get("method") == "turn/completed":
                result["terminal"] = d["params"]["turn"]["status"]
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
            if result.get("terminal") == "TIMEOUT" and result.get("thread_id"):
                try:
                    rpc.call(
                        "turn/interrupt",
                        {"threadId": result["thread_id"], "turnId": turn["turn"]["id"]},
                        timeout=10,
                    )
                except Exception:
                    pass
            rpc.close()
            result["public_events"] = rpc.events
        result["elapsed_seconds"] = time.monotonic() - started
        dump(output / ident / "result.json", result)
    print(ident, result["terminal"], result["elapsed_seconds"], flush=True)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["probe-skills"])
    ap.add_argument("--private", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--binary", default=shutil.which("codex"))
    args = ap.parse_args()
    for i in range(1, 5):
        result = probe(args.private, args.output, f"P{i}", args.binary)
        if result["terminal"] in ("failed", "ERROR"):
            break


def run_session(private, ident, prompt, inputs, *, memory=False, seconds=300):
    """One isolated persistent native session; input files are explicitly supplied."""
    started = time.monotonic()
    root = private / ident
    root.mkdir(parents=True, exist_ok=False)
    home, state, work = (root / n for n in ["home", "state", "work"])
    for p in [home, state, work]:
        p.mkdir()
    for name, content in inputs.items():
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    shutil.copyfile(auth, state / "auth.json")
    (state / "auth.json").chmod(0o600)
    config = 'web_search="disabled"\n[features]\nmemories=' + str(memory).lower() + "\n"
    if memory:
        config += "[memories]\ngenerate_memories=true\nuse_memories=true\n"
    (state / "config.toml").write_text(config)
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(state))
    rpc = RPC(
        ["/Applications/ChatGPT.app/Contents/Resources/codex", "app-server"],
        env,
        str(work),
        root / "stderr.log",
    )
    result = {
        "id": ident,
        "model": MODEL,
        "effort": EFFORT,
        "prompt": prompt,
        "memory_enabled": memory,
        "budget_seconds": seconds,
    }
    try:
        rpc.call(
            "initialize",
            {
                "clientInfo": {"name": "native-gap-recon", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        result["config"] = rpc.call("config/read", {"includeLayers": False})
        thread = rpc.call(
            "thread/start",
            {
                "cwd": str(work),
                "model": MODEL,
                "approvalPolicy": "never",
                "sandbox": "workspace-write",
                "ephemeral": False,
            },
        )
        result["thread_id"] = thread["thread"]["id"]
        result["thread_start_source"] = thread["thread"].get("source")
        turn = rpc.call(
            "turn/start",
            {
                "threadId": result["thread_id"],
                "effort": EFFORT,
                "input": [{"type": "text", "text": prompt}],
            },
        )
        while time.monotonic() < started + seconds:
            event = rpc.next(started + seconds - time.monotonic())
            if event.get("method") == "turn/completed":
                result["terminal"] = event["params"]["turn"]["status"]
                break
        else:
            result["terminal"] = "TIMEOUT"
    except Exception as e:
        result["terminal"] = "ERROR"
        result["error"] = str(e)
    finally:
        if result.get("terminal") in ("TIMEOUT", "ERROR") and result.get("thread_id"):
            try:
                rpc.call(
                    "turn/interrupt",
                    {"threadId": result["thread_id"], "turnId": turn["turn"]["id"]},
                    timeout=10,
                )
            except Exception:
                pass
        rpc.close()
        result["public_events"] = rpc.events
        result["elapsed_seconds"] = time.monotonic() - started
        dump(root / "result.json", result)
    return result


def fresh_base(image, base, destination, remaining=lambda: 120):
    """Export only base tree and its commit; exclude future objects and image extras."""
    import io
    import tarfile

    destination.mkdir(parents=True, exist_ok=False)
    prefix = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--entrypoint",
        "git",
        image,
        "-C",
        "/testbed",
    ]
    archive = subprocess.check_output(prefix + ["archive", base], timeout=remaining())
    commit = subprocess.check_output(
        prefix + ["cat-file", "commit", base], timeout=remaining()
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("archive escape")
            if member.issym() or member.islnk():
                raise ValueError("unexpected source archive link")
        tar.extractall(destination)

    def git(*args, input=None):
        return subprocess.check_output(
            ["git", "-C", str(destination), *args], input=input, timeout=remaining()
        )

    git("init", "-q")
    git("add", "-A")
    tree = git("write-tree").decode().strip()
    if not commit.startswith(("tree " + tree + "\n").encode()):
        raise ValueError("base tree mismatch")
    actual = (
        git("hash-object", "-t", "commit", "-w", "--stdin", input=commit)
        .decode()
        .strip()
    )
    if actual != base:
        raise ValueError("base commit mismatch")
    git("update-ref", "refs/heads/main", base)
    git("symbolic-ref", "HEAD", "refs/heads/main")
    (destination / ".git/shallow").write_text(base + "\n")
    return {
        "head": actual,
        "tree": tree,
        "archive_bytes": len(archive),
        "reference_assets_present": False,
    }


def native_smoke(
    private, ident, task, skills, image, binary_dir, seccomp, *, preflight=False
):
    """One full native turn in a task-only Linux sandbox, plus candidate capture."""
    started = time.monotonic()
    root = private / ident
    root.mkdir(parents=True, exist_ok=False)
    source, state, home, scratch = (
        root / n for n in ["repo", "state", "home", "scratch"]
    )
    result = {
        "id": ident,
        "model": MODEL,
        "effort": EFFORT,
        "budget_seconds": 900,
        "condition": "NATIVE_SKILLS_ONLY",
        "started_unix": time.time(),
        "task": task,
        "image": image,
        "phase": "preparing",
    }
    rpc = None
    name = "hermes-native-gap-" + ident

    def remaining():
        value = started + 900 - time.monotonic()
        if value <= 0:
            raise TimeoutError("outer activity budget exhausted")
        return value

    try:
        result["base_export"] = fresh_base(
            image, task["base_commit"], source, remaining
        )
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
            "/state": "deny",
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
        config += "[features]\nmemories=false\n"
        config += '[shell_environment_policy]\ninherit="none"\nset={PATH="/opt/conda/envs/testbed/bin:/usr/local/bin:/usr/bin:/bin",HOME="/home/native",TMPDIR="/workspace/scratch",PYTHONDONTWRITEBYTECODE="1"}\n'
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
            canary = "import pathlib, socket, sys; sys.path.insert(0, '/testbed'); import pyupgrade; assert pyupgrade.__file__.startswith('/testbed/'); print('IMPORT',pyupgrade.__file__); pathlib.Path('/testbed/canary-write').write_text('ok'); print('SKILLS', len(list(pathlib.Path('/home/native/.agents/skills').glob('*/SKILL.md'))));\nfor path in ['/state/canary-secret', '/swebench_matterhorn', '/root', '/.env']:\n try: print('UNEXPECTED_READ',path,list(pathlib.Path(path).iterdir()) if pathlib.Path(path).is_dir() else pathlib.Path(path).read_text()[:0]); raise RuntimeError('read allowed')\n except (PermissionError,FileNotFoundError) as e: print('DENIED',path,type(e).__name__)\ntry: socket.create_connection(('1.1.1.1',443),timeout=2); raise RuntimeError('network allowed')\nexcept OSError: print('NETWORK_DENIED')"
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
            result["terminal"] = "PREFLIGHT_COMPLETE"
            return result
        prompt = (
            task["problem_statement"]
            + "\n\nThe repository is /testbed at the repair-before base. Python and dependencies are installed in /opt/conda/envs/testbed; use its python/pytest. Scratch is /workspace/scratch. Historical skills may be useful references but are not mandatory; current requirements and actual source take priority. Make the requested repair and run relevant available tests. Network access is unavailable in this preconfigured repository maintenance environment."
        )
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
        while time.monotonic() < started + 900:
            event = rpc.next(started + 900 - time.monotonic())
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
                subprocess.run(
                    ["git", "-C", str(source), "add", "-N", "."],
                    check=True,
                    capture_output=True,
                )
                patch = subprocess.check_output(
                    ["git", "-C", str(source), "diff", "--binary", task["base_commit"]]
                )
                (root / "candidate.patch").write_bytes(patch)
                result["candidate_bytes"] = len(patch)
            else:
                result["candidate_capture_status"] = "UNAVAILABLE"
        except Exception as exc:
            result["candidate_capture_status"] = "ERROR"
            result["capture_error"] = str(exc)
        result["elapsed_seconds"] = time.monotonic() - started
        dump(root / "result.json", result)
    return result
