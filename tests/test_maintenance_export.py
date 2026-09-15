import hashlib
import json
import pytest
from hermes_skilleval.maintenance_export import export_run, public_check
from hermes_skilleval.maintenance_records import recompute


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def fixture(tmp_path):
    run = tmp_path / "run"
    task = tmp_path / "task"
    q = tmp_path / "q.json"
    task_obj = {
        "task_id": "t",
        "base_commit": "base",
        "repository": "repo",
        "family_id": "family",
        "split": "dev",
    }
    write(task / "task.json", task_obj)
    qualification = {
        **task_obj,
        "qualified": True,
        "qualification_binding": {
            "task_sha256": hashlib.sha256((task / "task.json").read_bytes()).hexdigest()
        },
        "test_ids": {"target": ["a::b"], "regression": ["a::b"]},
    }
    write(q, qualification)
    patch = run / "saved-capture/candidate.patch"
    patch.parent.mkdir(parents=True)
    patch.write_text("")
    patchsha = hashlib.sha256(patch.read_bytes()).hexdigest()
    record = {
        **task_obj,
        "arm": "N",
        "run_id": "r",
        "registry_id": "registry",
        "patch_sha256": patchsha,
        "qualification_sha256": hashlib.sha256(q.read_bytes()).hexdigest(),
        "execution_status": "STARTED",
        "verifier_valid": True,
        "resolved": True,
        "timed_out": True,
        "exit_code": -15,
        "timeout": 60,
        "error": "private /Users/secret/person/path",
    }
    write(run / "run.json", record)
    write(run / "started.json", record)
    write(run / "verification/run.json", record)
    write(run / "saved-capture.json", {"patch_sha256": patchsha})
    for kind in ["target", "regression"]:
        junit = run / "verification" / kind / "junit.xml"
        junit.parent.mkdir(parents=True)
        junit.write_text('<testsuite><testcase classname="a" name="b"/></testsuite>')
        write(
            junit.parent / "result.json",
            {
                "evidence_sha256": {
                    "junit.xml": hashlib.sha256(junit.read_bytes()).hexdigest()
                },
                "cases": [{"id": "a::b"}],
            },
        )
    record["check_evidence"] = {
        kind: {
            filename: hashlib.sha256(
                (run / "verification" / kind / filename).read_bytes()
            ).hexdigest()
            for filename in ["result.json", "junit.xml"]
        }
        for kind in ["target", "regression"]
    }
    write(run / "run.json", record)
    write(run / "verification/run.json", record)
    return run, task, q


@pytest.mark.parametrize("tamper", ["task", "qualification", "patch", "junit"])
def test_export_rejects_wrong_original_binding(tmp_path, tamper):
    run, task, q = fixture(tmp_path)
    if tamper == "task":
        data = json.loads((task / "task.json").read_text())
        data["task_id"] = "wrong"
        write(task / "task.json", data)
    elif tamper == "qualification":
        data = json.loads(q.read_text())
        data["qualified"] = False
        write(q, data)
    elif tamper == "patch":
        (run / "saved-capture/candidate.patch").write_text("changed")
    else:
        (run / "verification/target/junit.xml").write_text("changed")
    with pytest.raises(ValueError):
        export_run(run, task, q, tmp_path / "public")


def test_export_preserves_timeout_without_private_error(tmp_path):
    run, task, q = fixture(tmp_path)
    row = export_run(run, task, q, tmp_path / "public")
    assert row["timed_out"] is True and row["exit_code"] == -15
    assert "/Users/" not in (tmp_path / "public/verification.json").read_text()
    write(tmp_path / "index.json", {"runs": [row]})
    result = recompute(tmp_path / "index.json", tmp_path / "recomputed")
    assert result["summary"][0]["timeouts"] == 1


def test_public_patch_rejects_private_paths():
    with pytest.raises(ValueError, match="sensitive"):
        public_check(b'+ token_file = "/Users/person/private/auth.json"')


def test_export_rejects_whole_check_directory_swap(tmp_path):
    run, task, q = fixture(tmp_path)
    junit = run / "verification/target/junit.xml"
    junit.write_text(
        '<testsuite><testcase classname="a" name="b"><failure/></testcase></testsuite>'
    )
    check = json.loads((junit.parent / "result.json").read_text())
    check["evidence_sha256"]["junit.xml"] = hashlib.sha256(
        junit.read_bytes()
    ).hexdigest()
    write(junit.parent / "result.json", check)
    with pytest.raises(ValueError, match="run/check digest"):
        export_run(run, task, q, tmp_path / "public")


def test_records_rejects_conclusion_mismatch(tmp_path):
    run, task, q = fixture(tmp_path)
    row = export_run(run, task, q, tmp_path / "public")
    binding = tmp_path / "public/verification.json"
    data = json.loads(binding.read_text())
    data["resolved"] = False
    write(binding, data)
    row["files"]["binding"]["sha256"] = hashlib.sha256(binding.read_bytes()).hexdigest()
    write(tmp_path / "index.json", {"runs": [row]})
    result = recompute(tmp_path / "index.json", tmp_path / "recomputed")
    assert result["rows"][0]["resolved"] is None
    assert result["rows"][0]["verifier_valid"] is False
    assert "conclusion mismatch" in result["rows"][0]["error"]
