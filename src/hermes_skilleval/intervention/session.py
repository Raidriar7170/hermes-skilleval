"""Official app-server continuation inside the inherited Linux isolation boundary.

Only public app-server messages are used. No rollout files are edited or parsed.
The host controller cannot inspect private reasoning via this adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import stat
import subprocess
import threading
import time
import uuid

CWD = "/workspace/repo"
SCRATCH = "/workspace/scratch"
SESSION_HOME = "/var/lib/hermes-session"
IMAGE = "hermes-asi-executor:v1"
NEUTRAL = (
    "Continue the requested maintenance task from the current files and conversation. "
    "Work in bounded segments: after at most four completed shell/tool actions, finish "
    "this turn with a brief factual progress report. Do not launch background jobs. "
    "Report segment_status TASK_COMPLETE when ready to deliver a candidate, otherwise CONTINUE. "
    "Use /workspace/scratch for scratch files. Available skills are in /workspace/skills; "
    "you may read them natively. No extra external guidance is implied by continuation."
)


def public_only(value):
    """Drop private reasoning items recursively, including hydrated RPC turns."""
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


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def inventory(root: Path):
    """Content identity; capture link targets as text, never follow them."""
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            result[str(p.relative_to(root))] = "symlink:" + os.readlink(p)
            continue
        if p.is_fifo():
            result[str(p.relative_to(root))] = "fifo:" + oct(
                stat.S_IMODE(p.stat().st_mode)
            )
            continue
        if p.is_file():
            result[str(p.relative_to(root))] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return result


def clone_scratch(source, output):
    """Completed tools have no live pipe handles; preserve FIFO nodes, not buffers."""

    def copy_file(src, dst):
        mode = os.stat(src, follow_symlinks=False).st_mode
        if stat.S_ISFIFO(mode):
            os.mkfifo(dst, stat.S_IMODE(mode))
            shutil.copystat(src, dst)
            return dst
        return shutil.copy2(src, dst)

    return shutil.copytree(source, output, symlinks=True, copy_function=copy_file)


def snapshot(source: Path, scratch: Path, output: Path, metadata: dict):
    """Call only after the server/container has stopped and confirmed no live tools."""
    if not metadata.get("no_running_tool_confirmation"):
        raise ValueError("cannot snapshot live tools")
    output.mkdir(parents=True, exist_ok=False)
    before = {"source": inventory(source), "scratch": inventory(scratch)}
    shutil.copytree(source, output / "source", symlinks=True)
    clone_scratch(scratch, output / "scratch")
    after = {
        "source": inventory(output / "source"),
        "scratch": inventory(output / "scratch"),
    }
    if before != after:
        raise ValueError("source changed during checkpoint")
    dump(output / "checkpoint.json", {**metadata, "files": after})
    return output


class Session:
    """One isolated server with stable logical mount paths and persistent history.

    Separate Sessions share only a controller-owned, tool-denied Codex home.
    Each branch has independent repository and scratch mounts. Forking uses the
    official completed-turn ID; parent history never contains child turns.
    """

    def __init__(
        self,
        source,
        scratch,
        home,
        skills,
        output,
        *,
        image=IMAGE,
        model="gpt-5.6-sol",
        public_docs=None,
    ):
        self.source, self.scratch, self.home, self.skills, self.output = map(
            lambda p: Path(p).resolve(), (source, scratch, home, skills, output)
        )
        self.public_docs = (
            Path(public_docs).resolve() if public_docs is not None else None
        )
        self.image, self.model = image, model
        self.name = "hermes-asi-" + uuid.uuid4().hex[:16]
        self.messages = queue.Queue()
        self.events = []
        self.next_id = 0
        self.active = False
        self.closed = False
        self.thread_id = None
        self.last_turn_id = None
        self.active_seconds = 0.0
        self.pending = {}

    def __enter__(self):
        for p in (self.scratch, self.home, self.output):
            p.mkdir(parents=True, exist_ok=True)
        roots = {
            ":root": "deny",
            ":minimal": "read",
            CWD: "write",
            SCRATCH: "write",
            "/workspace/skills": "read",
            SESSION_HOME: "deny",
            "/usr": "read",
            "/lib": "read",
            "/bin": "read",
            "/etc": "read",
        }
        if self.public_docs is not None:
            roots["/workspace/public-docs"] = "read"
        mapping = ", ".join(
            json.dumps(k) + "=" + json.dumps(v) for k, v in roots.items()
        )
        overrides = [
            'default_permissions="hermes-task"',
            "permissions.hermes-task.filesystem={" + mapping + "}",
            "permissions.hermes-task.network.enabled=false",
            'shell_environment_policy.inherit="none"',
            'shell_environment_policy.set={PATH="/usr/local/bin:/usr/bin:/bin",TMPDIR="/workspace/scratch",PYTHONDONTWRITEBYTECODE="1"}',
            'web_search="disabled"',
            'model_reasoning_effort="medium"',
            "features.multi_agent=false",
            "features.multi_agent_v2=false",
        ]
        seccomp = Path(__file__).parents[1] / "_maintenance/docker-seccomp-userns.json"
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            self.name,
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
            f"{self.source}:{CWD}",
            "-v",
            f"{self.scratch}:{SCRATCH}",
            "-v",
            f"{self.skills}:/workspace/skills:ro",
            "-v",
            f"{self.home}:{SESSION_HOME}",
            "-w",
            CWD,
            "-e",
            f"CODEX_HOME={SESSION_HOME}",
            "-e",
            "HOME=/tmp/home",
            self.image,
            "codex",
        ]
        if self.public_docs is not None:
            # Insert the read-only documentation mount before the image argument.
            image_index = command.index(self.image)
            command[image_index:image_index] = [
                "-v",
                f"{self.public_docs}:/workspace/public-docs:ro",
            ]
        for setting in overrides:
            command += ["-c", setting]
        command += ["app-server"]
        self.stderr = (self.output / "stderr.txt").open("w")
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            text=True,
            bufsize=1,
        )
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.rpc(
                "initialize",
                {
                    "clientInfo": {"name": "hermes_asi", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.send({"method": "initialized"})
        except BaseException:
            self.close()
            raise
        return self

    def _read(self):
        for line in self.proc.stdout:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            # Never retain private reasoning or raw provider response streams.
            method = item.get("method", "")
            if (
                "reasoning" in method.lower()
                or method.startswith("codex/event/")
                or item.get("params", {}).get("item", {}).get("type") == "reasoning"
            ):
                continue
            self.messages.put(public_only(item))
        self.messages.put({"server_eof": True})

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def receive(self, timeout):
        try:
            item = self.messages.get(timeout=max(0.001, timeout))
        except queue.Empty as exc:
            raise TimeoutError("app-server response deadline") from exc
        if item.get("server_eof"):
            raise RuntimeError("app-server exited; inspect private stderr")
        self.events.append(item)
        if "id" in item and "method" in item:
            # Existing never-approval boundary: no implicit grants or user-input simulation.
            self.send(
                {
                    "id": item["id"],
                    "error": {"code": -32601, "message": "Unsupported client request"},
                }
            )
        return item

    def rpc(self, method, params, timeout=45):
        self.next_id += 1
        rid = self.next_id
        self.send({"id": rid, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            item = self.receive(deadline - time.monotonic())
            if item.get("id") == rid:
                if "error" in item:
                    raise RuntimeError(f"{method}: {item['error']}")
                return item["result"]
            if time.monotonic() >= deadline:
                raise TimeoutError(method)

    def start(self):
        result = self.rpc(
            "thread/start",
            {
                "cwd": CWD,
                "model": self.model,
                "approvalPolicy": "never",
                "permissions": "hermes-task",
                "experimentalRawEvents": False,
            },
        )
        self.thread_id = result["thread"]["id"]
        return result

    def fork(self, thread_id, last_turn_id):
        params = {
            "threadId": thread_id,
            "cwd": CWD,
            "model": self.model,
            "approvalPolicy": "never",
            "permissions": "hermes-task",
        }
        if last_turn_id is not None:
            params["lastTurnId"] = last_turn_id
        result = self.rpc("thread/fork", params)
        self.thread_id = result["thread"]["id"]
        return result

    def resume(self, thread_id):
        result = self.rpc(
            "thread/resume",
            {
                "threadId": thread_id,
                "cwd": CWD,
                "permissions": "hermes-task",
                "approvalPolicy": "never",
            },
        )
        self.thread_id = result["thread"]["id"]
        return result

    def turn(self, message, remaining_seconds):
        if remaining_seconds <= 0:
            raise ValueError("no remaining task budget")
        started = time.monotonic()
        self.active = True
        result = self.rpc(
            "turn/start",
            {
                "threadId": self.thread_id,
                "input": [{"type": "text", "text": message}],
                "effort": "medium",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "segment_status": {
                            "type": "string",
                            "enum": ["CONTINUE", "TASK_COMPLETE"],
                        },
                        "summary": {"type": "string"},
                    },
                    "required": ["segment_status", "summary"],
                    "additionalProperties": False,
                },
            },
            timeout=min(45, remaining_seconds),
        )
        self.last_turn_id = result["turn"]["id"]
        deadline = started + remaining_seconds
        try:
            while True:
                event = self.receive(deadline - time.monotonic())
                if event.get("method") == "turn/completed":
                    turn = event["params"]["turn"]
                    if turn["id"] == self.last_turn_id:
                        self.active = False
                        return turn
                if time.monotonic() >= deadline:
                    raise TimeoutError("task activity budget exhausted")
        finally:
            self.active_seconds += time.monotonic() - started

    def close(self):
        if self.closed:
            return
        self.closed = True
        subprocess.run(
            ["docker", "stop", "--time", "2", self.name],
            capture_output=True,
            timeout=15,
        )
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.reader.join(timeout=2)
        self.stderr.close()
        status = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", self.name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.stopped = status.returncode != 0 or status.stdout.strip() == "false"
        if not self.stopped:
            raise RuntimeError("container still running")
        dump(
            self.output / "session.json",
            {
                "thread_id": self.thread_id,
                "last_turn_id": self.last_turn_id,
                "active_seconds": self.active_seconds,
                "no_running_tool_confirmation": self.stopped,
                "completed_boundary": not self.active,
                "image": self.image,
                "model": self.model,
            },
        )
        # Public typed events only; raw provider items and reasoning events excluded.
        (self.output / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in self.events)
        )

    def __exit__(self, *_):
        self.close()
