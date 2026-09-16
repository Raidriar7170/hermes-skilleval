"""Container transport for the existing CodexCliRunner; no agent loop duplication."""

import hashlib
import json
import subprocess
import os
from pathlib import Path
from hermes_skilleval.live_agent_runtime import CodexCliRunner

IMAGE = "hermes-runtime-utility-executor:v1"


class ContainerRunner(CodexCliRunner):
    scratch_enabled = False

    def _check_output(self, command):
        return subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                IMAGE,
                "codex",
                *command[1:],
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        )

    def _preflight(self, request):
        result = super()._preflight(request)
        result["transport"] = "isolated-linux-container"
        result["executor_image_id"] = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], text=True
        ).strip()
        result["host_codex_binary_not_used_for_execution"] = True
        return result

    def name(self, request):
        return (
            "hermes-utility-" + hashlib.sha256(request.run_id.encode()).hexdigest()[:16]
        )

    def permission_overrides(self, request):
        roots = {
            ":root": "deny",
            ":minimal": "read",
            str(request.workspace_path): "write",
            str(Path(self.config.codex_home_base)): "deny",
            "/usr": "read",
            "/lib": "read",
            "/bin": "read",
            "/etc": "read",
        }
        if self.scratch_enabled:
            roots["/tmp/hermes-debug"] = "write"
        mapping = ", ".join(
            json.dumps(k) + "=" + json.dumps(v) for k, v in roots.items()
        )
        return [
            'default_permissions="hermes-task"',
            "permissions.hermes-task.filesystem={" + mapping + "}",
            "permissions.hermes-task.network.enabled=false",
            'shell_environment_policy.inherit="none"',
            'shell_environment_policy.set={PATH="/usr/local/bin:/usr/bin:/bin"}',
            'web_search="disabled"',
        ]

    def wrap(self, request, command):
        home = Path(self.config.codex_home_base) / request.run_id
        env = self._env(request)
        args = [
            "docker",
            "run",
            "--rm",
            "--name",
            self.name(request),
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=512m",
            "--security-opt",
            "seccomp=" + str(Path(__file__).with_name("docker-seccomp-userns.json")),
            "--memory",
            "4g",
            "--cpus",
            "2",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "-v",
            f"{request.workspace_path}:{request.workspace_path}",
            "-v",
            f"{home}:{home}",
            "-w",
            str(request.workspace_path),
        ]
        if self.scratch_enabled:
            args += [
                "--tmpfs",
                f"/tmp/hermes-debug:rw,nosuid,nodev,size=128m,uid={os.getuid()},gid={os.getgid()}",
            ]
        for key in ("CODEX_HOME", "HOME", "TMPDIR"):
            args += ["-e", key + "=" + env[key]]
        return args + [IMAGE, *command]

    def _command(self, request, preflight):
        command, out = super()._command(request, preflight)
        command[0] = "codex"
        return self.wrap(request, command), out

    def run(self, request, **kwargs):
        try:
            return super().run(request, **kwargs)
        finally:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self.name(request)],
                    capture_output=True,
                    timeout=20,
                )
            except subprocess.SubprocessError:
                (
                    Path(self.config.codex_home_base)
                    / request.run_id
                    / "cleanup-failed.txt"
                ).write_text("Container cleanup failed; inspect " + self.name(request))
