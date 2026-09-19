import json

from hermes_skilleval.intervention.functional_panel import (
    select_checkpoint,
    delay_roster,
    immediate_action,
)


def test_checkpoint_preference_is_event_based_and_preserves_degenerate_state(tmp_path):
    paths = []
    for stage in ("E0", "E2", "E1"):
        p = tmp_path / stage
        p.mkdir()
        (p / "checkpoint.json").write_text(json.dumps({"state": {"stage": stage}}))
        paths.append(str(p))
    assert select_checkpoint({"checkpoints": paths}).name == "E1"
    assert select_checkpoint({"checkpoints": paths[:2]}).name == "E2"
    assert select_checkpoint({"checkpoints": paths[:1]}).name == "E0"
    assert select_checkpoint({"checkpoints": []}) is None


def test_delay_selection_does_not_depend_on_sensitive_or_successful_states():
    panels = [
        (
            str(i),
            {
                "delay_eligible": i != 1,
                "wait_sensitive": i == 5,
                "lock_sha256": str(i),
                "now_skill": "a",
            },
        )
        for i in range(7)
    ]
    roster = delay_roster(panels)
    assert len(roster) == 16
    assert {r["task_id"] for r in roster} == {"0", "2", "3", "4"}
    assert immediate_action(["b", "a"], {"b": 0.0, "a": -0.1}) == "NO_INTERVENTION"
    assert immediate_action(["b", "a"], {"b": 0.2, "a": 0.2}) == "b"
