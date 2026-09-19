"""Control-flow regression fixtures only; no fixture is experimental evidence."""

import json
import pytest

from hermes_skilleval.intervention import functional_evaluate as evaluation


def test_resume_rebuilds_aggregate_after_last_task_commit(monkeypatch, tmp_path):
    output = tmp_path / "output"
    root = output / "task"
    root.mkdir(parents=True)
    row = {"task_id": "task", "method": "N0-v2", "repeat": 1}
    (root / "matrix-executions.json").write_text(json.dumps({"rows": [row]}))
    frozen = {"planned_matrix": 1, "roster": [row]}
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"tasks": [{"task_id": "task", "split": "test"}]}))
    monkeypatch.setattr(evaluation, "verify_freeze", lambda *a: None)
    monkeypatch.setattr(evaluation, "freeze", lambda *a: frozen)
    monkeypatch.setattr(evaluation, "assets", lambda *a: (None, None, None, None))
    monkeypatch.setattr(
        evaluation.shutil,
        "copyfile",
        lambda a, b: b.write_text("unit fixture, not credentials"),
    )

    def no_sampling(*a, **kw):
        raise AssertionError("completed task must not sample again")

    monkeypatch.setattr(evaluation, "run_once", no_sampling)
    monkeypatch.setattr(evaluation, "check_once", no_sampling)
    result = evaluation.matrix(
        protocol, None, tmp_path, output, None, None, None, tmp_path
    )
    assert result["matrix_recorded"] == 1
    assert json.loads((output / "matrix-executions.json").read_text())["rows"] == [row]
    assert not (output / "session-home/auth.json").exists()
    assert not (output / "matrix-records.json").exists()


def test_release_checks_nothing_until_every_execution_bundle_exists(
    monkeypatch, tmp_path
):
    output = tmp_path / "output"
    root = output / "task"
    root.mkdir(parents=True)
    row = {
        "task_id": "task",
        "method": "N0-v2",
        "repeat": 1,
        "run": str(root / "N0-v2-r1"),
        "execution": {"status": "COMPLETED"},
    }
    frozen = {"roster": [{"task_id": "task", "method": "N0-v2", "repeat": 1}]}
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"tasks": [{"task_id": "task", "split": "test"}]}))
    evaluation.dump(root / "panel-lock.json", {"status": "NO_OBSERVED_CHECKPOINT"})
    evaluation.dump(output / "policy-freeze.json", frozen)
    evaluation.dump(output / "delay-roster.json", {"rows": []})
    for kind, rows in (("matrix", [row]), ("panel", [])):
        evaluation.dump(
            output / (kind + "-executions.json"),
            {"policy_freeze": frozen, "rows": rows},
        )
    monkeypatch.setattr(evaluation, "verify_freeze", lambda *a: None)
    monkeypatch.setattr(evaluation, "freeze", lambda *a: frozen)
    calls = []
    monkeypatch.setattr(evaluation, "check_once", lambda *a: calls.append(a) or {})
    monkeypatch.setattr(evaluation, "verify_row", lambda r: {"y_functional": None})
    args = (protocol, None, tmp_path, output, None, None, None, tmp_path)
    with pytest.raises(FileNotFoundError):
        evaluation.release(*args)
    assert calls == []
    evaluation.dump(
        output / "delay-executions.json", {"policy_freeze": frozen, "rows": []}
    )
    assert evaluation.release(*args) == {"matrix": 1, "panel": 0, "delay": 0}
    assert len(calls) == 1
    assert (output / "release.json").exists()
