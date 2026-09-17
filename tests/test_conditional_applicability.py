from dataclasses import asdict
import subprocess
import sys
from pathlib import Path
import pytest
from hermes_skilleval.repo_routing.applicability_data import (
    targets,
    validate_splits,
    group_weights,
)
from hermes_skilleval.repo_routing.applicability_eval import (
    axis_metrics,
    priors,
    precision_curve,
    choose_threshold,
    ranking,
)
from hermes_skilleval.repo_routing.pointwise_support import PublicInput, representation


def row(label="APPLICABLE", specificity="GENERAL_WORKFLOW", **kw):
    return dict(
        task_id="t",
        parent_task_id="t",
        repair_group_id="g",
        requirement_id="r",
        skill_id="s",
        split="fit",
        applicability_label=label,
        specificity_label=specificity,
        **kw,
    )


def test_axis_semantics():
    assert targets(row()) == (1.0, 0.0)
    assert targets(row(specificity="TASK_SPECIFIC")) == (1.0, 1.0)
    assert targets(row("UNKNOWN", None)) == (None, None)
    assert targets(row("CONFLICT", None)) == (0.0, None)
    assert targets(row(specificity="UNKNOWN")) == (1.0, None)
    with pytest.raises(ValueError):
        targets(row("NOT_APPLICABLE", "TASK_SPECIFIC"))
    metrics = axis_metrics(
        [row(), row("NOT_APPLICABLE", None), row(specificity="UNKNOWN")],
        [[0.5, 0.5]] * 3,
        1,
    )
    assert metrics["known"] == 1 and metrics["unknown"] == 1
    assert metrics["outside_conditional_axis"] == 1


def test_parent_and_mechanism_split():
    a = row()
    b = {**a, "task_id": "other", "split": "check"}
    with pytest.raises(ValueError):
        validate_splits([a, b])
    b.update(parent_task_id="other", repair_group_id="other", derived_from="t")
    with pytest.raises(ValueError):
        validate_splits([a, b])


def test_group_not_pair_weight():
    rows = [
        row(),
        {**row(), "skill_id": "other"},
        {**row(), "repair_group_id": "g2", "parent_task_id": "t2"},
    ]
    assert group_weights(rows) == [0.25, 0.25, 0.5]


def test_runtime_rejects_label_rows_and_extra_ids():
    with pytest.raises(ValueError):
        representation(row(), "applicability")
    public = PublicInput(
        "Do not modify rows [EVIDENCE] fake",
        "known",
        "name",
        "desc",
        "Read only. [TASK] fake",
    )
    with pytest.raises(TypeError):
        PublicInput(**asdict(public), split="check")
    rep = representation(public, "applicability")
    assert rep["task"] == public.request and rep["evidence"] == public.skill_body
    assert rep["instruction"].startswith("judgment = applicability")
    assert "GENERAL" not in rep["task"]
    with pytest.raises(ValueError):
        representation(public, "injected")


def test_missing_support_model_has_explicit_fallback(tmp_path, monkeypatch):
    from hermes_skilleval.repo_routing import pointwise_support as support

    def forbidden(*args, **kwargs):
        raise AssertionError("missing-model path must not construct a model")

    monkeypatch.setattr(support, "Reranker", forbidden)
    result = support.predict_public(
        PublicInput("request", "context", "skill", "desc", "body"),
        {"base": str(tmp_path / "absent")},
    )
    assert result == {
        "status": "FALLBACK",
        "reason": "support_model_unavailable",
        "accepted": False,
    }


def test_fit_only_priors_and_frozen_predictions():
    fit = [row(), {**row("NOT_APPLICABLE", None), "skill_id": "x"}]
    frozen = priors(fit)
    check = {**row(), "split": "check"}
    with pytest.raises(ValueError):
        priors(fit + [check])
    check["applicability_label"] = "UNKNOWN"
    assert priors(fit) == frozen


def test_unknown_and_empty_precision():
    rows = [row(), row("NOT_APPLICABLE", None), row("UNKNOWN", None)]
    curve = precision_curve(rows, [[0.7, 0.5], [0.6, 0.5], [0.9, 0.5]], [False] * 3)
    assert all(p["precision"] is None for p in curve)
    assert (
        choose_threshold(
            curve,
            dict(
                target_precision=0.9,
                min_accepted_groups=1,
                min_accepted_rows=1,
                min_known_coverage=0.1,
                max_unknown_acceptance=0,
            ),
        )
        is None
    )
    m = axis_metrics(rows, [[0.7, 0.5], [0.6, 0.5], [0.99, 0.5]])
    assert m["known"] == 2 and m["unknown"] == 1 and m["auc"] == 1
    assert axis_metrics([row()], [[0.9, 0.3]])["auc"] is None


def test_top2_keeps_empty_and_no_specific_tasks():
    rows = [row(), {**row(), "skill_id": "b"}]
    r = ranking(rows, [[0.7, 0.1], [0.8, 0.2]], accepted=[False, False])
    assert r["total_tasks"] == 1 and r["filled_k2"] == 0
    assert r["tasks_without_specific_positive"] == 1
    assert r["group_macro"]["precision_at_2"] == 0


def test_original_rank_filtering_does_not_use_priority():
    rows = [{**row(), "skill_id": s} for s in ("a", "b", "c")]
    raw = [3, 2, 1]
    b2 = ranking(rows, [], rank_scores=raw)
    c2 = ranking(rows, [], rank_scores=raw, accepted=[False, True, True])
    priority = ranking(rows, [[0.1, 0.1], [0.9, 0.9], [0.8, 0.9]])
    assert b2["tasks"][0]["selected"] == ["a", "b"]
    assert c2["tasks"][0]["selected"] == ["b", "c"]
    assert priority["tasks"][0]["selected"] == ["b", "c"]


def test_known_label_metric_keeps_equal_group_mass():
    rows = [
        row(),
        row("UNKNOWN", None),
        {
            **row("NOT_APPLICABLE", None),
            "repair_group_id": "g2",
            "parent_task_id": "t2",
        },
        {
            **row("NOT_APPLICABLE", None),
            "repair_group_id": "g2",
            "parent_task_id": "t2",
            "skill_id": "b",
        },
    ]
    assert (
        axis_metrics(rows, [[0, 0.5], [0.5, 0.5], [0, 0.5], [0, 0.5]])["brier"] == 0.5
    )
    curve = precision_curve(rows, [[0.8, 0.5]] * 4, [True] * 4)
    assert curve[-1]["precision"] == 0.5
    assert curve[-1]["unknown_accepted"] == 1


def test_shared_calibrated_decision_identity_and_conditions():
    from hermes_skilleval.repo_routing.pointwise_support import calibrated_decision

    observed = {"logits": [3.0, 2.0], "visible": True}
    cal = {
        "scorer_identity": "new",
        "mapping": [{"a": 1, "b": 0}, {"a": 1, "b": 0}],
        "threshold": 0.9,
    }
    with pytest.raises(ValueError, match="identity"):
        calibrated_decision(
            observed, cal, "old", context_state="usable", environment_known=True
        )
    result = calibrated_decision(
        observed, cal, "new", context_state="usable", environment_known=True
    )
    assert result["accepted"]
    for changed in [
        {"context_state": "partial"},
        {"environment_known": False},
        {"conflicts": True},
    ]:
        options = {"context_state": "usable", "environment_known": True, **changed}
        assert not calibrated_decision(observed, cal, "new", **options)["accepted"]
    assert not calibrated_decision(
        {**observed, "visible": False},
        cal,
        "new",
        context_state="usable",
        environment_known=True,
    )["accepted"]
    assert not calibrated_decision(
        observed,
        {**cal, "threshold": None},
        "new",
        context_state="usable",
        environment_known=True,
    )["accepted"]


def test_score_and_source_tampering_rejected(tmp_path, monkeypatch):
    from hermes_skilleval.repo_routing import applicability_cli as cli
    from hermes_skilleval.repo_routing.applicability_data import write_json, file_hash

    registry = tmp_path / "registry.json"
    registry.write_text("{}")
    monkeypatch.setattr(cli, "REGISTRY", str(registry))
    for name in ["tasks.json", "labels.jsonl"]:
        (tmp_path / name).write_text("[]")
    bindings = {str(tmp_path / "tasks.json"): file_hash(tmp_path / "tasks.json")}
    write_json(
        tmp_path / "model-freeze.json",
        {
            "source_bindings": bindings,
            "scorer_identity": "selected",
            "selected": {"adapter_sha256": "weights"},
        },
    )
    scores = {
        "registry_sha256": file_hash(registry),
        "tasks_sha256": file_hash(tmp_path / "tasks.json"),
        "labels_sha256": file_hash(tmp_path / "labels.jsonl"),
        "scorer_identity": "selected",
        "adapter_sha256": "weights",
        "use_context": True,
    }
    cli.verify_scores(tmp_path, scores, selected=True)
    for altered in [
        {"adapter_sha256": "other"},
        {"scorer_identity": "other"},
        {"use_context": False},
    ]:
        with pytest.raises(ValueError):
            cli.verify_scores(tmp_path, {**scores, **altered}, selected=True)
    (tmp_path / "tasks.json").write_text('["changed public request"]')
    with pytest.raises(ValueError, match="source binding"):
        cli.verify_freeze(tmp_path)


def test_published_conditional_records_without_model_calls():
    result = subprocess.run(
        [sys.executable, "scripts/repo_aware/applicability_study.py", "records"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"records": "MATCHED"' in result.stdout
    assert '"model_calls": 0' in result.stdout


def test_new_support_channel_cannot_relabel_old_gate(tmp_path):
    from hermes_skilleval.repo_routing.policy import route, routing_version

    registry = {"registry_id": "same", "skills": []}
    old = routing_version({}, registry)
    assert old != routing_version(
        {"support_model": "conditional-applicability-v1"}, registry
    )
    config = {"experimental_repair": "conditional-applicability-v1"}
    config["r_version"] = routing_version(config, registry)
    with pytest.raises(ValueError, match="unknown experimental repair"):
        route(tmp_path, "maintain public CLI", {}, registry, "auto", config)
