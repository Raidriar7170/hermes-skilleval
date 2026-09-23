from dataclasses import replace

import pytest

from test_evidence_linked_composition import fixture
from hermes_skilleval.intervention.relation_store import RelationStore


def test_mixed_rows_resume_and_immutable_semantics(tmp_path):
    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "store.json", ledger, pool)
    store.ingest(
        store.pairs, {"relations": [rows[0], {**rows[1], "applicable": 1}, rows[2]]}
    )
    assert [r["state"] for r in store.records.values()] == [
        "VALID_POSITIVE",
        "FORMAT_INVALID",
        "REJECTED_PROPOSAL",
    ]
    assert store.pending() == [store.pairs[1]]
    resumed = RelationStore(store.path, ledger, pool)
    resumed.ingest(
        store.pairs, {"relations": [{**r, "relation": "TOPICAL_ONLY"} for r in rows]}
    )
    assert [r["state"] for r in resumed.records.values()] == [
        "VALID_POSITIVE",
        "VALID_ZERO",
        "REJECTED_PROPOSAL",
    ]
    assert resumed.pending() == []
    assert resumed.bounds(store.pairs[2]) == (0, 1)
    assert len(resumed.events) == 3


def test_unknown_missing_late_and_input_change(tmp_path):
    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "store.json", ledger, pool)
    store.ingest(store.pairs[:2], {"rows": [[*store.pairs[0], "UNRESOLVED"]]})
    assert [r["state"] for r in store.records.values()] == [
        "SEMANTIC_UNRESOLVED",
        "TRANSPORT_MISSING",
        "NOT_ANALYZED",
    ]
    before = dict(store.records)
    store.ingest(store.pairs, {"relations": rows}, late=True)
    assert store.records == before
    assert store.pending() == store.pairs[1:]
    with pytest.raises(ValueError, match="identity"):
        RelationStore(store.path, ledger, pool, effort="high")
    changed = replace(
        pool,
        candidates=(
            replace(
                pool.candidates[0],
                unit=replace(pool.candidates[0].unit, statement="changed source"),
            ),
            *pool.candidates[1:],
        ),
    )
    with pytest.raises(ValueError, match="identity"):
        RelationStore(store.path, ledger, changed)


def test_322_of_336_are_preserved(tmp_path):
    ledger, pool, _ = fixture()
    req = ledger["requirements"][0]
    ledger = {
        **ledger,
        "requirements": [{**req, "requirement_id": str(i)} for i in range(14)],
    }
    pool = replace(
        pool,
        candidates=tuple(
            replace(
                pool.candidates[0],
                unit=replace(pool.candidates[0].unit, unit_id=str(i)),
            )
            for i in range(24)
        ),
    )
    store = RelationStore(tmp_path / "store.json", ledger, pool)
    store.ingest(
        store.pairs, {"rows": [[*p, "TOPICAL_ONLY"] for p in store.pairs[:322]]}
    )
    assert store.summary()["counts"] == {"VALID_ZERO": 322, "TRANSPORT_MISSING": 14}
    assert len(RelationStore(store.path, ledger, pool).pending()) == 14


def test_bad_ids_do_not_discard_neighbors(tmp_path):
    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "store.json", ledger, pool)
    store.ingest(
        store.pairs, {"relations": [{"requirement_id": [], "unit_id": {}}, rows[0]]}
    )
    assert store.records[store.pairs[0]]["state"] == "VALID_POSITIVE"
    assert len(store.events) == 1


def test_exact_bounds_and_dense_share_solver(tmp_path):
    from hermes_skilleval.intervention.anytime_relation_selector import ExactSelector
    from hermes_skilleval.intervention.linked_composition import objective

    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "store.json", ledger, pool)
    solver = ExactSelector(pool, ledger, token_budget=300, count_tokens=len)
    pack, before = solver.solve(store)
    assert pack == solver.mmr
    assert before["upper"] > before["lower"]
    store.ingest(store.pairs, {"relations": rows})
    pack, result = solver.solve(store)
    assert result["lower"] <= result["upper"]
    assert pack.tokens <= 300
    matrix = [
        [store.bounds((o.id, c.unit.unit_id))[0] for o in pool.obligations]
        for c in pool.candidates
    ]
    assert result["lower"] == max(
        objective(pool, ids, ledger["weights"], matrix)["total"]
        for ids in solver.feasible
    )
    assert solver.requests(store, result) == []
    store.ingest(store.pairs, {"relations": rows})
    assert solver.solve(store)[1] == result


def test_failed_stage_cost_persists_and_protocols_do_not_mix(tmp_path):
    from hermes_skilleval.intervention.method_budget import MethodBudget, tail_budget

    now = [10.0]
    b = MethodBudget(tmp_path / "cost.json", 60, identity="A", clock=lambda: now[0])
    with pytest.raises(RuntimeError):
        with b.stage("helper"):
            now[0] += 20
            raise RuntimeError("helper failed")
    assert b.remaining == 40
    resumed = MethodBudget(b.path, 60, identity="A")
    assert resumed.spent == 20
    assert tail_budget("P", total=600, prefix=100, method_cost=b.spent) == 480
    assert tail_budget("P", total=600, prefix=100, method_cost=0) == 500
    assert tail_budget("C", total=600, prefix=100, method_cost=b.spent) == 500


def test_acquisition_returns_baseline_when_helper_fails(tmp_path):
    from hermes_skilleval.intervention.anytime_acquisition import acquire

    ledger, pool, _ = fixture()

    def failed(*args, **kwargs):
        assert (tmp_path / "mmr.json").exists()
        raise RuntimeError("service unavailable")

    result = acquire(
        ledger, pool, tmp_path, seconds=10, count_tokens=len, helper=failed
    )
    assert result["stop_reason"] == "HELPER_UNAVAILABLE"
    assert result["pack"]["method"] == "M"
    assert result["relation_seconds"] > 0
    assert result["relations"]["counts"] == {"TRANSPORT_MISSING": 3}
    assert not (tmp_path / "active.json").exists()
    assert (
        acquire(ledger, pool, tmp_path, seconds=10, count_tokens=len, helper=failed)
        == result
    )


def test_zero_budget_returns_saved_mmr_without_calls(tmp_path):
    from hermes_skilleval.intervention.anytime_acquisition import acquire

    ledger, pool, _ = fixture()

    def forbidden(*args, **kwargs):
        raise AssertionError("must not call")

    result = acquire(
        ledger, pool, tmp_path, seconds=0, count_tokens=len, helper=forbidden
    )
    assert result["unique_requested"] == 0
    assert result["stop_reason"] == "TIME_BUDGET"
    assert result["relations"]["counts"] == {"NOT_ANALYZED": 3}


def test_hidden_table_replay_preserves_unknown(tmp_path):
    from hermes_skilleval.intervention.budgeted_relation_session import BATCH_PROMPT
    from hermes_skilleval.intervention.relation_reference import replay_table

    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "store.json", ledger, pool, prompt=BATCH_PROMPT)
    store.ingest(store.pairs[:1], {"relations": rows[:1]})
    result = replay_table(ledger, pool, store.path, points=(1, 3), count_tokens=len)
    assert result["model_calls"] == 0
    assert result["reference_coverage"]["counts"]["NOT_ANALYZED"] == 2
    for row in result["rows"]:
        assert row["reference_objective_upper"] >= row["reference_objective_lower"]
        if row["progress_point"] == 3:
            assert row["relations"]["counts"]["NOT_ANALYZED"] == 2


def test_changed_query_contract_rejected(tmp_path):
    from hermes_skilleval.intervention.anytime_acquisition import acquire

    ledger, pool, _ = fixture()
    acquire(ledger, pool, tmp_path, seconds=0, count_tokens=len)
    with pytest.raises(ValueError, match="contract"):
        acquire(ledger, pool, tmp_path, seconds=0, strategy="S", count_tokens=len)


def test_all_requirements_must_enter_objective():
    from hermes_skilleval.intervention.anytime_relation_selector import ExactSelector

    ledger, pool, _ = fixture()
    with pytest.raises(ValueError, match="domain"):
        ExactSelector(pool, {**ledger, "requirements": []}, count_tokens=len)


def test_crash_after_partial_rows_resumes_without_resampling(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    from hermes_skilleval.intervention.anytime_acquisition import acquire

    script = r"""
import os,sys
from pathlib import Path
from test_evidence_linked_composition import fixture
from hermes_skilleval.intervention.anytime_acquisition import acquire
from hermes_skilleval.intervention.relation_store import RelationStore
from hermes_skilleval.intervention.budgeted_relation_session import BATCH_PROMPT
ledger,pool,_=fixture()
root=Path(sys.argv[1])
def crash(ledger,pool,pairs,*args,**kwargs):
    store=RelationStore(root/'relations.json',ledger,pool,prompt=BATCH_PROMPT)
    store.ingest(pairs[:1],{'rows':[[*pairs[0],'TOPICAL_ONLY']]})
    os._exit(19)
acquire(ledger,pool,root,seconds=30,count_tokens=len,helper=crash)
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(Path("src").resolve())
        + os.pathsep
        + str(Path("tests").resolve()),
    }
    child = subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env)
    assert child.returncode == 19
    ledger, pool, _ = fixture()
    from hermes_skilleval.intervention.budgeted_relation_session import BATCH_PROMPT

    stored = RelationStore(
        tmp_path / "relations.json", ledger, pool, prompt=BATCH_PROMPT
    )
    accepted = {p for p, r in stored.records.items() if r["state"] == "VALID_ZERO"}
    assert len(accepted) == 1

    def finish(ledger, pool, pairs, *args, **kwargs):
        assert not accepted.intersection(pairs)
        return {"rows": [[*p, "TOPICAL_ONLY"] for p in pairs]}

    result = acquire(
        ledger, pool, tmp_path, seconds=30, count_tokens=len, helper=finish
    )
    assert result["relations"]["counts"] == {"VALID_ZERO": 3}
    import json

    costs = json.loads((tmp_path / "budget.json").read_text())["stages"]
    assert any(s.get("cost_status") == "CONSERVATIVE_CHARGE" for s in costs)


def test_truncated_json_keeps_complete_rows():
    from hermes_skilleval.intervention.budgeted_relation_session import (
        parse_relation_response,
    )

    value = parse_relation_response('{"rows": [["r", "u", "TOPICAL_ONLY"], ["r",')
    assert value["rows"] == [["r", "u", "TOPICAL_ONLY"]]
    assert value["transport_status"] == "PARTIAL_JSON_PREFIX"


def test_runner_recovery_preserves_partial_cell(tmp_path, monkeypatch):
    import os
    import subprocess
    from hermes_skilleval.intervention.budgeted_context_study import (
        reconcile_runner,
        matrix,
        cell_path,
    )
    from hermes_skilleval.intervention.relation_store import atomic_json

    plan = {"order_seed": 1, "tasks": [{"instance_id": "task"}], "tail_repeats": 2}
    cell = matrix(plan)[0]
    partial = cell_path(tmp_path, cell)
    partial.mkdir(parents=True)
    (partial / "candidate.txt").write_text("original partial candidate")
    atomic_json(tmp_path / "runner-active.json", {"pid": 99999999, "phase": "P"})

    def dead(pid, signal):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", dead)
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: "")
    reconcile_runner(tmp_path, plan)
    import json

    assert (
        json.loads((partial / "execution.json").read_text())["status"]
        == "UNKNOWN_INTERRUPTED_ATTEMPT"
    )
    assert (partial / "candidate.txt").read_text() == "original partial candidate"
    assert not (tmp_path / "runner-active.json").exists()
    assert sum(cell_path(tmp_path, c).exists() for c in matrix(plan)) == 1


def test_report_separates_unproven_budget_from_functional_pass(tmp_path):
    from hermes_skilleval.intervention.budgeted_context_study import report
    from hermes_skilleval.intervention.relation_store import atomic_json

    atomic_json(
        tmp_path / "functional-results.json",
        {
            "planned": 1,
            "rows": [
                {
                    "task_id": "t",
                    "protocol": "P",
                    "arm": "A",
                    "repeat": 1,
                    "integrity": "CONFIRMED",
                    "target": "PASS",
                    "protected": "PASS",
                }
            ],
        },
    )
    atomic_json(
        tmp_path / "selection/t/selection.json",
        {"costs": {"A": 40}, "prefix_remaining_seconds": 400},
    )
    row = report(tmp_path)["rows"][0]
    assert row["functional"] == "PASS"
    assert row["strict_functional"] == "UNKNOWN"
    assert row["budget_status"] == "UNKNOWN"
