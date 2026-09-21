from dataclasses import replace
import pytest
from hermes_skilleval.intervention.evidence_linked_state import (
    analyze,
    observations,
    request_ledger,
    requirement_weights,
)


def event(command, output="", code=0):
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "commandExecution",
                "command": command,
                "aggregatedOutput": output,
                "exitCode": code,
                "status": "completed",
            }
        },
    }


def test_full_requirements_and_spans():
    request = (
        "## Public requirements\n"
        + "\n\n".join(
            f"- Requirement {i} must preserve lists and dictionaries unless empty, not both options."
            for i in range(12)
        )
        + "\n## Public interface\nNo new interface."
    )
    rows, unresolved = request_ledger(request)
    assert len(rows) == 13
    assert all("unless empty, not both" in r.expected_text for r in rows[:12])
    spans = [r.verbatim_span for r in rows] + [r["span"] for r in unresolved]
    covered = {i for s in spans for i in range(s["start"], s["end"])}
    assert all(i in covered for i, c in enumerate(request) if not c.isspace())
    single = requirement_weights(rows[:1])
    split = requirement_weights([rows[0], replace(rows[0], requirement_id="child")])
    assert sum(split.values()) == sum(single.values()) == 1


def test_environment_never_creates_obligation_and_other_pass_does_not_clear():
    events = [
        event(
            "python -m pytest a.py",
            "python: error while loading shared libraries: libpython.so",
            127,
        ),
        event("python -m pytest b.py", "1 passed"),
    ]
    result = analyze(
        "## Public requirements\n- Must preserve mapping entries.",
        events,
        checkpoint_event_count=2,
        initial_source_version="base",
    )
    assert len(result["requirements"]) == 1
    assert result["requirements"][0]["status"] == "unverified"
    assert result["observations"][0]["kind"] == "ENV_TOOL_FAILURE"
    assert result["observations"][0]["lifecycle"] == "current"
    assert result["environment_functional_weight"] == 0


def test_same_scope_and_source_supersedes_but_change_stales():
    events = [
        event("python -m pytest a.py", "AssertionError: wrong", 1),
        event("python -m pytest a.py", "1 passed"),
    ]
    rows = observations(events, checkpoint_event_count=2, initial_source_version="base")
    assert rows[0].lifecycle == "superseded"
    events.append(
        {
            "method": "item/completed",
            "params": {
                "item": {
                    "type": "fileChange",
                    "status": "completed",
                    "changes": [{"path": "a.py"}],
                }
            },
        }
    )
    rows = observations(events, checkpoint_event_count=3, initial_source_version="base")
    assert rows[1].lifecycle == "historical_unresolved"


def test_assertion_not_swallowed_by_environment_words():
    e = event(
        "pytest test_x.py", "AssertionError: expected message 'command not found'", 1
    )
    assert observations([e], checkpoint_event_count=1)[0].kind == "FUNCTIONAL_ASSERTION"


def test_environment_requirement_and_grounded_functional_assertion():
    request = "## Public requirements\n- Missing library must produce a helpful error."
    events = [event("pytest test_x.py", "AssertionError: missing helpful error", 1)]
    reqs, _ = request_ledger(request)
    link = {
        "requirement_id": reqs[0].requirement_id,
        "observation_id": "event-0",
        "requirement_quote": "Missing library",
        "observation_quote": "missing helpful error",
        "relation": "CONTRADICTS",
        "coverage_basis": "public assertion on required error",
    }
    result = analyze(
        request,
        events,
        checkpoint_event_count=1,
        links=[link],
        initial_source_version="base",
    )
    assert result["requirements"][0]["status"] == "contradicted"
    link["observation_quote"] = "fabricated"
    with pytest.raises(ValueError, match="Ungrounded"):
        analyze(request, events, checkpoint_event_count=1, links=[link])


def test_future_events_rejected_and_missing_source_no_supersession():
    events = [event("pytest a.py", "AssertionError", 1), event("pytest a.py", "pass")]
    with pytest.raises(ValueError, match="future"):
        observations(events, checkpoint_event_count=1)
    assert observations(events, checkpoint_event_count=2)[0].lifecycle == "unknown"


def test_interface_fields_grouped_and_runtime_metadata_not_weighted():
    request = "## Public interface\n1. Type: Class\n\nName: State\n\nPath: state.py\n\nDescription: must preserve names.\n\nShared environment: optional docs available.\n"
    rows, unresolved = request_ledger(request)
    assert len(rows) == 1
    assert (
        "Name: State" in rows[0].expected_text
        and "Description:" in rows[0].expected_text
    )
    assert any(r["reason"] == "execution_context" for r in unresolved)


def test_nested_bullet_representation_does_not_inflate_parent_weight():
    nested = "## Public requirements\n- Preserve contents:\n  - lists remain lists\n  - dictionaries remain dictionaries\n- Other behavior must remain unchanged."
    rows, _ = request_ledger(nested)
    assert len(rows) == 2
    assert list(requirement_weights(rows).values()) == [0.5, 0.5]
    assert "lists remain lists" in rows[0].expected_text


def test_unobserved_shell_write_stales_previous_pass():
    events = [
        event("pytest a.py", "1 passed"),
        event("python -c \"open('a.py','w').write('changed')\"", ""),
    ]
    rows = observations(events, checkpoint_event_count=2, initial_source_version="base")
    assert rows[0].lifecycle == "historical_unresolved"
    assert rows[1].source_version is None and rows[1].lifecycle == "unknown"


@pytest.mark.parametrize(
    "command",
    [
        "pytest a.py; echo broken > a.py",
        "bash -lc 'pytest a.py && touch a.py'",
        "cat a.py; rm a.py",
    ],
)
def test_compound_command_cannot_preserve_source_generation(command):
    changed = event(command, "1 passed")
    changed["params"]["item"]["commandActions"] = [{"type": "read"}]
    rows = observations(
        [event("pytest a.py", "1 passed"), changed],
        checkpoint_event_count=2,
        initial_source_version="base",
    )
    assert rows[0].lifecycle == "historical_unresolved"
    assert rows[1].source_version is None
    assert rows[1].lifecycle == "unknown"
