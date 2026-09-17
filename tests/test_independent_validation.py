import pytest

from hermes_skilleval.repo_routing.independent_validation import (
    validate_roster,
    select,
    calibrations,
)
from hermes_skilleval.repo_routing.environment_facts import probe_path, probe_identity


def task(tid="new", split="cal", group="new-mechanism"):
    return dict(
        task_id=tid,
        parent_task_id=tid,
        repair_group_id=group,
        split=split,
        repository="r",
        request_ref="https://example/" + tid,
        previously_observed=False,
    )


def test_split_and_history():
    validate_roster(
        [task(), task("two", "check", "second")], [task("old", group="old")]
    )
    with pytest.raises(ValueError):
        validate_roster([task()], [task()])
    with pytest.raises(ValueError):
        validate_roster([task(), task("two", "check")], [])
    duplicate = task("two", "check", "second")
    duplicate["request_ref"] = task()["request_ref"]
    with pytest.raises(ValueError):
        validate_roster([task(), duplicate], [])


def test_c2_filters_original_order_and_never_pads():
    rows = [dict(row_id=s, task_id="task", skill_id=s, repository="r") for s in "abc"]
    streams = {
        s: dict(
            scores={"B2": 3 - i, "cheap_text": i},
            policy_accepts=s == "b",
            public_conflict=False,
        )
        for i, s in enumerate("abc")
    }
    fixed = {"default": ["a", "b"]}
    one = select(rows, streams, fixed, 0.9)[0]
    assert one["B2"] == ["a", "b"] and one["C2"] == [] and one["C2_fallback"]
    streams["c"]["policy_accepts"] = True
    two = select(rows, streams, fixed, 0.9)[0]
    assert two["C2"] == ["b", "c"] and not two["C2_fallback"]
    assert select(list(reversed(rows)), streams, fixed, 0.9) == [two]


def test_probe_legacy_bytes_unchanged():
    assert probe_path().name == "environment_probe.py"
    assert probe_identity() == probe_identity({})
    assert (
        probe_path({"probe_variant": "explicit-capability-v1"}).name
        == "environment_probe_explicit.py"
    )
    with pytest.raises(ValueError):
        probe_path({"probe_variant": "arbitrary"})


def test_empty_cal_has_no_operating_point():
    # Real calibration belongs to the optional numerical stack; records do not.
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    result = calibrations(
        [],
        {},
        {
            "calibration": {"min_axis_groups": 3, "min_each_class": 3},
            "operating_point": {},
        },
    )
    assert all(c["threshold"] is None for c in result.values())


def test_cal_rejects_check_before_fitting():
    with pytest.raises(ValueError, match="cal-only"):
        calibrations([{"split": "check"}], {}, {})


def test_synthetic_complete_evaluation_no_acceptance():
    from hermes_skilleval.repo_routing.independent_validation import evaluate

    labels = []
    stream = []
    for group in range(3):
        for i, s in enumerate("abc"):
            rid = f"{group}::{s}"
            labels.append(
                dict(
                    row_id=rid,
                    task_id=str(group),
                    skill_id=s,
                    parent_task_id=str(group),
                    requirement_id="whole",
                    repair_group_id=str(group),
                    repository="r",
                    applicability_label="APPLICABLE" if i == 0 else "NOT_APPLICABLE",
                    specificity_label="TASK_SPECIFIC" if i == 0 else None,
                )
            )
            stream.append(
                dict(
                    row_id=rid,
                    input_eligible=True,
                    policy_accepts=False,
                    scores={
                        "A": 0.2,
                        "A_calibrated": 0.3,
                        "cheap_text_calibrated": 0.2,
                        "J": 0.1,
                        "B2": -1,
                    },
                )
            )
    pred = {
        "rows": stream,
        "selections": [
            dict(task_id=str(i), B2=["a", "b"], C2=[], T2=["b", "c"], F2=["a", "b"])
            for i in range(3)
        ],
    }
    result = evaluate(pred, labels, {"bootstrap": {"repetitions": 100, "seed": 7170}})
    assert result["acceptance"]["precision"] is None
    assert result["selections"]["C2"]["fallback_tasks"] == 3
    assert result["mechanisms"] == 3 and result["rows"] == 9
    assert result["metrics"]["J"]["joint"]["known"] == 9


def test_cli_prediction_rejects_label_path_before_any_file_read(tmp_path):
    from hermes_skilleval.repo_routing.independent_validation import main

    args = ["--stage", "score"]
    for name in ("tasks", "registry", "protocol", "project-root", "output"):
        args += ["--" + name, str(tmp_path / name)]
    args += ["--check-labels", str(tmp_path / "forbidden-labels")]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_cli_calibration_rejects_check_labels_before_read(tmp_path):
    from hermes_skilleval.repo_routing.independent_validation import main

    args = ["--stage", "calibrate"]
    for name in ("tasks", "registry", "protocol", "project-root", "output"):
        args += ["--" + name, str(tmp_path / name)]
    args += ["--check-labels", str(tmp_path / "forbidden-labels")]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_public_features_exclude_labels_group_ids_and_explanations():
    from hermes_skilleval.repo_routing.pointwise_support import public_input

    t = dict(
        request="Fix the public CLI",
        context={"summary": "Public source"},
        split="cal",
        repair_group_id="a",
        gold="x",
        quote_refs=["private"],
    )
    skill = dict(name="debug", description="check evidence", body="reproduce")
    original = public_input(t, skill)
    changed = dict(
        t,
        split="check",
        repair_group_id="b",
        gold="y",
        quote_refs=["different"],
        applicability_label="UNKNOWN",
    )
    assert public_input(changed, skill) == original
    assert set(original.__dict__) == {
        "request",
        "context",
        "skill_name",
        "skill_description",
        "skill_body",
    }


def test_label_grouping_cannot_override_frozen_weights(tmp_path):
    from hermes_skilleval.repo_routing.independent_validation import label_rows
    import json

    expected = dict(
        row_id="t::s",
        task_id="t",
        skill_id="s",
        split="cal",
        repair_group_id="g",
        parent_task_id="t",
        requirement_id="whole",
        repository="r",
    )
    label = dict(
        expected,
        parent_task_id="fabricated",
        applicability_label="NOT_APPLICABLE",
        specificity_label=None,
    )
    p = tmp_path / "labels.jsonl"
    p.write_text(json.dumps(label) + "\n")
    with pytest.raises(ValueError, match="grouping"):
        label_rows(p, [expected])


def test_prediction_hash_mismatch_rejects(tmp_path):
    from hermes_skilleval.repo_routing.independent_validation import checked
    from hermes_skilleval.repo_routing.applicability_data import file_hash

    p = tmp_path / "predictions.json"
    p.write_text('{"policy_accepts": false}')
    expected = file_hash(p)
    p.write_text('{"policy_accepts": true}')
    with pytest.raises(ValueError, match="binding mismatch"):
        checked(p, expected)
