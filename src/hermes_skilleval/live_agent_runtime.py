from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from hermes_skilleval.release_manifest import sha256_file


TRACE_SCHEMA_VERSION = "live-agent.v1"
SKILL_USE_STATES = {"MOUNTED_ONLY", "READ", "DECLARED", "UNKNOWN"}
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"AKIA[A-Z0-9]{12,}", re.IGNORECASE),
    re.compile(r"BEGIN (?:OPENSSH|RSA|DSA|EC )?PRIVATE KEY", re.IGNORECASE),
    re.compile(r"PRIVATE KEY", re.IGNORECASE),
    re.compile(r"ssh-(?:ed25519|rsa)\s+[A-Za-z0-9+/=._-]+", re.IGNORECASE),
    re.compile(
        r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password)"
        r"\b\s*[:=]\s*[^\s,;\"']+",
        re.IGNORECASE,
    ),
    re.compile(r"bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"
    ),
    re.compile(r"/root(?:/[^\s,;\"']*)?", re.IGNORECASE),
)


@dataclass(frozen=True)
class LiveAgentSkill:
    skill_id: str
    name: str
    body: str


@dataclass(frozen=True)
class AgentCondition:
    task_id: str
    prompt: str
    condition: str
    prompt_hash: str
    mounted_skills: list[LiveAgentSkill]


@dataclass(frozen=True)
class WorkspaceState:
    workspace_path: Path
    skill_dir: Path
    mounted_skills: list[dict[str, Any]]


@dataclass(frozen=True)
class AgentRequest:
    run_id: str
    task_id: str
    prompt: str
    condition: str
    prompt_hash: str
    workspace_path: Path
    mounted_skills: list[dict[str, Any]]
    timeout_seconds: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_condition(
        cls,
        *,
        run_id: str,
        condition: AgentCondition,
        workspace: WorkspaceState,
        timeout_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> "AgentRequest":
        _validate_workspace_matches_condition(condition, workspace)
        return cls(
            run_id=run_id,
            task_id=condition.task_id,
            prompt=condition.prompt,
            condition=condition.condition,
            prompt_hash=condition.prompt_hash,
            workspace_path=workspace.workspace_path,
            mounted_skills=workspace.mounted_skills,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )

    def to_dict(
        self,
        *,
        include_absolute_paths: bool = False,
        redact_secrets: bool = False,
    ) -> dict[str, Any]:
        workspace_path = (
            str(self.workspace_path)
            if include_absolute_paths
            else self.workspace_path.name
        )
        data = {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "prompt": self.prompt,
            "condition": self.condition,
            "prompt_hash": self.prompt_hash,
            "workspace_path": workspace_path,
            "mounted_skills": self.mounted_skills,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }
        if redact_secrets:
            return _redact_value(data)
        return data


@dataclass(frozen=True)
class RunnerOutput:
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    events: list[Any]


@dataclass(frozen=True)
class VerifierResult:
    passed: bool
    details: dict[str, Any]


@runtime_checkable
class AgentRunner(Protocol):
    def run(self, request: AgentRequest) -> RunnerOutput:
        ...


@runtime_checkable
class AgentVerifier(Protocol):
    def verify(self, request: AgentRequest, output: RunnerOutput) -> VerifierResult:
        ...


class FakeAgentRunner:
    def __init__(
        self,
        *,
        exit_code: int | None = 0,
        timed_out: bool = False,
        stdout: str = "",
        stderr: str = "",
        events: list[Any] | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.stdout = stdout
        self.stderr = stderr
        self.events = events or []

    def run(self, request: AgentRequest) -> RunnerOutput:
        return RunnerOutput(
            exit_code=self.exit_code,
            timed_out=self.timed_out,
            stdout=self.stdout,
            stderr=self.stderr,
            events=self.events,
        )


class FakeVerifier:
    def __init__(
        self,
        *,
        pass_: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.pass_ = pass_
        self.details = details or {}

    def verify(self, request: AgentRequest, output: RunnerOutput) -> VerifierResult:
        return VerifierResult(passed=self.pass_, details=self.details)


@dataclass(frozen=True)
class CodexCliRunnerConfig:
    codex_binary: Path | str = "codex"
    codex_home_mode: str = "isolated"
    codex_home_base: Path | str | None = None
    inherited_codex_home: Path | str | None = None
    allow_inherit_for_smoke: bool = False
    sandbox: str = "workspace-write"
    approval_policy: str = "never"
    extra_args: list[str] = field(default_factory=list)
    max_stdout_chars: int = 4000
    max_stderr_chars: int = 4000
    max_event_chars: int = 4000
    terminate_grace_seconds: float = 2.0


class CodexCliRunner:
    REQUIRED_EXEC_FLAGS = (
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "--cd",
        "--output-last-message",
    )
    FORBIDDEN_ARGS = {
        "--yolo",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
    }
    CONTROL_ARGS = {
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "-s",
        "--cd",
        "-C",
        "--output-last-message",
        "-o",
        "--config",
        "-c",
        "--add-dir",
        "--profile",
        "-p",
    }

    def __init__(self, config: CodexCliRunnerConfig | None = None) -> None:
        self.config = config or CodexCliRunnerConfig()

    def run(
        self,
        request: AgentRequest,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> RunnerOutput:
        self._validate_extra_env(extra_env)
        preflight = self._preflight(request)
        command, output_path = self._command(request)
        env = self._env(request, extra_env=extra_env)
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=request.workspace_path,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            stdout_raw, stderr_raw = process.communicate(timeout=request.timeout_seconds)
            stdout, stdout_truncated = _truncate(
                _redact(stdout_raw),
                self.config.max_stdout_chars,
            )
            stderr, stderr_truncated = _truncate(
                _redact(stderr_raw),
                self.config.max_stderr_chars,
            )
            events = [
                preflight,
                *self._parse_jsonl_events(stdout_raw),
                {
                    "type": "codex_process",
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                },
                *self._final_message_event(output_path),
            ]
            return RunnerOutput(
                exit_code=process.returncode,
                timed_out=False,
                stdout=stdout,
                stderr=stderr,
                events=events,
            )
        except subprocess.TimeoutExpired as exc:
            if process is not None:
                stdout_raw, stderr_raw = self._terminate_process_group(process)
            else:
                stdout_raw = _decode_timeout_output(exc.stdout)
                stderr_raw = _decode_timeout_output(exc.stderr)
            stdout, _ = _truncate(
                _redact(stdout_raw),
                self.config.max_stdout_chars,
            )
            stderr, _ = _truncate(
                _redact(stderr_raw),
                self.config.max_stderr_chars,
            )
            return RunnerOutput(
                exit_code=None,
                timed_out=True,
                stdout=stdout,
                stderr=stderr,
                events=[preflight, {"type": "codex_timeout"}],
            )

    def _preflight(self, request: AgentRequest) -> dict[str, Any]:
        self._validate_config(request)
        version = self._check_output((str(self.config.codex_binary), "--version"))
        help_text = self._check_output((str(self.config.codex_binary), "exec", "--help"))
        missing = [flag for flag in self.REQUIRED_EXEC_FLAGS if flag not in help_text]
        if missing:
            raise ValueError(
                "unsupported codex exec flags: " + ", ".join(sorted(missing))
            )
        self._check_global_leakage()
        return {
            "type": "preflight",
            "codex_version": _redact(version.strip()),
            "codex_home_mode": self.config.codex_home_mode,
            "evidence_mode": (
                "smoke-only"
                if self.config.codex_home_mode == "inherit"
                else "final-evidence"
            ),
            "sandbox": self.config.sandbox,
            "approval_policy": self.config.approval_policy,
        }

    def _validate_config(self, request: AgentRequest) -> None:
        if request.condition == "no-skill" and request.mounted_skills:
            raise ValueError("no-skill condition leaked mounted skills")
        if self.config.sandbox == "danger-full-access":
            raise ValueError("danger-full-access is not allowed for live-agent evidence")
        if self.config.sandbox != "workspace-write":
            raise ValueError("CodexCliRunner requires workspace-write sandbox")
        if self.config.approval_policy != "never":
            raise ValueError("CodexCliRunner requires approval policy never")
        if self.config.codex_home_mode not in {"isolated", "inherit"}:
            raise ValueError("codex_home_mode must be isolated or inherit")
        if (
            self.config.codex_home_mode == "inherit"
            and not self.config.allow_inherit_for_smoke
        ):
            raise ValueError("inherited CODEX_HOME is smoke-only")
        for arg in self.config.extra_args:
            if arg in self.CONTROL_ARGS:
                raise ValueError(f"forbidden Codex CLI control argument: {arg}")
            if arg in self.FORBIDDEN_ARGS or "dangerously-bypass" in arg:
                raise ValueError(f"forbidden Codex CLI argument: {arg}")
            if arg == "danger-full-access":
                raise ValueError("danger-full-access is not allowed")

    def _validate_extra_env(self, extra_env: dict[str, str] | None) -> None:
        if extra_env and "CODEX_HOME" in extra_env:
            raise ValueError("extra_env must not override CODEX_HOME")

    def _check_global_leakage(self) -> None:
        if self.config.codex_home_mode != "inherit":
            return
        home = self._inherited_home()
        leakage_names = ("skills", "plugins", "mcp.json", "config.toml")
        leaked = [name for name in leakage_names if (home / name).exists()]
        if leaked:
            raise ValueError("global Codex leakage detected: " + ", ".join(leaked))

    def _command(self, request: AgentRequest) -> tuple[list[str], Path]:
        output_path = request.workspace_path / ".hermes-runner" / "codex-last-message.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.config.codex_binary),
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            self.config.sandbox,
            "--config",
            "approval_policy=\"never\"",
            "--cd",
            str(request.workspace_path),
            "--output-last-message",
            str(output_path),
            *self.config.extra_args,
            "--",
            request.prompt,
        ]
        return command, output_path

    def _env(
        self,
        request: AgentRequest,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        env = os.environ.copy()
        if self.config.codex_home_mode == "isolated":
            base = (
                Path(self.config.codex_home_base)
                if self.config.codex_home_base is not None
                else request.workspace_path / ".codex-home"
            )
            home = base / _safe_path_part(request.run_id)
            home.mkdir(parents=True, exist_ok=True)
            env["CODEX_HOME"] = str(home)
        else:
            env["CODEX_HOME"] = str(self._inherited_home())
        if extra_env:
            env.update(extra_env)
        return env

    def _inherited_home(self) -> Path:
        if self.config.inherited_codex_home is not None:
            return Path(self.config.inherited_codex_home)
        return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))

    def _parse_jsonl_events(self, stdout: str) -> list[dict[str, Any]]:
        events = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                payload, _ = _truncate(_redact(line), self.config.max_event_chars)
                events.append(
                    {
                        "type": "unknown",
                        "original_type": "malformed_jsonl",
                        "payload": payload,
                    }
                )
                continue
            if not isinstance(event, dict):
                payload = self._redact_event_payload(event)
                events.append(
                    {
                        "type": "unknown",
                        "original_type": "non_object_jsonl",
                        "payload": payload,
                    }
                )
                continue
            events.append(self._redact_event_payload(event))
        return events

    def _final_message_event(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        message, _ = _truncate(
            _redact(path.read_text(encoding="utf-8")),
            self.config.max_event_chars,
        )
        return [{"type": "final", "message": message}]

    def _redact_event_payload(self, value: Any) -> Any:
        redacted = _redact_value(value)
        return _truncate_strings(redacted, self.config.max_event_chars)

    def _check_output(self, command: tuple[str, ...]) -> str:
        try:
            return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"Codex CLI preflight failed: {command}") from exc

    def _terminate_process_group(
        self,
        process: subprocess.Popen[str],
    ) -> tuple[str, str]:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return process.communicate()
        try:
            return process.communicate(timeout=self.config.terminate_grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return process.communicate()


@dataclass(frozen=True)
class AgentResult:
    request: AgentRequest
    process_exit_code: int | None
    timed_out: bool
    verifier_passed: bool
    verifier_details: dict[str, Any]
    task_success: bool
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    events: list[dict[str, Any]]
    skill_use: dict[str, dict[str, str]]
    final_message: str | None
    usage: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None

    def to_trace(self) -> dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "request": self.request.to_dict(redact_secrets=True),
            "result": {
                "process_exit_code": self.process_exit_code,
                "timed_out": self.timed_out,
                "verifier": {
                    "passed": self.verifier_passed,
                    "details": _redact_value(self.verifier_details),
                },
                "task_success": self.task_success,
                "usage": self.usage,
                "cost": self.cost,
                "stdout": self.stdout,
                "stderr": self.stderr,
                "stdout_truncated": self.stdout_truncated,
                "stderr_truncated": self.stderr_truncated,
                "final_message": self.final_message,
            },
            "mounted_skills": _redact_value(self.request.mounted_skills),
            "skill_use": _redact_mapping_keys(self.skill_use),
            "events": _redact_value(self.events),
        }


def build_condition(
    *,
    task_id: str,
    prompt: str,
    condition: str,
    routed_skills: list[LiveAgentSkill] | None = None,
    oracle_skills: list[LiveAgentSkill] | None = None,
) -> AgentCondition:
    routed = routed_skills or []
    oracle = oracle_skills or []
    if condition == "no-skill":
        if routed or oracle:
            raise ValueError("no-skill condition must not receive benchmark skills")
        mounted: list[LiveAgentSkill] = []
    elif condition == "routed-skill":
        mounted = routed
    elif condition == "oracle-skill":
        mounted = oracle
    else:
        raise ValueError(f"unsupported live-agent condition: {condition}")
    return AgentCondition(
        task_id=_non_empty(task_id, "task_id"),
        prompt=_non_empty(prompt, "prompt"),
        condition=condition,
        prompt_hash=_sha256_text(prompt),
        mounted_skills=mounted,
    )


def prepare_live_agent_workspace(
    *,
    base_dir: Path | str,
    run_id: str,
    mounted_skills: list[LiveAgentSkill],
) -> WorkspaceState:
    root = Path(base_dir) / _safe_path_part(run_id)
    if root.exists():
        raise ValueError(f"workspace already exists: {root}")
    records = _mounted_skill_records(mounted_skills)
    skill_dir = root / "skills"
    skill_dir.mkdir(parents=True)
    for skill, record in zip(mounted_skills, records, strict=True):
        path = root / record["relative_path"]
        path.write_text(skill.body, encoding="utf-8")
        record["sha256"] = sha256_file(path)
    return WorkspaceState(
        workspace_path=root,
        skill_dir=skill_dir,
        mounted_skills=records,
    )


def _validate_workspace_matches_condition(
    condition: AgentCondition,
    workspace: WorkspaceState,
) -> None:
    condition_skill_ids = [skill.skill_id for skill in condition.mounted_skills]
    workspace_skill_ids = [
        str(record.get("skill_id", ""))
        for record in workspace.mounted_skills
    ]
    if condition_skill_ids != workspace_skill_ids:
        raise ValueError(
            "workspace mounted skill IDs must match condition mounted skill IDs "
            f"in order: condition={condition_skill_ids!r}, "
            f"workspace={workspace_skill_ids!r}"
        )


def _mounted_skill_records(
    mounted_skills: list[LiveAgentSkill],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_skill_ids: set[str] = set()
    seen_relative_paths: set[str] = set()
    for skill in mounted_skills:
        if skill.skill_id in seen_skill_ids:
            raise ValueError(f"duplicate skill_id in mounted skills: {skill.skill_id}")
        seen_skill_ids.add(skill.skill_id)
        relative_path = Path("skills") / _skill_mount_filename(skill)
        relative_path_text = relative_path.as_posix()
        if relative_path_text in seen_relative_paths:
            raise ValueError(f"duplicate mounted skill path: {relative_path_text}")
        seen_relative_paths.add(relative_path_text)
        records.append(
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "relative_path": relative_path_text,
                "sha256": "",
            }
        )
    return records


def execute_live_agent(
    *,
    request: AgentRequest,
    runner: AgentRunner,
    verifier: AgentVerifier,
    max_log_chars: int = 4000,
) -> AgentResult:
    if request.condition == "no-skill" and request.mounted_skills:
        raise ValueError("no-skill condition leaked mounted skills")
    output = runner.run(request)
    events, skill_use, final_message = _parse_events(output.events, request)
    verification = verifier.verify(request, output)
    stdout, stdout_truncated = _truncate(_redact(output.stdout), max_log_chars)
    stderr, stderr_truncated = _truncate(_redact(output.stderr), max_log_chars)
    return AgentResult(
        request=request,
        process_exit_code=output.exit_code,
        timed_out=output.timed_out,
        verifier_passed=verification.passed,
        verifier_details=verification.details,
        task_success=verification.passed,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        events=events,
        skill_use=skill_use,
        final_message=final_message,
        usage=None,
        cost=None,
    )


def _parse_events(
    raw_events: list[Any],
    request: AgentRequest,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], str | None]:
    mounted = {record["skill_id"] for record in request.mounted_skills}
    skill_use = {
        skill_id: {"state": "MOUNTED_ONLY"}
        for skill_id in sorted(mounted)
    }
    events = []
    final_message = None
    for raw in raw_events:
        if not isinstance(raw, dict):
            raise ValueError("malformed event: expected object")
        event_type = raw.get("type")
        if not isinstance(event_type, str):
            raise ValueError("malformed event: missing type")
        if event_type == "skill_read":
            skill_id = _event_skill_id(raw)
            _set_skill_state(skill_use, mounted, skill_id, "READ")
            events.append({"type": "skill_read", "skill_id": skill_id})
        elif event_type == "skill_declared":
            skill_id = _event_skill_id(raw)
            _set_skill_state(skill_use, mounted, skill_id, "DECLARED")
            events.append({"type": "skill_declared", "skill_id": skill_id})
        elif event_type == "final":
            message = _redact(str(raw.get("message", "")))
            final_message = message
            events.append({"type": "final", "message": message})
        else:
            skill_id = raw.get("skill_id")
            if isinstance(skill_id, str) and skill_id.strip():
                _set_skill_state(skill_use, mounted, skill_id, "UNKNOWN")
            events.append(
                {
                    "type": "unknown",
                    "original_type": raw.get("original_type", event_type),
                    "payload": _redact_value(raw),
                }
            )
    return events, skill_use, final_message


def _set_skill_state(
    skill_use: dict[str, dict[str, str]],
    mounted: set[str],
    skill_id: str,
    state: str,
) -> None:
    if state not in SKILL_USE_STATES:
        raise ValueError(f"unsupported skill use state: {state}")
    if skill_id not in mounted:
        skill_use[skill_id] = {"state": "UNKNOWN"}
        return
    current = skill_use[skill_id]["state"]
    if current == "DECLARED":
        return
    skill_use[skill_id] = {"state": state}


def _event_skill_id(event: dict[str, Any]) -> str:
    value = event.get("skill_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("malformed event: skill_id must be non-empty")
    return value


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {
            _redact(str(key)): _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping_keys(value: dict[str, Any]) -> dict[str, Any]:
    return {
        _redact(str(key)): _redact_value(item)
        for key, item in value.items()
    }


def _redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _truncate_strings(value: Any, max_chars: int) -> Any:
    if isinstance(value, str):
        truncated, _ = _truncate(value, max_chars)
        return truncated
    if isinstance(value, dict):
        return {
            _truncate_strings(key, max_chars): _truncate_strings(item, max_chars)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_truncate_strings(item, max_chars) for item in value]
    return value


def _safe_path_part(value: str) -> str:
    text = _non_empty(value, "path part").replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)


def _skill_mount_filename(skill: LiveAgentSkill) -> str:
    base = _safe_path_part(skill.skill_id)
    digest = _sha256_text(skill.skill_id)[:12]
    return f"{base}--{digest}.md"


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
