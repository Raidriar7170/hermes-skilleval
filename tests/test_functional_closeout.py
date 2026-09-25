from copy import deepcopy
from functools import partial

import pytest

from test_evidence_linked_composition import fixture
from hermes_skilleval.intervention.functional_closeout import matrix, summarize_rows
from hermes_skilleval.intervention.pair_applicability import build_features
from hermes_skilleval.intervention.relation_query_study import run_public_policy
from hermes_skilleval.intervention.linked_context_study import read, functional_label
from hermes_skilleval.intervention.method_budget import tail_budget


def test_fixed_matrix_preserves_all_cells_and_seed():
    tasks = [{"instance_id": str(i), "mechanism": str(i)} for i in range(4)]
    cells = matrix(tasks)
    assert cells == matrix(tasks)
    assert len(cells) == 24
    assert len({(c["task_id"], c["arm"], c["repeat"]) for c in cells}) == 24
    assert {c["arm"] for c in cells} == {"N", "M", "R"}


def test_unknown_bounds_and_task_equal_weight():
    tasks = [{"instance_id": "t", "mechanism": "t"}]
    rows = [{**c, "functional": "PASS"} for c in matrix(tasks)]
    rows[next(i for i, r in enumerate(rows) if r["arm"] == "R")]["functional"] = (
        "UNKNOWN"
    )
    groups, contrasts = summarize_rows(tasks, rows)
    assert all(g["planned"] == 2 for g in groups)
    assert contrasts["R_minus_M"]["missing_bounds"] == [-0.5, 0.0]
    assert contrasts["R_minus_M"]["task_mean_difference"] is None
    assert contrasts["R_minus_M"]["task_counts"]["UNKNOWN"] == 1
    rows.pop()
    with pytest.raises(ValueError):
        summarize_rows(tasks, rows)


def test_public_adapter_fallback_independent_empty_stores(tmp_path, monkeypatch):
    from hermes_skilleval.intervention import relation_query_study

    # This invariant tests isolation/fallback, not the optional production tokenizer.
    monkeypatch.setattr(
        relation_query_study,
        "ExactSelector",
        partial(relation_query_study.ExactSelector, count_tokens=len),
    )
    ledger, pool, _ = fixture()
    features = build_features(ledger, pool, None)
    model = {"observations": [], "lifecycle": "reuse"}
    original = deepcopy(model)
    first = run_public_policy(ledger, pool, features, model, tmp_path / "r1")
    second = run_public_policy(ledger, pool, features, model, tmp_path / "r2")
    assert first["stop_reason"] == second["stop_reason"] == "NO_AFFORDABLE_BATCH"
    assert first["pack"]["units"] == second["pack"]["units"]
    assert first["seconds"] > 0 and second["seconds"] > 0
    assert model == original
    stores = [read(tmp_path / r / "store.json") for r in ("r1", "r2")]
    assert stores[0] == stores[1]
    assert all(r["record"]["state"] == "NOT_ANALYZED" for r in stores[0]["records"])
    with pytest.raises(FileExistsError):
        run_public_policy(ledger, pool, features, model, tmp_path / "r1")


def test_functional_and_cost_are_separate_no_refund():
    assert (
        functional_label(integrity="CONFIRMED", target="UNKNOWN", protected="FAIL")
        == "FAIL"
    )
    assert (
        functional_label(integrity="UNCONFIRMED", target="PASS", protected="PASS")
        == "UNKNOWN"
    )
    assert tail_budget("P", total=600, prefix=100, method_cost=75) == 425
    assert tail_budget("P", total=600, prefix=550, method_cost=75) == 0


def test_native_ready_runs_without_r_or_m(tmp_path, monkeypatch):
    from hermes_skilleval.intervention import diagnostic, study, repair_content_study
    from hermes_skilleval.intervention import repair_knowledge
    from hermes_skilleval.intervention.functional_closeout import run_study, sha
    from hermes_skilleval.intervention.relation_store import atomic_json

    output = tmp_path / "study"
    cp = tmp_path / "cp"
    atomic_json(cp / "checkpoint.json", {})
    atomic_json(
        output / "selection/t/N.json",
        {
            "status": "N_READY",
            "checkpoint": str(cp),
            "checkpoint_sha256": sha(cp / "checkpoint.json"),
            "prefix_remaining_seconds": 400,
            "N": {"message": None, "cost": 0},
        },
    )
    auth = tmp_path / "fake-auth"
    auth.touch()
    monkeypatch.setattr(repair_knowledge, "token_count", len)
    monkeypatch.setattr(diagnostic, "home_auth", lambda _: (tmp_path, auth))
    monkeypatch.setattr(repair_content_study, "verify_checkpoint", lambda _: {})
    started = []

    def run_once(task, dest, *args, **kwargs):
        started.append(dest.name)
        assert kwargs["initialization_seconds"] >= 0
        return {"status": "COMPLETED"}

    monkeypatch.setattr(study, "run_once", run_once)
    plan = {
        "tasks": [{"instance_id": "t", "mechanism": "test", "base_commit": "base"}],
        "image": "test",
        "plan_digest": "test",
    }
    run_study(plan, tmp_path, tmp_path, output, "tails")
    assert sorted(started) == ["N-r1", "N-r2"]
    assert not (output / "tails/t/R-r1/execution.json").exists()
    assert not (output / "tails/t/M-r1/execution.json").exists()
    assert (output / "pending/t/R-r1.json").exists()


def test_multiline_visible_source_is_not_json_escaped(tmp_path):
    from hermes_skilleval.intervention.functional_closeout import observed_behavior
    from hermes_skilleval.intervention.relation_store import atomic_json

    cp = tmp_path / "cp"
    atomic_json(
        cp / "checkpoint.json",
        {
            "visible_events": [
                {
                    "method": "item/completed",
                    "params": {"item": {"aggregatedOutput": "first line\nsecond line"}},
                }
            ]
        },
    )
    result = observed_behavior(
        tmp_path,
        {"task_id": "t", "arm": "R", "repeat": 1},
        {"checkpoint": str(cp)},
        {"pack": {"units": [{"unit_id": "u", "statement": "first line\nsecond line"}]}},
    )
    assert result["source_visibility"][0]["visibility"] == "already_visible_in_prefix"
