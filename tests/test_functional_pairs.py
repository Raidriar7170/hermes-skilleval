import pytest

from hermes_skilleval.intervention.functional_pairs import (
    paired_records,
    signal_summary,
    verify_collection_roster,
)


def sample(action, y, **extra):
    return {
        "task_id": "task",
        "state_id": "task:E1",
        "repeat": 1,
        "action": action,
        "y_functional": y,
        "binding_sha256": "binding",
        "candidates": ["skill"],
        "candidate_payloads": [{"id": "skill", "payload": "actual"}],
        "state": {"stage": "E1"},
        "file_policy_status": "PASS",
        **extra,
    }


def test_policy_change_is_zero_and_unknown_never_becomes_zero():
    pairs = paired_records(
        [
            sample("NO_INTERVENTION", 1),
            sample("skill", 1, file_policy_status="FAIL"),
            sample("GENERIC_REMINDER", None),
        ]
    )
    assert pairs[0]["delta_functional"] == 0
    assert pairs[0]["policy_only_transition"]
    assert pairs[0]["delta_vs_reminder"] is None
    assert pairs[1]["delta_functional"] is None
    assert (
        signal_summary(pairs, collection_complete=False)["status"]
        == "FUNCTIONAL_SIGNAL_UNRESOLVED"
    )


def test_shared_state_mismatch_rejected():
    with pytest.raises(ValueError, match="common state mismatch"):
        paired_records(
            [
                sample("NO_INTERVENTION", 0),
                sample("skill", 1, binding_sha256="different"),
            ]
        )


def test_damage_is_learnable_and_missing_baseline_is_unknown():
    pairs = paired_records([sample("NO_INTERVENTION", 1), sample("skill", 0)])
    assert pairs[0]["delta_functional"] == -1
    assert (
        signal_summary(pairs, collection_complete=True)["status"]
        == "FUNCTIONAL_ACTION_DIFFERENCE_OBSERVED"
    )
    pairs = paired_records([sample("skill", 1)])
    assert pairs[0]["delta_functional"] is None
    assert (
        signal_summary(pairs, collection_complete=True)["status"]
        == "FUNCTIONAL_SIGNAL_UNRESOLVED"
    )


def test_exact_roster_requires_unknown_samples_and_rejects_replacements():
    rows = [sample("NO_INTERVENTION", 1), sample("skill", None)]
    roster = {
        "source_protocol_sha256": "frozen",
        "realized_planned_tails": 2,
        "samples": rows,
    }
    verify_collection_roster(rows, roster, "frozen")
    partial = verify_collection_roster(
        rows[:1], roster, "frozen", require_complete=False
    )
    assert partial == {
        "realized_planned_tails": 2,
        "recorded_tails": 1,
        "missing_tails": 1,
        "complete": False,
    }
    for invalid in (
        rows[:1],
        rows + rows[:1],
        [rows[0], sample("unregistered-skill", None)],
        [rows[0], sample("skill", None, repeat=2)],
    ):
        with pytest.raises(ValueError, match="sample roster mismatch"):
            verify_collection_roster(invalid, roster, "frozen")
    with pytest.raises(ValueError, match="protocol mismatch"):
        verify_collection_roster(rows, roster, "changed")
    with pytest.raises(ValueError, match="sample roster mismatch"):
        verify_collection_roster(
            [sample("unregistered", None)], roster, "frozen", require_complete=False
        )
