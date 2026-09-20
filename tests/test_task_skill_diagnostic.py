"""Synthetic contract tests only; these are not research execution evidence."""

import json
from types import SimpleNamespace

import pytest

from hermes_skilleval.intervention.diagnostic import (
    acceptance_audit,
    compare_state,
    counts,
    freeze_roster,
    select_panel,
    visible_opportunity,
)

from hermes_skilleval.intervention.functional_outcomes import outcomes
from hermes_skilleval.intervention.study import run_once


def test_overconstrained_acceptance_never_establishes_failure_alone(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    junit = target / "junit.xml"
    junit.write_text(
        '<testsuite><testcase name="test_extract_strict_any_rejects_non_strict_lookup"><failure>Regex pattern did not match</failure></testcase></testsuite>'
    )
    row = {
        "task_id": "sqlite-utils-diagnostic-fcfccea",
        "y_functional": 0,
        "y_regression": 1,
        "checks_root": str(tmp_path),
    }
    audit = acceptance_audit(row)
    assert audit["raw_y_functional"] == 0
    assert audit["interpretable_y_functional"] is None
    assert row["y_functional"] == 0
    junit.write_text(
        '<testsuite><testcase name="test_extract_strict_any_rejects_non_strict_lookup"><failure>DID NOT RAISE</failure></testcase></testsuite>'
    )
    assert acceptance_audit(row)["interpretable_y_functional"] == 0
    junit.write_text(
        '<testsuite><testcase name="test_real_data_loss"><failure>Data lost</failure></testcase></testsuite>'
    )
    assert acceptance_audit(row)["interpretable_y_functional"] == 0
    assert (
        acceptance_audit({**row, "y_functional": None})["interpretable_y_functional"]
        is None
    )
    assert (
        acceptance_audit({**row, "y_functional": 1})["interpretable_y_functional"] == 1
    )


def event(text, command="python -m pytest tests/test_transform.py", code=1):
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "commandExecution",
                "command": command,
                "exitCode": code,
                "aggregatedOutput": text,
            }
        },
    }


def test_visible_checkpoint_uses_functional_public_evidence_not_infrastructure():
    s = SimpleNamespace(remaining_seconds=100)
    assert visible_opportunity(s, [], [], False, ("transform",)) == "E0"
    assert (
        visible_opportunity(
            s, ["E0"], [event("No module named pytest")], False, ("transform",)
        )
        is None
    )
    assert (
        visible_opportunity(
            s,
            ["E0"],
            [event("AssertionError: transform data lost")],
            False,
            ("transform",),
        )
        == "E1"
    )
    assert (
        visible_opportunity(
            s,
            ["E0"],
            [event("AssertionError: unrelated", command="python unrelated.py")],
            False,
            ("transform",),
        )
        is None
    )
    assert visible_opportunity(s, ["E0"], [], False, ("transform",)) is None
    assert visible_opportunity(s, ["E0"], [], True, ("transform",)) == "E2"


def cp(tmp_path, name, remaining=150, stage="E1"):
    p = tmp_path / name
    p.mkdir()
    (p / "checkpoint.json").write_text(
        json.dumps(
            {
                "state": {"stage": stage},
                "remaining_seconds": remaining,
                "thread_id": "public-parent",
                "last_turn_id": "finished",
            }
        )
    )
    return str(p)


def test_panel_uses_task_and_repeat_order_not_severity_or_successful_skill(tmp_path):
    rows = []
    tasks = []
    for i, ys in enumerate([(0, 1), (1, 1), (0, 0), (0, 1), (0, 0)]):
        tid = str(i)
        tasks.append({"task_id": tid})
        for r, y in enumerate(ys, 1):
            rows.append(
                {
                    "task_id": tid,
                    "repeat": r,
                    "y_functional": y,
                    "execution": {
                        "checkpoints": [
                            cp(
                                tmp_path,
                                tid + str(r),
                                remaining=89 if (i, r) == (0, 1) else 120,
                            )
                        ]
                    },
                }
            )
    panel = select_panel(tasks, rows)
    assert [s["task_id"] for s in panel["states"]] == ["0", "2", "3", "1"]
    assert panel["states"][0]["checkpoint"].endswith("02")
    assert panel["states"][-1]["stratum"] == "native_success_control"


def test_native_all_pass_stops_but_unknown_does_not(tmp_path):
    task = [{"task_id": "a"}]
    c = cp(tmp_path, "a")
    rows = [
        {
            "task_id": "a",
            "repeat": r,
            "y_functional": 1,
            "execution": {"checkpoints": [c]},
        }
        for r in (1, 2)
    ]
    assert select_panel(task, rows) == {
        "status": "NO_NATIVE_FAILURE_OBSERVED",
        "states": [],
    }
    rows[0]["y_functional"] = None
    assert select_panel(task, rows)["status"] != "NO_NATIVE_FAILURE_OBSERVED"


def test_tail_comparison_never_uses_screening_label_or_cost():
    rows = [
        {
            "arm": a,
            "repeat": r,
            "y_functional": 1,
            "native_y_functional": 0,
            "tokens": 100 if a == "K" else 900,
        }
        for a in ("N", "G", "K")
        for r in (1, 2)
    ]
    result = compare_state(rows)
    assert result["K_minus_N"]["observed_difference"] == 0
    assert result["K_minus_G"]["transitions"] == ["tie_pass", "tie_pass"]
    rows[-1]["y_functional"] = None
    result = compare_state(rows)
    assert result["arms"]["K"]["unknown"] == 1
    assert result["K_minus_N"]["observed_difference"] is None
    assert counts([1, None], 2)["rate_bounds"] == [0.5, 1.0]
    with pytest.raises(ValueError, match="duplicate"):
        compare_state(rows + [rows[0]])


def test_no_skill_roster_has_no_fake_k_success():
    selection = [
        {"task_id": "a", "skill_id": None},
        {"task_id": "b", "skill_id": "sqlite-schema"},
    ]
    roster = freeze_roster(selection, 3)
    assert roster == freeze_roster(selection, 3)
    assert len(roster) == 10
    assert {r["arm"] for r in roster if r["task_id"] == "a"} == {"N", "G"}


def test_existing_execution_and_interruption_never_resample(tmp_path, monkeypatch):
    import hermes_skilleval.intervention.study as study

    monkeypatch.setattr(study, "execute", lambda *a, **k: pytest.fail("resampled"))
    p = tmp_path / "done"
    p.mkdir()
    saved = {"status": "COMPLETED", "thread_id": "recorded"}
    (p / "execution.json").write_text(json.dumps(saved))
    assert run_once(None, p, None, None) == saved
    q = tmp_path / "interrupted"
    q.mkdir()
    assert run_once(None, q, None, None)["status"] == "UNKNOWN_INTERRUPTED_ATTEMPT"


def test_functional_labels_ignore_policy_and_cost_require_guidance_exposure():
    e = {
        "status": "COMPLETED",
        "thread_id": "actual",
        "injected": True,
        "model_input_observed": True,
        "tail_seconds": 1,
    }
    checks = {
        k: {"valid": True, "passed": True} for k in ("target", "regression", "policy")
    }
    assert outcomes(e, checks, integrity="VERIFIED")["y_functional"] == 1
    checks["policy"]["passed"] = False
    e["tail_seconds"] = 999
    assert outcomes(e, checks, integrity="VERIFIED")["y_functional"] == 1
    e["model_input_observed"] = False
    assert outcomes(e, checks, integrity="VERIFIED")["y_functional"] is None


def test_no_supported_skill_is_not_two_unknown_k_samples():
    rows = [
        {"arm": a, "repeat": r, "y_functional": 1} for a in ("N", "G") for r in (1, 2)
    ]
    result = compare_state(rows, has_skill=False)
    assert result["arms"]["K"]["planned"] == 0
    assert result["arms"]["K"]["unknown"] == 0
    assert result["K_minus_N"]["status"] == "NOT_TESTED"


def test_e1_tail_under_150_uses_delivery_checkpoint_not_legacy_threshold(
    tmp_path, monkeypatch
):
    from hermes_skilleval.intervention import rollouts
    from hermes_skilleval.intervention.session import snapshot
    from hermes_skilleval.intervention.state import observe, prefix_digest

    task = tmp_path / "task"
    task.mkdir()
    (task / "base").mkdir()
    (task / "base/a.py").write_text("value = 1\n")
    (task / "request.txt").write_text("repair transform")
    (task / "task.json").write_text(json.dumps({"profile": {"packages": {"a": "."}}}))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    state = observe(
        request="repair transform",
        repo_facts="a",
        stage="E1",
        turn_index=1,
        remaining=120,
        total=600,
        events=[],
    )
    checkpoint = snapshot(
        task / "base",
        scratch,
        tmp_path / "cp",
        {
            "no_running_tool_confirmation": True,
            "thread_id": "parent",
            "last_turn_id": "boundary",
            "visible_prefix_sha256": prefix_digest([]),
            "visible_events": [],
            "state": state.to_dict(),
            "remaining_seconds": 120,
            "total_seconds": 600,
        },
    )
    calls = []

    class FakeSession:
        def __init__(self, *args, **kwargs):
            self.events = []
            self.thread_id = "fork"
            self.last_turn_id = None
            calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def fork(self, *args):
            return {"thread": {"turns": []}}

        def resume(self, *args):
            return {}

        def turn(self, text, remaining):
            assert 0 < remaining <= 120
            self.last_turn_id = "tail-" + str(len(calls))
            self.events = [
                {
                    "method": "item/completed",
                    "params": {
                        "item": {
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": json.dumps(
                                {
                                    "segment_status": "CONTINUE"
                                    if len(calls) == 1
                                    else "TASK_COMPLETE",
                                    "summary": "synthetic contract fixture only",
                                }
                            ),
                        }
                    },
                }
            ]
            return {"status": "completed"}

        def rpc(self, *args):
            return {"thread": {"turns": []}}

    monkeypatch.setattr(rollouts, "Session", FakeSession)
    result = rollouts.execute(
        task,
        tmp_path / "run",
        tmp_path / "home",
        tmp_path / "skills",
        from_checkpoint=checkpoint,
        public_docs=tmp_path / "docs",
        checkpoint_selector=lambda s, seen, e, done: visible_opportunity(
            s, seen, e, done, ("transform",)
        ),
    )
    assert result["status"] == "COMPLETED"
    assert len(calls) == 3  # CONTINUE, first delivery, then neutral E2 continuation
    assert result["initial_remaining"] == 120
    assert all(c["public_docs"] == tmp_path / "docs" for c in calls)
    assert [p.split("/")[-1] for p in result["checkpoints"]] == ["E2"]
