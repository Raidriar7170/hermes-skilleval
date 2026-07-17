from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner


PREFIX = "TEST_ONLY_DO_NOT_USE"


def _opaque_candidate_id() -> str:
    return runner.opaque_candidate_id(1, "test-skill-00", 0, "a" * 64)


def _skills() -> list[dict[str, Any]]:
    return [
        {
            "id": f"test-skill-{index:02d}",
            "name": f"Test Skill {index:02d}",
            "category": "test-only",
            "description": f"{PREFIX} DESCRIPTION {index:02d}",
            "trigger_terms": [f"test-trigger-{index:02d}"],
            "body": f"{PREFIX} BODY {index:02d}",
        }
        for index in range(16)
    ]


def _authoritative_skills() -> list[dict[str, Any]]:
    repository = Path(__file__).resolve().parents[1]
    raw = json.loads(
        (
            repository / "docs/demo/phase9-real-skill-library-migration/skills.json"
        ).read_text(encoding="utf-8")
    )
    assert type(raw) is list
    return cast(list[dict[str, Any]], raw)


def _agent_contract_generator_request() -> dict[str, Any]:
    return runner.build_generator_request(
        _skills(),
        gold_skill_id="test-skill-00",
        negative_quota=2,
        positive_only_quota=1,
        round_number=1,
    )


def _agent_contract_generator_response() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "candidate_index": index,
                "prompt_text": f"{PREFIX} AGENT REQUEST {index}",
                "semantic_family_id": f"{PREFIX}_AGENT_FAMILY_{index}",
                "proposed_gold_skill_id": "test-skill-00",
                "proposed_negative_skill_id": ("test-skill-01" if index < 2 else None),
                "language": "en",
                "rationale": f"{PREFIX} AGENT RATIONALE {index}",
            }
            for index in range(3)
        ]
    }


def _agent_contract_reviewer_request(
    role: str = "reviewer_a",
) -> dict[str, Any]:
    return runner.build_reviewer_request(
        {
            "candidate_id": _opaque_candidate_id(),
            "prompt_text": f"{PREFIX} REVIEW REQUEST",
            "proposed_gold_skill_id": "test-skill-00",
            "proposed_negative_skill_id": "test-skill-01",
            "rationale": f"{PREFIX} HIDDEN RATIONALE",
        },
        _skills(),
        role=role,
    )


def _agent_contract_reviewer_response() -> dict[str, Any]:
    return {
        "decision": "ACCEPT",
        "reviewed_gold_skill_id": "test-skill-00",
        "reviewed_negative_skill_id": "test-skill-01",
        "natural": True,
        "single_primary_skill": True,
        "no_label_leakage": True,
        "negative_confusable": True,
        "confidence": "HIGH",
        "reason": f"{PREFIX} REVIEW REASON",
    }


def _agent_contract_envelope(
    request: dict[str, Any],
    response: dict[str, Any],
    *,
    session_id: str = "fresh-session-001",
) -> dict[str, Any]:
    config = runner.AGENT_CONFIGS[request["role"]]
    return {
        "role": request["role"],
        "session_id": session_id,
        "fork_context": False,
        "history_message_count": 0,
        "imported_memory_count": 0,
        "requested_model": config["model"],
        "returned_model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "transport_retry_count": 0,
        "request_sha256": request["request_sha256"],
        "response": response,
    }


def _agent_contract_rehash_request(request: dict[str, Any]) -> None:
    payload = {key: value for key, value in request.items() if key != "request_sha256"}
    request["request_sha256"] = runner.canonical_sha256(payload)


def test_agent_contract_constants_schemas_and_schedule_keys_are_frozen() -> None:
    assert runner.REQUIRED_AGENT_PACK_FILES == (
        "blind-v2-generation.jsonl",
        "blind-v2-review-a.jsonl",
        "blind-v2-review-b.jsonl",
        "blind-v2-contamination.jsonl",
        "agent-run-metadata.json",
    )
    assert runner.AGENT_CONFIGS == {
        "generator": {
            "model": "gpt-5.6-sol",
            "reasoning_effort": "max",
            "timeout_seconds": 1800,
        },
        "reviewer_a": {
            "model": "gpt-5.6-sol",
            "reasoning_effort": "ultra",
            "timeout_seconds": 900,
        },
        "reviewer_b": {
            "model": "gpt-5.6-luna",
            "reasoning_effort": "max",
            "timeout_seconds": 900,
        },
    }
    assert runner.SELECTION_SEED == 7170
    assert runner.GENERATOR_SYSTEM_PROMPT == (
        "You are the Generator for a preregistered Router V2 blind evaluation. "
        "Create natural English user requests for exactly one primary canonical skill. "
        "Do not mention skill IDs, skill names, gold labels, negative labels, "
        "benchmarks, routers, training, pilot data, Phase 16, Arm A, Arm C, or model "
        "behavior. For a negative-labeled candidate, choose one plausible but "
        "insufficient canonical negative skill. Use only the supplied skill definitions "
        "and quota. Do not use external memory or prior conversation. Return only JSON "
        "matching the supplied schema."
    )
    assert runner.REVIEWER_SYSTEM_PROMPT == (
        "You are a role-isolated reviewer for one preregistered Router V2 blind "
        "candidate. Use only the supplied task text, canonical skill definitions, and "
        "rubric. Independently decide the single primary gold skill and one "
        "plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural "
        "wording, label leakage, invalid negatives, and tasks with more than one equally "
        "primary skill. Do not use external memory, prior conversation, quotas, other "
        "reviews, generator labels, Router models, or model results. Return only JSON "
        "matching the supplied schema."
    )

    response_sha256 = "a" * 64
    raw = f"1:test-skill-00:7:{response_sha256}"
    candidate_id = hashlib.sha256(raw.encode()).hexdigest()[:24]
    assert (
        runner.opaque_candidate_id(1, "test-skill-00", 7, response_sha256)
        == candidate_id
    )
    assert len(candidate_id) == 24
    assert set(candidate_id) <= set("0123456789abcdef")
    assert (
        runner.selection_key(candidate_id)
        == hashlib.sha256(f"7170:{candidate_id}".encode()).hexdigest()
    )
    assert (
        runner.review_schedule_key("reviewer_a", candidate_id)
        == hashlib.sha256(f"review-a:7170:{candidate_id}".encode()).hexdigest()
    )
    assert (
        runner.review_schedule_key("reviewer_b", candidate_id)
        == hashlib.sha256(f"review-b:7171:{candidate_id}".encode()).hexdigest()
    )

    generator_schema = cast(dict[str, Any], runner.GENERATOR_RESPONSE_SCHEMA)
    generator_properties = cast(dict[str, Any], generator_schema["properties"])
    generator_candidates = cast(dict[str, Any], generator_properties["candidates"])
    generator_item = cast(dict[str, Any], generator_candidates["items"])
    assert generator_item["additionalProperties"] is False
    assert set(generator_item["required"]) == {
        "candidate_index",
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    reviewer_schema = cast(dict[str, Any], runner.REVIEWER_RESPONSE_SCHEMA)
    assert reviewer_schema["additionalProperties"] is False
    assert set(cast(list[str], reviewer_schema["required"])) == {
        "decision",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "natural",
        "single_primary_skill",
        "no_label_leakage",
        "negative_confusable",
        "confidence",
        "reason",
    }


def test_agent_contract_response_schemas_require_nonblank_strings() -> None:
    generator_schema = cast(dict[str, Any], runner.GENERATOR_RESPONSE_SCHEMA)
    generator_properties = cast(
        dict[str, Any],
        cast(
            dict[str, Any],
            cast(dict[str, Any], generator_schema["properties"])["candidates"],
        )["items"],
    )["properties"]
    for field in (
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "rationale",
    ):
        assert generator_properties[field]["pattern"] == r"\S"

    reviewer_schema = cast(dict[str, Any], runner.REVIEWER_RESPONSE_SCHEMA)
    reviewer_properties = cast(dict[str, Any], reviewer_schema["properties"])
    for field in (
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "reason",
    ):
        assert reviewer_properties[field]["pattern"] == r"\S"


def test_agent_contract_reviewer_schema_encodes_decision_state_model() -> None:
    expected_decisions = (
        "ACCEPT",
        "REJECT_AMBIGUOUS",
        "REJECT_NOT_CONFUSABLE",
        "REJECT_UNNATURAL",
        "REJECT_LABEL_LEAKAGE",
    )
    assert runner.AGENT_REVIEW_DECISIONS == expected_decisions

    schema = cast(dict[str, Any], runner.REVIEWER_RESPONSE_SCHEMA)
    properties = cast(dict[str, Any], schema["properties"])
    assert properties["decision"]["enum"] == list(expected_decisions)
    assert schema["allOf"] == [
        {
            "if": {
                "properties": {"reviewed_negative_skill_id": {"type": "null"}},
                "required": ["reviewed_negative_skill_id"],
            },
            "then": {"properties": {"negative_confusable": {"type": "null"}}},
            "else": {"properties": {"negative_confusable": {"type": "boolean"}}},
        }
    ]

    assert "oneOf" in schema
    branches = cast(list[dict[str, Any]], schema["oneOf"])
    by_decision: dict[str, dict[str, Any]] = {}
    for branch in branches:
        branch_properties = cast(dict[str, Any], branch["properties"])
        decision_contract = cast(dict[str, Any], branch_properties["decision"])
        by_decision[cast(str, decision_contract["const"])] = branch
    assert set(by_decision) == set(expected_decisions)

    accept = cast(dict[str, Any], by_decision["ACCEPT"]["properties"])
    assert accept["natural"] == {"const": True}
    assert accept["single_primary_skill"] == {"const": True}
    assert accept["no_label_leakage"] == {"const": True}
    assert by_decision["ACCEPT"]["then"] == {
        "properties": {"negative_confusable": {"const": True}}
    }

    ambiguous = cast(dict[str, Any], by_decision["REJECT_AMBIGUOUS"]["properties"])
    assert ambiguous["single_primary_skill"] == {"const": False}
    not_confusable = cast(
        dict[str, Any], by_decision["REJECT_NOT_CONFUSABLE"]["properties"]
    )
    assert not_confusable["reviewed_negative_skill_id"] == {
        "type": "string",
        "pattern": r"\S",
    }
    assert not_confusable["negative_confusable"] == {"const": False}
    unnatural = cast(dict[str, Any], by_decision["REJECT_UNNATURAL"]["properties"])
    assert unnatural["natural"] == {"const": False}
    leakage = cast(dict[str, Any], by_decision["REJECT_LABEL_LEAKAGE"]["properties"])
    assert leakage["no_label_leakage"] == {"const": False}


def test_agent_contract_generator_request_is_sealed_and_hash_bound() -> None:
    request = _agent_contract_generator_request()

    assert set(request) == {
        "schema_version",
        "role",
        "model",
        "reasoning_effort",
        "timeout_seconds",
        "system_prompt",
        "response_schema",
        "input",
        "request_sha256",
    }
    assert request["role"] == "generator"
    assert request["model"] == "gpt-5.6-sol"
    assert request["reasoning_effort"] == "max"
    assert request["timeout_seconds"] == 1800
    assert request["system_prompt"] == runner.GENERATOR_SYSTEM_PROMPT
    assert request["response_schema"] == runner.GENERATOR_RESPONSE_SCHEMA
    assert set(request["input"]) == {"canonical_skills", "rules", "quota"}
    assert request["input"]["rules"] == runner.GENERATOR_RULES
    assert request["input"]["quota"] == {
        "gold_skill_id": "test-skill-00",
        "negative_quota": 2,
        "positive_only_quota": 1,
        "round_number": 1,
    }
    protected = json.dumps(request["input"], sort_keys=True).casefold()
    for marker in (
        "pilot-002",
        "phase 16",
        "arm a",
        "arm c",
        "review result",
        "contamination output",
        "model result",
    ):
        assert marker not in protected

    unhashed = {key: value for key, value in request.items() if key != "request_sha256"}
    assert request["request_sha256"] == runner.canonical_sha256(unhashed)
    assert runner.validate_agent_request(request) == request


@pytest.mark.parametrize("role", ("reviewer_a", "reviewer_b"))
def test_agent_contract_reviewer_request_is_single_candidate_and_label_blind(
    role: str,
) -> None:
    request = _agent_contract_reviewer_request(role)

    assert request["role"] == role
    assert set(request["input"]) == {
        "task_id",
        "prompt_text",
        "canonical_skills",
        "rubric",
    }
    task_id = request["input"]["task_id"]
    assert task_id == _opaque_candidate_id()
    assert len(task_id) == 24
    assert set(task_id) <= set("0123456789abcdef")
    for label_marker in ("gold", "negative", "skill", "label"):
        assert label_marker not in task_id
    assert request["input"]["rubric"] == runner.REVIEW_RUBRIC
    encoded = json.dumps(request)
    assert "proposed_gold_skill_id" not in encoded
    assert "proposed_negative_skill_id" not in encoded
    assert f"{PREFIX} HIDDEN RATIONALE" not in encoded
    assert request["system_prompt"] == runner.REVIEWER_SYSTEM_PROMPT
    config = runner.AGENT_CONFIGS[role]
    assert request["model"] == config["model"]
    assert request["reasoning_effort"] == config["reasoning_effort"]
    assert request["timeout_seconds"] == config["timeout_seconds"]
    assert runner.validate_agent_request(request) == request


@pytest.mark.parametrize(
    "invalid_candidate_id",
    (
        "",
        "a" * 23,
        "a" * 25,
        "g" * 24,
        "A" * 24,
        "gold=test-skill-00",
        "negative-label-skill-id",
        True,
        24,
        24.0,
        None,
    ),
)
def test_agent_contract_rejects_nonopaque_candidate_ids(
    invalid_candidate_id: Any,
) -> None:
    message = "candidate id must be exactly 24 lowercase hex characters"
    candidate = {
        "candidate_id": invalid_candidate_id,
        "prompt_text": f"{PREFIX} REVIEW REQUEST",
    }

    with pytest.raises(ValueError, match=message):
        runner.build_reviewer_request(candidate, _skills(), role="reviewer_a")
    with pytest.raises(ValueError, match=message):
        runner.selection_key(invalid_candidate_id)
    with pytest.raises(ValueError, match=message):
        runner.review_schedule_key("reviewer_b", invalid_candidate_id)


def test_agent_contract_validation_rejects_nonopaque_reviewer_task_id() -> None:
    request = _agent_contract_reviewer_request()
    request["input"]["task_id"] = "gold=test-skill-00"
    _agent_contract_rehash_request(request)

    with pytest.raises(
        ValueError, match="candidate id must be exactly 24 lowercase hex characters"
    ):
        runner.validate_agent_request(request)


@pytest.mark.parametrize(
    "invalid_response_sha256",
    (
        "",
        "a" * 63,
        "a" * 65,
        "g" * 64,
        "A" * 64,
        "gold=test-skill-00",
        True,
        64,
        64.0,
        None,
    ),
)
def test_agent_contract_opaque_candidate_id_rejects_invalid_response_sha256(
    invalid_response_sha256: Any,
) -> None:
    with pytest.raises(
        ValueError,
        match="response SHA-256 must be exactly 64 lowercase hex characters",
    ):
        runner.opaque_candidate_id(1, "test-skill-00", 0, invalid_response_sha256)


def test_agent_contract_request_validation_recomputes_hash_and_whitelists() -> None:
    request = _agent_contract_generator_request()

    tampered = deepcopy(request)
    tampered["timeout_seconds"] = 900
    with pytest.raises(ValueError, match="request hash mismatch"):
        runner.validate_agent_request(tampered)

    extra = deepcopy(request)
    extra["unsupported_seed"] = 7170
    unhashed = {key: value for key, value in extra.items() if key != "request_sha256"}
    extra["request_sha256"] = runner.canonical_sha256(unhashed)
    with pytest.raises(ValueError, match="request fields mismatch"):
        runner.validate_agent_request(extra)

    leaked = deepcopy(request)
    leaked["input"]["review_results"] = [f"{PREFIX} SECRET"]
    unhashed = {key: value for key, value in leaked.items() if key != "request_sha256"}
    leaked["request_sha256"] = runner.canonical_sha256(unhashed)
    with pytest.raises(ValueError, match="generator input fields mismatch"):
        runner.validate_agent_request(leaked)


@pytest.mark.parametrize("invalid_minimum", (False, 0.0, "0", None))
def test_agent_contract_generator_schema_comparison_is_type_sensitive(
    invalid_minimum: Any,
) -> None:
    request = _agent_contract_generator_request()
    request["response_schema"]["properties"]["candidates"]["items"]["properties"][
        "candidate_index"
    ]["minimum"] = invalid_minimum
    _agent_contract_rehash_request(request)

    with pytest.raises(ValueError, match="generator response schema mismatch"):
        runner.validate_agent_request(request)


@pytest.mark.parametrize("invalid_boolean", (0, 0.0))
def test_agent_contract_reviewer_schema_comparison_is_type_sensitive(
    invalid_boolean: Any,
) -> None:
    request = _agent_contract_reviewer_request()
    request["response_schema"]["additionalProperties"] = invalid_boolean
    _agent_contract_rehash_request(request)

    with pytest.raises(ValueError, match="reviewer response schema mismatch"):
        runner.validate_agent_request(request)


@pytest.mark.parametrize("role", ("generator", "reviewer_a"))
def test_agent_contract_non_json_schema_values_raise_controlled_value_error(
    role: str,
) -> None:
    request = (
        _agent_contract_generator_request()
        if role == "generator"
        else _agent_contract_reviewer_request()
    )
    request["response_schema"]["invalid_non_json"] = object()

    with pytest.raises(ValueError, match="canonical JSON"):
        runner.validate_agent_request(request)


@pytest.mark.parametrize(
    ("role", "extra_field"),
    (
        ("generator", "model_result"),
        ("reviewer_a", "generator_labels"),
    ),
)
def test_agent_contract_builders_project_extra_canonical_skill_fields(
    role: str, extra_field: str
) -> None:
    skills = _skills()
    skills[0][extra_field] = f"{PREFIX} SECRET"

    request = (
        runner.build_generator_request(
            skills,
            gold_skill_id="test-skill-00",
            negative_quota=2,
            positive_only_quota=1,
        )
        if role == "generator"
        else runner.build_reviewer_request(
            {
                "candidate_id": _opaque_candidate_id(),
                "prompt_text": f"{PREFIX} REQUEST",
            },
            skills,
            role=role,
        )
    )

    sealed_skill = request["input"]["canonical_skills"][0]
    assert tuple(sealed_skill) == runner.CANONICAL_SKILL_FIELDS_IN_ORDER
    assert extra_field not in sealed_skill
    assert f"{PREFIX} SECRET" not in json.dumps(request)


@pytest.mark.parametrize("role", ("generator", "reviewer_a"))
def test_agent_contract_builders_project_real_authoritative_skills(role: str) -> None:
    source_skills = _authoritative_skills()
    expected = [
        {
            field: deepcopy(source_skill[field])
            for field in runner.CANONICAL_SKILL_FIELDS_IN_ORDER
        }
        for source_skill in source_skills
    ]
    gold_skill_id = cast(str, source_skills[0]["id"])
    request = (
        runner.build_generator_request(
            source_skills,
            gold_skill_id=gold_skill_id,
            negative_quota=2,
            positive_only_quota=1,
        )
        if role == "generator"
        else runner.build_reviewer_request(
            {
                "candidate_id": _opaque_candidate_id(),
                "prompt_text": f"{PREFIX} REQUEST",
            },
            source_skills,
            role=role,
        )
    )

    sealed_skills = request["input"]["canonical_skills"]
    assert sealed_skills == expected
    assert all(
        tuple(skill) == runner.CANONICAL_SKILL_FIELDS_IN_ORDER
        for skill in sealed_skills
    )
    assert all("path" not in skill for skill in sealed_skills)
    assert all("token_count_estimate" not in skill for skill in sealed_skills)
    assert sealed_skills[0]["trigger_terms"] is not source_skills[0]["trigger_terms"]

    source_skills[0]["trigger_terms"].append(f"{PREFIX} SOURCE MUTATION")
    assert sealed_skills == expected


@pytest.mark.parametrize(
    ("role", "missing_field"),
    (("generator", "description"), ("reviewer_a", "trigger_terms")),
)
def test_agent_contract_builders_reject_missing_canonical_skill_fields(
    role: str, missing_field: str
) -> None:
    skills = _skills()
    del skills[0][missing_field]

    with pytest.raises(ValueError, match="canonical skill 0 fields mismatch"):
        if role == "generator":
            runner.build_generator_request(
                skills,
                gold_skill_id="test-skill-00",
                negative_quota=2,
                positive_only_quota=1,
            )
        else:
            runner.build_reviewer_request(
                {
                    "candidate_id": _opaque_candidate_id(),
                    "prompt_text": f"{PREFIX} REQUEST",
                },
                skills,
                role=role,
            )


@pytest.mark.parametrize(
    ("role", "extra_field"),
    (
        ("generator", "model_result"),
        ("reviewer_a", "generator_labels"),
    ),
)
def test_agent_contract_validation_rejects_extra_sealed_skill_fields(
    role: str, extra_field: str
) -> None:
    request = (
        _agent_contract_generator_request()
        if role == "generator"
        else _agent_contract_reviewer_request()
    )
    request["input"]["canonical_skills"][0][extra_field] = f"{PREFIX} SECRET"
    _agent_contract_rehash_request(request)

    with pytest.raises(ValueError, match="canonical skill 0 fields mismatch"):
        runner.validate_agent_request(request)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        (field, invalid)
        for field in ("id", "name", "category", "description", "body")
        for invalid in (False, 1, 1.0, None, "", " ")
    ],
)
def test_agent_contract_canonical_skill_text_fields_are_nonempty_strings(
    field: str, invalid: Any
) -> None:
    skills = _skills()
    skills[0][field] = invalid

    with pytest.raises(ValueError, match=rf"canonical skill 0 {field}"):
        runner.build_generator_request(
            skills,
            gold_skill_id="test-skill-00",
            negative_quota=2,
            positive_only_quota=1,
        )


@pytest.mark.parametrize(
    "invalid_trigger_terms",
    (False, 1, 1.0, None, "trigger", [False], [1], [["nested"]], [""], [" "]),
)
def test_agent_contract_canonical_skill_trigger_terms_are_nonempty_strings(
    invalid_trigger_terms: Any,
) -> None:
    skills = _skills()
    skills[0]["trigger_terms"] = invalid_trigger_terms

    with pytest.raises(ValueError, match="canonical skill 0 trigger_terms"):
        runner.build_reviewer_request(
            {
                "candidate_id": _opaque_candidate_id(),
                "prompt_text": f"{PREFIX} REQUEST",
            },
            skills,
            role="reviewer_b",
        )


def test_agent_contract_requires_exactly_sixteen_unique_canonical_skills() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        runner.build_generator_request(
            _skills()[:-1],
            gold_skill_id="test-skill-00",
            negative_quota=2,
            positive_only_quota=1,
        )

    duplicated = _skills()
    duplicated[-1]["id"] = duplicated[0]["id"]
    with pytest.raises(ValueError, match="ids must be unique"):
        runner.build_reviewer_request(
            {
                "candidate_id": _opaque_candidate_id(),
                "prompt_text": f"{PREFIX} REQUEST",
            },
            duplicated,
            role="reviewer_a",
        )


def test_agent_contract_generator_response_and_envelope_validate() -> None:
    request = _agent_contract_generator_request()
    response = _agent_contract_generator_response()
    envelope = _agent_contract_envelope(request, response)
    seen: set[str] = set()

    assert runner.validate_agent_response(response, request=request) == response
    assert (
        runner.validate_agent_invocation_envelope(
            envelope, request=request, seen_session_ids=seen
        )
        == response
    )
    assert seen == {"fresh-session-001"}

    with pytest.raises(ValueError, match="session.*unique"):
        runner.validate_agent_invocation_envelope(
            envelope, request=request, seen_session_ids=seen
        )

    invalid_seen: set[str] = set()
    invalid = deepcopy(envelope)
    invalid["session_id"] = "fresh-session-invalid"
    invalid["response"]["candidates"].pop()
    with pytest.raises(ValueError, match="candidate count"):
        runner.validate_agent_invocation_envelope(
            invalid, request=request, seen_session_ids=invalid_seen
        )
    assert invalid_seen == set()


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("role", "reviewer_a"),
        ("fork_context", 0),
        ("history_message_count", False),
        ("history_message_count", 0.0),
        ("imported_memory_count", False),
        ("imported_memory_count", 0.0),
        ("requested_model", "gpt-5.6-luna"),
        ("returned_model", "gpt-5.6-luna"),
        ("reasoning_effort", "ultra"),
        ("timeout_seconds", 1800.0),
        ("transport_retry_count", False),
        ("transport_retry_count", 1.0),
        ("transport_retry_count", 2),
        ("request_sha256", "0" * 64),
    ),
)
def test_agent_contract_invocation_envelope_rejects_config_and_type_drift(
    field: str, invalid: Any
) -> None:
    request = _agent_contract_generator_request()
    envelope = _agent_contract_envelope(request, _agent_contract_generator_response())
    envelope[field] = invalid

    with pytest.raises(ValueError):
        runner.validate_agent_invocation_envelope(envelope, request=request)


def test_agent_contract_invocation_envelope_requires_one_nonempty_identity() -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()

    empty = _agent_contract_envelope(request, response, session_id=" ")
    with pytest.raises(ValueError, match="session.*non-empty"):
        runner.validate_agent_response_envelope(empty, request=request)

    both = _agent_contract_envelope(request, response)
    both["thread_id"] = "fresh-thread-001"
    with pytest.raises(ValueError, match="exactly one"):
        runner.validate_agent_response_envelope(both, request=request)

    unsupported = _agent_contract_envelope(request, response)
    unsupported["temperature"] = 0
    with pytest.raises(ValueError, match="envelope fields mismatch"):
        runner.validate_agent_response_envelope(unsupported, request=request)

    thread_only = _agent_contract_envelope(request, response)
    thread_only["thread_id"] = thread_only.pop("session_id")
    assert (
        runner.validate_agent_response_envelope(thread_only, request=request)
        == response
    )


@pytest.mark.parametrize(
    ("case", "invalid"),
    (
        ("candidate_index", True),
        ("candidate_index", 0.0),
        ("prompt_text", False),
        ("semantic_family_id", ""),
        ("proposed_gold_skill_id", "missing-skill"),
        ("proposed_negative_skill_id", "test-skill-00"),
        ("language", "zh"),
        ("rationale", 1),
    ),
)
def test_agent_contract_generator_response_rejects_field_and_type_drift(
    case: str, invalid: Any
) -> None:
    request = _agent_contract_generator_request()
    response = _agent_contract_generator_response()
    response["candidates"][0][case] = invalid

    with pytest.raises(ValueError):
        runner.validate_agent_response(response, request=request)


def test_agent_contract_generator_response_rejects_schema_and_quota_drift() -> None:
    request = _agent_contract_generator_request()

    extra = _agent_contract_generator_response()
    extra["candidates"][0]["unexpected"] = True
    with pytest.raises(ValueError, match="candidate fields mismatch"):
        runner.validate_agent_response(extra, request=request)

    duplicate = _agent_contract_generator_response()
    duplicate["candidates"][1]["candidate_index"] = 0
    with pytest.raises(ValueError, match="candidate indexes"):
        runner.validate_agent_response(duplicate, request=request)

    short = _agent_contract_generator_response()
    short["candidates"].pop()
    with pytest.raises(ValueError, match="candidate count"):
        runner.validate_agent_response(short, request=request)

    wrong_stratum = _agent_contract_generator_response()
    wrong_stratum["candidates"][2]["proposed_negative_skill_id"] = "test-skill-01"
    with pytest.raises(ValueError, match="negative quota"):
        runner.validate_agent_response(wrong_stratum, request=request)


def test_agent_contract_reviewer_response_validates_labels_and_strict_types() -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    assert runner.validate_agent_response(response, request=request) == response

    positive_only = deepcopy(response)
    positive_only["reviewed_negative_skill_id"] = None
    positive_only["negative_confusable"] = None
    assert (
        runner.validate_agent_response(positive_only, request=request) == positive_only
    )

    invalid_values = (
        ("decision", "MAYBE"),
        ("reviewed_gold_skill_id", "missing-skill"),
        ("reviewed_gold_skill_id", None),
        ("reviewed_negative_skill_id", "test-skill-00"),
        ("natural", 1),
        ("single_primary_skill", 1),
        ("no_label_leakage", 1),
        ("negative_confusable", 1),
        ("confidence", "VERY_HIGH"),
        ("reason", ""),
    )
    for field, invalid in invalid_values:
        drifted = deepcopy(response)
        drifted[field] = invalid
        with pytest.raises(ValueError):
            runner.validate_agent_response(drifted, request=request)

    extra = {**response, "rationale": f"{PREFIX} LEAK"}
    with pytest.raises(ValueError, match="reviewer response fields mismatch"):
        runner.validate_agent_response(extra, request=request)


def test_agent_contract_reviewer_rejection_response_and_envelope_validate() -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["decision"] = "REJECT_NOT_CONFUSABLE"
    response["negative_confusable"] = False
    envelope = _agent_contract_envelope(
        request, response, session_id="fresh-rejection-session"
    )

    assert runner.validate_agent_response(response, request=request) == response
    assert (
        runner.validate_agent_invocation_envelope(envelope, request=request) == response
    )


@pytest.mark.parametrize(
    ("decision", "negative_confusable"),
    (("ACCEPT", True), ("REJECT_NOT_CONFUSABLE", False)),
)
def test_agent_contract_reviewer_negative_confusability_accepts_strict_booleans(
    decision: str,
    negative_confusable: bool,
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["decision"] = decision
    response["negative_confusable"] = negative_confusable

    assert runner.validate_agent_response(response, request=request) == response


@pytest.mark.parametrize("invalid", (None, 0, 0.0, "false"))
def test_agent_contract_reviewer_negative_confusability_rejects_non_booleans(
    invalid: Any,
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["negative_confusable"] = invalid

    with pytest.raises(ValueError, match="reviewer negative confusability mismatch"):
        runner.validate_agent_response(response, request=request)


@pytest.mark.parametrize("invalid", (False, True))
def test_agent_contract_reviewer_without_negative_requires_null_confusability(
    invalid: bool,
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["reviewed_negative_skill_id"] = None
    response["negative_confusable"] = invalid

    with pytest.raises(ValueError, match="reviewer negative confusability mismatch"):
        runner.validate_agent_response(response, request=request)


@pytest.mark.parametrize(
    ("decision", "updates"),
    (
        ("ACCEPT", {}),
        ("REJECT_AMBIGUOUS", {"single_primary_skill": False}),
        ("REJECT_NOT_CONFUSABLE", {"negative_confusable": False}),
        ("REJECT_UNNATURAL", {"natural": False}),
        ("REJECT_LABEL_LEAKAGE", {"no_label_leakage": False}),
    ),
)
def test_agent_contract_reviewer_accepts_each_consistent_decision_state(
    decision: str, updates: dict[str, Any]
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["decision"] = decision
    response.update(updates)

    assert runner.validate_agent_response(response, request=request) == response


def test_agent_contract_reviewer_allows_multiple_rubric_failures() -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response.update(
        {
            "decision": "REJECT_AMBIGUOUS",
            "natural": False,
            "single_primary_skill": False,
            "no_label_leakage": False,
            "negative_confusable": False,
        }
    )

    assert runner.validate_agent_response(response, request=request) == response


@pytest.mark.parametrize(
    ("decision", "updates"),
    (
        ("ACCEPT", {"natural": False}),
        ("ACCEPT", {"single_primary_skill": False}),
        ("ACCEPT", {"no_label_leakage": False}),
        ("ACCEPT", {"negative_confusable": False}),
        ("REJECT_AMBIGUOUS", {"single_primary_skill": True}),
        ("REJECT_UNNATURAL", {"natural": True}),
        ("REJECT_LABEL_LEAKAGE", {"no_label_leakage": True}),
        ("REJECT_NOT_CONFUSABLE", {"negative_confusable": True}),
        (
            "REJECT_NOT_CONFUSABLE",
            {"reviewed_negative_skill_id": None, "negative_confusable": None},
        ),
    ),
)
def test_agent_contract_reviewer_rejects_decision_rubric_contradictions(
    decision: str, updates: dict[str, Any]
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["decision"] = decision
    response.update(updates)

    with pytest.raises(ValueError, match="reviewer decision/rubric mismatch"):
        runner.validate_agent_response(response, request=request)


@pytest.mark.parametrize(
    "removed_decision", ("REJECT_WRONG_GOLD", "REJECT_WRONG_NEGATIVE")
)
def test_agent_contract_reviewer_rejects_unobservable_decision_codes(
    removed_decision: str,
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response["decision"] = removed_decision

    with pytest.raises(ValueError, match="reviewer decision mismatch"):
        runner.validate_agent_response(response, request=request)


@pytest.mark.parametrize(
    "field",
    (
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "rationale",
    ),
)
def test_agent_contract_generator_response_rejects_whitespace_strings(
    field: str,
) -> None:
    request = _agent_contract_generator_request()
    response = _agent_contract_generator_response()
    response["candidates"][0][field] = " \t"

    with pytest.raises(ValueError):
        runner.validate_agent_response(response, request=request)


@pytest.mark.parametrize(
    "field", ("reviewed_gold_skill_id", "reviewed_negative_skill_id", "reason")
)
def test_agent_contract_reviewer_response_rejects_whitespace_strings(
    field: str,
) -> None:
    request = _agent_contract_reviewer_request()
    response = _agent_contract_reviewer_response()
    response[field] = " \t"

    with pytest.raises(ValueError):
        runner.validate_agent_response(response, request=request)


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _pack_success_invocation(
    request: dict[str, Any],
    response: dict[str, Any],
    *,
    session_id: str,
    transport_retry_count: int,
) -> dict[str, Any]:
    envelope = _agent_contract_envelope(request, response, session_id=session_id)
    envelope["transport_retry_count"] = transport_retry_count
    return {
        "transport_failure": False,
        "response_bytes_present": True,
        "envelope": envelope,
    }


def _pack_transport_failure_invocation(
    request: dict[str, Any], *, session_id: str
) -> dict[str, Any]:
    config = runner.AGENT_CONFIGS[request["role"]]
    return {
        "transport_failure": True,
        "response_bytes_present": False,
        "role": request["role"],
        "session_id": session_id,
        "fork_context": False,
        "history_message_count": 0,
        "imported_memory_count": 0,
        "requested_model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "request_sha256": request["request_sha256"],
    }


def _write_agent_pack(
    root: Path,
    *,
    rejected_candidate_count: int = 0,
    transport_retry_role: str | None = None,
) -> None:
    root.mkdir()
    generation_rows: list[dict[str, Any]] = []
    review_rows: dict[str, list[dict[str, Any]]] = {
        "reviewer_a": [],
        "reviewer_b": [],
    }
    contamination_rows: list[dict[str, Any]] = []
    role_session_ids: dict[str, list[str]] = {
        "generator": [],
        "reviewer_a": [],
        "reviewer_b": [],
    }
    role_invocation_counts = dict.fromkeys(role_session_ids, 0)
    candidate_ids: list[str] = []

    for index in range(128 + rejected_candidate_count):
        distribution_index = index % 128
        gold_index = distribution_index // 8
        has_negative = distribution_index % 8 < 6
        prompt = f"{PREFIX} REQUEST {index:03d} UNIQUE {index:05d}"
        gold = f"test-skill-{gold_index:02d}"
        negative = f"test-skill-{(gold_index + 1) % 16:02d}" if has_negative else None
        generation_request = runner.build_generator_request(
            _skills(),
            gold_skill_id=gold,
            negative_quota=int(has_negative),
            positive_only_quota=int(not has_negative),
            round_number=1,
        )
        generated = {
            "candidate_index": 0,
            "prompt_text": prompt,
            "semantic_family_id": f"{PREFIX}_FAMILY_{index:03d}",
            "proposed_gold_skill_id": gold,
            "proposed_negative_skill_id": negative,
            "language": "en",
            "rationale": f"{PREFIX} GENERATOR RATIONALE {index:03d}",
        }
        generation_response = {"candidates": [generated]}
        candidate_id = runner.opaque_candidate_id(
            1, gold, 0, runner.canonical_sha256(generation_response)
        )
        candidate_ids.append(candidate_id)
        candidate = {
            "candidate_id": candidate_id,
            "generation_round": 1,
            "prompt_text": prompt,
            "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "semantic_family_id": generated["semantic_family_id"],
            "proposed_gold_skill_id": gold,
            "proposed_negative_skill_id": negative,
            "language": "en",
            "rationale": generated["rationale"],
        }
        generator_session = f"generator-{candidate_id}"
        generator_invocations = [
            _pack_success_invocation(
                generation_request,
                generation_response,
                session_id=generator_session,
                transport_retry_count=0,
            )
        ]
        if transport_retry_role == "generator" and index == 0:
            failure_session = f"generator-transport-failure-{candidate_id}"
            generator_invocations.insert(
                0,
                _pack_transport_failure_invocation(
                    generation_request, session_id=failure_session
                ),
            )
            generator_invocations[1]["envelope"]["transport_retry_count"] = 1
            role_session_ids["generator"].append(failure_session)
        role_session_ids["generator"].append(generator_session)
        role_invocation_counts["generator"] += len(generator_invocations)
        generation_rows.append(
            {
                **candidate,
                "request": generation_request,
                "invocations": generator_invocations,
            }
        )
        contamination_rows.append({"candidate_id": candidate_id})

        for role in ("reviewer_a", "reviewer_b"):
            review_request = runner.build_reviewer_request(
                candidate, _skills(), role=role
            )
            review_response = {
                "decision": "ACCEPT",
                "reviewed_gold_skill_id": gold,
                "reviewed_negative_skill_id": negative,
                "natural": True,
                "single_primary_skill": True,
                "no_label_leakage": True,
                "negative_confusable": True if negative is not None else None,
                "confidence": ("LOW", "MEDIUM", "HIGH")[index % 3],
                "reason": f"{PREFIX} {role.upper()} REASON {index:03d}",
            }
            if index >= 128 and role == "reviewer_a":
                review_response["decision"] = "REJECT_AMBIGUOUS"
                review_response["single_primary_skill"] = False
            review_session = f"{role}-{candidate_id}"
            review_invocations = [
                _pack_success_invocation(
                    review_request,
                    review_response,
                    session_id=review_session,
                    transport_retry_count=0,
                )
            ]
            if transport_retry_role == role and index == 0:
                failure_session = f"{role}-transport-failure-{candidate_id}"
                review_invocations.insert(
                    0,
                    _pack_transport_failure_invocation(
                        review_request, session_id=failure_session
                    ),
                )
                review_invocations[1]["envelope"]["transport_retry_count"] = 1
                role_session_ids[role].append(failure_session)
            role_session_ids[role].append(review_session)
            role_invocation_counts[role] += len(review_invocations)
            review_rows[role].append(
                {
                    "candidate_id": candidate_id,
                    "request": review_request,
                    "invocations": review_invocations,
                }
            )

    payloads = {
        "blind-v2-generation.jsonl": _jsonl_bytes(generation_rows),
        "blind-v2-review-a.jsonl": _jsonl_bytes(review_rows["reviewer_a"]),
        "blind-v2-review-b.jsonl": _jsonl_bytes(review_rows["reviewer_b"]),
        "blind-v2-contamination.jsonl": _jsonl_bytes(contamination_rows),
    }
    for filename, payload in payloads.items():
        (root / filename).write_bytes(payload)

    metadata = {
        "schema_version": "router-v2-blind-v2-agent-run-metadata-v1",
        "first_read_timestamp": "2026-07-16T00:00:00Z",
        "roles": {
            role: {
                "config": deepcopy(runner.AGENT_CONFIGS[role]),
                "request_count": len(generation_rows),
                "invocation_count": role_invocation_counts[role],
                "session_or_thread_ids": role_session_ids[role],
                "fork_context": False,
                "history_message_count": 0,
                "imported_memory_count": 0,
            }
            for role in ("generator", "reviewer_a", "reviewer_b")
        },
        "review_schedule_sha256": {
            role: runner.canonical_sha256(
                sorted(
                    candidate_ids,
                    key=lambda value: runner.review_schedule_key(role, value),
                )
            )
            for role in ("reviewer_a", "reviewer_b")
        },
        "source_file_sha256": {
            filename: hashlib.sha256(payload).hexdigest()
            for filename, payload in payloads.items()
        },
    }
    (root / "agent-run-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )


def _refresh_agent_pack_metadata(root: Path) -> None:
    metadata_path = root / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source_file_sha256"] = {
        filename: hashlib.sha256((root / filename).read_bytes()).hexdigest()
        for filename in runner.REQUIRED_AGENT_PACK_FILES[:-1]
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rewrite_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_bytes(_jsonl_bytes(rows))
    _refresh_agent_pack_metadata(path.parent)


def _validate_agent_pack(pack: Path, repository_root: Path) -> dict[str, Any]:
    return runner.validate_agent_pack(
        pack,
        repository_root=repository_root,
        canonical_skills=_skills(),
        train_prompts=[f"{PREFIX} TRAIN REFERENCE"],
        pilot_prompts=[f"{PREFIX} PILOT REFERENCE"],
        phase16_prompts=[f"{PREFIX} PHASE16 REFERENCE"],
        train_family_ids={f"{PREFIX}_TRAIN_FAMILY"},
        pilot_family_ids={f"{PREFIX}_PILOT_FAMILY"},
        first_read_timestamp="2026-07-16T00:00:00Z",
        semantic_similarity=lambda _left, _right: 0.0,
    )


def test_agent_pack_is_exact_unanimous_agent_review_without_human_fields(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, rejected_candidate_count=1)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["task_count"] == 128
    assert result["negative_labeled_task_count"] == 96
    assert result["family_count"] == 128
    assert result["negative_target_coverage_count"] == 16
    assert result["exact_three_way_agreement_count"] == 128
    assert result["excluded_candidate_count"] == 1
    assert result["model_scores_observed"] is False
    assert all(row["prompt_text"].startswith(PREFIX) for row in result["tasks"])
    assert (
        sum(row["proposed_negative_skill_id"] is None for row in result["tasks"]) == 32
    )
    assert (
        result["agent_roles"]["reviewer_a"]["config"]
        == runner.AGENT_CONFIGS["reviewer_a"]
    )
    assert (
        result["agent_roles"]["reviewer_b"]["config"]
        == runner.AGENT_CONFIGS["reviewer_b"]
    )

    encoded = json.dumps(result, sort_keys=True)
    for forbidden in (
        "author_id",
        "author_reason",
        "reviewer_id",
        "reviewer_ids",
        "review_confidence",
        "review_reason",
        "reviewer_qualification",
        "human_author_count",
        "human_reviewer_count",
        "independent_human_reviewer_count",
        "ai_assistance_disclosure",
        "dataset_license",
        "publication_permission",
        "prompts_may_be_public_after_evaluation",
    ):
        assert forbidden not in encoded
    assert not hasattr(runner, "validate_human_pack")


@pytest.mark.parametrize(
    ("role", "updates"),
    (
        ("reviewer_a", {"reviewed_gold_skill_id": "test-skill-02"}),
        (
            "reviewer_b",
            {"reviewed_negative_skill_id": None, "negative_confusable": None},
        ),
        (
            "reviewer_a",
            {"decision": "REJECT_AMBIGUOUS", "single_primary_skill": False},
        ),
        (
            "reviewer_b",
            {"decision": "REJECT_UNNATURAL", "natural": False},
        ),
        (
            "reviewer_a",
            {"decision": "REJECT_LABEL_LEAKAGE", "no_label_leakage": False},
        ),
        (
            "reviewer_b",
            {
                "decision": "REJECT_NOT_CONFUSABLE",
                "negative_confusable": False,
            },
        ),
    ),
)
def test_unanimous_agent_pack_excludes_disagreement_without_global_invalid(
    tmp_path: Path, role: str, updates: dict[str, Any]
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / f"blind-v2-review-{'a' if role == 'reviewer_a' else 'b'}.jsonl"
    rows = _read_jsonl(path)
    candidate_id = rows[0]["candidate_id"]
    rows[0]["invocations"][-1]["envelope"]["response"].update(updates)
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["task_count"] == 127
    assert result["excluded_candidate_count"] == 1
    assert candidate_id not in {row["candidate_id"] for row in result["tasks"]}
    assert "research_conclusion" not in result


@pytest.mark.parametrize(
    "leaked_field",
    ("proposed_gold_skill_id", "rationale", "generator_response"),
)
def test_agent_pack_reviewer_request_leak_is_global_protocol_invalid(
    tmp_path: Path, leaked_field: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0]["request"]["input"][leaked_field] = f"{PREFIX} LEAK"
    _agent_contract_rehash_request(rows[0]["request"])
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["production_ready"] is False
    assert result["release_authorized"] is False
    assert result["default_router_unchanged"] is True
    assert result["failure_stage"] == "reviewer_request"
    assert result["tasks"] == []


@pytest.mark.parametrize("role", ("generator", "reviewer_a", "reviewer_b"))
def test_agent_pack_allows_one_transport_retry_with_no_response_bytes(
    tmp_path: Path, role: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role=role)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["task_count"] == 128
    assert result["transport_retry_count"] == 1
    assert result["agent_roles"][role]["invocation_count"] == 129


@pytest.mark.parametrize(
    "invalid_retry",
    (
        "second_success",
        "response_object_on_failure",
        "request_hash_drift",
        "config_drift",
    ),
)
def test_agent_pack_rejects_non_transport_retry_candidate(
    tmp_path: Path, invalid_retry: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    candidate_id = rows[0]["candidate_id"]
    invocations = rows[0]["invocations"]
    if invalid_retry == "second_success":
        failure_session = invocations[0]["session_id"]
        invocations[0] = deepcopy(invocations[1])
        invocations[0]["envelope"]["session_id"] = failure_session
    elif invalid_retry == "response_object_on_failure":
        invocations[0]["response"] = {}
    elif invalid_retry == "request_hash_drift":
        invocations[0]["request_sha256"] = "0" * 64
    else:
        invocations[0]["requested_model"] = runner.AGENT_CONFIGS["reviewer_b"]["model"]
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["task_count"] == 127
    assert result["excluded_candidate_count"] == 1
    assert candidate_id not in {row["candidate_id"] for row in result["tasks"]}


@pytest.mark.parametrize("drift", ("reviewer_config", "duplicate_session"))
def test_agent_pack_role_isolation_metadata_drift_is_protocol_invalid(
    tmp_path: Path, drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if drift == "reviewer_config":
        metadata["roles"]["reviewer_b"]["config"] = deepcopy(
            runner.AGENT_CONFIGS["reviewer_a"]
        )
    else:
        metadata["roles"]["reviewer_b"]["session_or_thread_ids"][0] = metadata["roles"][
            "reviewer_a"
        ]["session_or_thread_ids"][0]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "agent_run_metadata"


def test_agent_pack_requires_external_root_and_all_five_files(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    pack = repository / "agent-pack"
    repository.mkdir()
    _write_agent_pack(pack)

    with pytest.raises(ValueError, match="outside the repository"):
        _validate_agent_pack(pack, repository)

    external = tmp_path / "external-agent-pack"
    _write_agent_pack(external)
    (external / "blind-v2-contamination.jsonl").unlink()
    with pytest.raises(ValueError, match="missing required agent pack file"):
        _validate_agent_pack(external, repository)


def test_dataset_freeze_is_deterministic_and_private_when_permission_is_false(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)

    assert first == second
    assert set(first) == {
        "blind-v2-tasks.jsonl",
        "blind-v2-review-summary.json",
        "blind-v2-manifest.json",
    }
    combined = b"".join(first.values())
    assert f"{PREFIX} REQUEST".encode() not in combined
    manifest = json.loads(first["blind-v2-manifest.json"])
    assert manifest["task_count"] == 64
    assert manifest["negative_labeled_task_count"] == 48
    assert manifest["model_scores_observed"] is False
    assert manifest["evaluation_started"] is False
    assert manifest["retraining_after_data_access"] is False
    assert manifest["gate_changed_after_data_access"] is False

    recovered = runner.validate_frozen_dataset_documents(validation, first)
    assert len(recovered) == 64
    assert all(row["prompt_text"].startswith(PREFIX) for row in recovered)
    assert all(
        "prompt_text" not in json.loads(line)
        for line in first["blind-v2-tasks.jsonl"].splitlines()
    )


def test_authoritative_lineage_binds_all_models_inputs_and_review_bytes(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    repository = Path(__file__).resolve().parents[1]
    bindings = runner.build_authoritative_lineage_bindings(
        repository / runner.PREREGISTRATION_RELATIVE,
        repository_root=repository,
        pilot_manifest_path=repository / runner.PILOT_MANIFEST_RELATIVE,
        frozen_documents=documents,
    )

    assert len(bindings["evaluation_models"]) == 6
    assert {(row["arm"], row["seed"]) for row in bindings["evaluation_models"]} == {
        (arm, seed) for arm in ("A", "C") for seed in (7170, 7171, 7172)
    }
    assert all(row["model_files"] for row in bindings["evaluation_models"])
    assert (
        bindings["blind_v2_dataset"]["source_file_sha256"]
        == validation["source_file_sha256"]
    )
    assert bindings["human_review"]["exact_review_agreement_count"] == 64
    assert "pilot_002_result_report" in bindings["frozen_inputs"]
    assert len(bindings["old_phase16_prompt_files"]) == 16


def test_preregistration_authority_rejects_gate_source_and_model_drift() -> None:
    repository = Path(__file__).resolve().parents[1]
    preregistration = repository / "artifacts/router-v2-blind-v2/preregistration.json"
    pilot = repository / (
        "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-002-eval-replay/pilot-manifest.json"
    )

    authority = runner.validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot,
        verify_model_files=False,
    )
    assert authority["status"] == "VALID"

    original = json.loads(preregistration.read_text(encoding="utf-8"))

    def write_tampered(value: dict[str, Any], name: str) -> Path:
        value = deepcopy(value)
        value.pop("preregistration_sha256", None)
        value["preregistration_sha256"] = runner.canonical_sha256(value)
        path = repository / f".{PREFIX}-{name}"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    gate = deepcopy(original)
    gate["gate"]["mrr_mean_delta_min"] = "-0.02000000"
    gate_path = write_tampered(gate, "gate.json")
    try:
        with pytest.raises(ValueError, match="gate binding"):
            runner.validate_preregistration_authority(
                gate_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        gate_path.unlink(missing_ok=True)

    source = deepcopy(original)
    source["evaluator"]["source_files"][0]["sha256"] = "0" * 64
    source_path = write_tampered(source, "source.json")
    try:
        with pytest.raises(ValueError, match="evaluator source hash"):
            runner.validate_preregistration_authority(
                source_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        source_path.unlink(missing_ok=True)

    missing_source = deepcopy(original)
    missing_source["evaluator"]["source_files"] = missing_source["evaluator"][
        "source_files"
    ][:-1]
    missing_source_path = write_tampered(missing_source, "missing-source.json")
    try:
        with pytest.raises(ValueError, match="evaluator source set"):
            runner.validate_preregistration_authority(
                missing_source_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        missing_source_path.unlink(missing_ok=True)

    statistics = deepcopy(original)
    statistics["statistics"]["bootstrap_seed"] = 7171
    statistics_path = write_tampered(statistics, "statistics.json")
    try:
        with pytest.raises(ValueError, match="statistics binding"):
            runner.validate_preregistration_authority(
                statistics_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        statistics_path.unlink(missing_ok=True)

    namespace = deepcopy(original)
    namespace["evaluation_output_namespace"] = "artifacts/alternate"
    namespace_path = write_tampered(namespace, "namespace.json")
    try:
        with pytest.raises(ValueError, match="canonical namespace binding"):
            runner.validate_preregistration_authority(
                namespace_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        namespace_path.unlink(missing_ok=True)

    model = deepcopy(original)
    model["base_model"]["model_id"] = "tampered/model"
    model_path = write_tampered(model, "model.json")
    try:
        with pytest.raises(ValueError, match="base model binding"):
            runner.validate_preregistration_authority(
                model_path,
                repository_root=repository,
                pilot_manifest_path=pilot,
                verify_model_files=False,
                canonical_path_required=False,
            )
    finally:
        model_path.unlink(missing_ok=True)


def _model_entry(path: Path) -> tuple[list[dict[str, Any]], str]:
    payload = path / "model.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"test-only-model-bytes")
    rows = [
        {
            "path": "model.bin",
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            "size": payload.stat().st_size,
        }
    ]
    return rows, hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class _FakeEncoder:
    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        assert normalize_embeddings is True
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_model_load_smoke_uses_only_one_a_and_three_c_then_removes_temp(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    base_rows, base_manifest_hash = _model_entry(base)
    artifacts = []
    for seed in (7170, 7171, 7172):
        model = tmp_path / f"c-{seed}"
        rows, manifest_hash = _model_entry(model)
        manifest_path = tmp_path / f"c-{seed}-manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")
        artifacts.append(
            {
                "arm": "C",
                "seed": seed,
                "model_path": str(model),
                "model_file_manifest": rows,
                "model_file_manifest_sha256": manifest_hash,
                "model_manifest_path": str(manifest_path),
                "model_manifest_file_sha256": hashlib.sha256(b"{}").hexdigest(),
            }
        )
    pilot = {
        "base_model": {
            "id": "test-only/base",
            "revision": "1" * 40,
            "path": str(base),
            "file_manifest_rows": base_rows,
            "file_manifest_sha256": base_manifest_hash,
        },
        "training_artifacts": artifacts,
    }
    pilot_path = tmp_path / "pilot-manifest.json"
    pilot_path.write_text(json.dumps(pilot), encoding="utf-8")
    preregistration_path = tmp_path / "preregistration.json"
    preregistration_path.write_text("{}", encoding="utf-8")
    calls: list[tuple[str, int, Path]] = []
    authority_calls: list[tuple[Path, Path, Path]] = []

    def factory(arm: str, seed: int, model_path: Path) -> _FakeEncoder:
        calls.append((arm, seed, model_path))
        return _FakeEncoder()

    def authority_validator(
        preregistration: Path | str,
        *,
        repository_root: Path | str,
        pilot_manifest_path: Path | str,
        verify_model_files: bool,
    ) -> dict[str, Any]:
        assert verify_model_files is True
        authority_calls.append(
            (Path(preregistration), Path(repository_root), Path(pilot_manifest_path))
        )
        return {"status": "VALID"}

    result = runner.run_model_load_smoke(
        pilot_path,
        preregistration_path=preregistration_path,
        repository_root=tmp_path,
        encoder_factory=factory,
        authority_validator=authority_validator,
    )

    assert result["smoke_status"] == "PASS"
    assert result["embedding_dimension"] == 3
    assert [(arm, seed) for arm, seed, _ in calls] == [
        ("A", 7170),
        ("C", 7170),
        ("C", 7171),
        ("C", 7172),
    ]
    assert calls[0][2] != base
    assert not calls[0][2].exists()
    assert authority_calls == [(preregistration_path, tmp_path, pilot_path)]
    assert runner.MODEL_LOAD_SMOKE_TEXTS == (
        "synthetic blind-v2 model load query",
        "synthetic blind-v2 skill description",
    )


def test_model_load_smoke_receipt_is_commit_bound_and_tamper_evident(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "SMOKE_RECEIPT_ROOT", tmp_path / "smoke-receipts")
    smoke = {
        "schema_version": "router-v2-blind-v2-model-load-smoke-v1",
        "smoke_status": "PASS",
        "models": [
            {"arm": "A", "seed": 7170},
            {"arm": "C", "seed": 7170},
            {"arm": "C", "seed": 7171},
            {"arm": "C", "seed": 7172},
        ],
        "embedding_dimension": 384,
        "device": "cpu",
        "synthetic_strings": list(runner.MODEL_LOAD_SMOKE_TEXTS),
        "benchmark_metrics_computed": False,
        "blind_v2_data_read": False,
    }
    receipt = runner.build_model_load_smoke_receipt(
        smoke, commit_a="a" * 40, preregistration_sha256="b" * 64
    )
    path = runner.write_model_load_smoke_receipt(receipt)

    assert receipt["schema_version"] == (
        "router-v2-blind-v2-model-load-smoke-receipt-v1"
    )
    assert receipt["smoke"] == smoke
    assert (
        runner.validate_model_load_smoke_receipt(
            commit_a="a" * 40, preregistration_sha256="b" * 64
        )
        == receipt
    )
    tampered = json.loads(path.read_text())
    tampered["embedding_dimension"] = 1
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt hash mismatch"):
        runner.validate_model_load_smoke_receipt(
            commit_a="a" * 40, preregistration_sha256="b" * 64
        )

    drifted = {**receipt, "unexpected": True}
    drifted.pop("receipt_sha256")
    drifted["receipt_sha256"] = runner.canonical_sha256(drifted)
    path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt structure mismatch"):
        runner.validate_model_load_smoke_receipt(
            commit_a="a" * 40, preregistration_sha256="b" * 64
        )


def test_commit_b_must_be_direct_child_of_commit_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit_a = "a" * 40
    head = "b" * 40
    sibling_parent = "c" * 40
    expected_changed = "\n".join(
        (runner.DATASET_FREEZE_RELATIVE / name).as_posix()
        for name in runner.DATASET_FREEZE_FILENAMES
    )
    outputs = {
        ("status", "--porcelain", "--untracked-files=all"): "",
        ("rev-parse", "HEAD"): head,
        ("rev-parse", "HEAD^"): sibling_parent,
        ("rev-parse", f"{commit_a}^"): runner.PREREGISTRATION_PARENT_COMMIT,
        ("rev-parse", "origin/main"): runner.PREREGISTRATION_PARENT_COMMIT,
        ("rev-list", "--count", f"{commit_a}..{head}"): "1",
        ("diff", "--name-only", f"{commit_a}..{head}"): expected_changed,
    }
    monkeypatch.setattr(
        runner,
        "_git",
        lambda repository, *arguments: outputs[arguments],
    )

    with pytest.raises(ValueError, match="direct child"):
        runner.validate_commit_b_repository(tmp_path, commit_a=commit_a)


class _FakeScorer:
    def __init__(self, calls: list[str] | None = None) -> None:
        self.calls = calls

    def rank(self, query: str, skill_ids: list[str]) -> list[str]:
        if self.calls is not None:
            self.calls.append(query)
        task_index = int(query.rsplit(" ", 1)[-1])
        gold = f"test-skill-{task_index // 4:02d}"
        return [gold, *[skill_id for skill_id in skill_ids if skill_id != gold]]


class _FakeSentenceModel:
    def __init__(self) -> None:
        self.encoded: list[list[str]] = []

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        self.encoded.append(texts)
        return [[1.0, 0.0] for _ in texts]


def test_real_scorer_consumes_already_canonical_query_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scorer = object.__new__(runner._SentenceTransformerScorer)
    model = _FakeSentenceModel()
    scorer._model = model
    scorer._skill_ids = ["a", "b"]
    scorer._skill_vectors = [[1.0, 0.0], [0.0, 1.0]]
    monkeypatch.setattr(
        runner,
        "router_query_text",
        lambda value: (_ for _ in ()).throw(AssertionError("query contract repeated")),
    )

    assert scorer.rank("already canonical", ["a", "b"]) == ["a", "b"]
    assert model.encoded == [["already canonical"]]


def test_real_scorer_quantizes_to_eight_decimals_before_tie_break() -> None:
    scorer = object.__new__(runner._SentenceTransformerScorer)
    model = _FakeSentenceModel()
    scorer._model = model
    scorer._skill_ids = ["b", "a"]
    scorer._skill_vectors = [[0.123456784, 0.0], [0.123456783, 0.0]]

    assert scorer.rank("already canonical", ["b", "a"]) == ["a", "b"]


def test_evaluate_routes_produces_complete_a_c_grid_without_arm_b() -> None:
    tasks = [
        {
            "task_id": f"{PREFIX}_TASK_{index:02d}",
            "prompt_text": f"{PREFIX} QUERY {index}",
            "semantic_family_id": f"{PREFIX}_FAMILY_{index:02d}",
            "gold_skill_id": f"test-skill-{index // 4:02d}",
            "negative_skill_id": (
                f"test-skill-{((index // 4) + 1) % 16:02d}" if index % 4 < 3 else None
            ),
        }
        for index in range(64)
    ]
    bindings = [
        {"arm": arm, "seed": seed, "model_path": f"/{PREFIX}/{arm}/{seed}"}
        for seed in (7170, 7171, 7172)
        for arm in ("A", "C")
    ]

    calls: list[str] = []
    rows = runner.evaluate_routes(
        tasks,
        _skills(),
        bindings,
        scorer_factory=lambda arm, seed, path: _FakeScorer(calls),
        clock_ns=iter(range(1, 769)).__next__,
    )

    assert len(rows) == 384
    assert {(row["arm"], row["seed"]) for row in rows} == {
        (arm, seed) for arm in ("A", "C") for seed in (7170, 7171, 7172)
    }
    assert all(row["gold_rank"] == 1 for row in rows)
    assert all(row["latency_ns"] == 1 for row in rows)
    assert len(calls) == 768
    assert all(calls.count(f"{PREFIX} QUERY {index}") == 12 for index in range(64))

    started = runner.build_attempt_started_document(
        {
            "commit_a": "a" * 40,
            "commit_b": "b" * 40,
            "attempt_token_sha256": "d" * 64,
        }
    )
    terminal = runner.build_attempt_terminal_document(
        len(runner.EVALUATION_OUTPUT_FILENAMES)
    )
    inputs = {
        "preregistration.json": b"{}\n",
        "blind-v2-manifest.json": b"{}\n",
        "review-summary.json": b"{}\n",
    }
    documents = runner.build_evaluation_documents(
        rows,
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings={"evaluation_models": [{"arm": "A"}, {"arm": "C"}]},
        input_artifacts=inputs,
        attempt_artifacts={
            "attempt-1.started.json": runner._canonical_json_bytes(started),
            "attempt-1.terminal.json": runner._canonical_json_bytes(terminal),
        },
    )
    assert set(documents) == set(runner.EVALUATION_OUTPUT_FILENAMES)
    lineage = json.loads(documents["lineage-manifest.json"])
    lineage_paths = {row["path"] for row in lineage["artifacts"]}
    assert lineage_paths == (
        set(runner.EVALUATION_OUTPUT_FILENAMES) - {"lineage-manifest.json"}
        | {"attempt-1.started.json", "attempt-1.terminal.json"}
    )
    assert lineage["frozen_bindings"]["evaluation_models"] == [
        {"arm": "A"},
        {"arm": "C"},
    ]


def test_single_attempt_is_terminal_on_failure_and_cannot_retry(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    output = repository / runner.FINAL_NAMESPACE_RELATIVE
    output.parent.mkdir(parents=True)

    with pytest.raises(ValueError, match="canonical namespace"):
        runner.run_single_attempt(
            repository / "alternate-final-namespace",
            repository_root=repository,
            started_payload={"commit_b": "b" * 40},
            evaluate=lambda: {},
            protected_roots=[],
        )

    def fail() -> dict[str, bytes]:
        raise RuntimeError("TEST_ONLY_INFRASTRUCTURE_FAILURE")

    with pytest.raises(RuntimeError, match="TEST_ONLY_INFRASTRUCTURE_FAILURE"):
        runner.run_single_attempt(
            output,
            repository_root=repository,
            started_payload={"commit_b": "b" * 40},
            evaluate=fail,
            protected_roots=[tmp_path / "training-root"],
        )

    assert (output / "attempt-1.started.json").is_file()
    terminal = json.loads((output / "attempt-1.terminal.json").read_text())
    assert terminal["status"] == "INFRASTRUCTURE_FAILURE"
    assert terminal["research_conclusion"] == (
        "BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE"
    )
    with pytest.raises(FileExistsError):
        runner.run_single_attempt(
            output,
            repository_root=repository,
            started_payload={"commit_b": "b" * 40},
            evaluate=lambda: {},
            protected_roots=[],
        )

    protected_repository = tmp_path / "protected-repo"
    protected = protected_repository / runner.FINAL_NAMESPACE_RELATIVE
    protected.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="protected root"):
        runner.run_single_attempt(
            protected,
            repository_root=protected_repository,
            started_payload={"commit_b": "b" * 40},
            evaluate=lambda: {},
            protected_roots=[protected_repository / "artifacts"],
        )


def test_final_cli_freezes_only_protocol_subcommands() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "scripts/run_router_v2_blind_v2_final.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0
    for subcommand in ("smoke", "pack-status", "freeze", "evaluate"):
        assert subcommand in result.stdout
    for forbidden in ("train", "mine", "tune", "attempt-2", "blind-v3"):
        assert forbidden not in result.stdout

    freeze = subprocess.run(
        [
            sys.executable,
            "scripts/run_router_v2_blind_v2_final.py",
            "freeze",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert freeze.returncode == 0
    for caller_controlled in (
        "--pack-root",
        "--skills",
        "--train-reference",
        "--pilot-reference",
        "--commit-a",
        "--output-dir",
    ):
        assert caller_controlled not in freeze.stdout

    pack_status = subprocess.run(
        [
            sys.executable,
            "scripts/run_router_v2_blind_v2_final.py",
            "pack-status",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert pack_status.returncode == 0
    assert "--preregistration" in pack_status.stdout
    assert "--template-output" not in pack_status.stdout

    evaluate = subprocess.run(
        [
            sys.executable,
            "scripts/run_router_v2_blind_v2_final.py",
            "evaluate",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert evaluate.returncode == 0
    for caller_controlled in (
        "--tasks",
        "--skills",
        "--commit-a",
        "--commit-b",
        "--evaluator-commit",
        "--attempt-token-sha256",
        "--output-root",
    ):
        assert caller_controlled not in evaluate.stdout
