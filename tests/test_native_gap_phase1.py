"""Regression checks for the Phase 1 evidence and isolation boundary."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


MODULE = Path(__file__).parents[1] / "scripts/native_gap_phase1.py"
spec = importlib.util.spec_from_file_location("native_gap_phase1_tests", MODULE)
assert spec is not None and spec.loader is not None
native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)


def test_nested_terminal_reasoning_is_removed():
    event = {
        "method": "turn/completed",
        "params": {
            "turn": {
                "items": [
                    {"type": "reasoning", "summary": ["private"]},
                    {"type": "agentMessage", "text": "public"},
                ]
            }
        },
    }
    clean = native.public_only(event)
    assert "private" not in json.dumps(clean)
    assert clean["params"]["turn"]["items"] == [
        {"type": "agentMessage", "text": "public"}
    ]


def test_base_export_excludes_future_objects(tmp_path, monkeypatch):
    upstream = tmp_path / "upstream"
    upstream.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(upstream), *args])

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Fixture")
    (upstream / "source.py").write_text("value = 1\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD").decode().strip()
    archive, commit = git("archive", base), git("cat-file", "commit", base)
    (upstream / "hidden-answer").write_text("future reference")
    git("add", ".")
    git("commit", "-qm", "future")
    future = git("rev-parse", "HEAD").decode().strip()
    real = subprocess.check_output

    def export(command, **kwargs):
        if command[0] == "docker":
            return archive if "archive" in command else commit
        return real(command, **kwargs)

    monkeypatch.setattr(native.subprocess, "check_output", export)
    target = tmp_path / "agent"
    native.fresh_base("fixture-image", base, target)
    assert not (target / "hidden-answer").exists()
    assert (
        real(["git", "-C", str(target), "rev-parse", "HEAD"]).decode().strip() == base
    )
    assert (
        subprocess.run(
            ["git", "-C", str(target), "cat-file", "-e", future], capture_output=True
        ).returncode
        != 0
    )


def test_preparation_failure_still_records_attempt(tmp_path, monkeypatch):
    def fail(*args):
        raise TimeoutError("export exceeded remaining budget")

    monkeypatch.setattr(native, "fresh_base", fail)
    result = native.native_smoke(
        tmp_path,
        "attempt",
        {"base_commit": "base"},
        tmp_path / "skills",
        "image",
        tmp_path / "bin",
        tmp_path / "seccomp",
    )
    saved = json.loads((tmp_path / "attempt/result.json").read_text())
    assert saved["terminal"] == result["terminal"] == "ERROR"
    assert saved["phase"] == "preparing"
    assert "thread_id" not in saved
    assert saved["candidate_capture_status"] == "UNAVAILABLE"
    assert saved["elapsed_seconds"] >= 0


def test_implicit_inputs_do_not_name_skills_or_markers():
    for prompt in native.PROMPTS[1:]:
        assert "SKILL.md" not in prompt
        for name, _, body in native.SKILLS:
            assert name not in prompt
            assert (
                next(w for w in body.split() if w.endswith("_V1.")).rstrip(".")
                not in prompt
            )
