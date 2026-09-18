"""Contract checks, not substitutes for the real paired runtime study."""

import pytest

from hermes_skilleval.intervention.controller import Controller
from hermes_skilleval.intervention.session import public_only, inventory, snapshot
from hermes_skilleval.intervention.state import observe, opportunity, is_test_command
from hermes_skilleval.intervention.rollouts import utility


def test_versioned_checks_are_verified_at_their_explicit_root(tmp_path):
    import json
    from hermes_skilleval.intervention.records import verify_artifacts

    run = tmp_path / "retained-run"
    revised = tmp_path / "revised-checks"
    revised.mkdir()
    checks = {"policy": {"valid": True, "passed": False}}
    (revised / "acceptance.json").write_text(json.dumps({"checks": checks}))
    row = {
        "run": str(run),
        "checks_root": str(revised),
        "execution": {"status": "COMPLETED"},
        "quality": False,
        "checks": checks,
    }
    assert verify_artifacts(row)["status"] == "VERIFIED"
    row["checks"] = {"policy": {"valid": True, "passed": True}}
    with pytest.raises(ValueError, match="acceptance record mismatch"):
        verify_artifacts(row)


def test_public_usage_excludes_resumed_prefix_and_duplicate_updates(tmp_path):
    import json
    from hermes_skilleval.intervention.usage import reported_usage

    def usage(turn, total, last):
        def counter(n):
            return dict(
                totalTokens=n,
                inputTokens=n,
                cachedInputTokens=0,
                cacheWriteInputTokens=0,
                outputTokens=0,
                reasoningOutputTokens=0,
            )

        return {
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "fork",
                "turnId": turn,
                "tokenUsage": {"total": counter(total), "last": counter(last)},
            },
        }

    directory = tmp_path / "turn-001"
    directory.mkdir()
    events = [
        usage("prefix", 100, 20),
        {"method": "turn/started", "params": {"turn": {"id": "tail"}}},
        usage("tail", 110, 10),
        usage("tail", 110, 10),
        {"method": "turn/completed", "params": {"turn": {"id": "tail"}}},
    ]
    (directory / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
    result = reported_usage(tmp_path)
    assert result["tokens"]["totalTokens"] == 10
    assert result["request_updates"] == 1
    assert result["all_started_turns_completed_with_usage"]


def test_missing_runtime_cost_is_not_reported_as_zero():
    from hermes_skilleval.intervention.evaluate import summarize_rows

    rows = [
        {
            "method": "N0",
            "quality": quality,
            "utility": utility_value,
            "checks": {},
            "execution": {
                "status": status,
                "tail_seconds": seconds,
                "controller_overhead_seconds": None,
            },
        }
        for quality, utility_value, status, seconds in (
            (True, 0.99, "COMPLETED", 100),
            (None, None, "UNKNOWN_INTERRUPTED_ATTEMPT", None),
        )
    ]
    result = summarize_rows(rows)["N0"]
    assert result["runs"] == 2 and result["unknown"] == 1
    assert result["mean_active_seconds"] == 100
    assert result["active_seconds_measured_runs"] == 1
    assert result["overhead_measured_runs"] == 0


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


def test_unknown_labels_do_not_remove_real_wait_chain_states():
    from dataclasses import replace
    from hermes_skilleval.intervention.study import paired_rows

    class TextFixtureEncoder:
        def encode(self, text):
            return text

        def features(self, observation, no_state=False):
            return observation.stage

    class CatalogFixture:
        full_bodies = {"skill": "body"}

    rows = []
    for stage in ("E0", "E1", "E2"):
        observation = replace(state([]), stage=stage)
        for action in ("NO_INTERVENTION", "skill"):
            rows.append(
                {
                    "task_id": "task",
                    "split": "train",
                    "state_id": "task:" + stage,
                    "stage": stage,
                    "state": observation.to_dict(),
                    "repeat": 1,
                    "action": action,
                    "quality": None,
                    "utility": None,
                    "candidates": ["skill"],
                    "run": "not-executed-test-fixture",
                }
            )
    paired, chains, missing = paired_rows(
        rows,
        TextFixtureEncoder(),
        CatalogFixture(),
        split="train",
        native_status={"task": "EXECUTOR_ERROR"},
    )
    assert paired == [] and len(missing) == 3
    assert [r["stage"] for r in chains["task"]] == ["E0", "E1", "E2"]
    assert not chains["task"][1]["terminal_confirmed"]
    assert chains["task"][2]["terminal_confirmed"]


def test_final_uncertainty_clusters_repeats_by_task():
    from hermes_skilleval.intervention.report import final_comparisons

    rows = [
        {
            "task_id": task,
            "method": method,
            "repeat": repeat,
            "quality": True,
            "utility": 0.9 + (0.02 if method == "H-full" else 0),
        }
        for task in ("first", "second")
        for method in ("N0", "H-full")
        for repeat in (1, 2)
    ]
    result = final_comparisons(rows)["N0"]
    assert result["paired_runs"] == 4
    assert result["utility"]["independent_tasks"] == 2
    assert result["utility"]["mean"] == pytest.approx(0.02)


def test_failed_tool_with_null_output_is_observable_not_parser_failure():
    observation = state(
        [event("rg absent first.py", 1, None), event("rg other second.py", 1, None)]
    )
    assert observation.repeated_error_count == 1
    assert observation.failure_text is None
    assert not observation.public_test_failure_seen
    failed_test = state([event("pytest -q", 1, None)])
    assert failed_test.public_test_failure_seen
    assert opportunity(failed_test, ["E0"]) == "E1"


def test_scratch_snapshot_preserves_independent_fifo_nodes(tmp_path):
    import os
    from hermes_skilleval.intervention.session import clone_scratch

    source = tmp_path / "source"
    source.mkdir()
    os.mkfifo(source / "stream")
    clone_scratch(source, tmp_path / "first")
    clone_scratch(source, tmp_path / "second")
    assert (
        inventory(source)
        == inventory(tmp_path / "first")
        == inventory(tmp_path / "second")
    )
    assert (tmp_path / "first/stream").is_fifo()
    (tmp_path / "first/stream").unlink()
    assert (source / "stream").is_fifo() and (tmp_path / "second/stream").is_fifo()
