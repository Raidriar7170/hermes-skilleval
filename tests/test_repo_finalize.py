import json

from hermes_skilleval._maintenance import finalize as controller
from hermes_skilleval.repository_maintenance import manifest


def fixture(tmp_path, monkeypatch):
    task = tmp_path / "task"
    (task / "base").mkdir(parents=True)
    (task / "base/a.py").write_text("base\n")
    obj = {
        "task_id": "t",
        "base_commit": "abc",
        "target_selector": "target",
        "regression_selector": "regression",
        "trusted_test_file": "test_task.py",
    }
    (task / "task.json").write_text(json.dumps(obj))
    (task / "trusted").mkdir()
    q = tmp_path / "q.json"
    q.write_text(
        json.dumps(
            {
                **obj,
                "qualified": True,
                "qualification_binding": {},
                "base_manifest": manifest(task / "base"),
                "test_ids": {"target": ["a::target"], "regression": ["a::regression"]},
            }
        )
    )
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.py").write_text("agent patch\n")
    exe = tmp_path / "executor.json"
    exe.write_text(
        json.dumps(
            {
                "task_id": "t",
                "base_commit": "abc",
                "run_id": "run",
                "workspace": str(work),
                "execution_status": "STARTED",
            }
        )
    )
    monkeypatch.setattr(controller, "binding", lambda _: {})
    monkeypatch.setattr(controller, "stopped", lambda _: None)

    def fake_check(candidate, trusted, output, selector, **kw):
        output.mkdir(parents=True)
        result = {"valid": True, "passed": True, "cases": [{"id": "a::" + selector}]}
        (output / "result.json").write_text(json.dumps(result))
        (output / "junit.xml").write_text("<testsuite/>")
        return result

    monkeypatch.setattr(controller, "check", fake_check)
    return task, q, work, exe


def test_task_mismatch_fails_closed(tmp_path, monkeypatch):
    task, q, work, exe = fixture(tmp_path, monkeypatch)
    r = json.loads(exe.read_text())
    r["task_id"] = "other"
    exe.write_text(json.dumps(r))
    result = controller.finalize(exe, task, q, tmp_path / "out")
    assert result["resolved"] is None and "binding mismatch" in result["error"]


def test_base_mutation_fails_closed(tmp_path, monkeypatch):
    task, q, work, exe = fixture(tmp_path, monkeypatch)
    (task / "base/a.py").write_text("different base")
    result = controller.finalize(exe, task, q, tmp_path / "out")
    assert result["resolved"] is None and "base changed" in result["error"]


def test_reverification_uses_saved_patch(tmp_path, monkeypatch):
    task, q, work, exe = fixture(tmp_path, monkeypatch)
    first = controller.finalize(exe, task, q, tmp_path / "first")
    assert first["resolved"] is True
    (work / "a.py").write_text("late unrelated edit\n")
    second = controller.finalize(exe, task, q, tmp_path / "second")
    assert (
        second["resolved"] is True and second["patch_sha256"] == first["patch_sha256"]
    )
    assert (tmp_path / "second/rebuilt/a.py").read_text() == "agent patch\n"


def test_launch_arm_mismatch_fails_closed(tmp_path, monkeypatch):
    task, q, work, exe = fixture(tmp_path, monkeypatch)
    launch = json.loads(exe.read_text())
    launch["arm"] = "S"
    (exe.parent / "started.json").write_text(json.dumps(launch))
    result = controller.finalize(exe, task, q, tmp_path / "out")
    assert result["resolved"] is None and "arm binding" in result["error"]


def test_partial_missing_junit_preserves_check_evidence(tmp_path, monkeypatch):
    task, q, work, exe = fixture(tmp_path, monkeypatch)
    original = controller.check

    def missing(candidate, trusted, output, selector, **kw):
        result = original(candidate, trusted, output, selector, **kw)
        if selector == "regression":
            (output / "junit.xml").unlink()
            result["valid"] = False
        return result

    monkeypatch.setattr(controller, "check", missing)
    record = controller.finalize(exe, task, q, tmp_path / "out")
    assert record["resolved"] is None and record["verifier_valid"] is False
    assert "junit.xml" in record["check_evidence"]["target"]
    assert "junit.xml" not in record["check_evidence"]["regression"]
