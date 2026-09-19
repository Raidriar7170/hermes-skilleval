"""Counterexample fixtures; these numbers are not research results."""

from copy import deepcopy

from hermes_skilleval.intervention.functional_policy import METHODS
from hermes_skilleval.intervention.functional_report import functional_main_table


def fixture():
    roster = [
        {"task_id": t, "method": m, "repeat": r}
        for t in ("a", "b")
        for m in METHODS
        for r in (1, 2)
    ]
    return (
        roster,
        [
            {
                **r,
                "y_functional": 1,
                "file_policy_status": "PASS",
                "qualified_delivery": 1,
                "execution": {"tail_seconds": 100},
            }
            for r in roster
        ],
        {"a": "family-a", "b": "family-b"},
    )


def test_policy_or_cost_alone_can_never_trigger_functional_gain():
    roster, rows, families = fixture()
    original = functional_main_table(rows, roster, families)
    changed = deepcopy(rows)
    for row in changed:
        if row["method"] == "N0-v2":
            row.update(
                file_policy_status="FAIL",
                qualified_delivery=0,
                execution={"tail_seconds": 600},
            )
        else:
            row["execution"]["tail_seconds"] = 1
    assert functional_main_table(changed, roster, families) == original
    assert original["functional_gain_claim"] == "NOT_ESTABLISHED"


def test_missing_repeat_preserves_planned_denominator_and_excludes_incomplete_task():
    roster, rows, families = fixture()
    rows = [
        r
        for r in rows
        if not (r["task_id"] == "a" and r["method"] == "H-full-v2" and r["repeat"] == 2)
    ]
    report = functional_main_table(rows, roster, families)
    assert report["table"]["H-full-v2"]["planned"] == 4
    assert report["table"]["H-full-v2"]["unknown_or_missing"] == 1
    assert report["comparisons"]["N0-v2"]["complete_paired_tasks"] == 1
    assert report["functional_gain_claim"] == "INCONCLUSIVE"


def test_delayed_success_without_sensitive_state_cannot_claim_wait_head_value():
    from hermes_skilleval.intervention.functional_report import mechanism_tables

    lock = {
        "action_roster": [
            {"repeat": r, "action": a}
            for r in (1, 2)
            for a in ("NO_INTERVENTION", "skill", "GENERIC_REMINDER")
        ],
        "methods": {
            m: {"immediate_gain_action": "skill"}
            for m in ("H-full-v2", "H-task-fixedC-v2", "P1-v2")
        },
        "state": {"stage": "E1"},
        "representation_identifiable": True,
        "binding": {"candidates": [{"id": "skill"}]},
        "now_skill": "skill",
        "wait_sensitive": False,
    }
    panel = [
        {"task_id": "task", **sample, "y_functional": 0}
        for sample in lock["action_roster"]
    ]
    roster = [
        {"task_id": "task", "repeat": r, "action": a}
        for r in (1, 2)
        for a in ("DEFER_SAME-v2", "WAIT_THEN_FULL-v2")
    ]
    delayed = [
        {
            **sample,
            "y_functional": 1,
            "execution": {"injected": True, "decisions": [{"stage": "E2"}]},
        }
        for sample in roster
    ]
    result = mechanism_tables(
        panel, delayed, [("task", lock)], {"task": "family"}, roster
    )
    assert result["waiting_incremental_claim"] == "NOT_IDENTIFIABLE"
    assert (
        result["timing_effects"]["WAIT_THEN_FULL-v2"]["all_selected"]["effect"]["mean"]
        == 1
    )
    assert result["state_incremental_claim"] == "NOT_ESTABLISHED"


def test_same_count_of_wrong_panel_samples_is_not_complete():
    import pytest
    from hermes_skilleval.intervention.functional_report import mechanism_tables

    lock = {"action_roster": [{"repeat": 1, "action": "NO_INTERVENTION"}]}
    rows = [
        {"task_id": "task", "repeat": 1, "action": "unregistered", "y_functional": 1}
    ]
    with pytest.raises(ValueError, match="unregistered common-panel"):
        mechanism_tables(rows, [], [("task", lock)], {"task": "family"}, [])
