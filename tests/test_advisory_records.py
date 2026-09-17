import json
import pytest
from hermes_skilleval.repo_routing.advisory_records import recompute, sha
from hermes_skilleval.repo_routing.advisory_study import schedule


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def index(root):
    write(
        root / "evidence-index.json",
        {
            "files": {
                str(p.relative_to(root)): sha(p)
                for p in root.rglob("*")
                if p.is_file() and p.name != "evidence-index.json"
            }
        },
    )


def fixture(root):
    rows = [{**r, "result": "NOT_RUN"} for r in schedule()]
    write(root / "protocol.json", {"schedule": schedule()})
    write(root / "runs.json", rows)
    write(
        root / "qualification.json",
        {
            "tasks": [
                {
                    "task_id": t,
                    "test_ids": {
                        "target": ["test_behavior::test_target"],
                        "regression": ["test_behavior::test_regression"],
                    },
                }
                for t in sorted({r["task_id"] for r in rows})
            ]
        },
    )
    index(root)
    return rows


def test_complete_denominator_without_models(tmp_path):
    fixture(tmp_path)
    r = recompute(tmp_path)
    assert r["model_calls"] == 0 and r["planned"] == 32
    assert all(v == {"NOT_RUN": 8} for v in r["counts"].values())
    assert all(v["J2_comparisons"]["N"] == "UNKNOWN" for v in r["paired"].values())


def test_tampered_records_fail(tmp_path):
    fixture(tmp_path)
    (tmp_path / "runs.json").write_text("[]")
    with pytest.raises(ValueError, match="evidence changed"):
        recompute(tmp_path)
    index(tmp_path)
    with pytest.raises(ValueError, match="denominator"):
        recompute(tmp_path)


def test_empty_acceptance_report_rejected(tmp_path):
    rows = fixture(tmp_path)
    r = rows[0]
    r.update(
        result="SUCCESS",
        execution_status="STARTED",
        patch_status="RECONSTRUCTED",
        policy_status="PASS",
    )
    write(tmp_path / "runs.json", rows)
    reports = tmp_path / "checks" / r["run_id"]
    reports.mkdir(parents=True)
    (reports / "target.xml").write_text("<testsuite/>")
    (reports / "regression.xml").write_text("<testsuite/>")
    patch = tmp_path / "patches" / (r["run_id"] + ".patch")
    patch.parent.mkdir()
    patch.write_bytes(b"")
    r["patch_sha256"] = sha(patch)
    write(tmp_path / "runs.json", rows)
    index(tmp_path)
    with pytest.raises(ValueError, match="empty/incomplete"):
        recompute(tmp_path)


def test_index_cannot_omit_required_inputs(tmp_path):
    fixture(tmp_path)
    saved = json.loads((tmp_path / "evidence-index.json").read_text())
    del saved["files"]["runs.json"]
    write(tmp_path / "evidence-index.json", saved)
    with pytest.raises(ValueError, match="required evidence"):
        recompute(tmp_path)


def test_success_requires_patch_identity(tmp_path):
    rows = fixture(tmp_path)
    rows[0].update(
        result="SUCCESS",
        execution_status="STARTED",
        patch_status="RECONSTRUCTED",
        policy_status="PASS",
    )
    write(tmp_path / "runs.json", rows)
    index(tmp_path)
    with pytest.raises(ValueError, match="indexed patch/report"):
        recompute(tmp_path)


@pytest.mark.parametrize(
    "fields,message",
    [
        ({"result": "TIMEOUT", "timed_out": False}, "observed timeout"),
        (
            {"result": "FUNCTIONAL_FAILURE", "provider_error_events": ["turn.failed"]},
            "provider error",
        ),
        ({"result": "MADE_UP"}, "unknown result"),
    ],
)
def test_result_classification_is_checked(tmp_path, fields, message):
    rows = fixture(tmp_path)
    rows[0].update(fields)
    write(tmp_path / "runs.json", rows)
    index(tmp_path)
    with pytest.raises(ValueError, match=message):
        recompute(tmp_path)
