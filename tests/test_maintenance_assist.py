"""No-model contract tests. Mocked transport here is not real smoke evidence."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from hermes_skilleval._maintenance import assist
from hermes_skilleval._maintenance.assist_snapshot import inspect_source, snapshot
from hermes_skilleval._maintenance.assist_checks import paired_results, parse_checks
from hermes_skilleval.repository_profile import SQLITE_UTILS
from hermes_skilleval.repository_maintenance import capture


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE
    )


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "source repo"
    root.mkdir()
    (root / "sqlite_utils").mkdir()
    (root / "sqlite_utils/__init__.py").write_text("value = 1\n")
    (root / "keep.txt").write_text("original\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "-qm",
        "base",
    )
    return root


def test_dirty_snapshot_and_agent_commit_only_capture_new_delta(repo, tmp_path):
    source = repo / "sqlite_utils/__init__.py"
    source.write_text("value = 2\n")
    git(repo, "add", ".")
    source.write_text("value = 3\n")
    (repo / "new input.txt").write_text("explicit input")
    (repo / "not included.txt").write_text("not copied")
    state = inspect_source(repo, ["new input.txt"])
    base = tmp_path / "snapshot"
    snapshot(repo, base, state, ["new input.txt"])
    assert not (base / ".git").exists()
    assert not (base / "not included.txt").exists()
    work = tmp_path / "work"
    shutil.copytree(base, work)
    git(work, "init", "-q")
    (work / "sqlite_utils/__init__.py").write_text("value = 4\n")
    (work / "keep.txt").unlink()
    git(work, "add", ".")
    git(
        work,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "-qm",
        "agent commit",
    )
    (work / "sqlite_utils/new.py").write_text("new = True\n")
    cap = capture(base, work, tmp_path / "captured", strict=True)
    patch = (tmp_path / "captured/candidate.patch").read_text()
    assert "-value = 3" in patch and "+value = 4" in patch
    assert "-value = 1" not in patch
    assert cap["changed_files"] == [
        "keep.txt",
        "sqlite_utils/__init__.py",
        "sqlite_utils/new.py",
    ]
    assert inspect_source(repo, ["new input.txt"]) == state


def test_snapshot_rejects_unmerged_sensitive_and_symlink_inputs(repo, tmp_path):
    (repo / "sqlite_utils/link.py").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        inspect_source(repo, ["sqlite_utils/link.py"])
    (repo / "sqlite_utils/link.py").unlink()
    (repo / "secret.txt").write_text("-----BEGIN OPENSSH PRIVATE KEY-----")
    with pytest.raises(ValueError, match="sensitive"):
        inspect_source(repo, ["secret.txt"])


def test_snapshot_detects_content_change_without_git_status_change(repo, tmp_path):
    file = repo / "keep.txt"
    file.write_text("dirty first")
    state = inspect_source(repo)
    file.write_text("dirty second")
    with pytest.raises(ValueError, match="source changed"):
        snapshot(repo, tmp_path / "snap", state)


def config():
    return {
        "version": "assist-checks-v1",
        "requirements": [
            {"id": "r1", "description": "new behavior"},
            {"id": "r2", "description": "uncovered"},
        ],
        "checks": [{"id": "check", "kind": "requirement", "requirements": ["r1"]}],
    }


def result(outcomes, valid=True):
    return {
        "valid": valid,
        "passed": valid and all(v == "passed" for v in outcomes.values()),
        "cases": [{"id": k, "outcome": v} for k, v in outcomes.items()],
    }


def test_paired_existing_vs_new_failures_and_unknown_requirements():
    paired = paired_results(
        config(),
        {"check": result({"a": "failed", "b": "passed"})},
        {"check": result({"a": "failed", "b": "failed"})},
    )
    assert paired["checks"]["check"]["pre_existing_failures"] == ["a"]
    assert paired["checks"]["check"]["new_failures"] == ["b"]
    assert paired["requirements"]["r1"]["status"] == "CHECKED_FAIL"
    assert paired["requirements"]["r2"]["status"] == "NOT_VERIFIED"
    assert paired["resolved"] is None


@pytest.mark.parametrize(
    "candidate",
    [
        result({}),
        result({"a": "skipped"}, False),
        result({"a": "error"}, False),
        {"valid": False, "error": "timeout"},
        {"valid": False, "error": "candidate import missing"},
    ],
)
def test_missing_empty_skipped_error_timeout_never_certify(candidate):
    paired = paired_results(
        config(), {"check": result({"a": "passed"})}, {"check": candidate}
    )
    assert paired["requirements"]["r1"]["status"] == "NOT_VERIFIED"
    assert paired["resolved"] is None


def test_check_configuration_rejects_shell_and_ignored_overrides(tmp_path):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    (trusted / "test_req.py").write_text("def test_req(): pass")
    (trusted / "pytest.ini").write_text("[pytest]\n")
    cfg = config()
    cfg["checks"][0].update(
        trusted_dir="trusted",
        argv=["python", "-m", "pytest", "test_req.py", "-k", "req"],
        cwd="/tmp",
        env={},
        timeout=12,
    )
    path = tmp_path / "checks.json"
    for field, bad in [
        ("argv", "pytest test_req.py; echo hacked"),
        ("env", {"PYTHONPATH": "/input"}),
        ("cwd", "/input"),
        ("timeout", 0),
    ]:
        new = json.loads(json.dumps(cfg))
        new["checks"][0][field] = bad
        path.write_text(json.dumps(new))
        with pytest.raises(ValueError):
            parse_checks(path)
    path.write_text(json.dumps(cfg))
    assert parse_checks(path)["checks"][0]["timeout"] == 12


@pytest.mark.parametrize(
    "timed_out,violate,started",
    [
        (False, False, True),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
def test_assist_contract_with_explicit_mock_transport(
    repo, tmp_path, monkeypatch, timed_out, violate, started
):
    profile = replace(
        SQLITE_UTILS,
        file_policy={
            "version": "operations-v1",
            "rules": [{"path": "sqlite_utils", "operations": ["add", "modify"]}],
        },
    )
    request = tmp_path / "request.md"
    request.write_text("Developer-defined unit fixture")
    args = argparse.Namespace(
        repo=repo,
        request=request,
        output=tmp_path / "result",
        plan_only=False,
        skill_assets=tmp_path,
        arm="N",
        timeout=12,
        model="unit-test-only",
        effort="medium",
    )
    cfg = {
        "version": "assist-checks-v1",
        "requirements": [{"id": "r", "description": "unknown"}],
        "checks": [],
    }
    state = inspect_source(repo)
    monkeypatch.setattr(
        assist,
        "preflight",
        lambda _: (
            {"missing": [], "source": state, "checks": cfg, "selected_ids": []},
            profile,
            {},
            {},
        ),
    )
    real_run = subprocess.run

    def canary(cmd, **kwargs):
        if "hermes_skilleval._maintenance.canary" in cmd:
            Path(cmd[cmd.index("--output") + 1]).write_text('{"passed": true}')
            return subprocess.CompletedProcess(cmd, 0)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(assist.subprocess, "run", canary)

    def agent(**kwargs):
        work = kwargs["workspace_root"]
        shutil.copytree(kwargs["base"], work, dirs_exist_ok=True)
        (work / ("forbidden.txt" if violate else "sqlite_utils/new.py")).write_text(
            "value = 2\n"
        )
        return {
            "workspace": str(work),
            "cleanup_confirmed": True,
            "exit_code": None if timed_out else 0,
            "timed_out": timed_out,
            "usage": None,
            "execution_status": "STARTED" if started else "NOT_STARTED",
        }

    monkeypatch.setattr(assist, "run_agent", agent)
    output, code = assist.execute(args)
    assert output["source_unchanged"] is True
    assert output["resolved"] is None
    assert output["requirements"]["r"]["status"] == "NOT_VERIFIED"
    assert (args.output / "capture/candidate.patch").stat().st_size > 0
    assert output["usage"] is None
    assert code == (2 if timed_out or violate or not started else 0)
    if violate:
        assert output["policy_status"] == "REJECTED_NOT_FUNCTIONALLY_VERIFIED"
    else:
        assert output["rebuild"] == "MATCHED_CAPTURE"


def test_source_git_disables_repository_fsmonitor_hook(repo, tmp_path):
    marker = tmp_path / "hook-executed"
    git(repo, "config", "core.fsmonitor", "touch " + str(marker))
    inspect_source(repo)
    assert not marker.exists()


@pytest.mark.parametrize(
    "failure", [subprocess.TimeoutExpired(["docker"], 30), KeyboardInterrupt()]
)
def test_preflight_probe_cleanup_on_timeout_or_cancel(monkeypatch, failure):
    from hermes_skilleval._maintenance import check as checker

    names = []

    def fail(command, **kwargs):
        names.append(command[command.index("--name") + 1])
        raise failure

    stopped = []
    monkeypatch.setattr(assist.subprocess, "check_output", fail)
    monkeypatch.setattr(checker, "stopped", stopped.append)
    with pytest.raises(type(failure)):
        assist.resource_probe("image", ["codex", "--help"])
    assert stopped == names and names[0].startswith("hermes-assist-preflight-")
