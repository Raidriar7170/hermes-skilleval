"""Focused parent-clock regression checks use no models or task repairs."""

import importlib.util
import json
from pathlib import Path
import sys
import time

SPEC = importlib.util.spec_from_file_location(
    "phase2", Path(__file__).parents[1] / "scripts/native_gap_phase2.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_clock_includes_dispatch_preparation(tmp_path):
    def command(deadline):
        time.sleep(0.05)
        return [sys.executable, "-c", "import time; time.sleep(.05)"]

    result = MODULE.supervise(tmp_path / "attempt", command, 3)
    assert result["elapsed_seconds"] >= 0.1
    assert result["budget_valid"]
    assert result["deadline"] == result["t0"] + 3


def test_prepare_error_preserves_outer_record(tmp_path):
    def command(deadline):
        time.sleep(0.02)
        raise ValueError("invalid binding")

    result = MODULE.supervise(tmp_path / "attempt", command, 3)
    assert result["parent_status"] == "ERROR"
    assert result["elapsed_seconds"] >= 0.02
    assert not result["model_started"]
    assert json.loads((tmp_path / "attempt/result.json").read_text()) == result


def test_deadline_not_reset_after_slow_prepare(tmp_path):
    def command(deadline):
        time.sleep(0.10)
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    result = MODULE.supervise(tmp_path / "attempt", command, 0.2)
    assert result["parent_status"] == "TIMEOUT"
    assert 0.2 <= result["elapsed_seconds"] < 2
    assert not result["budget_valid"]  # never clip real cleanup overrun


def test_cross_process_monotonic_origin(tmp_path):
    child = tmp_path / "child.json"

    def command(deadline):
        return [
            sys.executable,
            "-c",
            f"import json,time; from pathlib import Path; Path({str(child)!r}).write_text(json.dumps(time.monotonic()))",
        ]

    result = MODULE.supervise(tmp_path / "attempt", command, 3)
    assert result["t0"] <= json.loads(child.read_text()) <= result["t1"]


def test_timeout_recovers_durable_activity(tmp_path):
    root = tmp_path / "attempt"

    def command(deadline):
        return [
            sys.executable,
            "-c",
            f'import time,json; from pathlib import Path; p=Path({str(root)!r}); (p/"manifest.json").write_text(json.dumps({{"phase":"agent_started"}})); (p/"public-events-live.json").write_text(json.dumps([{{"params":{{"item":{{"type":"commandExecution"}}}}}}])); time.sleep(10)',
        ]

    result = MODULE.supervise(root, command, 0.2)
    assert result["model_started"] == "UNKNOWN"
    assert result["model_start_requested"]
    assert result["tool_action_observed"]


def test_mmr_tie_stop_and_no_forced_body():
    spec = importlib.util.spec_from_file_location(
        "nav",
        Path(__file__).parents[1] / "scripts/native_gap_phase2_support/navigation.py",
    )
    nav = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nav)
    entries = [
        {"name": n, "description": "Original metadata", "path": f"/skills/{n}/SKILL.md"}
        for n in ["z", "a", "b"]
    ]
    chosen, _ = nav.select_metadata(
        [1.0, 0.0], [[1.0, 0.0], [1.0, 0.0], [-1.0, 0.0]], entries
    )
    assert chosen == [1, 0]
    block = nav.render([entries[i] for i in chosen])
    assert "$" not in block and "Original metadata" in block
    assert nav.select_metadata([0.0, 0.0], [[1.0, 0.0]] * 3, entries)[0] == []


def test_capture_ignores_agent_git_config_and_replaces_partial(tmp_path):
    import shutil
    import subprocess

    root = tmp_path / "attempt"
    source = root / "repo"
    source.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "a.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    base = (
        subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"])
        .decode()
        .strip()
    )
    shutil.copytree(source / ".git", root / "capture-git")
    marker = tmp_path / "unexpected-hook"
    hook = tmp_path / "hook"
    hook.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
    hook.chmod(0o755)
    subprocess.run(
        ["git", "-C", str(source), "config", "core.fsmonitor", str(hook)], check=True
    )
    (source / "a.txt").write_text("changed\n")
    (root / "candidate.patch").write_text("truncated")
    result = MODULE.capture_candidate(root, base)
    assert not marker.exists()
    patch = (root / "candidate.patch").read_text()
    assert "+changed" in patch and "-base" in patch
    assert result["bytes"] == len(patch.encode())


def test_private_oracle_mutation_fails_closed(tmp_path):
    import hashlib
    import pytest

    spec = importlib.util.spec_from_file_location(
        "integrity",
        Path(__file__).parents[1] / "scripts/native_gap_phase2_support/integrity.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.P = tmp_path
    (tmp_path / "trusted-targets").mkdir()
    f = tmp_path / "trusted-targets/task.json"
    f.write_text("frozen oracle")
    freeze = {
        "private_assets": [
            {
                "asset": "trusted-task-task",
                "path": "task.json",
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            }
        ]
    }
    module.verify_private_assets(freeze)
    f.write_text("different oracle")
    with pytest.raises(ValueError, match="frozen private asset changed"):
        module.verify_private_assets(freeze)


def test_old_python_rejected_before_attempt(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(MODULE.sys, "version_info", (3, 9, 0))
    root = tmp_path / "attempt"
    with pytest.raises(RuntimeError, match="Python >=3.11"):
        MODULE.run_descriptor("unread-descriptor.json", root)
    assert not root.exists()
