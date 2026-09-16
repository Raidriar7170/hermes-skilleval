import copy
from types import SimpleNamespace

import pytest

from hermes_skilleval.repo_routing.applicability_data import read_rows, read_json
from hermes_skilleval.repo_routing.decision_cli import selection, replay, DEFAULT
from hermes_skilleval.repo_routing.decision_contract import (
    event_rows,
    priority,
    validate_contract,
    select_for_goal,
    score_axes,
    guarded_score,
)
from hermes_skilleval.repo_routing.context import digest
from hermes_skilleval.repo_routing.pointwise_support import PublicInput


@pytest.fixture
def selected():
    return selection(DEFAULT)


def test_real_selection_replay_and_full_catalog(selected):
    assert (
        selected["targets"]["applicability"]["contract"]["candidate_id"]
        == "training-lambda-0"
    )
    assert (
        selected["targets"]["task_specific"]["contract"]["candidate_id"]
        == "training-lambda-1"
    )
    assert all(v["contract"]["epoch"] == 3 for v in selected["targets"].values())
    result = replay(DEFAULT, selected)
    assert all(
        len(result["streams"][k]["orders"]["csv-diff-issue-39"]) == 10
        for k in ("legacy_product", "A_app_only", "J_joint_specific")
    )
    assert result["new_forward_calls"] == 0
    assert result["streams"]["rank_plus_support"]["accepted_precision"] is None


def test_a_ignores_specificity():
    assert priority([[0.8, 0.01], [0.6, 0.99]], "applicability") == priority(
        [[0.8, 1], [0.6, 0]], "applicability"
    )


def test_selection_reorder_and_split_guard(selected):
    rows = [r for r in read_rows(DEFAULT / "labels.jsonl") if r["split"] == "model-dev"]
    candidates = []
    for t in selected["targets"]["task_specific"]["trials"]:
        candidates.append(
            {
                **{k: v for k, v in t.items() if k not in {"metrics", "loss"}},
                "rows": read_json(
                    DEFAULT / f"{t['candidate_id']}-dev-{t['epoch']}.json"
                )["rows"][::-1],
            }
        )
    actual = select_for_goal(rows[::-1], candidates[::-1], "task_specific", "bound")
    assert actual["contract"]["epoch"] == 3
    bad = copy.deepcopy(rows)
    bad[0]["split"] = "check"
    with pytest.raises(ValueError, match="model-dev"):
        select_for_goal(bad, candidates, "task_specific", "bound")
    # No API for cal/check predictions exists; the only accepted rows are model-dev.
    bad[0]["split"] = "cal"
    with pytest.raises(ValueError):
        select_for_goal(bad, candidates, "task_specific", "bound")


def test_event_unknown_and_outside_axis():
    rows = [
        {"applicability_label": a, "specificity_label": s}
        for a, s in [
            ("UNKNOWN", None),
            ("APPLICABLE", "UNKNOWN"),
            ("NOT_APPLICABLE", None),
            ("APPLICABLE", "GENERAL_WORKFLOW"),
            ("APPLICABLE", "TASK_SPECIFIC"),
        ]
    ]
    assert [r["applicability_label"] for r in event_rows(rows)] == [
        "UNKNOWN",
        "UNKNOWN",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "APPLICABLE",
    ]
    assert rows[2]["specificity_label"] is None


def test_direct_supervision_not_name(selected):
    c = copy.deepcopy(selected["targets"]["task_specific"]["contract"])
    c["candidate_id"] = "looks-joint"
    c["supervised_denominators"]["specificity_given_applicable"] = 0
    with pytest.raises(ValueError, match="direct supervision"):
        validate_contract(c)
    c = copy.deepcopy(selected["targets"]["applicability"]["contract"])
    c["ranking_formula"] = "raw_app_times_conditional_specificity"
    with pytest.raises(ValueError, match="mismatch"):
        validate_contract(c)


def test_single_axis_actual_scorer(selected):
    class Values:
        def detach(self):
            return self

        def cpu(self):
            return self

        def tolist(self):
            return [1.0]

    seen = []
    ranker = SimpleNamespace(
        scores=lambda sections: (seen.extend(sections) or Values(), [])
    )
    result = score_axes(
        ranker,
        PublicInput("request", "context", "skill", "description", "body"),
        selected["targets"]["applicability"]["contract"],
    )
    assert len(seen) == 1
    assert "judgment = applicability" in seen[0]["instruction"]
    assert result["accepted"] is False


def test_invalid_contract_and_input_before_model(selected, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("heavy model constructed")

    public = PublicInput("request", "context", "skill", "description", "body")
    c = copy.deepcopy(selected["targets"]["task_specific"]["contract"])
    config = {"adapter_files": {"adapter_model.safetensors": c["adapter_sha256"]}}
    facts = {"context_state": "usable", "environment_known": True}
    token = {"visible": True, "public_input_identity": digest(public.__dict__)}
    c["supervised_denominators"]["specificity_given_applicable"] = 0
    with pytest.raises(ValueError):
        guarded_score(public, config, c, facts, token, factory=forbidden)
    c = copy.deepcopy(selected["targets"]["applicability"]["contract"])
    config["adapter_files"]["adapter_model.safetensors"] = c["adapter_sha256"]
    with pytest.raises(ValueError, match="token/input"):
        guarded_score(
            public,
            config,
            c,
            facts,
            {**token, "public_input_identity": "old"},
            factory=forbidden,
        )
    c["support_mode"] = "supported"
    c["calibration_ref"] = "bound"
    with pytest.raises(ValueError, match="threshold"):
        guarded_score(public, config, c, facts, token, factory=forbidden)
    with pytest.raises(ValueError, match="calibration/input"):
        guarded_score(
            public,
            config,
            c,
            facts,
            token,
            calibration={"threshold": 0.8, "input_identity": "old"},
            factory=forbidden,
        )


def test_supported_binding_and_raw_priority_survive_mapping(selected, monkeypatch):
    from hermes_skilleval.repo_routing import pointwise_support
    from hermes_skilleval.repo_routing.decision_contract import contract_identity

    c = copy.deepcopy(selected["targets"]["task_specific"]["contract"])
    original_identity = contract_identity(c)
    c.update(support_mode="supported", calibration_ref="cal.json")
    assert contract_identity(c) == original_identity
    public = PublicInput("request", "context", "skill", "description", "body")
    token = {"visible": True, "public_input_identity": digest(public.__dict__)}
    cal = {
        "threshold": 0.5,
        "mapping": {"a": 1, "b": 10},
        "axis": "applicability",
        "public_input_identities": [digest(public.__dict__)],
        "contract_identity": original_identity,
        "scorer_identity": "scorer",
    }
    config = {
        "base": "base",
        "device": "cpu",
        "max_length": 8192,
        "adapter": "adapter",
        "adapter_files": {"adapter_model.safetensors": c["adapter_sha256"]},
    }

    class Values:
        def detach(self):
            return self

        def cpu(self):
            return self

        def tolist(self):
            return [0.0, 0.0]

    monkeypatch.setattr(pointwise_support, "scorer_identity", lambda config: "scorer")
    result = guarded_score(
        public,
        config,
        c,
        {"context_state": "usable", "environment_known": True},
        token,
        calibration=cal,
        factory=lambda *a, **kw: SimpleNamespace(scores=lambda s: (Values(), [])),
    )
    assert result["accepted"] and result["priority_score"] == 0.25
    assert result["support_probability"] > 0.99
    bad = copy.deepcopy(cal)
    bad["public_input_identities"] = ["changed"]
    with pytest.raises(ValueError, match="calibration/input"):
        guarded_score(
            public,
            config,
            c,
            {"context_state": "usable", "environment_known": True},
            token,
            calibration=bad,
            factory=lambda *a, **kw: pytest.fail("constructed"),
        )


def test_selection_rejects_changed_frozen_input(tmp_path):
    import shutil

    shutil.copytree(DEFAULT, tmp_path / "records")
    path = tmp_path / "records" / "tasks.json"
    path.write_text(path.read_text().replace("table.triggers_dict", "table.changed"))
    with pytest.raises(ValueError, match="identity mismatch"):
        selection(tmp_path / "records")


def test_online_cli_does_not_read_training_labels(tmp_path, monkeypatch, selected):
    import json
    from hermes_skilleval.repo_routing import decision_cli

    c = selected["targets"]["applicability"]["contract"]
    files = {
        "contract.json": c,
        "manifest.json": {"applicability": c},
        "config.json": {
            "adapter_files": {"adapter_model.safetensors": c["adapter_sha256"]}
        },
        "public.json": PublicInput(
            "request", "context", "skill", "description", "body"
        ).__dict__,
    }
    for name, value in files.items():
        (tmp_path / name).write_text(json.dumps(value))
    monkeypatch.setattr(
        decision_cli,
        "selection",
        lambda *a: pytest.fail("online read development labels"),
    )
    monkeypatch.setattr(
        decision_cli, "read_rows", lambda *a: pytest.fail("online read label rows")
    )
    monkeypatch.setattr(
        decision_cli, "tokenize", lambda *a, **kw: {"public::public": {"visible": True}}
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes-applicability",
            "advise",
            "--config",
            str(tmp_path / "config.json"),
            "--contract",
            str(tmp_path / "contract.json"),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--input",
            str(tmp_path / "public.json"),
            "--output",
            str(tmp_path / "result.json"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        decision_cli.main()
    assert exc.value.code == 2  # unknown context blocks before heavy constructor
    assert read_json(tmp_path / "result.json")["model_constructions"] == 0
