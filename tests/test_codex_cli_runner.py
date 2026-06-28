import json
import os
import stat
import sys
import textwrap
from pathlib import Path

import jsonschema
import pytest

from hermes_skilleval.live_agent_runtime import (
    AgentRequest,
    CodexCliRunner,
    CodexCliRunnerConfig,
    FakeAgentRunner,
    FakeVerifier,
    LiveAgentSkill,
    build_condition,
    execute_live_agent,
    prepare_live_agent_workspace,
)


def _skill(skill_id: str = "skill/browser") -> LiveAgentSkill:
    return LiveAgentSkill(skill_id=skill_id, name="Browser", body="Skill body")


def _request(tmp_path: Path, *, condition_name: str = "routed-skill") -> AgentRequest:
    skills = [_skill()] if condition_name != "no-skill" else []
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition=condition_name,
        routed_skills=skills,
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id=f"run-{condition_name}",
        mounted_skills=condition.mounted_skills,
    )
    return AgentRequest.from_condition(
        run_id=f"run-{condition_name}",
        condition=condition,
        workspace=workspace,
        timeout_seconds=5,
    )


def _fake_codex(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake-codex.py"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, signal, sys, time\n"
        + textwrap.dedent(body).lstrip(),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _runner(tmp_path: Path, codex: Path, **kwargs) -> CodexCliRunner:
    return CodexCliRunner(
        CodexCliRunnerConfig(
            codex_binary=codex,
            codex_home_base=tmp_path / "codex-home",
            **kwargs,
        )
    )


def test_codex_cli_runner_builds_safe_default_command_and_isolated_home(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message --skip-git-repo-check")
            raise SystemExit(0)
        record = {
            "argv": sys.argv[1:],
            "env": {
                "CODEX_HOME": os.environ.get("CODEX_HOME"),
                "HOME": os.environ.get("HOME"),
            },
        }
        out = os.environ["FAKE_CODEX_RECORD"]
        open(out, "w", encoding="utf-8").write(json.dumps(record))
        output_file = sys.argv[sys.argv.index("--output-last-message") + 1]
        open(output_file, "w", encoding="utf-8").write("done")
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )
    record_path = tmp_path / "record.json"
    request = _request(tmp_path)
    runner = _runner(tmp_path, codex)
    env = {"FAKE_CODEX_RECORD": str(record_path)}

    output = runner.run(request, extra_env=env)
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert output.exit_code == 0
    assert output.timed_out is False
    assert record["argv"][:2] == ["exec", "--json"]
    for flag in [
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(request.workspace_path),
        "--output-last-message",
        "--skip-git-repo-check",
    ]:
        assert flag in record["argv"]
    assert record["env"]["CODEX_HOME"].startswith(str(tmp_path / "codex-home"))
    assert record["env"]["CODEX_HOME"] != os.environ.get("CODEX_HOME")
    assert record["env"]["HOME"].startswith(record["env"]["CODEX_HOME"])
    assert record["env"]["HOME"] != os.environ.get("HOME")
    assert output.events[-1]["type"] == "final"
    assert output.events[-1]["message"] == "done"


def test_codex_cli_runner_rejects_codex_home_extra_env_override(tmp_path):
    codex = _fake_codex(tmp_path, "print('should not run')\n")

    with pytest.raises(ValueError, match="CODEX_HOME"):
        _runner(tmp_path, codex).run(
            _request(tmp_path),
            extra_env={"CODEX_HOME": str(tmp_path / "attacker-home")},
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"sandbox": "danger-full-access"}, "danger-full-access"),
        ({"extra_args": ["--dangerously-bypass-approvals-and-sandbox"]}, "dangerously"),
        ({"extra_args": ["--yolo"]}, "--yolo"),
        ({"extra_args": ["--sandbox", "read-only"]}, "--sandbox"),
        ({"extra_args": ["--cd", "/tmp"]}, "--cd"),
        ({"extra_args": ["--output-last-message", "/tmp/out"]}, "--output-last-message"),
        ({"extra_args": ["--config", "approval_policy=\"on-request\""]}, "--config"),
        ({"extra_args": ["--sandbox=danger-full-access"]}, "--sandbox"),
        ({"extra_args": ["--config=approval_policy=\"on-request\""]}, "--config"),
        ({"extra_args": ["-c=approval_policy=\"on-request\""]}, "-c"),
        ({"extra_args": ["--add-dir=/"]}, "--add-dir"),
        ({"extra_args": ["--yolo=true"]}, "--yolo"),
        ({"extra_args": ["--profile=unsafe"]}, "--profile"),
    ],
)
def test_codex_cli_runner_rejects_unsafe_flags(tmp_path, kwargs, match):
    codex = _fake_codex(tmp_path, "print('should not run')\n")
    runner = _runner(tmp_path, codex, **kwargs)

    with pytest.raises(ValueError, match=match):
        runner.run(_request(tmp_path))


def test_codex_cli_runner_passes_flag_like_prompt_after_delimiter(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        out = os.environ["FAKE_CODEX_RECORD"]
        open(out, "w", encoding="utf-8").write(json.dumps({"argv": sys.argv[1:]}))
        """,
    )
    condition = build_condition(
        task_id="task-1",
        prompt="--yolo --sandbox danger-full-access",
        condition="routed-skill",
        routed_skills=[_skill()],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-flag-prompt",
        mounted_skills=condition.mounted_skills,
    )
    request = AgentRequest.from_condition(
        run_id="run-flag-prompt",
        condition=condition,
        workspace=workspace,
        timeout_seconds=5,
    )
    record = tmp_path / "record.json"

    _runner(tmp_path, codex).run(request, extra_env={"FAKE_CODEX_RECORD": str(record)})
    argv = json.loads(record.read_text(encoding="utf-8"))["argv"]

    assert "--" in argv
    assert argv[-2:] == ["--", "--yolo --sandbox danger-full-access"]


def test_codex_cli_runner_inherit_home_is_smoke_only_metadata(tmp_path, monkeypatch):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )
    inherited_home = tmp_path / "inherited-codex-home"
    inherited_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(inherited_home))

    runner = _runner(tmp_path, codex, codex_home_mode="inherit", allow_inherit_for_smoke=True)
    output = runner.run(_request(tmp_path))

    assert output.events[0]["type"] == "preflight"
    assert output.events[0]["codex_home_mode"] == "inherit"
    assert output.events[0]["evidence_mode"] == "smoke-only"


def test_codex_cli_runner_preflight_rejects_missing_required_flags(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --sandbox")
            raise SystemExit(0)
        raise SystemExit(0)
        """,
    )

    with pytest.raises(ValueError, match="unsupported codex exec flags"):
        _runner(tmp_path, codex).run(_request(tmp_path))


def test_codex_cli_runner_preflight_rejects_global_leakage_in_inherit_mode(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )
    home = tmp_path / "leaky-home"
    (home / "skills").mkdir(parents=True)

    runner = _runner(
        tmp_path,
        codex,
        codex_home_mode="inherit",
        allow_inherit_for_smoke=True,
        inherited_codex_home=home,
    )

    with pytest.raises(ValueError, match="global Codex leakage"):
        runner.run(_request(tmp_path))


def test_codex_cli_runner_isolated_clean_home_passes(tmp_path, monkeypatch):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )
    host_home = tmp_path / "host-home"
    host_home.mkdir()
    monkeypatch.setenv("HOME", str(host_home))

    output = _runner(tmp_path, codex).run(_request(tmp_path))

    inventory = output.events[0]["global_capability_inventory"]
    assert inventory["home_isolated"] is True
    assert inventory["user_skill_dir"]["status"] == "ISOLATED_HOME"


def test_codex_cli_runner_rejects_user_home_skill_leakage_when_not_isolating_home(
    tmp_path,
    monkeypatch,
):
    codex = _fake_codex(tmp_path, "print('should not run')\n")
    host_home = tmp_path / "host-home"
    (host_home / ".agents" / "skills" / "global").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(host_home))

    with pytest.raises(ValueError, match="user skill leakage"):
        _runner(tmp_path, codex, isolate_home=False).run(_request(tmp_path))


def test_codex_cli_runner_rejects_admin_skill_leakage(tmp_path):
    codex = _fake_codex(tmp_path, "print('should not run')\n")
    admin_skills = tmp_path / "etc-codex-skills"
    (admin_skills / "admin").mkdir(parents=True)

    with pytest.raises(ValueError, match="admin skill leakage"):
        _runner(tmp_path, codex, admin_skill_paths=[admin_skills]).run(_request(tmp_path))


def test_codex_cli_runner_rejects_preexisting_parent_repo_skills(tmp_path):
    codex = _fake_codex(tmp_path, "print('should not run')\n")
    repo = tmp_path / "repo"
    (repo / ".agents" / "skills" / "global").mkdir(parents=True)
    request = _request(repo / "workspaces")

    with pytest.raises(ValueError, match="workspace parent skill leakage"):
        _runner(tmp_path, codex).run(request)


def test_codex_cli_runner_rejects_no_skill_leakage_before_subprocess(tmp_path):
    codex = _fake_codex(tmp_path, "raise SystemExit('should not run')\n")
    request = AgentRequest(
        run_id="run-leak",
        task_id="task-1",
        prompt="Do it",
        condition="no-skill",
        prompt_hash="hash",
        workspace_path=tmp_path / "workspace",
        mounted_skills=[{"skill_id": "skill/leaked"}],
        timeout_seconds=5,
    )

    with pytest.raises(ValueError, match="no-skill"):
        _runner(tmp_path, codex).run(request)


def test_codex_cli_runner_timeout_kills_process_group(tmp_path):
    marker = tmp_path / "terminated.txt"
    codex = _fake_codex(
        tmp_path,
        f"""
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        def handler(signum, frame):
            open({str(marker)!r}, "w", encoding="utf-8").write(str(signum))
            raise SystemExit(124)
        signal.signal(signal.SIGTERM, handler)
        time.sleep(10)
        """,
    )
    request = _request(tmp_path)
    request = AgentRequest(
        **{**request.to_dict(include_absolute_paths=True), "workspace_path": request.workspace_path},
    )
    object.__setattr__(request, "timeout_seconds", 1)

    output = _runner(tmp_path, codex).run(request)

    assert output.exit_code is None
    assert output.timed_out is True
    assert marker.exists()


def test_codex_cli_runner_timeout_kill_fallback_for_ignored_sigterm(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(10)
        """,
    )
    request = _request(tmp_path)
    object.__setattr__(request, "timeout_seconds", 1)

    output = _runner(tmp_path, codex).run(request)

    assert output.exit_code is None
    assert output.timed_out is True


def test_codex_cli_runner_nonzero_exit_does_not_define_task_success(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "final", "message": "done"}))
        raise SystemExit(7)
        """,
    )

    result = execute_live_agent(
        request=_request(tmp_path),
        runner=_runner(tmp_path, codex),
        verifier=FakeVerifier(pass_=False),
    )

    assert result.process_exit_code == 7
    assert result.verifier_passed is False
    assert result.task_success is False


def test_codex_cli_runner_parses_jsonl_unknown_malformed_and_skill_events(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "skill_read", "skill_id": "skill/browser"}))
        print("{not-json")
        print(json.dumps({"type": "future_event", "skill_id": "skill/unknown", "token": "sk-secret123456"}))
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )

    result = execute_live_agent(
        request=_request(tmp_path),
        runner=_runner(tmp_path, codex),
        verifier=FakeVerifier(pass_=False),
    )
    trace = result.to_trace()
    serialized = json.dumps(trace)

    assert result.process_exit_code == 0
    assert result.verifier_passed is False
    assert result.task_success is False
    assert trace["skill_use"]["skill/browser"]["state"] == "READ"
    assert any(event["type"] == "unknown" for event in trace["events"])
    assert any(event.get("original_type") == "malformed_jsonl" for event in trace["events"])
    assert "sk-secret123456" not in serialized


def test_codex_cli_runner_redacts_and_truncates_stdout_stderr(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print("token=SECRET123 " + ("x" * 200))
        print("api_key=ERRSECRET", file=sys.stderr)
        """,
    )

    output = _runner(tmp_path, codex, max_stdout_chars=40, max_stderr_chars=40).run(
        _request(tmp_path)
    )

    assert "SECRET123" not in output.stdout
    assert "ERRSECRET" not in output.stderr
    assert len(output.stdout) <= 40
    assert len(output.stderr) <= 40


def test_codex_cli_runner_redacts_runner_events_and_final_message(tmp_path):
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        output_file = sys.argv[sys.argv.index("--output-last-message") + 1]
        open(output_file, "w", encoding="utf-8").write("token=FINALSECRET " + ("z" * 200))
        print(json.dumps({"type": "future_event", "payload": "api_key=EVENTSECRET " + ("x" * 200)}))
        """,
    )

    output = _runner(tmp_path, codex, max_event_chars=50).run(_request(tmp_path))
    serialized = json.dumps(output.events)

    assert "FINALSECRET" not in serialized
    assert "EVENTSECRET" not in serialized
    assert len(output.events[-1]["message"]) <= 50
    assert len(output.events[1]["payload"]) <= 50


def test_live_agent_trace_schema_validates_fake_and_codex_traces(tmp_path):
    schema = json.loads(
        Path("schemas/live-agent-trace.schema.json").read_text(encoding="utf-8")
    )
    codex = _fake_codex(
        tmp_path,
        """
        if sys.argv[1:] == ["--version"]:
            print("codex 1.2.3")
            raise SystemExit(0)
        if sys.argv[1:3] == ["exec", "--help"]:
            print("--json --ephemeral --ignore-user-config --ignore-rules --sandbox --cd --output-last-message")
            raise SystemExit(0)
        print(json.dumps({"type": "final", "message": "done"}))
        """,
    )

    codex_trace = execute_live_agent(
        request=_request(tmp_path),
        runner=_runner(tmp_path, codex),
        verifier=FakeVerifier(pass_=True),
    ).to_trace()
    jsonschema.validate(codex_trace, schema)

    fake_trace = execute_live_agent(
        request=_request(tmp_path / "fake", condition_name="routed-skill"),
        runner=FakeAgentRunner(events=[{"type": "final", "message": "done"}]),
        verifier=FakeVerifier(pass_=True),
    ).to_trace()
    jsonschema.validate(fake_trace, schema)


def test_live_agent_trace_schema_rejects_malformed_skill_state(tmp_path):
    schema = json.loads(
        Path("schemas/live-agent-trace.schema.json").read_text(encoding="utf-8")
    )
    trace = execute_live_agent(
        request=_request(tmp_path),
        runner=FakeAgentRunner(events=[{"type": "final", "message": "done"}]),
        verifier=FakeVerifier(pass_=True),
    ).to_trace()
    trace["skill_use"]["skill/browser"]["state"] = "USED_MAYBE"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(trace, schema)
