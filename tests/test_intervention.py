"""Contract checks, not substitutes for the real paired runtime study."""

import pytest

from hermes_skilleval.intervention.controller import Controller
from hermes_skilleval.intervention.session import public_only, inventory, snapshot
from hermes_skilleval.intervention.state import observe, opportunity, is_test_command
from hermes_skilleval.intervention.rollouts import utility


def event(command, exit_code, output=""):
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "commandExecution",
                "command": command,
                "exitCode": exit_code,
                "aggregatedOutput": output,
            }
        },
    }


def state(events):
    return observe(
        request="repair",
        repo_facts="python",
        stage="E0",
        turn_index=1,
        remaining=400,
        total=600,
        events=events,
    )


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "python -m pytest tests",
        '/usr/bin/bash -lc "python -m pytest -q"',
        "uv run pytest",
        "cd src && pytest",
    ],
)
def test_real_public_test_commands(command):
    assert is_test_command(command)


@pytest.mark.parametrize(
    "command", ["rg pytest missing_dir", "cat test_pytest.py", "echo pytest"]
)
def test_mentions_are_not_test_executions(command):
    assert not is_test_command(command)


def test_first_failed_test_survives_later_success_within_boundary():
    s = state([event("pytest -q", 1, "failed"), event("pytest -q", 0, "passed")])
    assert s.public_test_exit == 0
    assert opportunity(s, ["E0"]) == "E1"


def test_missing_tests_and_monotone_opportunities():
    s = state([event("rg pytest missing_dir", 2, "not found")])
    assert s.public_test_exit is None and s.observed_pass_count is None
    assert opportunity(s, ["E0"]) is None
    assert opportunity(s, ["E0", "E1"], candidate_complete=True) == "E2"
    assert opportunity(s, ["E0", "E2"]) is None


def test_waiting_and_exactly_one_injection():
    c = Controller("H-full")
    assert c.decide("E0", ["a"], {"a": 0.1}, 0.2)["action"] == "WAIT"
    assert c.decide("E1", ["a"], {"a": 0.3}, 0.1)["action"] == "INJECT"
    assert c.decide("E2", ["a"], {"a": 1}, 0, False)["action"] == "CONTINUE"
    assert c.remaining_interventions == 0


def test_noop_and_unavailable_are_different():
    c = Controller("H-full")
    assert (
        c.decide("E2", ["a"], {"a": -0.1}, 0, False)["reason"] == "NOOP_MODEL_DECISION"
    )
    assert c.decide("E0", ["a"])["reason"] == "METHOD_UNAVAILABLE"


def test_rule_keeps_dynamic_top_when_it_equals_static_top():
    c = Controller("R1")
    assert (
        c.decide("E1", ["same-top", "second"], dynamic_top="same-top")["skill_id"]
        == "same-top"
    )


def test_nested_reasoning_is_not_persisted():
    raw = {
        "result": {
            "thread": {
                "turns": [
                    {
                        "items": [
                            {"type": "reasoning", "content": "private"},
                            {"type": "agentMessage", "text": "public"},
                        ]
                    }
                ]
            }
        }
    }
    assert public_only(raw)["result"]["thread"]["turns"][0]["items"] == [
        {"type": "agentMessage", "text": "public"}
    ]


def test_snapshot_never_follows_links_and_requires_stopped_boundary(tmp_path):
    source = tmp_path / "source"
    scratch = tmp_path / "scratch"
    source.mkdir()
    scratch.mkdir()
    (source / "text").write_text("v1")
    (source / "link").symlink_to("/outside/not-readable")
    with pytest.raises(ValueError, match="live tools"):
        snapshot(source, scratch, tmp_path / "bad", {})
    snapshot(source, scratch, tmp_path / "cp", {"no_running_tool_confirmation": True})
    (source / "text").write_text("v2")
    assert (tmp_path / "cp/source/text").read_text() == "v1"
    assert inventory(tmp_path / "cp/source")["link"] == "symlink:/outside/not-readable"


def test_quality_dominates_cost_and_unknown_stays_unknown():
    assert utility(True, 600, 600, 1200) > utility(False, 600, 0, 0)
    assert utility(None, 600, 10, 0) is None
    assert utility(True, 600, 300, 600) == pytest.approx(0.965)


def test_completion_is_schema_value_not_prose():
    from hermes_skilleval.intervention.rollouts import task_complete
    import json

    def events(status, summary):
        return [
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "type": "agentMessage",
                        "phase": "final_answer",
                        "text": json.dumps(
                            {"segment_status": status, "summary": summary}
                        ),
                    }
                },
            }
        ]

    assert not task_complete(events("CONTINUE", "Do not mark TASK_COMPLETE yet"))
    assert task_complete(events("TASK_COMPLETE", "Candidate ready"))
    assert not task_complete([])
