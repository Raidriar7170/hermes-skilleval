from types import SimpleNamespace
import pytest
from hermes_skilleval.intervention.linked_context_study import (
    early_checkpoint,
    evaluate_tails,
)


def event(command, code=0, actions=()):
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "commandExecution",
                "command": command,
                "exitCode": code,
                "aggregatedOutput": "output",
                "commandActions": list(actions),
            }
        },
    }


def test_early_boundary_requires_actual_source_or_check_observation():
    state = SimpleNamespace(
        completed_turn_index=1, request="Fix lib/widget.py behavior"
    )
    assert (
        early_checkpoint(
            state,
            [],
            [event("ls lib/widget.py", actions=[{"type": "listFiles"}])],
            False,
        )
        is None
    )
    assert (
        early_checkpoint(state, [], [event("touch lib/widget.py; echo ok")], False)
        is None
    )
    assert (
        early_checkpoint(
            state,
            [],
            [event("cat lib/widget.py", code=1, actions=[{"type": "read"}])],
            False,
        )
        is None
    )
    assert (
        early_checkpoint(
            state, [], [event("cat lib/widget.py", actions=[{"type": "read"}])], False
        )
        == "E1"
    )
    assert early_checkpoint(state, [], [event("pytest test_widget.py")], False) == "E1"
    assert early_checkpoint(state, [], [], True) == "E2"


def test_hidden_evaluation_rejects_an_active_runner(tmp_path, monkeypatch):
    import hermes_skilleval.intervention.linked_context_study as study

    monkeypatch.setattr(study, "verify_frozen", lambda *args: None)
    (tmp_path / "tail-runner-active.json").write_text("{}")
    with pytest.raises(ValueError, match="active"):
        evaluate_tails({}, tmp_path, tmp_path, tmp_path, tmp_path)


def test_directory_alone_cannot_release_hidden_labels(tmp_path, monkeypatch):
    import json
    import hermes_skilleval.intervention.linked_context_study as study

    monkeypatch.setattr(study, "verify_frozen", lambda *args: None)
    (tmp_path / "selection-lock.json").write_text(
        json.dumps(
            {"plan_digest": "p", "cells": [{"task_id": "t", "arm": "N", "repeat": 1}]}
        )
    )
    (tmp_path / "tails" / "t" / "N-r1").mkdir(parents=True)
    with pytest.raises(ValueError, match="all planned attempts"):
        evaluate_tails({"plan_digest": "p"}, tmp_path, tmp_path, tmp_path, tmp_path)


def test_overlay_content_must_match_frozen_qualification(tmp_path, monkeypatch):
    import json
    import hermes_skilleval.intervention.linked_context_study as study

    monkeypatch.setattr(study, "verify_frozen", lambda *args: None)
    (tmp_path / "selection-lock.json").write_text(
        json.dumps({"plan_digest": "p", "cells": []})
    )
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "manifest.json").write_text("{}")
    plan = {
        "plan_digest": "p",
        "tasks": [{"instance_id": "t", "trusted_overlay_files": {}}],
    }
    with pytest.raises(ValueError, match="overlay differs"):
        evaluate_tails(plan, tmp_path, tmp_path, tmp_path, tmp_path)


def test_preprocessing_failure_preserves_prefix_without_fabricating_a_method(tmp_path):
    from hermes_skilleval.intervention.linked_context_study import (
        preprocessing_unavailable,
    )

    (tmp_path / "checkpoint.json").write_text("{}")
    state = preprocessing_unavailable("t", tmp_path, "Incomplete relation matrix")
    assert state["status"] == "UNAVAILABLE_PREPROCESS_FAILURE"
    assert state["checkpoint"] == str(tmp_path)
    assert state["packs"] == {} and not state["method_available"]
    assert state["remaining_after_common_charge"] is None
    assert set(state["messages"]) == {"N", "M-local", "H-sim", "H-link"}
    assert all(x is None for x in state["messages"].values())
