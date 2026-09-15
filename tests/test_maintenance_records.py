import hashlib
import json
import pytest
from hermes_skilleval.maintenance_records import recompute


def test_missing_evidence_cannot_pass(tmp_path):
    row = {
        "task_id": "t",
        "repository": "r",
        "family_id": "f",
        "split": "dev",
        "arm": "N",
        "attempt": 1,
        "execution_status": "STARTED",
        "files": {"patch": {"path": "absent.patch", "sha256": "x"}},
        "expected_test_ids": {},
    }
    p = tmp_path / "index.json"
    p.write_text(json.dumps({"runs": [row]}))
    result = recompute(p, tmp_path / "out")
    assert result["summary"][0]["unknown"] == 1
    assert result["summary"][0]["resolved"] == 0
    with pytest.raises(ValueError, match="preserve"):
        recompute(p, tmp_path / "out")


def test_duplicate_attempt_rejected(tmp_path):
    r = {
        "task_id": "t",
        "repository": "r",
        "family_id": "f",
        "split": "dev",
        "arm": "N",
        "attempt": 1,
        "execution_status": "STARTED",
        "files": {},
    }
    p = tmp_path / "index.json"
    p.write_text(json.dumps({"runs": [r, r]}))
    with pytest.raises(ValueError, match="duplicate"):
        recompute(p, tmp_path / "out")


def test_skip_never_certifies_pass(tmp_path):
    (tmp_path / "patch").write_text("")
    (tmp_path / "tests.xml").write_text(
        '<testsuite><testcase classname="a" name="b"><skipped/></testcase></testsuite>'
    )
    files = {
        k: {
            "path": name,
            "sha256": hashlib.sha256((tmp_path / name).read_bytes()).hexdigest(),
        }
        for k, name in [
            ("patch", "patch"),
            ("target", "tests.xml"),
            ("regression", "tests.xml"),
        ]
    }
    r = {
        "task_id": "t",
        "repository": "r",
        "family_id": "f",
        "split": "dev",
        "arm": "N",
        "attempt": 1,
        "execution_status": "STARTED",
        "files": files,
        "expected_test_ids": {"target": ["a::b"], "regression": ["a::b"]},
    }
    p = tmp_path / "index.json"
    p.write_text(json.dumps({"runs": [r]}))
    assert recompute(p, tmp_path / "out")["rows"][0]["resolved"] is None


def test_cost_subsets_and_missing_usage_are_not_double_counted():
    from hermes_skilleval.maintenance_records import aggregate_costs

    common = {"split": "confirmation", "repository": "r", "arm": "N"}
    rows = [
        {
            **common,
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 70,
                "output_tokens": 20,
                "reasoning_output_tokens": 4,
            },
        },
        {**common, "usage": None},
    ]
    costs = aggregate_costs(rows)[0]
    assert costs["measures"]["input_tokens"] == {
        "sum_known": 100,
        "known_attempts": 1,
        "total_attempts": 2,
    }
    assert costs["measures"]["uncached_input_tokens"]["sum_known"] == 30
    assert costs["measures"]["output_tokens"]["sum_known"] == 20
    assert costs["measures"]["execution_seconds"]["sum_known"] is None
    assert costs["cost_usd"] is None
