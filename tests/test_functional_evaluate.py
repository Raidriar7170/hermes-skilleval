"""Control-flow regression fixtures only; no fixture is experimental evidence."""

import json

from hermes_skilleval.intervention import functional_evaluate as evaluation


def test_resume_rebuilds_aggregate_after_last_task_commit(monkeypatch, tmp_path):
    output = tmp_path / "output"
    root = output / "task"
    root.mkdir(parents=True)
    row = {"task_id": "task", "method": "N0-v2", "repeat": 1}
    (root / "matrix-records.json").write_text(json.dumps({"rows": [row]}))
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
    result = evaluation.matrix(
        protocol, None, tmp_path, output, None, None, None, tmp_path
    )
    assert result["matrix_recorded"] == 1
    assert json.loads((output / "matrix-records.json").read_text())["rows"] == [row]
    assert not (output / "session-home/auth.json").exists()
