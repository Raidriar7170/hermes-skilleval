import json
from pathlib import Path

import pytest

from hermes_skilleval.live_agent_runtime import (
    AgentRequest,
    AgentRunner,
    AgentVerifier,
    FakeAgentRunner,
    FakeVerifier,
    LiveAgentSkill,
    build_condition,
    execute_live_agent,
    prepare_live_agent_workspace,
)


def _skill(skill_id: str = "skill/browser-login") -> LiveAgentSkill:
    return LiveAgentSkill(
        skill_id=skill_id,
        name="Browser Login",
        body="Use browser automation. token=SECRET123",
    )


def test_live_agent_request_and_result_serialize_schema(tmp_path):
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill()],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-1",
        mounted_skills=condition.mounted_skills,
    )
    request = AgentRequest(
        run_id="run-1",
        task_id="task-1",
        prompt=condition.prompt,
        condition=condition.condition,
        prompt_hash=condition.prompt_hash,
        workspace_path=workspace.workspace_path,
        mounted_skills=workspace.mounted_skills,
        timeout_seconds=30,
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(events=[{"type": "final", "message": "done"}]),
        verifier=FakeVerifier(pass_=True, details={"checked": True}),
    )
    trace = result.to_trace()

    assert isinstance(FakeAgentRunner(), AgentRunner)
    assert isinstance(FakeVerifier(pass_=True), AgentVerifier)
    assert trace["schema_version"] == "live-agent.v1"
    assert trace["request"]["task_id"] == "task-1"
    assert trace["result"]["process_exit_code"] == 0
    assert trace["result"]["verifier"]["passed"] is True
    assert trace["result"]["task_success"] is True
    assert trace["result"]["usage"] is None
    assert trace["result"]["cost"] is None
    json.dumps(trace)


def test_condition_builders_preserve_prompt_hash_and_skill_injection():
    prompt = "Complete the same task."
    no_skill = build_condition(task_id="t", prompt=prompt, condition="no-skill")
    routed = build_condition(
        task_id="t",
        prompt=prompt,
        condition="routed-skill",
        routed_skills=[_skill("skill/routed")],
    )
    oracle = build_condition(
        task_id="t",
        prompt=prompt,
        condition="oracle-skill",
        oracle_skills=[_skill("skill/oracle")],
    )

    assert no_skill.prompt_hash == routed.prompt_hash == oracle.prompt_hash
    assert no_skill.mounted_skills == []
    assert [skill.skill_id for skill in routed.mounted_skills] == ["skill/routed"]
    assert [skill.skill_id for skill in oracle.mounted_skills] == ["skill/oracle"]


def test_no_skill_condition_rejects_skill_leakage():
    with pytest.raises(ValueError, match="no-skill"):
        build_condition(
            task_id="t",
            prompt="Do it",
            condition="no-skill",
            routed_skills=[_skill()],
        )


def test_routed_condition_rejects_oracle_workspace(tmp_path):
    routed = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill("skill/routed")],
    )
    oracle = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="oracle-skill",
        oracle_skills=[_skill("skill/oracle")],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-routed-oracle-mismatch",
        mounted_skills=oracle.mounted_skills,
    )

    with pytest.raises(ValueError, match="mounted skill IDs"):
        AgentRequest.from_condition(
            run_id="run-routed-oracle-mismatch",
            condition=routed,
            workspace=workspace,
            timeout_seconds=10,
        )


def test_oracle_condition_rejects_routed_workspace(tmp_path):
    routed = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill("skill/routed")],
    )
    oracle = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="oracle-skill",
        oracle_skills=[_skill("skill/oracle")],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-oracle-routed-mismatch",
        mounted_skills=routed.mounted_skills,
    )

    with pytest.raises(ValueError, match="mounted skill IDs"):
        AgentRequest.from_condition(
            run_id="run-oracle-routed-mismatch",
            condition=oracle,
            workspace=workspace,
            timeout_seconds=10,
        )


def test_no_skill_condition_rejects_non_empty_workspace_before_execution(tmp_path):
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="no-skill",
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-no-skill-workspace-leak",
        mounted_skills=[_skill("skill/leaked")],
    )

    with pytest.raises(ValueError, match="mounted skill IDs"):
        AgentRequest.from_condition(
            run_id="run-no-skill-workspace-leak",
            condition=condition,
            workspace=workspace,
            timeout_seconds=10,
        )


def test_matching_condition_workspace_builds_and_executes(tmp_path):
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill("skill/a"), _skill("skill/b")],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-match",
        mounted_skills=condition.mounted_skills,
    )

    request = AgentRequest.from_condition(
        run_id="run-match",
        condition=condition,
        workspace=workspace,
        timeout_seconds=10,
    )
    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(events=[{"type": "final", "message": "ok"}]),
        verifier=FakeVerifier(pass_=True),
    )

    assert [record["skill_id"] for record in request.mounted_skills] == [
        "skill/a",
        "skill/b",
    ]
    assert result.task_success is True
    assert condition.prompt_hash == request.prompt_hash


def test_workspace_preparation_mounts_skills_and_rejects_reuse(tmp_path):
    skill = _skill()
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-1",
        mounted_skills=[skill],
    )

    assert workspace.workspace_path.exists()
    assert workspace.skill_dir.exists()
    mounted = workspace.mounted_skills[0]
    assert mounted["skill_id"] == "skill/browser-login"
    assert mounted["sha256"]
    assert (workspace.workspace_path / mounted["relative_path"]).read_text(
        encoding="utf-8"
    ) == skill.body

    with pytest.raises(ValueError, match="already exists"):
        prepare_live_agent_workspace(
            base_dir=tmp_path,
            run_id="run-1",
            mounted_skills=[skill],
        )


def test_workspace_mount_filenames_are_collision_resistant(tmp_path):
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-collision",
        mounted_skills=[
            _skill("skill/a"),
            _skill("skill_a"),
        ],
    )

    paths = [record["relative_path"] for record in workspace.mounted_skills]
    assert len(paths) == len(set(paths))
    assert all((workspace.workspace_path / path).is_file() for path in paths)

    with pytest.raises(ValueError, match="duplicate skill_id"):
        prepare_live_agent_workspace(
            base_dir=tmp_path,
            run_id="run-duplicate",
            mounted_skills=[_skill("skill/a"), _skill("skill/a")],
        )
    assert not (tmp_path / "run-duplicate").exists()


def test_fake_runner_separates_process_exit_from_verifier_result(tmp_path):
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill()],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-2",
        mounted_skills=condition.mounted_skills,
    )
    request = AgentRequest.from_condition(
        run_id="run-2",
        condition=condition,
        workspace=workspace,
        timeout_seconds=10,
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(exit_code=0, events=[{"type": "final", "message": "ok"}]),
        verifier=FakeVerifier(pass_=False, details={"reason": "wrong output"}),
    )

    assert result.process_exit_code == 0
    assert result.verifier_passed is False
    assert result.task_success is False


def test_fake_runner_process_failure_is_not_verifier_failure(tmp_path):
    request = _request(tmp_path, run_id="run-process-fail")

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(exit_code=7, stderr="process failed"),
        verifier=FakeVerifier(pass_=True),
    )

    assert result.process_exit_code == 7
    assert result.verifier_passed is True
    assert result.task_success is True
    assert result.stderr == "process failed"


def test_fake_runner_timeout_records_process_state(tmp_path):
    request = _request(tmp_path, run_id="run-timeout")

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(timed_out=True, exit_code=None),
        verifier=FakeVerifier(pass_=False),
    )

    assert result.timed_out is True
    assert result.process_exit_code is None
    assert result.task_success is False


def test_skill_use_evidence_tracks_mounted_read_declared_and_unknown(tmp_path):
    skill = _skill("skill/a")
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[skill, _skill("skill/b"), _skill("skill/c")],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-evidence",
        mounted_skills=condition.mounted_skills,
    )
    request = AgentRequest.from_condition(
        run_id="run-evidence",
        condition=condition,
        workspace=workspace,
        timeout_seconds=10,
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(
            events=[
                {"type": "skill_read", "skill_id": "skill/a"},
                {"type": "skill_declared", "skill_id": "skill/b"},
                {"type": "skill_read", "skill_id": "skill/not-mounted"},
            ]
        ),
        verifier=FakeVerifier(pass_=True),
    )

    assert result.skill_use["skill/a"]["state"] == "READ"
    assert result.skill_use["skill/b"]["state"] == "DECLARED"
    assert result.skill_use["skill/c"]["state"] == "MOUNTED_ONLY"
    assert result.skill_use["skill/not-mounted"]["state"] == "UNKNOWN"


def test_malformed_event_fails_closed(tmp_path):
    request = _request(tmp_path, run_id="run-malformed")

    with pytest.raises(ValueError, match="malformed event"):
        execute_live_agent(
            request=request,
            runner=FakeAgentRunner(events=["not-an-object"]),
            verifier=FakeVerifier(pass_=True),
        )


def test_unknown_events_are_preserved_without_crashing(tmp_path):
    request = _request(tmp_path, run_id="run-unknown")

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(events=[{"type": "future_event", "payload": "x"}]),
        verifier=FakeVerifier(pass_=True),
    )

    assert result.events[0]["type"] == "unknown"
    assert result.events[0]["original_type"] == "future_event"


def test_secret_redaction_and_log_truncation(tmp_path):
    request = _request(
        tmp_path,
        run_id="run-redact",
        prompt="Do the task with token=PROMPTSECRET",
        metadata={"note": "password=METASECRET"},
    )
    secret_text = "token=SECRET123 password=hunter2 " + ("x" * 200)

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(
            stdout=secret_text,
            stderr="api_key=abc123",
            events=[{"type": "final", "message": secret_text}],
        ),
        verifier=FakeVerifier(pass_=True, details={"note": "api_key=VERIFYSECRET"}),
        max_log_chars=80,
    )
    trace = result.to_trace()
    serialized = json.dumps(trace)

    assert "SECRET123" not in serialized
    assert "hunter2" not in serialized
    assert "abc123" not in serialized
    assert "PROMPTSECRET" not in serialized
    assert "METASECRET" not in serialized
    assert "VERIFYSECRET" not in serialized
    assert str(tmp_path) not in serialized
    assert "[REDACTED]" in serialized
    assert trace["result"]["stdout_truncated"] is True
    assert len(trace["result"]["stdout"]) <= 80


def test_release_sensitive_patterns_are_redacted_from_trace(tmp_path):
    request = _request(
        tmp_path,
        run_id="run-sensitive",
        prompt=(
            "Bearer bearer-secret sk-1234567890abcdef "
            "BEGIN OPENSSH PRIVATE KEY /root/private-cache 10.0.0.1"
        ),
        metadata={
            "aws": "AKIA1234567890ABCDEF",
            "ssh": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIexample",
        },
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(
            stdout="access_token: value-123 auth-token=secret-value",
            stderr="PRIVATE KEY 192.168.0.10",
            events=[
                {"type": "final", "message": "api-key=secret 172.16.0.5"},
                {
                    "type": "future_event",
                    "payload": "Bearer event-secret /root/event-cache",
                },
            ],
        ),
        verifier=FakeVerifier(
            pass_=True,
            details={"path": "/root/verifier", "secret": "sk-verifier123456"},
        ),
    )

    serialized = json.dumps(result.to_trace())
    for leaked in [
        "bearer-secret",
        "sk-1234567890abcdef",
        "PRIVATE KEY",
        "/root/private-cache",
        "10.0.0.1",
        "AKIA1234567890ABCDEF",
        "ssh-ed25519",
        "value-123",
        "secret-value",
        "192.168.0.10",
        "172.16.0.5",
        "event-secret",
        "/root/verifier",
        "sk-verifier123456",
    ]:
        assert leaked not in serialized
    assert serialized.count("[REDACTED]") >= 8


def test_sensitive_skill_ids_are_redacted_from_trace_events_and_skill_use(tmp_path):
    skill_id = "sk-1234567890abcdef"
    condition = build_condition(
        task_id="task-1",
        prompt="Do the task",
        condition="routed-skill",
        routed_skills=[_skill(skill_id)],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id="run-sensitive-skill-id",
        mounted_skills=condition.mounted_skills,
    )
    request = AgentRequest.from_condition(
        run_id="run-sensitive-skill-id",
        condition=condition,
        workspace=workspace,
        timeout_seconds=10,
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(
            events=[
                {"type": "skill_read", "skill_id": skill_id},
                {"type": "skill_declared", "skill_id": "Bearer leaked-token"},
            ]
        ),
        verifier=FakeVerifier(pass_=True),
    )

    serialized = json.dumps(result.to_trace())
    assert skill_id not in serialized
    assert "leaked-token" not in serialized
    assert "[REDACTED]" in serialized


def test_secret_like_dict_keys_are_recursively_redacted_from_trace(tmp_path):
    request = _request(
        tmp_path,
        run_id="run-secret-keys",
        metadata={
            "sk-1234567890abcdef": "metadata-key",
            "nested": {"password=SECRET": "nested-key"},
        },
    )

    result = execute_live_agent(
        request=request,
        runner=FakeAgentRunner(
            events=[
                {
                    "type": "future_event",
                    "Bearer leaked-token": {
                        "password=SECRET": "event-key",
                    },
                }
            ]
        ),
        verifier=FakeVerifier(
            pass_=True,
            details={
                "api_key=VERIFYSECRET": "verifier-key",
                "nested": {"password=SECRET": "verifier-nested-key"},
            },
        ),
    )

    serialized = json.dumps(result.to_trace())
    for leaked in [
        "sk-1234567890abcdef",
        "api_key=VERIFYSECRET",
        "Bearer leaked-token",
        "password=SECRET",
    ]:
        assert leaked not in serialized
    assert "[REDACTED]" in serialized


def _request(
    tmp_path: Path,
    *,
    run_id: str,
    prompt: str = "Do the task",
    metadata: dict[str, str] | None = None,
) -> AgentRequest:
    condition = build_condition(
        task_id="task-1",
        prompt=prompt,
        condition="routed-skill",
        routed_skills=[_skill()],
    )
    workspace = prepare_live_agent_workspace(
        base_dir=tmp_path,
        run_id=run_id,
        mounted_skills=condition.mounted_skills,
    )
    return AgentRequest.from_condition(
        run_id=run_id,
        condition=condition,
        workspace=workspace,
        timeout_seconds=10,
        metadata=metadata,
    )
