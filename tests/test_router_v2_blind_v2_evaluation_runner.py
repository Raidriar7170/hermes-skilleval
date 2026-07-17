from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
from copy import deepcopy
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    Decimal,
    Inexact,
    getcontext,
    localcontext,
)
from pathlib import Path
from typing import Any, Callable, cast

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner


PREFIX = "TEST_ONLY_DO_NOT_USE"
TASK4_SELECTION_AUTHORITY = {
    "selection_seed": 7170,
    "selection_order": "ascending_selection_key(candidate_id)_within_stratum",
    "max_generation_rounds": 2,
    "round_1_candidate_count": 256,
    "round_1_negative_per_skill": 12,
    "round_1_positive_only_per_skill": 4,
    "round_2_deficit_multiplier": 2,
    "final_negative_per_skill": 6,
    "final_positive_only_per_skill": 2,
}


def _task5_scanner_model_authority(
    files: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    materialized_files = deepcopy(
        files
        or [
            {
                "path": "1_Pooling/config.json",
                "sha256": hashlib.sha256(b"test pooling config").hexdigest(),
            },
            {
                "path": "model.safetensors",
                "sha256": hashlib.sha256(b"test model weights").hexdigest(),
            },
        ]
    )
    return {
        "materialized_model_files": materialized_files,
        "materialized_model_files_sha256": runner.canonical_sha256(materialized_files),
    }


def _task4_protected_prompts() -> dict[str, list[str]]:
    return {
        "train": [f"{PREFIX} TRAIN REFERENCE"],
        "pilot-002": [f"{PREFIX} PILOT REFERENCE"],
        "phase16": [f"{PREFIX} PHASE16 REFERENCE"],
        "prior_candidate": [],
    }


def _task4_protected_family_ids() -> dict[str, set[str]]:
    return {
        "train": {f"{PREFIX}_TRAIN_FAMILY"},
        "pilot-002": {f"{PREFIX}_PILOT_FAMILY"},
        "phase16": set(),
        "prior_candidate": set(),
    }


def _agent_pack_prompt(round_number: int, serial: int) -> str:
    unique_tokens = " ".join(
        hashlib.sha256(f"{round_number}:{serial}:{offset}".encode()).hexdigest()[:12]
        for offset in range(8)
    )
    return f"{PREFIX} {unique_tokens}"


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


def test_task4_contamination_constants_and_decimal_jaccard_are_frozen() -> None:
    assert runner.SEMANTIC_MODEL_ID == "sentence-transformers/all-mpnet-base-v2"
    assert runner.SEMANTIC_MODEL_REVISION == "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    assert runner.TOKEN_5GRAM_JACCARD_MAX == Decimal("0.80")
    assert runner.CHARACTER_5GRAM_JACCARD_MAX == Decimal("0.85")
    assert runner.SEMANTIC_COSINE_MAX == Decimal("0.90")
    assert runner.SELECTION_AUTHORITY == TASK4_SELECTION_AUTHORITY
    assert runner._jaccard(set(), set()) == Decimal("1")
    assert runner._jaccard({"a", "b", "c", "d"}, {"a", "b", "c", "e"}) == Decimal("0.6")


def test_task4_selection_authority_is_immutable() -> None:
    with pytest.raises(TypeError):
        cast(dict[str, Any], runner.SELECTION_AUTHORITY)["selection_seed"] = 7171

    document = runner._selection_authority_document()
    document["selection_seed"] = 7171
    assert runner.SELECTION_AUTHORITY["selection_seed"] == 7170


def test_task4_selection_ignores_compatibility_seed_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    candidate_id = "a" * 24
    expected_key = hashlib.sha256(f"7170:{candidate_id}".encode()).hexdigest()

    monkeypatch.setattr(runner, "SELECTION_SEED", 7171)

    assert runner.selection_key(candidate_id) == expected_key
    scan = runner._scan_contamination(
        [],
        protected_prompts={scope: [] for scope in runner.CONTAMINATION_SCOPES},
        protected_family_ids={scope: set() for scope in runner.CONTAMINATION_SCOPES},
        semantic_similarity=lambda _left, _right: 0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    assert scan["scanner_config"]["selection_seed"] == 7170
    result = _validate_agent_pack(pack, tmp_path / "repo")
    assert result["status"] == "VALID"
    assert result["selection_audit"]["selection_authority"] == (
        TASK4_SELECTION_AUTHORITY
    )


def test_task4_protected_authority_inputs_are_explicitly_required() -> None:
    parameters = inspect.signature(runner.validate_agent_pack).parameters

    for name in (
        "phase16_family_ids",
        "prior_candidate_prompts",
        "prior_candidate_family_ids",
    ):
        assert parameters[name].default is inspect.Parameter.empty


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (0, "0"),
        (-0.0, "0"),
        (1, "1"),
        (-1, "-1"),
        (0.9, "0.9"),
        (Decimal("0.90"), "0.9"),
    ),
)
def test_task4_semantic_decimal_accepts_range_and_canonicalizes(
    raw: int | float | Decimal, expected: str
) -> None:
    value = runner._semantic_decimal(lambda _left, _right: raw, "left", "right")

    assert runner._canonical_decimal(value) == expected


@pytest.mark.parametrize(
    "raw",
    (
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-1.0001"),
        Decimal("1.0001"),
    ),
)
def test_task4_semantic_decimal_rejects_bool_nonfinite_and_out_of_range(
    raw: object,
) -> None:
    with pytest.raises(ValueError):
        runner._semantic_decimal(lambda _left, _right: cast(Any, raw), "left", "right")


def test_task4_semantic_evidence_canonicalizes_float_decimal_and_negative_zero() -> (
    None
):
    candidate = _task4_scan_candidate(
        "a" * 24, "semantic candidate prompt", "semantic-family"
    )
    protected_prompts = {
        "train": ["semantic protected prompt"],
        "pilot-002": [],
        "phase16": [],
        "prior_candidate": [],
    }
    protected_family_ids: dict[str, set[str]] = {
        scope: set() for scope in runner.CONTAMINATION_SCOPES
    }

    float_scan = runner._scan_contamination(
        [candidate],
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
        semantic_similarity=lambda _left, _right: 0.9,
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    decimal_scan = runner._scan_contamination(
        [candidate],
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
        semantic_similarity=lambda _left, _right: Decimal("0.90"),
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    negative_zero_scan = runner._scan_contamination(
        [candidate],
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
        semantic_similarity=lambda _left, _right: -0.0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    zero_scan = runner._scan_contamination(
        [candidate],
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
        semantic_similarity=lambda _left, _right: Decimal("0.00"),
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert float_scan["rows"] == decimal_scan["rows"]
    assert negative_zero_scan["rows"] == zero_scan["rows"]


def test_task4_decimal_context_cannot_change_jaccard_or_scanner_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_prompt = "decimal context candidate prompt with unique long tokens"
    protected_prompt = "decimal context protected prompt with distinct long tokens"
    shared = {f"shared-{index}" for index in range(79)}
    union = shared | {f"extra-{index}" for index in range(20)}
    monkeypatch.setattr(
        runner,
        "_token_5grams",
        lambda text: (
            shared
            if text == candidate_prompt
            else union
            if text == protected_prompt
            else {f"token:{text}"}
        ),
    )
    monkeypatch.setattr(
        runner,
        "_character_5grams",
        lambda text: {f"character:{text}"},
    )
    candidate = _task4_scan_candidate(
        "1" * 24, candidate_prompt, "decimal-context-family"
    )

    def run_with_context(precision: int, rounding: str) -> tuple[Any, ...]:
        with localcontext() as context:
            context.prec = precision
            context.rounding = rounding
            value = runner._jaccard(shared, union)
            scan = runner._scan_contamination(
                [candidate],
                protected_prompts={
                    "train": [protected_prompt],
                    "pilot-002": [],
                    "phase16": [],
                    "prior_candidate": [],
                },
                protected_family_ids={
                    scope: set() for scope in runner.CONTAMINATION_SCOPES
                },
                semantic_similarity=lambda _left, _right: 0,
                semantic_model_authority=_task5_scanner_model_authority(),
            )
            return (
                value,
                runner._canonical_decimal(Decimal("1.2300")),
                scan["rows"],
                runner.canonical_sha256(scan),
            )

    low_precision = run_with_context(2, ROUND_HALF_EVEN)
    high_precision = run_with_context(28, ROUND_DOWN)

    assert low_precision == high_precision
    assert low_precision[0] < runner.TOKEN_5GRAM_JACCARD_MAX
    assert low_precision[1] == "1.23"
    assert low_precision[2][0]["scanner_decision"] == "PASS"
    assert "token_5gram_jaccard:train" not in low_precision[2][0]["rejection_codes"]


def test_task4_jaccard_isolates_all_decimal_context_state() -> None:
    shared = {f"shared-{index}" for index in range(79)}
    union = shared | {f"extra-{index}" for index in range(20)}

    outer_before = getcontext().copy()
    expected = runner._jaccard(shared, union)
    with localcontext() as hostile_context:
        hostile_context.prec = 2
        hostile_context.Emin = -9
        hostile_context.Emax = 9
        hostile_context.capitals = 0
        hostile_context.clamp = 1
        hostile_context.traps[Inexact] = True
        hostile_context.clear_flags()
        hostile_before = hostile_context.copy()

        actual = runner._jaccard(shared, union)

        assert repr(hostile_context) == repr(hostile_before)

    assert actual == expected
    assert actual < runner.TOKEN_5GRAM_JACCARD_MAX
    assert repr(getcontext()) == repr(outer_before)


def test_task4_protected_authority_scope_and_prompt_order_are_canonical() -> None:
    candidate = _task4_scan_candidate(
        "d" * 24, "canonical authority candidate", "canonical-family"
    )
    forward_prompts = {
        "train": ["z reference", "a reference", "a reference"],
        "pilot-002": [],
        "phase16": [],
        "prior_candidate": [],
    }
    reverse_prompts = {
        scope: (
            ["a reference", "z reference", "a reference"] if scope == "train" else []
        )
        for scope in reversed(runner.CONTAMINATION_SCOPES)
    }
    forward_families: dict[str, set[str]] = {
        scope: set() for scope in runner.CONTAMINATION_SCOPES
    }
    reverse_families: dict[str, set[str]] = {
        scope: set() for scope in reversed(runner.CONTAMINATION_SCOPES)
    }

    forward = runner._scan_contamination(
        [candidate],
        protected_prompts=forward_prompts,
        protected_family_ids=forward_families,
        semantic_similarity=lambda _left, _right: Decimal("0.90"),
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    reverse = runner._scan_contamination(
        [candidate],
        protected_prompts=reverse_prompts,
        protected_family_ids=reverse_families,
        semantic_similarity=lambda _left, _right: Decimal("0.90"),
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert forward == reverse


def test_task4_contamination_uses_one_immutable_protected_authority_snapshot() -> None:
    candidates = [
        _task4_scan_candidate(
            "e" * 24,
            "first immutable snapshot candidate with unique long text",
            "first-snapshot-family",
        ),
        _task4_scan_candidate(
            "f" * 24,
            "second immutable snapshot candidate with distinct long text",
            "second-snapshot-family",
        ),
    ]
    baseline_prompts = {
        "train": ["baseline train protected reference with unique long text"],
        "pilot-002": [],
        "phase16": [],
        "prior_candidate": [],
    }
    baseline_families: dict[str, set[str]] = {
        scope: set() for scope in runner.CONTAMINATION_SCOPES
    }
    baseline = runner._scan_contamination(
        candidates,
        protected_prompts=deepcopy(baseline_prompts),
        protected_family_ids=deepcopy(baseline_families),
        semantic_similarity=lambda _left, _right: 0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    mutable_prompts = deepcopy(baseline_prompts)
    mutable_families = deepcopy(baseline_families)
    callback_count = 0

    def mutate_original_authority(_left: str, _right: str) -> int:
        nonlocal callback_count
        callback_count += 1
        if callback_count == 1:
            mutable_prompts["pilot-002"].append(candidates[1]["prompt_text"])
            mutable_families["phase16"].add(candidates[1]["semantic_family_id"])
        return 0

    mutated = runner._scan_contamination(
        candidates,
        protected_prompts=mutable_prompts,
        protected_family_ids=mutable_families,
        semantic_similarity=mutate_original_authority,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert callback_count > 0
    assert mutable_prompts != baseline_prompts
    assert mutable_families != baseline_families
    assert mutated == baseline


def _task4_scan_candidate(
    candidate_id: str,
    prompt_text: str,
    semantic_family_id: str,
    *,
    generation_round: int = 1,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "generation_round": generation_round,
        "prompt_text": prompt_text,
        "prompt_text_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
        "semantic_family_id": semantic_family_id,
        "proposed_gold_skill_id": "test-skill-00",
        "proposed_negative_skill_id": "test-skill-01",
        "language": "en",
        "rationale": f"{PREFIX} LABELS MUST STAY UNCHANGED",
    }


def test_task4_contamination_scan_rejects_protected_exact_normalized_and_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        _task4_scan_candidate("1" * 24, "EXACT protected request", "family-a"),
        _task4_scan_candidate("2" * 24, "Ｆｏｏ request", "family-b"),
        _task4_scan_candidate("3" * 24, "Distinct family request", "family-pilot"),
        _task4_scan_candidate("4" * 24, "Prior protected request", "family-d"),
    ]
    original_labels = [
        (row["proposed_gold_skill_id"], row["proposed_negative_skill_id"])
        for row in candidates
    ]
    monkeypatch.setattr(runner, "_token_5grams", lambda text: {f"token:{text}"})
    monkeypatch.setattr(runner, "_character_5grams", lambda text: {f"character:{text}"})

    scan = runner._scan_contamination(
        candidates,
        protected_prompts={
            "train": ["EXACT protected request"],
            "pilot-002": ["Foo request"],
            "phase16": [],
            "prior_candidate": ["Prior protected request"],
        },
        protected_family_ids={
            "train": set(),
            "pilot-002": {"family-pilot"},
            "phase16": set(),
            "prior_candidate": set(),
        },
        semantic_similarity=lambda _left, _right: 0.0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    by_id = {row["candidate_id"]: row for row in scan["rows"]}
    assert "exact_prompt_bytes:train" in by_id["1" * 24]["rejection_codes"]
    assert "normalized_prompt:pilot-002" in by_id["2" * 24]["rejection_codes"]
    assert "protected_family:pilot-002" in by_id["3" * 24]["rejection_codes"]
    assert "exact_prompt_bytes:prior_candidate" in by_id["4" * 24]["rejection_codes"]
    assert scan["clean_candidate_ids"] == []
    assert all(
        set(row)
        == {
            "candidate_id",
            "scanner_decision",
            "rejection_codes",
            "evidence_sha256",
        }
        for row in scan["rows"]
    )
    assert [
        (row["proposed_gold_skill_id"], row["proposed_negative_skill_id"])
        for row in candidates
    ] == original_labels


@pytest.mark.parametrize(
    ("rule", "expected_code"),
    (
        ("token", "token_5gram_jaccard:train"),
        ("character", "character_5gram_jaccard:train"),
        ("semantic", "semantic_cosine:train"),
    ),
)
def test_task4_contamination_threshold_equality_rejects_without_float_drift(
    monkeypatch: pytest.MonkeyPatch,
    rule: str,
    expected_code: str,
) -> None:
    left = {f"shared-{index}" for index in range(17)}
    token_right = {f"shared-{index}" for index in range(4)} | {"token-extra"}
    character_right = left | {"char-extra-1", "char-extra-2", "char-extra-3"}
    monkeypatch.setattr(
        runner,
        "_token_5grams",
        lambda text: (
            (
                {f"shared-{index}" for index in range(4)}
                if text == "candidate prompt"
                else token_right
            )
            if rule == "token"
            else {f"token:{text}"}
        ),
    )
    monkeypatch.setattr(
        runner,
        "_character_5grams",
        lambda text: (
            left
            if text == "candidate prompt"
            else character_right
            if rule == "character"
            else {f"character:{text}"}
        ),
    )
    semantic_calls: list[tuple[str, str]] = []

    def semantic_similarity(left_text: str, right_text: str) -> float:
        semantic_calls.append((left_text, right_text))
        return 0.90 if rule == "semantic" else 0.0

    scan = runner._scan_contamination(
        [_task4_scan_candidate("5" * 24, "candidate prompt", "family-clean")],
        protected_prompts={
            "train": ["protected prompt"],
            "pilot-002": [],
            "phase16": [],
            "prior_candidate": [],
        },
        protected_family_ids={
            "train": set(),
            "pilot-002": set(),
            "phase16": set(),
            "prior_candidate": set(),
        },
        semantic_similarity=semantic_similarity,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert expected_code in scan["rows"][0]["rejection_codes"]
    assert scan["rows"][0]["scanner_decision"] == "REJECT"
    assert semantic_calls == [("candidate prompt", "protected prompt")]


def test_task4_current_candidate_conflict_uses_round_then_selection_key() -> None:
    same_round_ids = ("6" * 24, "7" * 24)
    expected_same_round_winner = min(same_round_ids, key=runner.selection_key)
    candidates = [
        _task4_scan_candidate(
            same_round_ids[0], "Shared current prompt", "shared-family"
        ),
        _task4_scan_candidate(
            same_round_ids[1], "Shared current prompt", "shared-family"
        ),
        _task4_scan_candidate(
            "8" * 24,
            "Shared current prompt",
            "shared-family",
            generation_round=2,
        ),
    ]

    scan = runner._scan_contamination(
        candidates,
        protected_prompts={
            "train": [],
            "pilot-002": [],
            "phase16": [],
            "prior_candidate": [],
        },
        protected_family_ids={
            "train": set(),
            "pilot-002": set(),
            "phase16": set(),
            "prior_candidate": set(),
        },
        semantic_similarity=lambda _left, _right: 0.0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert scan["clean_candidate_ids"] == [expected_same_round_winner]
    by_id = {row["candidate_id"]: row for row in scan["rows"]}
    for candidate_id in {row["candidate_id"] for row in candidates} - {
        expected_same_round_winner
    }:
        assert by_id[candidate_id]["scanner_decision"] == "REJECT"
        assert any(
            code.startswith("current_candidate:")
            for code in by_id[candidate_id]["rejection_codes"]
        )


def test_task4_current_candidate_loser_cannot_escape_protected_rejected_winner() -> (
    None
):
    winner_id = "b" * 24
    loser_id = "c" * 24
    scan = runner._scan_contamination(
        [
            _task4_scan_candidate(
                winner_id,
                "shared protected winner prompt",
                "protected-winner-family",
                generation_round=1,
            ),
            _task4_scan_candidate(
                loser_id,
                "shared protected winner prompt",
                "loser-family",
                generation_round=2,
            ),
        ],
        protected_prompts={scope: [] for scope in runner.CONTAMINATION_SCOPES},
        protected_family_ids={
            "train": {"protected-winner-family"},
            "pilot-002": set(),
            "phase16": set(),
            "prior_candidate": set(),
        },
        semantic_similarity=lambda _left, _right: 0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    by_id = {row["candidate_id"]: row for row in scan["rows"]}
    assert by_id[winner_id]["scanner_decision"] == "REJECT"
    assert by_id[loser_id]["scanner_decision"] == "REJECT"
    assert any(
        code.startswith(f"current_candidate:{winner_id}:")
        for code in by_id[loser_id]["rejection_codes"]
    )
    assert scan["clean_candidate_ids"] == []


@pytest.mark.parametrize("scope", ("train", "pilot-002", "phase16", "prior_candidate"))
def test_task4_contamination_scan_rejects_every_protected_family_scope(
    scope: str,
) -> None:
    protected_family_ids = {
        name: ({"protected-family"} if name == scope else set())
        for name in runner.CONTAMINATION_SCOPES
    }

    scan = runner._scan_contamination(
        [
            _task4_scan_candidate(
                "9" * 24, "Unique protected family prompt", "protected-family"
            )
        ],
        protected_prompts={name: [] for name in runner.CONTAMINATION_SCOPES},
        protected_family_ids=protected_family_ids,
        semantic_similarity=lambda _left, _right: 0.0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    assert scan["rows"][0]["scanner_decision"] == "REJECT"
    assert f"protected_family:{scope}" in scan["rows"][0]["rejection_codes"]


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


def _pack_invocation_identity(invocation: dict[str, Any]) -> str:
    identity_source = invocation.get("envelope", invocation)
    identity_fields = {"session_id", "thread_id"}.intersection(identity_source)
    assert len(identity_fields) == 1
    return cast(str, identity_source[next(iter(identity_fields))])


def _task5_fixture_projected_skills() -> list[dict[str, Any]]:
    return [
        {
            field: deepcopy(skill[field])
            for field in (
                "id",
                "name",
                "category",
                "description",
                "trigger_terms",
                "body",
            )
        }
        for skill in _skills()
    ]


def _task5_fixture_request(
    *,
    role: str,
    gold_skill_id: str | None = None,
    negative_quota: int | None = None,
    positive_only_quota: int | None = None,
    round_number: int | None = None,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = runner.AGENT_CONFIGS[role]
    if role == "generator":
        request_input = {
            "canonical_skills": _task5_fixture_projected_skills(),
            "rules": deepcopy(runner.GENERATOR_RULES),
            "quota": {
                "gold_skill_id": gold_skill_id,
                "negative_quota": negative_quota,
                "positive_only_quota": positive_only_quota,
                "round_number": round_number,
            },
        }
        schema_version = "router-v2-blind-v2-generation-request-v1"
        system_prompt = runner.GENERATOR_SYSTEM_PROMPT
        response_schema = runner.GENERATOR_RESPONSE_SCHEMA
    else:
        assert candidate is not None
        request_input = {
            "task_id": candidate["candidate_id"],
            "prompt_text": candidate["prompt_text"],
            "canonical_skills": _task5_fixture_projected_skills(),
            "rubric": deepcopy(runner.REVIEW_RUBRIC),
        }
        schema_version = "router-v2-blind-v2-review-request-v1"
        system_prompt = runner.REVIEWER_SYSTEM_PROMPT
        response_schema = runner.REVIEWER_RESPONSE_SCHEMA
    payload = {
        "schema_version": schema_version,
        "role": role,
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": system_prompt,
        "response_schema": deepcopy(response_schema),
        "input": request_input,
    }
    return {**payload, "request_sha256": _task5_test_canonical_sha256(payload)}


def _write_agent_pack(
    root: Path,
    *,
    legacy_single_candidate_generation: bool = False,
    rejected_candidate_count: int = 0,
    transport_retry_role: str | None = None,
    round_one_candidate_count: int = 256,
    round_one_negative_per_skill: int = 12,
    round_one_rejections: dict[tuple[str, str], int] | None = None,
    round_one_contamination_rejections: dict[tuple[str, str], int] | None = None,
    include_round_two: bool = False,
    round_two_deficit_multiplier: int = 2,
    reject_all_round_two: bool = False,
    include_round_three: bool = False,
    selection_authority: dict[str, Any] | None = None,
    protected_prompts: dict[str, list[str]] | None = None,
    protected_family_ids: dict[str, set[str]] | None = None,
    semantic_similarity: Callable[[str, str], int | float | Decimal] | None = None,
    current_conflict_with_protected: bool = False,
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

    candidate_specs: list[dict[str, Any]] = []
    round_one_rejections = round_one_rejections or {}
    round_one_contamination_rejections = round_one_contamination_rejections or {}
    rejected_by_stratum: dict[tuple[str, str], int] = {}
    contaminated_by_stratum: dict[tuple[str, str], int] = {}
    serial = 0
    for gold_index in range(16):
        gold = f"test-skill-{gold_index:02d}"
        for stratum_index in range(16):
            if len(candidate_specs) >= round_one_candidate_count:
                break
            has_negative = stratum_index < round_one_negative_per_skill
            stratum = "negative" if has_negative else "positive_only"
            rejected_so_far = rejected_by_stratum.get((gold, stratum), 0)
            contaminated_so_far = contaminated_by_stratum.get((gold, stratum), 0)
            should_reject = serial < rejected_candidate_count or rejected_so_far < (
                round_one_rejections.get((gold, stratum), 0)
            )
            should_contaminate = contaminated_so_far < (
                round_one_contamination_rejections.get((gold, stratum), 0)
            )
            if should_reject:
                rejected_by_stratum[(gold, stratum)] = rejected_so_far + 1
            if should_contaminate:
                contaminated_by_stratum[(gold, stratum)] = contaminated_so_far + 1
            candidate_specs.append(
                {
                    "generation_round": 1,
                    "serial": serial,
                    "gold": gold,
                    "negative": (
                        f"test-skill-{(gold_index + 1) % 16:02d}"
                        if has_negative
                        else None
                    ),
                    "review_rejected": should_reject,
                    "contamination_rejected": should_contaminate,
                }
            )
            serial += 1

    round_one_accepted_counts: dict[tuple[str, str], int] = {}
    for spec in candidate_specs:
        if spec["review_rejected"] or spec["contamination_rejected"]:
            continue
        stratum = "negative" if spec["negative"] is not None else "positive_only"
        key = (cast(str, spec["gold"]), stratum)
        round_one_accepted_counts[key] = round_one_accepted_counts.get(key, 0) + 1
    deficits = {
        (skill["id"], stratum): max(
            0,
            quota - round_one_accepted_counts.get((cast(str, skill["id"]), stratum), 0),
        )
        for skill in _skills()
        for stratum, quota in (("negative", 6), ("positive_only", 2))
    }
    if include_round_two:
        for (gold, stratum), deficit in deficits.items():
            for _ in range(deficit * round_two_deficit_multiplier):
                gold_index = int(gold.rsplit("-", 1)[1])
                candidate_specs.append(
                    {
                        "generation_round": 2,
                        "serial": serial,
                        "gold": gold,
                        "negative": (
                            f"test-skill-{(gold_index + 1) % 16:02d}"
                            if stratum == "negative"
                            else None
                        ),
                        "review_rejected": reject_all_round_two,
                        "contamination_rejected": False,
                    }
                )
                serial += 1
    if include_round_three:
        candidate_specs.append(
            {
                "generation_round": 3,
                "serial": serial,
                "gold": "test-skill-00",
                "negative": "test-skill-01",
                "review_rejected": False,
                "contamination_rejected": False,
            }
        )

    if current_conflict_with_protected:
        protected = next(
            spec for spec in candidate_specs if spec["contamination_rejected"]
        )
        protected_stratum = (
            "negative" if protected["negative"] is not None else "positive_only"
        )
        loser = next(
            spec
            for spec in candidate_specs
            if spec["generation_round"] == 2
            and spec["gold"] == protected["gold"]
            and ("negative" if spec["negative"] is not None else "positive_only")
            == protected_stratum
        )
        loser["prompt_override"] = _agent_pack_prompt(
            cast(int, protected["generation_round"]), cast(int, protected["serial"])
        )

    invocation_groups: list[list[dict[str, Any]]] = []
    if legacy_single_candidate_generation:
        invocation_groups = [[spec] for spec in candidate_specs]
    else:
        grouped_specs: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for spec in candidate_specs:
            key = (cast(int, spec["generation_round"]), cast(str, spec["gold"]))
            grouped_specs.setdefault(key, []).append(spec)
        invocation_groups = list(grouped_specs.values())

    candidate_by_id: dict[str, dict[str, Any]] = {}
    spec_by_id: dict[str, dict[str, Any]] = {}
    for group_index, group in enumerate(invocation_groups):
        first_spec = group[0]
        round_number = cast(int, first_spec["generation_round"])
        gold = cast(str, first_spec["gold"])
        negative_quota = sum(spec["negative"] is not None for spec in group)
        positive_only_quota = len(group) - negative_quota
        generation_request = _task5_fixture_request(
            role="generator",
            gold_skill_id=gold,
            negative_quota=negative_quota,
            positive_only_quota=positive_only_quota,
            round_number=round_number,
        )
        generated_candidates: list[dict[str, Any]] = []
        for candidate_index, spec in enumerate(group):
            serial = cast(int, spec["serial"])
            prompt = cast(
                str,
                spec.get("prompt_override", _agent_pack_prompt(round_number, serial)),
            )
            generated_candidates.append(
                {
                    "candidate_index": candidate_index,
                    "prompt_text": prompt,
                    "semantic_family_id": (
                        f"{PREFIX}_TRAIN_FAMILY"
                        if spec["contamination_rejected"]
                        else f"{PREFIX}_FAMILY_R{round_number}_{serial:03d}"
                    ),
                    "proposed_gold_skill_id": gold,
                    "proposed_negative_skill_id": spec["negative"],
                    "language": "en",
                    "rationale": f"{PREFIX} GENERATOR RATIONALE {serial:03d}",
                }
            )
        generation_response = {"candidates": generated_candidates}
        response_sha256 = _task5_test_canonical_sha256(generation_response)
        for generated, spec in zip(generated_candidates, group, strict=True):
            candidate_id = hashlib.sha256(
                (
                    f"{round_number}:{gold}:{generated['candidate_index']}:"
                    f"{response_sha256}"
                ).encode()
            ).hexdigest()[:24]
            prompt = cast(str, generated["prompt_text"])
            candidate = {
                "candidate_id": candidate_id,
                "generation_round": round_number,
                "prompt_text": prompt,
                "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "semantic_family_id": generated["semantic_family_id"],
                "proposed_gold_skill_id": gold,
                "proposed_negative_skill_id": generated["proposed_negative_skill_id"],
                "language": "en",
                "rationale": generated["rationale"],
            }
            candidate_by_id[candidate_id] = candidate
            spec_by_id[candidate_id] = spec
        generator_session = f"generator-r{round_number}-{gold}-{group_index:03d}"
        generator_invocations = [
            _pack_success_invocation(
                generation_request,
                generation_response,
                session_id=generator_session,
                transport_retry_count=0,
            )
        ]
        if transport_retry_role == "generator" and group_index == 0:
            failure_session = f"generator-transport-failure-{group_index:03d}"
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
                "generation_round": round_number,
                "gold_skill_id": gold,
                "request": generation_request,
                "invocations": generator_invocations,
            }
        )

    protected_prompts = protected_prompts or _task4_protected_prompts()
    protected_family_ids = protected_family_ids or _task4_protected_family_ids()
    semantic_similarity = semantic_similarity or (lambda _left, _right: 0.0)
    scan = runner._scan_contamination(
        list(candidate_by_id.values()),
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
        semantic_similarity=semantic_similarity,
        semantic_model_authority=_task5_scanner_model_authority(),
    )
    contamination_rows.extend(scan["rows"])
    clean_candidate_ids = set(scan["clean_candidate_ids"])

    for candidate_id, candidate in candidate_by_id.items():
        if candidate_id not in clean_candidate_ids:
            continue
        spec = spec_by_id[candidate_id]
        gold = cast(str, candidate["proposed_gold_skill_id"])
        negative = cast(str | None, candidate["proposed_negative_skill_id"])
        index = cast(int, spec["serial"])
        for role in ("reviewer_a", "reviewer_b"):
            review_request = _task5_fixture_request(role=role, candidate=candidate)
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
            if spec["review_rejected"] and role == "reviewer_a":
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

    for role in ("reviewer_a", "reviewer_b"):
        review_rows[role].sort(
            key=lambda row: runner.review_schedule_key(role, row["candidate_id"])
        )
        role_session_ids[role] = [
            _pack_invocation_identity(invocation)
            for row in review_rows[role]
            for invocation in row["invocations"]
        ]

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
                "request_count": (
                    len(generation_rows)
                    if role == "generator"
                    else len(review_rows[role])
                ),
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
                [row["candidate_id"] for row in review_rows[role]]
            )
            for role in ("reviewer_a", "reviewer_b")
        },
        "selection_authority": deepcopy(
            selection_authority or TASK4_SELECTION_AUTHORITY
        ),
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


def _fixture_generation_candidates(root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in _read_jsonl(root / "blind-v2-generation.jsonl"):
        response = row["invocations"][-1]["envelope"]["response"]
        response_sha256 = _task5_test_canonical_sha256(response)
        for generated in response["candidates"]:
            candidate_id = hashlib.sha256(
                (
                    f"{row['generation_round']}:{row['gold_skill_id']}:"
                    f"{generated['candidate_index']}:{response_sha256}"
                ).encode()
            ).hexdigest()[:24]
            prompt = generated["prompt_text"]
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "generation_round": row["generation_round"],
                    "prompt_text": prompt,
                    "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "semantic_family_id": generated["semantic_family_id"],
                    "proposed_gold_skill_id": generated["proposed_gold_skill_id"],
                    "proposed_negative_skill_id": generated[
                        "proposed_negative_skill_id"
                    ],
                    "language": generated["language"],
                    "rationale": generated["rationale"],
                }
            )
    return candidates


def _task5_test_canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _task5_test_canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _task5_fixture_run_records(root: Path, role: str) -> list[dict[str, Any]]:
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    records: list[dict[str, Any]] = []
    for row in _read_jsonl(root / filename):
        invocations = row["invocations"]
        request_payload = {
            key: value
            for key, value in row["request"].items()
            if key != "request_sha256"
        }
        request_sha256 = _task5_test_canonical_sha256(request_payload)
        attempts = []
        for ordinal, invocation in enumerate(invocations, start=1):
            envelope = invocation.get("envelope")
            if envelope is None:
                attempts.append(
                    {
                        "attempt_ordinal": ordinal,
                        "session_or_thread_id": _pack_invocation_identity(invocation),
                        "request_sha256": request_sha256,
                        "requested_model": invocation["requested_model"],
                        "returned_model": None,
                        "reasoning_effort": invocation["reasoning_effort"],
                        "transport_failure": True,
                        "response_bytes_present": False,
                        "response_sha256": None,
                        "outcome": "TRANSPORT_FAILURE_NO_RESPONSE",
                    }
                )
                continue
            attempts.append(
                {
                    "attempt_ordinal": ordinal,
                    "session_or_thread_id": _pack_invocation_identity(invocation),
                    "request_sha256": request_sha256,
                    "requested_model": envelope["requested_model"],
                    "returned_model": envelope["returned_model"],
                    "reasoning_effort": envelope["reasoning_effort"],
                    "transport_failure": False,
                    "response_bytes_present": True,
                    "response_sha256": _task5_test_canonical_sha256(
                        envelope["response"]
                    ),
                    "outcome": "VALID_RESPONSE",
                }
            )
        final_attempt = attempts[-1]
        if role == "generator":
            response = invocations[-1].get("envelope", {}).get("response")
            if type(response) is dict and type(response.get("candidates")) is list:
                response_sha256 = _task5_test_canonical_sha256(response)
                quota = row["request"]["input"]["quota"]
                candidate_ids = [
                    hashlib.sha256(
                        (
                            f"{quota['round_number']}:{quota['gold_skill_id']}:"
                            f"{candidate['candidate_index']}:{response_sha256}"
                        ).encode()
                    ).hexdigest()[:24]
                    for candidate in response["candidates"]
                ]
            else:
                candidate_ids = []
        else:
            candidate_ids = [row["candidate_id"]]
        records.append(
            {
                "invocation_id": request_sha256[:24],
                "candidate_ids": candidate_ids,
                "request_sha256": request_sha256,
                "response_sha256": final_attempt["response_sha256"],
                "requested_model": final_attempt["requested_model"],
                "returned_model": final_attempt["returned_model"],
                "reasoning_effort": final_attempt["reasoning_effort"],
                "session_or_thread_ids": [
                    _pack_invocation_identity(invocation) for invocation in invocations
                ],
                "transport_retry_count": len(invocations) - 1,
                "outcome": final_attempt["outcome"],
                "attempts": attempts,
            }
        )
    return records


@pytest.mark.parametrize("role", ("generator", "reviewer_a", "reviewer_b"))
def test_task5_fixture_recomputes_request_hash_instead_of_trusting_self_hash(
    tmp_path: Path,
    role: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    path = pack / filename
    rows = _read_jsonl(path)
    request_payload = {
        key: value
        for key, value in rows[0]["request"].items()
        if key != "request_sha256"
    }
    expected = _task5_test_canonical_sha256(request_payload)
    rows[0]["request"]["request_sha256"] = "0" * 64
    path.write_bytes(_jsonl_bytes(rows))

    records = _task5_fixture_run_records(pack, role)

    assert records[0]["request_sha256"] == expected
    assert records[0]["request_sha256"] != "0" * 64


def _task5_fixture_retry_records(
    records_by_role: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    retries: list[dict[str, Any]] = []
    for role, records in records_by_role.items():
        for record in records:
            if record["transport_retry_count"] == 0:
                continue
            identities = record["session_or_thread_ids"]
            retries.append(
                {
                    "role": role,
                    "invocation_id": record["invocation_id"],
                    "candidate_ids": deepcopy(record["candidate_ids"]),
                    "request_sha256": record["request_sha256"],
                    "response_sha256": record["response_sha256"],
                    "failed_session_or_thread_id": identities[0],
                    "retry_session_or_thread_id": identities[1],
                    "failed_attempt_ordinal": 1,
                    "retry_attempt_ordinal": 2,
                    "retry_count": 1,
                }
            )
    return sorted(retries, key=lambda row: (row["role"], row["invocation_id"]))


def _rewrite_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_bytes(_jsonl_bytes(rows))
    _refresh_agent_pack_metadata(path.parent)


def _sync_agent_pack_role_metadata(root: Path, role: str) -> None:
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    rows = _read_jsonl(root / filename)
    invocation_lists = [
        row["invocations"] for row in rows if type(row["invocations"]) is list
    ]
    metadata_path = root / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["roles"][role]["invocation_count"] = sum(
        len(invocations) for invocations in invocation_lists
    )
    metadata["roles"][role]["session_or_thread_ids"] = [
        _pack_invocation_identity(invocation)
        for invocations in invocation_lists
        for invocation in invocations
        if type(invocation) is dict
    ]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _task5_construction_input_bindings(
    protected_prompts: dict[str, list[str]],
    protected_family_ids: dict[str, set[str]],
) -> dict[str, Any]:
    skill_payload = _task5_test_canonical_json_bytes(_skills())
    protected_sources: dict[str, list[dict[str, str]]] = {}
    for scope in ("train", "pilot-002"):
        family_ids = sorted(protected_family_ids[scope])
        payload = _jsonl_bytes(
            [
                {
                    "query_text": prompt,
                    "positive_source_record_id": family_ids[
                        min(index, len(family_ids) - 1)
                    ],
                }
                for index, prompt in enumerate(protected_prompts[scope])
            ]
        )
        protected_sources[scope] = [
            {
                "path": f"authority/{scope}.jsonl",
                "file_sha256": hashlib.sha256(payload).hexdigest(),
                "source_bytes_hex": payload.hex(),
            }
        ]
    protected_sources["phase16"] = [
        {
            "path": f"authority/phase16/{index:03d}.md",
            "file_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "source_bytes_hex": prompt.encode("utf-8").hex(),
        }
        for index, prompt in enumerate(protected_prompts["phase16"])
    ]
    return {
        "canonical_skill_source": {
            "path": "authority/skills.json",
            "file_sha256": hashlib.sha256(skill_payload).hexdigest(),
            "source_bytes_hex": skill_payload.hex(),
        },
        "protected_scope_sources": protected_sources,
    }


def _validate_agent_pack(
    pack: Path,
    repository_root: Path,
    *,
    protected_prompts: dict[str, list[str]] | None = None,
    protected_family_ids: dict[str, set[str]] | None = None,
    semantic_similarity: Callable[[str, str], int | float | Decimal] | None = None,
    semantic_model_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    protected_prompts = protected_prompts or _task4_protected_prompts()
    protected_family_ids = protected_family_ids or _task4_protected_family_ids()
    return runner.validate_agent_pack(
        pack,
        repository_root=repository_root,
        canonical_skills=_skills(),
        train_prompts=protected_prompts["train"],
        pilot_prompts=protected_prompts["pilot-002"],
        phase16_prompts=protected_prompts["phase16"],
        prior_candidate_prompts=protected_prompts["prior_candidate"],
        train_family_ids=protected_family_ids["train"],
        pilot_family_ids=protected_family_ids["pilot-002"],
        phase16_family_ids=protected_family_ids["phase16"],
        prior_candidate_family_ids=protected_family_ids["prior_candidate"],
        first_read_timestamp="2026-07-16T00:00:00Z",
        semantic_similarity=semantic_similarity or (lambda _left, _right: 0.0),
        semantic_model_authority=(
            semantic_model_authority or _task5_scanner_model_authority()
        ),
        construction_input_bindings=_task5_construction_input_bindings(
            protected_prompts, protected_family_ids
        ),
    )


def test_task5_round_one_generation_uses_16_invocations_with_16_candidates_each(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    generation_rows = _read_jsonl(pack / "blind-v2-generation.jsonl")

    assert len(generation_rows) == 16
    for gold_index, row in enumerate(generation_rows):
        assert set(row) == {
            "generation_round",
            "gold_skill_id",
            "request",
            "invocations",
        }
        assert row["generation_round"] == 1
        assert row["gold_skill_id"] == f"test-skill-{gold_index:02d}"
        quota = row["request"]["input"]["quota"]
        assert quota == {
            "gold_skill_id": row["gold_skill_id"],
            "negative_quota": 12,
            "positive_only_quota": 4,
            "round_number": 1,
        }
        response = row["invocations"][-1]["envelope"]["response"]
        assert [
            candidate["candidate_index"] for candidate in response["candidates"]
        ] == list(range(16))
        response_sha256 = _task5_test_canonical_sha256(response)
        expected_ids = [
            hashlib.sha256(
                f"1:{row['gold_skill_id']}:{index}:{response_sha256}".encode()
            ).hexdigest()[:24]
            for index in range(16)
        ]
        assert len(set(expected_ids)) == 16

    validation = _validate_agent_pack(pack, tmp_path / "repo")
    assert validation["status"] == "VALID"
    assert validation["agent_roles"]["generator"]["request_count"] == 16
    assert validation["agent_roles"]["generator"]["invocation_count"] == 16
    assert [
        len(record["candidate_ids"])
        for record in validation["agent_run_records"]["generator"]
    ] == [16] * 16


def test_task5_validation_commits_canonical_skill_and_protected_input_authority(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    validation = _validate_agent_pack(pack, tmp_path / "repo")

    authority = validation["construction_input_authority"]
    assert authority["canonical_skill_projection"]["row_count"] == 16
    assert set(authority["protected_artifact_projections"]) == {
        "train",
        "pilot-002",
        "phase16",
    }
    assert all(
        projection["protected_authority"]["prompt_count"] > 0
        for projection in authority["protected_artifact_projections"].values()
    )


def test_task5_rejects_256_single_candidate_generator_requests(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, legacy_single_candidate_generation=True)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "generation_ledger"


def test_task5_invalid_generator_response_never_enters_candidate_pipeline(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    generation_path = pack / "blind-v2-generation.jsonl"
    generation_rows = _read_jsonl(generation_path)
    generation_rows[0]["invocations"][-1]["envelope"]["response"]["candidates"][0].pop(
        "rationale"
    )
    _rewrite_jsonl(generation_path, generation_rows)
    semantic_calls: list[tuple[str, str]] = []

    result = _validate_agent_pack(
        pack,
        tmp_path / "repo",
        semantic_similarity=lambda left, right: (
            semantic_calls.append((left, right)) or 0.0
        ),
    )

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "generation_rounds"
    assert semantic_calls == []
    failed_record = result["agent_run_records"]["generator"][0]
    failed_response = generation_rows[0]["invocations"][-1]["envelope"]["response"]
    assert failed_record["candidate_ids"] == []
    assert failed_record["response_sha256"] == _task5_test_canonical_sha256(
        failed_response
    )
    assert failed_record["returned_model"] == runner.AGENT_CONFIGS["generator"]["model"]
    assert failed_record["outcome"] == "SUBSTANTIVE_INVALID_RESPONSE"
    assert "response" not in failed_record
    assert result["tasks"] == []


@pytest.mark.parametrize("invocation_count", (2, 3))
def test_task5_multiple_substantive_responses_are_global_protocol_invalid(
    tmp_path: Path,
    invocation_count: int,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    review_path = pack / "blind-v2-review-a.jsonl"
    review_rows = _read_jsonl(review_path)
    original = review_rows[0]["invocations"][0]
    for ordinal in range(1, invocation_count):
        duplicate = deepcopy(original)
        duplicate["envelope"]["session_id"] = (
            f"reviewer-a-illegal-substantive-{ordinal}"
        )
        duplicate["envelope"]["transport_retry_count"] = 1
        review_rows[0]["invocations"].append(duplicate)
    _rewrite_jsonl(review_path, review_rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize("scope", runner.CONTAMINATION_SCOPES)
@pytest.mark.parametrize("authority_kind", ("prompt", "family"))
def test_task4_pack_rejects_unmatched_protected_authority_mutation(
    tmp_path: Path, scope: str, authority_kind: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    protected_prompts = _task4_protected_prompts()
    protected_family_ids = _task4_protected_family_ids()
    if authority_kind == "prompt":
        protected_prompts[scope].append(
            f"{PREFIX} UNMATCHED {scope} PROTECTED PROMPT MUTATION"
        )
    else:
        protected_family_ids[scope].add(
            f"{PREFIX}_UNMATCHED_{scope}_PROTECTED_FAMILY_MUTATION"
        )

    result = _validate_agent_pack(
        pack,
        tmp_path / "repo",
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
    )

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "contamination_ledger"


def test_task4_legal_protected_authorities_have_distinct_audit_hashes(
    tmp_path: Path,
) -> None:
    baseline_pack = tmp_path / "baseline-pack"
    changed_pack = tmp_path / "changed-pack"
    baseline_prompts = _task4_protected_prompts()
    baseline_families = _task4_protected_family_ids()
    changed_prompts = deepcopy(baseline_prompts)
    changed_families = deepcopy(baseline_families)
    changed_prompts["prior_candidate"].extend(
        [f"{PREFIX} UNMATCHED DUPLICATE", f"{PREFIX} UNMATCHED DUPLICATE"]
    )
    changed_families["phase16"].add(f"{PREFIX}_UNMATCHED_PHASE16_FAMILY")
    _write_agent_pack(
        baseline_pack,
        protected_prompts=baseline_prompts,
        protected_family_ids=baseline_families,
    )
    _write_agent_pack(
        changed_pack,
        protected_prompts=changed_prompts,
        protected_family_ids=changed_families,
    )

    baseline = _validate_agent_pack(
        baseline_pack,
        tmp_path / "repo",
        protected_prompts=baseline_prompts,
        protected_family_ids=baseline_families,
    )
    changed = _validate_agent_pack(
        changed_pack,
        tmp_path / "repo",
        protected_prompts=changed_prompts,
        protected_family_ids=changed_families,
    )

    assert baseline["status"] == changed["status"] == "VALID"
    assert (
        baseline["contamination_audit"]["protected_authority"]
        != changed["contamination_audit"]["protected_authority"]
    )
    assert (
        baseline["contamination_audit"]["protected_authority_sha256"]
        != changed["contamination_audit"]["protected_authority_sha256"]
    )
    prior_summary = changed["contamination_audit"]["protected_authority"][
        "prior_candidate"
    ]
    assert prior_summary["prompt_count"] == 2
    assert set(prior_summary) == {
        "prompt_count",
        "prompt_bytes_sha256",
        "normalized_prompt_list_sha256",
        "family_count",
        "family_ids_sha256",
    }


def test_task4_pack_current_loser_is_rejected_after_protected_winner(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_contamination_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
        current_conflict_with_protected=True,
    )
    generation_rows = _fixture_generation_candidates(pack)
    prompt_groups: dict[str, list[dict[str, Any]]] = {}
    for row in generation_rows:
        prompt_groups.setdefault(row["prompt_text"], []).append(row)
    winner, loser = next(
        sorted(rows, key=lambda row: row["generation_round"])
        for rows in prompt_groups.values()
        if len(rows) == 2
    )

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["candidate_outcomes"][winner["candidate_id"]] == (
        "REJECTED_CONTAMINATION"
    )
    assert result["candidate_outcomes"][loser["candidate_id"]] == (
        "REJECTED_CONTAMINATION"
    )


@pytest.mark.parametrize(
    ("rule", "expected_code"),
    (
        ("token", "token_5gram_jaccard:train"),
        ("character", "character_5gram_jaccard:train"),
        ("semantic", "semantic_cosine:train"),
    ),
)
def test_task4_pack_threshold_equality_rejects_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule: str,
    expected_code: str,
) -> None:
    pack = tmp_path / "agent-pack"
    target_prompt = _agent_pack_prompt(1, 0)
    protected_prompt = f"{PREFIX} TRAIN REFERENCE"
    token_shared = {f"token-shared-{index}" for index in range(4)}
    character_shared = {f"character-shared-{index}" for index in range(17)}
    monkeypatch.setattr(
        runner,
        "_token_5grams",
        lambda text: (
            token_shared
            if rule == "token" and text == target_prompt
            else token_shared | {"token-extra"}
            if rule == "token" and text == protected_prompt
            else {f"token:{text}"}
        ),
    )
    monkeypatch.setattr(
        runner,
        "_character_5grams",
        lambda text: (
            character_shared
            if rule == "character" and text == target_prompt
            else character_shared
            | {"character-extra-1", "character-extra-2", "character-extra-3"}
            if rule == "character" and text == protected_prompt
            else {f"character:{text}"}
        ),
    )

    def semantic_similarity(left: str, right: str) -> Decimal:
        return (
            Decimal("0.90")
            if rule == "semantic"
            and left == target_prompt
            and right == protected_prompt
            else Decimal("0")
        )

    _write_agent_pack(pack, semantic_similarity=semantic_similarity)

    result = _validate_agent_pack(
        pack, tmp_path / "repo", semantic_similarity=semantic_similarity
    )
    target_id = next(
        row["candidate_id"]
        for row in _fixture_generation_candidates(pack)
        if row["prompt_text"] == target_prompt
    )
    contamination = {
        row["candidate_id"]: row
        for row in _read_jsonl(pack / "blind-v2-contamination.jsonl")
    }

    assert result["status"] == "VALID"
    assert result["candidate_outcomes"][target_id] == "REJECTED_CONTAMINATION"
    assert expected_code in contamination[target_id]["rejection_codes"]


def test_task4_round_one_is_exact_256_with_frozen_per_skill_strata(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["selection_audit"]["round_1_candidate_count"] == 256
    assert result["selection_audit"]["round_2_candidate_count"] == 0
    assert all(
        counts == {"negative": 12, "positive_only": 4}
        for counts in result["selection_audit"]["round_1_distribution"].values()
    )
    assert (
        result["selection_audit"]["round_1_request_quota_distribution"]
        == (result["selection_audit"]["round_1_distribution"])
    )


@pytest.mark.parametrize(
    "fixture_options",
    (
        {"round_one_candidate_count": 255},
        {"round_one_negative_per_skill": 11},
    ),
)
def test_task4_round_one_count_or_stratum_drift_is_global_protocol_invalid(
    tmp_path: Path, fixture_options: dict[str, Any]
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, **fixture_options)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "generation_rounds"


def test_task4_round_two_uses_twice_post_pipeline_numeric_deficits_only(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    round_one_rejections = {
        ("test-skill-00", "positive_only"): 3,
    }
    _write_agent_pack(
        pack,
        round_one_rejections=round_one_rejections,
        round_one_contamination_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
    )

    result = _validate_agent_pack(pack, tmp_path / "repo")
    generation_invocations = _read_jsonl(pack / "blind-v2-generation.jsonl")
    generation_rows = _fixture_generation_candidates(pack)
    round_two_rows = [row for row in generation_rows if row["generation_round"] == 2]

    assert result["status"] == "VALID"
    assert result["selection_audit"]["round_1_post_pipeline_deficits"] == {
        "test-skill-00": {"negative": 1, "positive_only": 1}
    }
    assert len(round_two_rows) == 4
    round_two_invocations = [
        row for row in generation_invocations if row["generation_round"] == 2
    ]
    assert len(round_two_invocations) == 1
    assert (
        sum(row["proposed_negative_skill_id"] is not None for row in round_two_rows)
        == 2
    )
    assert sum(row["proposed_negative_skill_id"] is None for row in round_two_rows) == 2
    assert (
        result["selection_audit"]["round_2_request_quota_distribution"]
        == (result["selection_audit"]["round_2_distribution"])
    )
    for row in round_two_invocations:
        request_input = row["request"]["input"]
        assert set(request_input) == {"canonical_skills", "rules", "quota"}
        encoded = json.dumps(request_input, sort_keys=True).casefold()
        for forbidden in (
            "rejected prompt",
            "rejection reason",
            "reviewer label",
            "contamination score",
            "arm a",
            "arm c",
        ):
            assert forbidden not in encoded

    round_two_ids = {row["candidate_id"] for row in round_two_rows}
    round_one_ids = {
        row["candidate_id"] for row in generation_rows if row["generation_round"] == 1
    }
    all_role_sessions: list[str] = []
    for role in ("a", "b"):
        review_rows = _read_jsonl(pack / f"blind-v2-review-{role}.jsonl")
        assert round_two_ids <= {row["candidate_id"] for row in review_rows}
        assert all(
            set(row["request"]["input"])
            == {"task_id", "prompt_text", "canonical_skills", "rubric"}
            for row in review_rows
            if row["candidate_id"] in round_two_ids
        )
        role_name = f"reviewer_{role}"
        assert [row["candidate_id"] for row in review_rows] == sorted(
            (row["candidate_id"] for row in review_rows),
            key=lambda candidate_id: runner.review_schedule_key(
                role_name, candidate_id
            ),
        )
        round_one_sessions = {
            _pack_invocation_identity(invocation)
            for row in review_rows
            if row["candidate_id"] in round_one_ids
            for invocation in row["invocations"]
        }
        round_two_sessions = {
            _pack_invocation_identity(invocation)
            for row in review_rows
            if row["candidate_id"] in round_two_ids
            for invocation in row["invocations"]
        }
        assert round_one_sessions.isdisjoint(round_two_sessions)
        all_role_sessions.extend(round_one_sessions | round_two_sessions)
    assert len(all_role_sessions) == len(set(all_role_sessions))


@pytest.mark.parametrize("drift", ("short_round_two", "round_three"))
def test_task4_rejects_round_two_count_drift_and_any_round_three(
    tmp_path: Path, drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    options: dict[str, Any] = {
        "round_one_rejections": {("test-skill-00", "negative"): 7},
        "include_round_two": True,
    }
    if drift == "short_round_two":
        options["round_two_deficit_multiplier"] = 1
    else:
        options["include_round_three"] = True
    _write_agent_pack(pack, **options)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "generation_rounds"


def test_task4_round_two_insufficiency_records_deficits_and_ledger_hashes(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
        reject_all_round_two=True,
    )

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INSUFFICIENT"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_DATASET_INSUFFICIENT"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["deficits"] == {"test-skill-00": {"negative": 1, "positive_only": 0}}
    assert result["ledger_sha256"] == result["source_file_sha256"]
    assert result["tasks"] == []
    round_two_ids = {
        row["candidate_id"]
        for row in _fixture_generation_candidates(pack)
        if row["generation_round"] == 2
    }
    assert {
        result["candidate_outcomes"][candidate_id] for candidate_id in round_two_ids
    } == {"REJECTED_REVIEW"}


@pytest.mark.parametrize(
    ("transport_case", "expected_status", "expected_stage"),
    (
        ("empty", "INVALID", "invocation_protocol"),
        ("invalid_retry_count", "INVALID", "invocation_protocol"),
    ),
)
def test_task4_round_two_transport_failure_is_not_masked_by_round_one_surplus(
    tmp_path: Path,
    transport_case: str,
    expected_status: str,
    expected_stage: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
    )
    round_two_ids = {
        row["candidate_id"]
        for row in _fixture_generation_candidates(pack)
        if row["generation_round"] == 2
    }
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    round_two_rows = [row for row in rows if row["candidate_id"] in round_two_ids]
    if transport_case == "empty":
        for row in round_two_rows:
            row["invocations"] = []
    else:
        round_two_rows[0]["invocations"][0]["envelope"]["transport_retry_count"] = 1
    _rewrite_jsonl(path, rows)
    if transport_case == "empty":
        _sync_agent_pack_role_metadata(pack, "reviewer_a")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == expected_status
    assert result["failure_stage"] == expected_stage
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"


def test_task4_round_two_session_reuse_is_global_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
    )
    round_two_ids = {
        row["candidate_id"]
        for row in _fixture_generation_candidates(pack)
        if row["generation_round"] == 2
    }
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    round_one_row = next(
        row for row in rows if row["candidate_id"] not in round_two_ids
    )
    round_two_row = next(row for row in rows if row["candidate_id"] in round_two_ids)
    reused_session = _pack_invocation_identity(round_one_row["invocations"][0])
    round_two_row["invocations"][0]["envelope"]["session_id"] = reused_session
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "agent_run_metadata"


@pytest.mark.parametrize(
    ("round_number", "expected_stage"),
    ((1, "generation_rounds"), (2, "contamination_ledger")),
)
def test_task4_generator_quota_self_signed_drift_is_protocol_invalid(
    tmp_path: Path, round_number: int, expected_stage: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_rejections=(
            {("test-skill-00", "negative"): 7} if round_number == 2 else None
        ),
        include_round_two=round_number == 2,
    )
    path = pack / "blind-v2-generation.jsonl"
    rows = _read_jsonl(path)
    row = next(row for row in rows if row["generation_round"] == round_number)
    quota = row["request"]["input"]["quota"]
    quota["negative_quota"] = 0
    quota["positive_only_quota"] = 1
    _agent_contract_rehash_request(row["request"])
    for invocation in row["invocations"]:
        invocation["envelope"]["request_sha256"] = row["request"]["request_sha256"]
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == expected_stage


def test_task4_selection_is_hash_ordered_unique_and_canonical_twice(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    first = _validate_agent_pack(pack, tmp_path / "repo")
    second = _validate_agent_pack(pack, tmp_path / "repo")

    assert first == second
    assert runner.canonical_sha256(first) == runner.canonical_sha256(second)
    assert first["status"] == "VALID"
    tasks = first["tasks"]
    assert len(tasks) == 128
    assert sum(row["proposed_negative_skill_id"] is not None for row in tasks) == 96
    assert len({row["candidate_id"] for row in tasks}) == 128
    assert len({row["prompt_text"].encode() for row in tasks}) == 128
    assert len({runner._normalize(row["prompt_text"]) for row in tasks}) == 128
    assert len({row["semantic_family_id"] for row in tasks}) == 128
    for skill in _skills():
        skill_tasks = [
            row for row in tasks if row["proposed_gold_skill_id"] == skill["id"]
        ]
        for has_negative, expected_count in ((True, 6), (False, 2)):
            stratum_ids = [
                row["candidate_id"]
                for row in skill_tasks
                if (row["proposed_negative_skill_id"] is not None) is has_negative
            ]
            assert len(stratum_ids) == expected_count
            assert stratum_ids == sorted(stratum_ids, key=runner.selection_key)
    assert first["selection_audit"]["selected_candidate_ids"] == [
        row["candidate_id"] for row in tasks
    ]
    assert first["contamination_audit"]["required_semantic_model_id"] == (
        "sentence-transformers/all-mpnet-base-v2"
    )
    assert first["contamination_audit"]["required_semantic_model_revision"] == (
        "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    )
    assert first["contamination_audit"]["semantic_scorer_runtime_verified"] is False
    assert first["contamination_audit"]["semantic_scorer_receipt_sha256"] is None


def test_task4_semantic_audit_freezes_required_contract_without_runtime_claim(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    result = _validate_agent_pack(pack, tmp_path / "repo")
    scan = runner._scan_contamination(
        [],
        protected_prompts={scope: [] for scope in runner.CONTAMINATION_SCOPES},
        protected_family_ids={scope: set() for scope in runner.CONTAMINATION_SCOPES},
        semantic_similarity=lambda _left, _right: 0,
        semantic_model_authority=_task5_scanner_model_authority(),
    )

    for audit in (scan["scanner_config"], result["contamination_audit"]):
        assert audit["required_semantic_model_id"] == (
            "sentence-transformers/all-mpnet-base-v2"
        )
        assert audit["required_semantic_model_revision"] == (
            "e8c3b32edf5434bc2275fc9bab85f82640a19130"
        )
        assert audit["semantic_scorer_runtime_verified"] is False
        assert audit["semantic_scorer_receipt_sha256"] is None
        assert "semantic_model_id" not in audit
        assert "semantic_model_revision" not in audit


def test_task5_scanner_model_files_are_bound_from_validated_authority(
    tmp_path: Path,
) -> None:
    authority = _task5_scanner_model_authority()
    scan = runner._scan_contamination(
        [],
        protected_prompts={scope: [] for scope in runner.CONTAMINATION_SCOPES},
        protected_family_ids={scope: set() for scope in runner.CONTAMINATION_SCOPES},
        semantic_similarity=lambda _left, _right: 0,
        semantic_model_authority=authority,
    )
    assert (
        scan["scanner_config"]["materialized_model_files"]
        == authority["materialized_model_files"]
    )
    assert (
        scan["scanner_config"]["materialized_model_files_sha256"]
        == authority["materialized_model_files_sha256"]
    )

    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(
        pack,
        tmp_path / "repo",
        semantic_model_authority=authority,
    )
    audit = validation["contamination_audit"]
    assert audit["materialized_model_files"] == authority["materialized_model_files"]
    assert (
        audit["materialized_model_files_sha256"]
        == authority["materialized_model_files_sha256"]
    )
    assert len(audit["scanner_config_sha256"]) == 64
    assert audit["semantic_scorer_runtime_verified"] is False
    assert audit["semantic_scorer_receipt_sha256"] is None

    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    manifest = json.loads(documents["blind-v2-manifest.json"])
    frozen = manifest["agent_construction"]["contamination"]
    assert frozen["materialized_model_files"] == authority["materialized_model_files"]
    assert (
        frozen["materialized_model_files_sha256"]
        == authority["materialized_model_files_sha256"]
    )
    assert frozen["scanner_config_sha256"] == audit["scanner_config_sha256"]
    assert frozen["semantic_scorer_runtime_verified"] is False
    assert frozen["semantic_scorer_receipt_sha256"] is None


@pytest.mark.parametrize(
    ("case", "expected_message"),
    (
        ("duplicate_path", "paths must be unique"),
        ("unsorted", "files must be sorted"),
        ("noncanonical_path", "path must be normalized"),
        ("nul_path", "path must be normalized"),
        ("invalid_hash", "file SHA-256"),
        ("aggregate_mismatch", "aggregate hash mismatch"),
    ),
)
def test_task5_scanner_model_authority_is_fail_closed(
    case: str, expected_message: str
) -> None:
    files = deepcopy(_task5_scanner_model_authority()["materialized_model_files"])
    if case == "duplicate_path":
        files[1]["path"] = files[0]["path"]
        authority = _task5_scanner_model_authority(files)
    elif case == "unsorted":
        authority = _task5_scanner_model_authority(list(reversed(files)))
    elif case == "noncanonical_path":
        files[1]["path"] = "weights/../model.safetensors"
        authority = _task5_scanner_model_authority(files)
    elif case == "nul_path":
        files[1]["path"] = "model\0.safetensors"
        authority = _task5_scanner_model_authority(files)
    elif case == "invalid_hash":
        files[1]["sha256"] = "f" * 63
        authority = _task5_scanner_model_authority(files)
    else:
        authority = _task5_scanner_model_authority(files)
        authority["materialized_model_files_sha256"] = "0" * 64

    with pytest.raises(ValueError, match=expected_message):
        runner._scan_contamination(
            [],
            protected_prompts={scope: [] for scope in runner.CONTAMINATION_SCOPES},
            protected_family_ids={
                scope: set() for scope in runner.CONTAMINATION_SCOPES
            },
            semantic_similarity=lambda _left, _right: 0,
            semantic_model_authority=authority,
        )


def test_task4_selection_authority_drift_is_global_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    drifted = deepcopy(TASK4_SELECTION_AUTHORITY)
    drifted["selection_seed"] = 7171
    _write_agent_pack(pack, selection_authority=drifted)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "selection_authority"


def test_task4_deterministic_selection_internal_value_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    original_selection_key = runner.selection_key
    calls = 0

    def fail_after_contamination_scan(candidate_id: str) -> str:
        nonlocal calls
        calls += 1
        if calls > 256:
            raise ValueError(f"{PREFIX} DETERMINISTIC SELECTION FAILURE")
        return original_selection_key(candidate_id)

    monkeypatch.setattr(runner, "selection_key", fail_after_contamination_scan)

    with pytest.raises(ValueError, match=f"{PREFIX} DETERMINISTIC SELECTION FAILURE"):
        _validate_agent_pack(pack, tmp_path / "repo")


def test_task4_deterministic_selection_protocol_violation_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validate_selection = runner._validate_deterministic_selection

    def force_unique_violation(selected: list[dict[str, Any]], **kwargs: Any) -> None:
        kwargs["selected_ids"] = set()
        validate_selection(selected, **kwargs)

    monkeypatch.setattr(
        runner,
        "_validate_deterministic_selection",
        force_unique_violation,
        raising=False,
    )

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "deterministic_selection"
    assert result["failure_reason"] == (
        "selected task, prompt, normalized prompt, and family values must be unique"
    )


def test_task4_contamination_ledger_is_non_voting_and_hidden_from_reviewers(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    contamination_rows = _read_jsonl(pack / "blind-v2-contamination.jsonl")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert all(
        set(row)
        == {
            "candidate_id",
            "scanner_decision",
            "rejection_codes",
            "evidence_sha256",
        }
        for row in contamination_rows
    )
    encoded_ledger = json.dumps(contamination_rows, sort_keys=True)
    for forbidden in (
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
    ):
        assert forbidden not in encoded_ledger
    for role in ("a", "b"):
        for row in _read_jsonl(pack / f"blind-v2-review-{role}.jsonl"):
            encoded_request = json.dumps(row["request"], sort_keys=True)
            assert "scanner_decision" not in encoded_request
            assert "rejection_codes" not in encoded_request
            assert "evidence_sha256" not in encoded_request


@pytest.mark.parametrize(
    ("drift", "failure_stage"),
    (("invalid_utf8", "ledger_structure"), ("label_field", "contamination_ledger")),
)
def test_task4_contamination_ledger_rejects_utf8_or_schema_drift(
    tmp_path: Path, drift: str, failure_stage: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-contamination.jsonl"
    if drift == "invalid_utf8":
        path.write_bytes(b"\xff\n")
        _refresh_agent_pack_metadata(pack)
    else:
        rows = _read_jsonl(path)
        rows[0]["proposed_gold_skill_id"] = "test-skill-00"
        _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == failure_stage


@pytest.mark.parametrize(
    ("mutation", "field"),
    (
        ("field_value", "description"),
        ("field_value", "body"),
        ("field_value", "name"),
        ("field_value", "trigger_terms"),
        ("skill_order", None),
        ("delete_skill", None),
        ("extra_skill_field", None),
    ),
)
def test_agent_pack_generator_request_binds_authoritative_canonical_skills(
    tmp_path: Path, mutation: str, field: str | None
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-generation.jsonl"
    rows = _read_jsonl(path)
    request = rows[0]["request"]
    sealed_skills = request["input"]["canonical_skills"]
    if mutation == "field_value":
        assert field is not None
        sealed_skills[0][field] = (
            [f"{PREFIX} DRIFTED TRIGGER"]
            if field == "trigger_terms"
            else f"{PREFIX} DRIFTED {field.upper()}"
        )
    elif mutation == "skill_order":
        sealed_skills[0], sealed_skills[1] = sealed_skills[1], sealed_skills[0]
    elif mutation == "delete_skill":
        sealed_skills.pop()
    else:
        sealed_skills[0]["unsealed_field"] = f"{PREFIX} DRIFTED EXTRA"
    _agent_contract_rehash_request(request)
    for invocation in rows[0]["invocations"]:
        invocation.get("envelope", invocation)["request_sha256"] = request[
            "request_sha256"
        ]
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "generation_ledger"


def test_agent_pack_required_file_read_failure_is_audited_protocol_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    failed_filename = "blind-v2-review-a.jsonl"
    original_read_bytes = Path.read_bytes

    def fail_one_required_read(path: Path) -> bytes:
        if path.name == failed_filename:
            raise OSError(f"{PREFIX} REQUIRED FILE READ FAILURE")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_one_required_read)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "ledger_structure"
    assert result["failure_reason"] == f"{PREFIX} REQUIRED FILE READ FAILURE"


def test_agent_pack_stale_source_file_hash_is_global_invalid(tmp_path: Path) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-generation.jsonl"
    rows = _read_jsonl(path)
    rows[0]["rationale"] = f"{PREFIX} STALE HASH MUTATION"
    path.write_bytes(_jsonl_bytes(rows))

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "agent_run_metadata"
    assert result["failure_reason"] == "blind-v2-generation.jsonl source hash mismatch"


def test_agent_pack_generator_response_hash_must_bind_candidate_id(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-generation.jsonl"
    rows = _read_jsonl(path)
    old_candidate_ids = {
        candidate["candidate_id"]
        for candidate in _fixture_generation_candidates(pack)
        if candidate["proposed_gold_skill_id"] == rows[0]["gold_skill_id"]
    }
    changed_rationale = f"{PREFIX} RESPONSE HASH MUTATION"
    rows[0]["invocations"][-1]["envelope"]["response"]["candidates"][0]["rationale"] = (
        changed_rationale
    )
    _rewrite_jsonl(path, rows)

    new_candidate_ids = {
        candidate["candidate_id"]
        for candidate in _fixture_generation_candidates(pack)
        if candidate["proposed_gold_skill_id"] == rows[0]["gold_skill_id"]
    }
    assert old_candidate_ids.isdisjoint(new_candidate_ids)
    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "contamination_ledger"


def test_agent_pack_reviewer_ledgers_use_distinct_role_schedules(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    reviewer_a_ids = [
        row["candidate_id"] for row in _read_jsonl(pack / "blind-v2-review-a.jsonl")
    ]
    reviewer_b_ids = [
        row["candidate_id"] for row in _read_jsonl(pack / "blind-v2-review-b.jsonl")
    ]

    assert reviewer_a_ids == sorted(
        reviewer_a_ids,
        key=lambda candidate_id: runner.review_schedule_key("reviewer_a", candidate_id),
    )
    assert reviewer_b_ids == sorted(
        reviewer_b_ids,
        key=lambda candidate_id: runner.review_schedule_key("reviewer_b", candidate_id),
    )
    assert reviewer_a_ids != reviewer_b_ids


def test_agent_pack_reviewer_actual_order_tamper_is_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0], rows[1] = rows[1], rows[0]
    _rewrite_jsonl(path, rows)
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["roles"]["reviewer_a"]["session_or_thread_ids"] = [
        _pack_invocation_identity(invocation)
        for row in rows
        for invocation in row["invocations"]
    ]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "agent_run_metadata"


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
    assert result["exact_three_way_agreement_count"] == 255
    assert result["pipeline_rejected_candidate_count"] == 1
    assert result["excluded_candidate_count"] == 128
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
    assert result["task_count"] == 128
    assert result["excluded_candidate_count"] == 128
    assert result["candidate_outcomes"][candidate_id] == "REJECTED_REVIEW"
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
    expected_invocation_count = 17 if role == "generator" else 257
    assert result["agent_roles"][role]["invocation_count"] == expected_invocation_count


def test_agent_pack_two_exact_successes_are_global_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    invocations = retry_row["invocations"]
    failure_session = invocations[0]["session_id"]
    invocations[0] = deepcopy(invocations[1])
    invocations[0]["envelope"]["session_id"] = failure_session
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    ("role", "container_drift"),
    (
        ("generator", "non_list"),
        ("reviewer_a", "non_list"),
        ("generator", "non_dict_item"),
        ("reviewer_a", "non_dict_item"),
    ),
)
def test_agent_pack_invocation_container_type_drift_is_global_invalid(
    tmp_path: Path, role: str, container_drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
    }[role]
    path = pack / filename
    rows = _read_jsonl(path)
    rows[0]["invocations"] = {} if container_drift == "non_list" else [None]
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, role)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize("role", ("generator", "reviewer_a"))
def test_agent_pack_empty_invocation_list_is_global_protocol_invalid(
    tmp_path: Path, role: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
    }[role]
    path = pack / filename
    rows = _read_jsonl(path)
    rows[0]["invocations"] = []
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, role)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_three_successes_with_count_two_is_global_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    row = rows[0]
    success = row["invocations"][-1]
    row["invocations"] = []
    for index in range(3):
        invocation = deepcopy(success)
        invocation["envelope"]["session_id"] = (
            f"reviewer-a-three-count-two-{row['candidate_id']}-{index}"
        )
        invocation["envelope"]["transport_retry_count"] = 2
        row["invocations"].append(invocation)
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_three_exact_successes_with_count_zero_are_global_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    row = rows[0]
    candidate_id = row["candidate_id"]
    success = row["invocations"][-1]
    row["invocations"] = []
    for index in range(3):
        invocation = deepcopy(success)
        invocation["envelope"]["session_id"] = (
            f"reviewer-a-three-count-zero-{candidate_id}-{index}"
        )
        invocation["envelope"]["transport_retry_count"] = 0
        row["invocations"].append(invocation)
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_allowed_retry_requires_success_count_one(tmp_path: Path) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    retry_row["invocations"][-1]["envelope"]["transport_retry_count"] = 0
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_single_success_requires_count_zero(tmp_path: Path) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0]["invocations"][-1]["envelope"]["transport_retry_count"] = 1
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    ("shape", "schema_drift"),
    (
        ("success", "extra"),
        ("success", "missing_envelope"),
        ("success", "non_object_envelope"),
        ("failure", "extra_response"),
        ("failure", "extra_envelope"),
        ("failure", "missing_role"),
    ),
)
def test_agent_pack_invocation_top_level_schema_drift_is_global_invalid(
    tmp_path: Path, shape: str, schema_drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        transport_retry_role="reviewer_a" if shape == "failure" else None,
    )
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    row = (
        next(row for row in rows if len(row["invocations"]) == 2)
        if shape == "failure"
        else rows[0]
    )
    invocation = row["invocations"][0 if shape == "failure" else -1]
    if schema_drift == "extra":
        invocation["unexpected"] = True
    elif schema_drift == "missing_envelope":
        invocation.pop("envelope")
    elif schema_drift == "non_object_envelope":
        invocation["envelope"] = None
    elif schema_drift == "extra_response":
        invocation["response"] = {}
    elif schema_drift == "extra_envelope":
        invocation["envelope"] = deepcopy(row["invocations"][-1]["envelope"])
    else:
        invocation.pop("role")
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    ("shape", "field", "value"),
    (
        ("success", "transport_failure", "missing"),
        ("success", "transport_failure", True),
        ("success", "transport_failure", "no"),
        ("success", "response_bytes_present", "missing"),
        ("success", "response_bytes_present", False),
        ("success", "response_bytes_present", 1),
        ("failure", "transport_failure", "missing"),
        ("failure", "transport_failure", False),
        ("failure", "transport_failure", "yes"),
        ("failure", "response_bytes_present", "missing"),
        ("failure", "response_bytes_present", True),
        ("failure", "response_bytes_present", 0),
    ),
)
def test_agent_pack_transport_flags_require_exact_bool_for_record_shape(
    tmp_path: Path, shape: str, field: str, value: Any
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        transport_retry_role="reviewer_a" if shape == "failure" else None,
    )
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    row = (
        next(row for row in rows if len(row["invocations"]) == 2)
        if shape == "failure"
        else rows[0]
    )
    invocation = row["invocations"][0 if shape == "failure" else -1]
    if value == "missing":
        invocation.pop(field)
    else:
        invocation[field] = value
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    "envelope_drift",
    ("extra_field", "missing_protocol_field", "missing_response"),
)
def test_agent_pack_success_envelope_requires_exact_contract_fields(
    tmp_path: Path, envelope_drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    envelope = rows[0]["invocations"][-1]["envelope"]
    if envelope_drift == "extra_field":
        envelope["unexpected_protocol_field"] = True
    elif envelope_drift == "missing_protocol_field":
        envelope.pop("reasoning_effort")
    else:
        envelope.pop("response")
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("role", "reviewer_b"),
        ("fork_context", True),
        ("history_message_count", 1),
        ("imported_memory_count", 1),
        ("requested_model", "wrong-model"),
        ("reasoning_effort", "wrong-effort"),
        ("timeout_seconds", 901),
        ("request_sha256", "0" * 64),
    ),
)
def test_agent_pack_success_invocation_protocol_drift_is_global_invalid(
    tmp_path: Path, field: str, value: Any
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0]["invocations"][-1]["envelope"][field] = value
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize("retry_count", (False, 0.0, "0", 2))
def test_agent_pack_transport_retry_count_requires_exact_int_protocol_value(
    tmp_path: Path, retry_count: Any
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0]["invocations"][-1]["envelope"]["transport_retry_count"] = retry_count
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_success_invocation_identity_is_global_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0]["invocations"][-1]["envelope"]["thread_id"] = "unexpected-thread"
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("role", "reviewer_b"),
        ("fork_context", True),
        ("request_sha256", "0" * 64),
        ("requested_model", "wrong-model"),
    ),
)
def test_agent_pack_transport_retry_protocol_drift_is_global_invalid(
    tmp_path: Path, field: str, value: Any
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    retry_row["invocations"][0][field] = value
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_illegal_retry_with_protocol_drift_is_global_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    failure = retry_row["invocations"][0]
    failure["response_bytes_present"] = True
    failure["role"] = "reviewer_b"
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize(
    "protocol_drift",
    ("role", "request_hash", "config", "session"),
)
def test_agent_pack_non_boolean_retry_shape_still_audits_protocol_fields(
    tmp_path: Path, protocol_drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    failure = retry_row["invocations"][0]
    failure["transport_failure"] = "yes"
    if protocol_drift == "role":
        failure["role"] = "reviewer_b"
    elif protocol_drift == "request_hash":
        failure["request_sha256"] = "0" * 64
    elif protocol_drift == "config":
        failure["requested_model"] = "wrong-model"
    else:
        failure["thread_id"] = "unexpected-thread"
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


def test_agent_pack_non_boolean_retry_shape_is_global_protocol_invalid(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    retry_row = next(row for row in rows if len(row["invocations"]) == 2)
    retry_row["invocations"][0]["transport_failure"] = "yes"
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "invocation_protocol"


@pytest.mark.parametrize("invalid_response", ("missing_field", "refusal"))
def test_agent_pack_response_payload_error_excludes_only_candidate(
    tmp_path: Path, invalid_response: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    candidate_id = rows[0]["candidate_id"]
    response = rows[0]["invocations"][-1]["envelope"]["response"]
    if invalid_response == "missing_field":
        response.pop("reason")
    else:
        rows[0]["invocations"][-1]["envelope"]["response"] = {
            "refusal": f"{PREFIX} REFUSAL"
        }
    _rewrite_jsonl(path, rows)

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "VALID"
    assert result["task_count"] == 128
    assert result["excluded_candidate_count"] == 128
    assert result["candidate_outcomes"][candidate_id] == "REJECTED_INVOCATION"
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


@pytest.mark.parametrize(
    "config_drift",
    (
        "timeout_float",
        "timeout_bool",
        "model_bool",
        "reasoning_empty",
        "extra_field",
    ),
)
def test_agent_pack_metadata_config_requires_exact_fields_and_types(
    tmp_path: Path, config_drift: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    config = metadata["roles"]["reviewer_a"]["config"]
    if config_drift == "timeout_float":
        config["timeout_seconds"] = 900.0
    elif config_drift == "timeout_bool":
        config["timeout_seconds"] = True
    elif config_drift == "model_bool":
        config["model"] = True
    elif config_drift == "reasoning_empty":
        config["reasoning_effort"] = " "
    else:
        config["unexpected"] = "field"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = _validate_agent_pack(pack, tmp_path / "repo")

    assert result["status"] == "INVALID"
    assert result["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["failure_stage"] == "agent_run_metadata"


@pytest.mark.parametrize(
    "field",
    (
        "request_count",
        "invocation_count",
        "history_message_count",
        "imported_memory_count",
    ),
)
def test_agent_pack_metadata_numeric_fields_reject_bool(
    tmp_path: Path, field: str
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["roles"]["reviewer_b"][field] = True
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


@pytest.mark.parametrize("symlink_scope", ("one", "all"))
def test_agent_pack_required_files_cannot_resolve_inside_repository(
    tmp_path: Path, symlink_scope: str
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    pack = tmp_path / "external-agent-pack"
    _write_agent_pack(pack)
    filenames = (
        runner.REQUIRED_AGENT_PACK_FILES[:1]
        if symlink_scope == "one"
        else runner.REQUIRED_AGENT_PACK_FILES
    )
    for filename in filenames:
        path = pack / filename
        target = repository / filename
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)

    with pytest.raises(ValueError, match="outside the repository"):
        _validate_agent_pack(pack, repository)


def test_agent_pack_required_path_must_be_a_regular_file(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    pack = tmp_path / "external-agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-contamination.jsonl"
    path.unlink()
    path.mkdir()

    with pytest.raises(ValueError):
        _validate_agent_pack(pack, repository)


@pytest.mark.parametrize("retry_role", ("generator", "reviewer_a", "reviewer_b"))
def test_task5_run_hashes_and_retry_records_bind_exact_fixture_invocations(
    tmp_path: Path,
    retry_role: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role=retry_role)
    expected_records = {
        role: _task5_fixture_run_records(pack, role)
        for role in ("generator", "reviewer_a", "reviewer_b")
    }
    expected_retries = _task5_fixture_retry_records(expected_records)

    validation = _validate_agent_pack(pack, tmp_path / "repo")
    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    manifest = json.loads(documents["blind-v2-manifest.json"])
    construction = manifest["agent_construction"]

    for role, records in expected_records.items():
        expected_request_hash = _task5_test_canonical_sha256(
            [record["request_sha256"] for record in records]
        )
        expected_response_hash = _task5_test_canonical_sha256(
            [record["response_sha256"] for record in records]
        )
        expected_run_hash = _task5_test_canonical_sha256(records)
        evidence = validation["agent_run_evidence"][role]
        assert evidence["request_hashes_sha256"] == expected_request_hash
        assert evidence["response_hashes_sha256"] == expected_response_hash
        assert evidence["run_sha256"] == expected_run_hash

    assert validation["retry_records"] == expected_retries
    assert construction["retry_records"] == expected_retries


def test_task5_commit_b_run_records_independently_recompute_committed_evidence(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_b")
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    assert {
        name: hashlib.sha256(payload).hexdigest() for name, payload in first.items()
    } == {name: hashlib.sha256(payload).hexdigest() for name, payload in second.items()}
    manifest = json.loads(first["blind-v2-manifest.json"])
    construction = manifest["agent_construction"]
    committed_records = construction["sanitized_run_records"]

    assert set(committed_records) == {"generator", "reviewer_a", "reviewer_b"}
    record_fields = {
        "invocation_id",
        "candidate_ids",
        "request_sha256",
        "response_sha256",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "session_or_thread_ids",
        "transport_retry_count",
        "outcome",
        "attempts",
    }
    for role, records in committed_records.items():
        assert records
        assert all(set(record) == record_fields for record in records)
        evidence = construction["agent_roles"][role]
        assert evidence["request_hashes_sha256"] == _task5_test_canonical_sha256(
            [record["request_sha256"] for record in records]
        )
        assert evidence["response_hashes_sha256"] == _task5_test_canonical_sha256(
            [
                record["response_sha256"]
                for record in records
                if record["response_sha256"] is not None
            ]
        )
        assert evidence["run_sha256"] == _task5_test_canonical_sha256(records)

    expected_retries = _task5_fixture_retry_records(committed_records)
    assert construction["retry_records"] == expected_retries
    assert construction["transport_retry_count"] == len(expected_retries) == 1
    encoded = json.dumps(committed_records, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        '"prompt_text":',
        '"response":',
        '"rationale":',
        '"reason":',
        '"refusal":',
        f"{PREFIX} GENERATOR RATIONALE",
        f"{PREFIX} REVIEWER_A REASON",
        f"{PREFIX} REVIEWER_B REASON",
    ):
        assert forbidden not in encoded


def _task5_resync_role_aggregates_from_records(
    validation: dict[str, Any], role: str
) -> None:
    records = validation["agent_run_records"][role]
    evidence = validation["agent_run_evidence"][role]
    evidence["requested_models"] = sorted(
        {record["requested_model"] for record in records}
    )
    evidence["returned_models"] = sorted(
        {
            record["returned_model"]
            for record in records
            if record["returned_model"] is not None
        }
    )
    evidence["request_count"] = len(records)
    evidence["invocation_count"] = sum(
        len(record["session_or_thread_ids"]) for record in records
    )
    evidence["session_or_thread_ids"] = [
        identity for record in records for identity in record["session_or_thread_ids"]
    ]
    evidence["request_hashes_sha256"] = _task5_test_canonical_sha256(
        [record["request_sha256"] for record in records]
    )
    evidence["response_hashes_sha256"] = _task5_test_canonical_sha256(
        [
            record["response_sha256"]
            for record in records
            if record["response_sha256"] is not None
        ]
    )
    evidence["run_sha256"] = _task5_test_canonical_sha256(records)


def _task5_identity_authority_from_validation(
    validation: dict[str, Any],
) -> dict[str, Any]:
    ledger_paths = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }
    roles: dict[str, dict[str, Any]] = {}
    for role, ledger_path in ledger_paths.items():
        records = validation["agent_run_records"][role]
        invocation_ids = [record["invocation_id"] for record in records]
        candidate_ids = [
            candidate_id
            for record in records
            for candidate_id in record["candidate_ids"]
        ]
        sessions = [
            identity
            for record in records
            for identity in record["session_or_thread_ids"]
        ]
        roles[role] = {
            "ledger_path": ledger_path,
            "ledger_file_sha256": validation["source_file_sha256"][ledger_path],
            "invocation_ids": invocation_ids,
            "invocation_ids_sha256": _task5_test_canonical_sha256(invocation_ids),
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": _task5_test_canonical_sha256(candidate_ids),
            "request_count": len(records),
            "invocation_count": len(sessions),
            "session_or_thread_ids": sessions,
            "session_or_thread_ids_sha256": _task5_test_canonical_sha256(sessions),
        }
    return {
        "roles": roles,
        "authority_sha256": _task5_test_canonical_sha256(roles),
    }


def _task5_resync_validation_from_source_pack(
    validation: dict[str, Any], pack: Path, *roles: str
) -> None:
    metadata = json.loads((pack / "agent-run-metadata.json").read_text("utf-8"))
    validation["source_file_bytes"] = {
        filename: (pack / filename).read_bytes().hex()
        for filename in runner.REQUIRED_AGENT_PACK_FILES
    }
    validation["source_file_sha256"] = {
        filename: hashlib.sha256((pack / filename).read_bytes()).hexdigest()
        for filename in runner.REQUIRED_AGENT_PACK_FILES
    }
    validation["agent_roles"] = deepcopy(metadata["roles"])
    validation["review_schedule_sha256"] = deepcopy(metadata["review_schedule_sha256"])
    for role in roles:
        validation["agent_run_records"][role] = _task5_fixture_run_records(pack, role)
        _task5_resync_role_aggregates_from_records(validation, role)
    validation["retry_records"] = _task5_fixture_retry_records(
        validation["agent_run_records"]
    )
    validation["transport_retry_count"] = len(validation["retry_records"])
    validation["agent_run_identity_authority"] = (
        _task5_identity_authority_from_validation(validation)
    )


@pytest.mark.parametrize(
    "mutation", ("response_rationale", "response_family", "response_index")
)
def test_task5_freeze_revalidates_generation_response_candidate_and_opaque_id(
    tmp_path: Path,
    mutation: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    generation_path = pack / "blind-v2-generation.jsonl"
    generation_rows = _read_jsonl(generation_path)
    generated = generation_rows[0]["invocations"][0]["envelope"]["response"][
        "candidates"
    ][0]
    if mutation == "response_rationale":
        generated["rationale"] = f"{PREFIX} FORGED RESPONSE RATIONALE"
    elif mutation == "response_family":
        generated["semantic_family_id"] = f"{PREFIX}_FORGED_RESPONSE_FAMILY"
    else:
        generated["candidate_index"] = 1
    _rewrite_jsonl(generation_path, generation_rows)
    _task5_resync_validation_from_source_pack(validation, pack, "generator")

    with pytest.raises(ValueError):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_rejects_resynchronized_two_substantive_generator_responses(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    generation_path = pack / "blind-v2-generation.jsonl"
    rows = _read_jsonl(generation_path)
    second = deepcopy(rows[0]["invocations"][0])
    second["envelope"]["session_id"] = f"{PREFIX}-ILLEGAL-SECOND-SUBSTANTIVE"
    rows[0]["invocations"].append(second)
    _rewrite_jsonl(generation_path, rows)
    _sync_agent_pack_role_metadata(pack, "generator")
    _refresh_agent_pack_metadata(pack)
    _task5_resync_validation_from_source_pack(validation, pack, "generator")

    with pytest.raises(ValueError):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


@pytest.mark.parametrize("role", ("generator", "reviewer_a", "reviewer_b"))
def test_task5_freeze_requires_canonical_source_request_skill_authority(
    tmp_path: Path,
    role: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    path = pack / filename
    rows = _read_jsonl(path)
    request = rows[0]["request"]
    request["input"]["canonical_skills"][0]["description"] = (
        f"{PREFIX} FORGED CANONICAL DESCRIPTION"
    )
    request["request_sha256"] = _task5_test_canonical_sha256(
        {key: value for key, value in request.items() if key != "request_sha256"}
    )
    for invocation in rows[0]["invocations"]:
        invocation.get("envelope", invocation)["request_sha256"] = request[
            "request_sha256"
        ]
    _rewrite_jsonl(path, rows)
    _task5_resync_validation_from_source_pack(validation, pack, role)

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_revalidates_reviewer_schedule_from_sealed_source(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rows[0], rows[1] = rows[1], rows[0]
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text("utf-8"))
    metadata["review_schedule_sha256"]["reviewer_a"] = _task5_test_canonical_sha256(
        [row["candidate_id"] for row in rows]
    )
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    _task5_resync_validation_from_source_pack(validation, pack, "reviewer_a")

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_revalidates_reviewer_rubric_from_sealed_source(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    request = rows[0]["request"]
    request["input"]["rubric"]["natural"] = f"{PREFIX} FORGED RUBRIC"
    request["request_sha256"] = _task5_test_canonical_sha256(
        {key: value for key, value in request.items() if key != "request_sha256"}
    )
    rows[0]["invocations"][0]["envelope"]["request_sha256"] = request["request_sha256"]
    _rewrite_jsonl(path, rows)
    _task5_resync_validation_from_source_pack(validation, pack, "reviewer_a")

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_revalidates_reviewer_coverage_from_sealed_source(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    candidate_id = next(
        candidate_id
        for candidate_id, outcome in validation["candidate_outcomes"].items()
        if outcome == "NOT_SELECTED"
    )
    path = pack / "blind-v2-review-a.jsonl"
    rows = [row for row in _read_jsonl(path) if row["candidate_id"] != candidate_id]
    _rewrite_jsonl(path, rows)
    _sync_agent_pack_role_metadata(pack, "reviewer_a")
    metadata_path = pack / "agent-run-metadata.json"
    metadata = json.loads(metadata_path.read_text("utf-8"))
    metadata["roles"]["reviewer_a"]["request_count"] = len(rows)
    metadata["review_schedule_sha256"]["reviewer_a"] = _task5_test_canonical_sha256(
        [row["candidate_id"] for row in rows]
    )
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    _task5_resync_validation_from_source_pack(validation, pack, "reviewer_a")

    generation_rows = _fixture_generation_candidates(pack)
    candidate_fields = {
        "candidate_id",
        "generation_round",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    accepted = sorted(
        [
            {key: value for key, value in item.items() if key in candidate_fields}
            for item in generation_rows
            if item["candidate_id"] != candidate_id
        ],
        key=lambda item: item["candidate_id"],
    )
    validation["selection_audit"]["accepted_pool_sha256"] = (
        _task5_test_canonical_sha256(accepted)
    )
    validation["selection_audit_sha256"] = _task5_test_canonical_sha256(
        validation["selection_audit"]
    )
    validation["candidate_outcomes"][candidate_id] = "REJECTED_INVOCATION"
    validation["exact_three_way_agreement_count"] = 255
    validation["selection_not_selected_count"] = 127
    validation["pipeline_rejected_candidate_count"] = 1

    with pytest.raises(
        ValueError,
        match="Agent (?:run identity|source ledger freeze) authority mismatch",
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_rebinds_complete_contamination_audit_authority(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda audit: audit.__setitem__("required_semantic_model_id", "forged/model"),
        lambda audit: audit.__setitem__("required_semantic_model_revision", "f" * 40),
        lambda audit: audit.update(
            {
                "materialized_model_files": [
                    {
                        "path": "forged/model.safetensors",
                        "sha256": "f" * 64,
                    }
                ],
                "materialized_model_files_sha256": _task5_test_canonical_sha256(
                    [
                        {
                            "path": "forged/model.safetensors",
                            "sha256": "f" * 64,
                        }
                    ]
                ),
            }
        ),
        lambda audit: audit.__setitem__("scanner_config_sha256", "f" * 64),
        lambda audit: audit.__setitem__("evidence_sha256", "f" * 64),
    )

    for mutate in mutations:
        forged = deepcopy(validation)
        mutate(forged["contamination_audit"])
        with pytest.raises(
            ValueError, match="Agent source ledger freeze authority mismatch"
        ):
            runner.build_dataset_freeze_documents(forged, commit_a="a" * 40)


def test_task5_freeze_rejects_resynchronized_contamination_decision_drift(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    candidate_id = next(
        candidate_id
        for candidate_id, outcome in validation["candidate_outcomes"].items()
        if outcome == "NOT_SELECTED"
    )
    path = pack / "blind-v2-contamination.jsonl"
    rows = _read_jsonl(path)
    row = next(item for item in rows if item["candidate_id"] == candidate_id)
    row["scanner_decision"] = "REJECT"
    row["rejection_codes"] = ["forged:decision"]
    row["evidence_sha256"] = "f" * 64
    _rewrite_jsonl(path, rows)
    _task5_resync_validation_from_source_pack(validation, pack)

    generation_rows = _fixture_generation_candidates(pack)
    candidate_fields = {
        "candidate_id",
        "generation_round",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    accepted = sorted(
        [
            {key: value for key, value in item.items() if key in candidate_fields}
            for item in generation_rows
            if item["candidate_id"] != candidate_id
        ],
        key=lambda item: item["candidate_id"],
    )
    validation["selection_audit"]["accepted_pool_sha256"] = (
        _task5_test_canonical_sha256(accepted)
    )
    validation["selection_audit_sha256"] = _task5_test_canonical_sha256(
        validation["selection_audit"]
    )
    validation["candidate_outcomes"][candidate_id] = "REJECTED_CONTAMINATION"
    validation["exact_three_way_agreement_count"] = 255
    validation["selection_not_selected_count"] = 127
    validation["pipeline_rejected_candidate_count"] = 1
    audit = validation["contamination_audit"]
    audit["clean_candidate_count"] = 255
    audit["rejected_candidate_count"] = 1
    audit["ledger_sha256"] = validation["source_file_sha256"][
        "blind-v2-contamination.jsonl"
    ]
    audit["evidence_sha256"] = _task5_test_canonical_sha256(rows)

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_agent_run_identity_authority_binds_ledger_metadata(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="generator")
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    authority = validation["agent_run_identity_authority"]
    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    construction = json.loads(documents["blind-v2-manifest.json"])["agent_construction"]

    assert construction["agent_run_identity_authority"] == authority
    assert authority["authority_sha256"] == _task5_test_canonical_sha256(
        authority["roles"]
    )
    ledger_paths = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }
    for role, role_authority in authority["roles"].items():
        records = validation["agent_run_records"][role]
        metadata = validation["agent_roles"][role]
        invocation_ids = [record["invocation_id"] for record in records]
        candidate_ids = [
            candidate_id
            for record in records
            for candidate_id in record["candidate_ids"]
        ]
        assert role_authority == {
            "ledger_path": ledger_paths[role],
            "ledger_file_sha256": validation["source_file_sha256"][ledger_paths[role]],
            "invocation_ids": invocation_ids,
            "invocation_ids_sha256": _task5_test_canonical_sha256(invocation_ids),
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": _task5_test_canonical_sha256(candidate_ids),
            "request_count": metadata["request_count"],
            "invocation_count": metadata["invocation_count"],
            "session_or_thread_ids": metadata["session_or_thread_ids"],
            "session_or_thread_ids_sha256": _task5_test_canonical_sha256(
                metadata["session_or_thread_ids"]
            ),
        }


def test_task5_freeze_rejects_forged_record_with_resynchronized_aggregates(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    existing_ids = {
        candidate_id
        for record in validation["agent_run_records"]["generator"]
        for candidate_id in record["candidate_ids"]
    }
    forged_candidate_id = "f" * 24
    assert forged_candidate_id not in existing_ids
    validation["agent_run_records"]["generator"].append(
        {
            "invocation_id": "e" * 24,
            "candidate_ids": [forged_candidate_id],
            "request_sha256": "e" * 64,
            "response_sha256": None,
            "requested_model": runner.AGENT_CONFIGS["generator"]["model"],
            "returned_model": None,
            "reasoning_effort": runner.AGENT_CONFIGS["generator"]["reasoning_effort"],
            "session_or_thread_ids": ["forged-generator-session"],
            "transport_retry_count": 0,
            "outcome": "TRANSPORT_FAILURE_NO_RESPONSE",
            "attempts": [
                {
                    "attempt_ordinal": 1,
                    "session_or_thread_id": "forged-generator-session",
                    "request_sha256": "e" * 64,
                    "requested_model": runner.AGENT_CONFIGS["generator"]["model"],
                    "returned_model": None,
                    "reasoning_effort": runner.AGENT_CONFIGS["generator"][
                        "reasoning_effort"
                    ],
                    "transport_failure": True,
                    "response_bytes_present": False,
                    "response_sha256": None,
                    "outcome": "TRANSPORT_FAILURE_NO_RESPONSE",
                }
            ],
        }
    )
    _task5_resync_role_aggregates_from_records(validation, "generator")
    validation["retry_records"] = _task5_fixture_retry_records(
        validation["agent_run_records"]
    )
    validation["transport_retry_count"] = len(validation["retry_records"])

    with pytest.raises(ValueError, match="Agent run identity authority mismatch"):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


@pytest.mark.parametrize(
    "mutation",
    (
        "duplicate_id",
        "negative_count",
        "family_drift",
        "prompt_hash",
        "selection_id",
        "selection_hash",
    ),
)
def test_task5_freeze_revalidates_selected_tasks_and_selection_audit(
    tmp_path: Path,
    mutation: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    tasks = validation["tasks"]
    selection = validation["selection_audit"]
    if mutation == "duplicate_id":
        tasks[1]["candidate_id"] = tasks[0]["candidate_id"]
    elif mutation == "negative_count":
        negative = next(
            task for task in tasks if task["proposed_negative_skill_id"] is not None
        )
        negative["proposed_negative_skill_id"] = None
    elif mutation == "family_drift":
        tasks[1]["semantic_family_id"] = tasks[0]["semantic_family_id"]
    elif mutation == "prompt_hash":
        tasks[0]["prompt_text_sha256"] = "0" * 64
    elif mutation == "selection_id":
        selection["selected_candidate_ids"][0] = "f" * 24
    else:
        selection["selected_candidate_ids_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="Agent dataset selection validation mismatch"):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_rejects_resynchronized_round_lineage_not_derived_from_source(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    selection = validation["selection_audit"]
    first_gold = sorted(selection["round_2_distribution"])[0]
    selection["round_2_distribution"][first_gold]["negative"] = 1
    selection["round_2_request_quota_distribution"][first_gold]["negative"] = 1
    selection["round_2_candidate_count"] = 1
    selection["round_1_post_pipeline_deficits"] = {
        first_gold: {"negative": 1, "positive_only": 0}
    }
    validation["selection_audit_sha256"] = _task5_test_canonical_sha256(selection)

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_preserves_source_derived_round_two_selection_lineage(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(
        pack,
        round_one_rejections={("test-skill-00", "positive_only"): 3},
        round_one_contamination_rejections={("test-skill-00", "negative"): 7},
        include_round_two=True,
    )
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)

    assert first == second
    manifest = json.loads(first["blind-v2-manifest.json"])
    selection = manifest["agent_construction"]["deterministic_selection"]
    expected_round_two = {
        skill["id"]: {"negative": 0, "positive_only": 0} for skill in _skills()
    }
    expected_round_two["test-skill-00"] = {
        "negative": 2,
        "positive_only": 2,
    }
    assert selection["round_1_candidate_count"] == 256
    assert selection["round_2_candidate_count"] == 4
    assert selection["round_1_post_pipeline_deficits"] == {
        "test-skill-00": {"negative": 1, "positive_only": 1}
    }
    assert selection["round_2_distribution"] == expected_round_two
    assert selection["round_2_request_quota_distribution"] == expected_round_two
    assert selection == validation["selection_audit"]
    combined = b"".join(first.values())
    for forbidden in (
        b'"source_file_bytes"',
        b'"source_bytes"',
        b'"source_bytes_hex"',
        b'"raw_source"',
        b'"response":',
        b'"raw_response"',
        b'"response_body"',
        b'"rationale":',
        b'"reason":',
        b'"refusal":',
        b'"analysis":',
        b'"reasoning":',
        b'"chain_of_thought":',
        b'"raw_reasoning":',
        b'"hidden_reasoning":',
        b'"human_review":',
    ):
        assert forbidden not in combined


def test_task5_validation_carries_hash_bound_source_bytes_without_committing_them(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)

    validation = _validate_agent_pack(pack, tmp_path / "repo")

    assert set(validation["source_file_bytes"]) == set(runner.REQUIRED_AGENT_PACK_FILES)
    for filename, payload_hex in validation["source_file_bytes"].items():
        assert payload_hex == (pack / filename).read_bytes().hex()
        assert (
            validation["source_file_sha256"][filename]
            == hashlib.sha256(bytes.fromhex(payload_hex)).hexdigest()
        )

    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    combined = b"".join(documents.values())
    assert b'"source_file_bytes"' not in combined
    assert f"{PREFIX} GENERATOR RATIONALE".encode() not in combined
    assert f"{PREFIX} REVIEWER_A REASON".encode() not in combined
    assert f"{PREFIX} REVIEWER_B REASON".encode() not in combined


@pytest.mark.parametrize(
    "mutation",
    ("prompt_and_hash", "task_run_detached", "resynchronized_selection_hashes"),
)
def test_task5_freeze_rejects_selected_task_drift_from_sealed_source_ledgers(
    tmp_path: Path,
    mutation: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    tasks = validation["tasks"]

    if mutation == "task_run_detached":
        left, right = tasks[0], tasks[1]
        assert left["proposed_gold_skill_id"] == right["proposed_gold_skill_id"]
        assert (left["proposed_negative_skill_id"] is None) == (
            right["proposed_negative_skill_id"] is None
        )
        for field in (
            "prompt_text",
            "prompt_text_sha256",
            "semantic_family_id",
        ):
            left[field], right[field] = right[field], left[field]
    else:
        prompt = f"{PREFIX} SYNCHRONIZED FORGED PROMPT"
        tasks[0]["prompt_text"] = prompt
        tasks[0]["prompt_text_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        if mutation == "resynchronized_selection_hashes":
            validation["selection_audit"]["accepted_pool_sha256"] = (
                _task5_test_canonical_sha256(tasks)
            )
            validation["selection_audit_sha256"] = _task5_test_canonical_sha256(
                validation["selection_audit"]
            )

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_rejects_resynchronized_alternate_eligible_selection(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    tasks = validation["tasks"]
    target = tasks[0]
    generation_by_id = {
        row["candidate_id"]: row for row in _fixture_generation_candidates(pack)
    }
    replacement_id = next(
        candidate_id
        for candidate_id, outcome in validation["candidate_outcomes"].items()
        if outcome == "NOT_SELECTED"
        and generation_by_id[candidate_id]["proposed_gold_skill_id"]
        == target["proposed_gold_skill_id"]
        and (generation_by_id[candidate_id]["proposed_negative_skill_id"] is not None)
        == (target["proposed_negative_skill_id"] is not None)
    )
    replacement = generation_by_id[replacement_id]
    original_id = target["candidate_id"]
    tasks[0] = {
        field: replacement[field]
        for field in (
            "candidate_id",
            "generation_round",
            "prompt_text",
            "prompt_text_sha256",
            "semantic_family_id",
            "proposed_gold_skill_id",
            "proposed_negative_skill_id",
            "language",
            "rationale",
        )
    }
    tasks.sort(
        key=lambda task: (
            task["proposed_gold_skill_id"],
            task["proposed_negative_skill_id"] is None,
            hashlib.sha256(f"7170:{task['candidate_id']}".encode("utf-8")).hexdigest(),
        )
    )
    selected_ids = [task["candidate_id"] for task in tasks]
    validation["candidate_outcomes"][original_id] = "NOT_SELECTED"
    validation["candidate_outcomes"][replacement_id] = "SELECTED"
    selection = validation["selection_audit"]
    selection["selected_candidate_ids"] = selected_ids
    selection["selected_candidate_ids_sha256"] = _task5_test_canonical_sha256(
        selected_ids
    )
    selection["selected_by_stratum"] = {
        gold: {
            "negative": [
                task["candidate_id"]
                for task in tasks
                if task["proposed_gold_skill_id"] == gold
                and task["proposed_negative_skill_id"] is not None
            ],
            "positive_only": [
                task["candidate_id"]
                for task in tasks
                if task["proposed_gold_skill_id"] == gold
                and task["proposed_negative_skill_id"] is None
            ],
        }
        for gold in sorted({task["proposed_gold_skill_id"] for task in tasks})
    }
    validation["selection_audit_sha256"] = _task5_test_canonical_sha256(selection)

    with pytest.raises(
        ValueError, match="Agent source ledger freeze authority mismatch"
    ):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


def test_task5_freeze_requires_strict_commit_a_and_normalizes_bad_container(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    for commit_a in ("A" * 40, "g" * 40, "a" * 39):
        with pytest.raises(
            ValueError, match="Commit A must be exactly 40 lowercase hex characters"
        ):
            runner.build_dataset_freeze_documents(validation, commit_a=commit_a)
    malformed_values: tuple[Any, ...] = (None, [])
    for malformed in malformed_values:
        with pytest.raises(
            ValueError, match="Agent dataset freeze validation container mismatch"
        ):
            runner.build_dataset_freeze_documents(
                cast(Any, malformed), commit_a="a" * 40
            )


@pytest.mark.parametrize(
    "mutation", ("constant_run_hash", "wrong_request_hash", "wrong_retry_session")
)
def test_task5_dataset_freeze_rejects_misbound_run_or_retry_evidence(
    tmp_path: Path,
    mutation: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    if mutation == "constant_run_hash":
        validation["agent_run_evidence"]["generator"]["run_sha256"] = "0" * 64
    elif mutation == "wrong_request_hash":
        validation["agent_run_records"]["reviewer_b"][0]["request_sha256"] = "0" * 64
    else:
        validation["retry_records"][0]["retry_session_or_thread_id"] = (
            "wrong-retry-session"
        )

    with pytest.raises(ValueError, match="Agent run or retry evidence mismatch"):
        runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)


@pytest.mark.parametrize(
    "invalid_response", ("missing_reason", "refusal", "wrong_model")
)
def test_task5_substantive_invalid_candidate_lineage_still_freezes(
    tmp_path: Path,
    invalid_response: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    path = pack / "blind-v2-review-a.jsonl"
    rows = _read_jsonl(path)
    rejected = rows[0]
    candidate_id = rejected["candidate_id"]
    if invalid_response == "missing_reason":
        rejected["invocations"][0]["envelope"]["response"].pop("reason")
    elif invalid_response == "refusal":
        rejected["invocations"][0]["envelope"]["response"] = {
            "refusal": f"{PREFIX} REFUSAL"
        }
    else:
        rejected["invocations"][0]["envelope"]["returned_model"] = "gpt-5.6-unexpected"
    _rewrite_jsonl(path, rows)

    validation = _validate_agent_pack(pack, tmp_path / "repo")
    assert validation["status"] == "VALID"
    assert validation["task_count"] == 128
    assert validation["negative_labeled_task_count"] == 96
    assert candidate_id not in {task["candidate_id"] for task in validation["tasks"]}
    rejected_record = next(
        record
        for record in validation["agent_run_records"]["reviewer_a"]
        if record["candidate_ids"] == [candidate_id]
    )
    envelope = rejected["invocations"][0]["envelope"]
    response_sha256 = _task5_test_canonical_sha256(envelope["response"])
    session_id = _pack_invocation_identity(rejected["invocations"][0])
    assert rejected_record == {
        "invocation_id": rejected_record["request_sha256"][:24],
        "candidate_ids": [candidate_id],
        "request_sha256": _task5_test_canonical_sha256(
            {
                key: value
                for key, value in rejected["request"].items()
                if key != "request_sha256"
            }
        ),
        "response_sha256": response_sha256,
        "requested_model": runner.AGENT_CONFIGS["reviewer_a"]["model"],
        "returned_model": envelope["returned_model"],
        "reasoning_effort": runner.AGENT_CONFIGS["reviewer_a"]["reasoning_effort"],
        "session_or_thread_ids": [session_id],
        "transport_retry_count": 0,
        "outcome": "SUBSTANTIVE_INVALID_RESPONSE",
        "attempts": [
            {
                "attempt_ordinal": 1,
                "session_or_thread_id": session_id,
                "request_sha256": rejected_record["request_sha256"],
                "requested_model": runner.AGENT_CONFIGS["reviewer_a"]["model"],
                "returned_model": envelope["returned_model"],
                "reasoning_effort": runner.AGENT_CONFIGS["reviewer_a"][
                    "reasoning_effort"
                ],
                "transport_failure": False,
                "response_bytes_present": True,
                "response_sha256": response_sha256,
                "outcome": "SUBSTANTIVE_INVALID_RESPONSE",
            }
        ],
    }
    assert validation["transport_retry_count"] == 0
    assert validation["retry_records"] == []
    assert validation["agent_run_evidence"]["reviewer_a"][
        "run_sha256"
    ] == _task5_test_canonical_sha256(validation["agent_run_records"]["reviewer_a"])
    assert validation["agent_run_evidence"]["reviewer_a"][
        "response_hashes_sha256"
    ] == _task5_test_canonical_sha256(
        [
            record["response_sha256"]
            for record in validation["agent_run_records"]["reviewer_a"]
            if record["response_sha256"] is not None
        ]
    )

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    assert first == second
    task_ids = {
        json.loads(line)["task_id"]
        for line in first["blind-v2-tasks.jsonl"].splitlines()
    }
    assert candidate_id not in task_ids
    assert len(task_ids) == 128
    manifest = json.loads(first["blind-v2-manifest.json"])
    review_summary = json.loads(first["blind-v2-review-summary.json"])
    construction = manifest["agent_construction"]
    assert manifest["exact_three_way_agreement_count"] == 255
    assert manifest["selection_not_selected_count"] == 127
    assert manifest["pipeline_rejected_candidate_count"] == 1
    assert manifest["excluded_candidate_count"] == 128
    assert manifest["candidate_outcomes"][candidate_id] == "REJECTED_INVOCATION"
    for document in (review_summary, construction):
        assert document["exact_three_way_agreement_count"] == 255
        assert document["selection_not_selected_count"] == 127
        assert document["pipeline_rejected_candidate_count"] == 1
        assert document["excluded_candidate_count"] == 128
        assert document["candidate_outcomes"] == manifest["candidate_outcomes"]
    combined = b"".join(first.values())
    assert b'"rationale"' not in combined
    assert b'"reason"' not in combined
    assert f"{PREFIX} REFUSAL".encode() not in combined
    if invalid_response == "wrong_model":
        assert b"gpt-5.6-unexpected" in combined


@pytest.mark.parametrize("role", ("generator", "reviewer_a", "reviewer_b"))
def test_task5_transport_retry_then_refusal_preserves_retry_lineage_and_freezes(
    tmp_path: Path,
    role: str,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role=role)
    filename = {
        "generator": "blind-v2-generation.jsonl",
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    path = pack / filename
    rows = _read_jsonl(path)
    rejected = next(row for row in rows if len(row["invocations"]) == 2)
    candidate_ids = (
        [
            candidate["candidate_id"]
            for candidate in _fixture_generation_candidates(pack)
            if candidate["proposed_gold_skill_id"] == rejected["gold_skill_id"]
        ]
        if role == "generator"
        else [rejected["candidate_id"]]
    )
    rejected["invocations"][-1]["envelope"]["response"] = {
        "refusal": f"{PREFIX} FINAL REFUSAL"
    }
    assert len(rejected["invocations"]) == 2
    _rewrite_jsonl(path, rows)

    validation = _validate_agent_pack(pack, tmp_path / "repo")
    if role == "generator":
        assert validation["status"] == "INVALID"
        assert validation["failure_stage"] == "generation_rounds"
        assert validation["tasks"] == []
        return
    candidate_id = candidate_ids[0]
    assert validation["status"] == "VALID"
    assert validation["task_count"] == 128
    assert validation["negative_labeled_task_count"] == 96
    assert candidate_id not in {task["candidate_id"] for task in validation["tasks"]}
    record = next(
        item
        for item in validation["agent_run_records"][role]
        if item["candidate_ids"] == candidate_ids
    )
    identities = [
        _pack_invocation_identity(invocation) for invocation in rejected["invocations"]
    ]
    final_envelope = rejected["invocations"][-1]["envelope"]
    final_response_sha256 = _task5_test_canonical_sha256(final_envelope["response"])
    assert record == {
        "invocation_id": record["request_sha256"][:24],
        "candidate_ids": candidate_ids,
        "request_sha256": _task5_test_canonical_sha256(
            {
                key: value
                for key, value in rejected["request"].items()
                if key != "request_sha256"
            }
        ),
        "response_sha256": final_response_sha256,
        "requested_model": runner.AGENT_CONFIGS[role]["model"],
        "returned_model": final_envelope["returned_model"],
        "reasoning_effort": runner.AGENT_CONFIGS[role]["reasoning_effort"],
        "session_or_thread_ids": identities,
        "transport_retry_count": 1,
        "outcome": "SUBSTANTIVE_INVALID_RESPONSE",
        "attempts": [
            {
                "attempt_ordinal": 1,
                "session_or_thread_id": identities[0],
                "request_sha256": record["request_sha256"],
                "requested_model": runner.AGENT_CONFIGS[role]["model"],
                "returned_model": None,
                "reasoning_effort": runner.AGENT_CONFIGS[role]["reasoning_effort"],
                "transport_failure": True,
                "response_bytes_present": False,
                "response_sha256": None,
                "outcome": "TRANSPORT_FAILURE_NO_RESPONSE",
            },
            {
                "attempt_ordinal": 2,
                "session_or_thread_id": identities[1],
                "request_sha256": record["request_sha256"],
                "requested_model": runner.AGENT_CONFIGS[role]["model"],
                "returned_model": final_envelope["returned_model"],
                "reasoning_effort": runner.AGENT_CONFIGS[role]["reasoning_effort"],
                "transport_failure": False,
                "response_bytes_present": True,
                "response_sha256": final_response_sha256,
                "outcome": "SUBSTANTIVE_INVALID_RESPONSE",
            },
        ],
    }
    assert validation["transport_retry_count"] == 1
    assert validation["retry_records"] == [
        {
            "role": role,
            "invocation_id": record["invocation_id"],
            "candidate_ids": candidate_ids,
            "request_sha256": record["request_sha256"],
            "response_sha256": final_response_sha256,
            "failed_session_or_thread_id": identities[0],
            "retry_session_or_thread_id": identities[1],
            "failed_attempt_ordinal": 1,
            "retry_attempt_ordinal": 2,
            "retry_count": 1,
        }
    ]

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    assert {
        name: hashlib.sha256(payload).hexdigest() for name, payload in first.items()
    } == {name: hashlib.sha256(payload).hexdigest() for name, payload in second.items()}
    construction = json.loads(first["blind-v2-manifest.json"])["agent_construction"]
    assert construction["retry_records"] == validation["retry_records"]
    assert (
        construction["sanitized_run_records"][role]
        == validation["agent_run_records"][role]
    )
    combined = b"".join(first.values())
    assert f"{PREFIX} FINAL REFUSAL".encode() not in combined


def test_task5_commit_b_freezes_agent_tasks_lineage_and_retry_evidence(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack, transport_retry_role="reviewer_a")
    validation = _validate_agent_pack(pack, tmp_path / "repo")

    first = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    second = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)

    assert first == second
    assert set(first) == {
        "blind-v2-tasks.jsonl",
        "blind-v2-review-summary.json",
        "blind-v2-manifest.json",
    }
    task_rows = [
        json.loads(line) for line in first["blind-v2-tasks.jsonl"].splitlines()
    ]
    assert task_rows == [
        {
            "task_id": task["candidate_id"],
            "prompt_text": task["prompt_text"],
            "prompt_text_sha256": task["prompt_text_sha256"],
            "semantic_family_id": task["semantic_family_id"],
            "gold_skill_id": task["proposed_gold_skill_id"],
            "negative_skill_id": task["proposed_negative_skill_id"],
            "source_type": "AGENT_GENERATED",
        }
        for task in validation["tasks"]
    ]
    assert len(task_rows) == 128
    assert sum(row["negative_skill_id"] is not None for row in task_rows) == 96
    assert len({row["semantic_family_id"] for row in task_rows}) == 128

    review_summary = json.loads(first["blind-v2-review-summary.json"])
    combined = b"".join(first.values())
    assert f"{PREFIX} ".encode() in combined
    assert f"{PREFIX} GENERATOR RATIONALE".encode() not in combined
    assert f"{PREFIX} REVIEWER_A REASON".encode() not in combined
    assert f"{PREFIX} REVIEWER_B REASON".encode() not in combined
    assert b'"rationale"' not in combined
    assert b'"reason"' not in combined

    manifest = json.loads(first["blind-v2-manifest.json"])
    assert manifest["task_count"] == 128
    assert manifest["negative_labeled_task_count"] == 96
    assert manifest["family_count"] == 128
    assert manifest["human_author_count"] == 0
    assert manifest["human_reviewer_count"] == 0
    assert manifest["exact_three_way_agreement_count"] == 256
    assert manifest["selection_not_selected_count"] == 128
    assert manifest["pipeline_rejected_candidate_count"] == 0
    assert manifest["excluded_candidate_count"] == 128
    assert manifest["model_scores_observed"] is False
    assert manifest["evaluation_started"] is False
    assert manifest["retraining_after_data_access"] is False
    assert manifest["gate_changed_after_data_access"] is False

    construction = manifest["agent_construction"]
    assert construction["human_author_count"] == 0
    assert construction["human_reviewer_count"] == 0
    for document in (review_summary, construction):
        assert document["exact_three_way_agreement_count"] == 256
        assert document["selection_not_selected_count"] == 128
        assert document["pipeline_rejected_candidate_count"] == 0
        assert document["excluded_candidate_count"] == 128
        assert document["candidate_outcomes"] == manifest["candidate_outcomes"]
    assert construction["generation_ledger"] == {
        "path": "blind-v2-generation.jsonl",
        "sha256": validation["source_file_sha256"]["blind-v2-generation.jsonl"],
    }
    assert construction["reviewer_ledgers"] == {
        "reviewer_a": {
            "path": "blind-v2-review-a.jsonl",
            "sha256": validation["source_file_sha256"]["blind-v2-review-a.jsonl"],
            "schedule_sha256": validation["review_schedule_sha256"]["reviewer_a"],
        },
        "reviewer_b": {
            "path": "blind-v2-review-b.jsonl",
            "sha256": validation["source_file_sha256"]["blind-v2-review-b.jsonl"],
            "schedule_sha256": validation["review_schedule_sha256"]["reviewer_b"],
        },
    }
    assert construction["agent_run_metadata"] == {
        "path": "agent-run-metadata.json",
        "sha256": validation["source_file_sha256"]["agent-run-metadata.json"],
    }
    assert construction["transport_retry_count"] == 1
    assert len(construction["retry_records"]) == 1
    assert construction["retry_records"][0]["role"] == "reviewer_a"
    assert construction["retry_records"][0]["retry_count"] == 1

    prompt_hashes = {
        "generator": hashlib.sha256(
            runner.GENERATOR_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "reviewer_a": hashlib.sha256(
            runner.REVIEWER_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "reviewer_b": hashlib.sha256(
            runner.REVIEWER_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
    }
    schema_hashes = {
        "generator": runner.canonical_sha256(runner.GENERATOR_RESPONSE_SCHEMA),
        "reviewer_a": runner.canonical_sha256(runner.REVIEWER_RESPONSE_SCHEMA),
        "reviewer_b": runner.canonical_sha256(runner.REVIEWER_RESPONSE_SCHEMA),
    }
    for role, config in runner.AGENT_CONFIGS.items():
        role_evidence = construction["agent_roles"][role]
        assert role_evidence["config"] == config
        assert role_evidence["requested_models"] == [config["model"]]
        assert role_evidence["returned_models"] == [config["model"]]
        assert role_evidence["reasoning_effort"] == config["reasoning_effort"]
        assert role_evidence["system_prompt_sha256"] == prompt_hashes[role]
        assert role_evidence["response_schema_sha256"] == schema_hashes[role]
        assert (
            role_evidence["session_or_thread_ids"]
            == validation["agent_roles"][role]["session_or_thread_ids"]
        )
        assert len(role_evidence["request_hashes_sha256"]) == 64
        assert len(role_evidence["response_hashes_sha256"]) == 64
        assert len(role_evidence["run_sha256"]) == 64

    contamination = construction["contamination"]
    assert (
        contamination["ledger_file_sha256"]
        == validation["source_file_sha256"]["blind-v2-contamination.jsonl"]
    )
    assert contamination["required_semantic_model_id"] == runner.SEMANTIC_MODEL_ID
    assert (
        contamination["required_semantic_model_revision"]
        == runner.SEMANTIC_MODEL_REVISION
    )
    assert len(contamination["scanner_config_sha256"]) == 64
    assert contamination["semantic_scorer_runtime_verified"] is False
    assert contamination["semantic_scorer_receipt_sha256"] is None

    selection = construction["deterministic_selection"]
    assert selection == validation["selection_audit"]
    assert selection["selection_authority"]["selection_seed"] == 7170
    assert len(selection["selected_candidate_ids"]) == 128
    assert len(selection["selected_candidate_ids_sha256"]) == 64
    assert review_summary["agent_roles"] == construction["agent_roles"]
    assert review_summary["retry_records"] == construction["retry_records"]

    recovered = runner.validate_frozen_dataset_documents(validation, first)
    assert len(recovered) == 128
    assert all(row["prompt_text"].startswith(PREFIX) for row in recovered)


def test_task5_authoritative_lineage_binds_agent_construction_without_human_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = tmp_path / "agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "repo")
    documents = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    repository = Path(__file__).resolve().parents[1]
    preregistration_path = repository / runner.PREREGISTRATION_RELATIVE
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        runner,
        "validate_preregistration_authority",
        lambda *args, **kwargs: {
            "preregistration_file_sha256": hashlib.sha256(
                preregistration_path.read_bytes()
            ).hexdigest(),
            "preregistration_sha256": preregistration["preregistration_sha256"],
        },
    )
    bindings = runner.build_authoritative_lineage_bindings(
        preregistration_path,
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
    assert "human_review" not in bindings
    construction = bindings["agent_construction"]
    assert construction["human_author_count"] == 0
    assert construction["human_reviewer_count"] == 0
    assert construction["exact_three_way_agreement_count"] == 256
    assert set(construction["reviewer_ledgers"]) == {"reviewer_a", "reviewer_b"}
    assert (
        construction["reviewer_ledgers"]["reviewer_a"]["sha256"]
        != (construction["reviewer_ledgers"]["reviewer_b"]["sha256"])
    )
    assert construction["agent_roles"]["generator"]["requested_models"] == [
        "gpt-5.6-sol"
    ]
    assert construction["agent_roles"]["reviewer_a"]["reasoning_effort"] == ("ultra")
    assert construction["agent_roles"]["reviewer_b"]["returned_models"] == [
        "gpt-5.6-luna"
    ]
    assert (
        construction["reviewer_ledgers"]["reviewer_a"]["schedule_sha256"]
        == validation["review_schedule_sha256"]["reviewer_a"]
    )
    assert (
        construction["deterministic_selection"]["selection_authority"]["selection_seed"]
        == 7170
    )
    assert (
        construction["contamination"]["ledger_file_sha256"]
        == validation["source_file_sha256"]["blind-v2-contamination.jsonl"]
    )
    assert construction["contamination"]["semantic_scorer_runtime_verified"] is False
    assert construction["contamination"]["semantic_scorer_receipt_sha256"] is None
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
    def __init__(
        self,
        calls: list[str] | None = None,
        gold_by_query: dict[str, str] | None = None,
    ) -> None:
        self.calls = calls
        self.gold_by_query = gold_by_query

    def rank(self, query: str, skill_ids: list[str]) -> list[str]:
        if self.calls is not None:
            self.calls.append(query)
        gold = (
            self.gold_by_query[query]
            if self.gold_by_query is not None
            else f"test-skill-{int(query.rsplit(' ', 1)[-1]) // 8:02d}"
        )
        return [gold, *[skill_id for skill_id in skill_ids if skill_id != gold]]


def _task5_evaluation_route_rows(
    input_artifacts: dict[str, bytes] | None = None,
) -> list[dict[str, Any]]:
    if input_artifacts is None:
        tasks = [
            {
                "task_id": f"{PREFIX}_TASK_{index:03d}",
                "gold_skill_id": f"test-skill-{index // 8:02d}",
                "negative_skill_id": (
                    f"test-skill-{((index // 8) + 1) % 16:02d}"
                    if index % 8 < 6
                    else None
                ),
                "semantic_family_id": f"{PREFIX}_FAMILY_{index:03d}",
            }
            for index in range(128)
        ]
    else:
        tasks = [
            json.loads(line)
            for line in input_artifacts["blind-v2-tasks.jsonl"].splitlines()
        ]
    model_grid_authority_sha256 = _task5_test_canonical_sha256(
        _task5_evaluation_models()
    )
    return [
        {
            "arm": arm,
            "seed": seed,
            "model_grid_authority_sha256": model_grid_authority_sha256,
            "task_id": task["task_id"],
            "gold_skill_id": task["gold_skill_id"],
            "tempting_negative_skill_id": task["negative_skill_id"],
            "semantic_family_id": task["semantic_family_id"],
            "gold_rank": 1,
            "tempting_negative_rank": (
                6 if task["negative_skill_id"] is not None else None
            ),
            "latency_ns": 10_000_000,
        }
        for seed in (7170, 7171, 7172)
        for arm in ("A", "C")
        for task in tasks
    ]


def _task5_evaluation_models() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for seed in (7170, 7171, 7172):
        for arm in ("A", "C"):
            label = f"{PREFIX}:{arm}:{seed}"
            model_files = [
                {
                    "path": "model.safetensors",
                    "size": 1024 + seed,
                    "sha256": hashlib.sha256(
                        f"{label}:model-file".encode()
                    ).hexdigest(),
                }
            ]
            bindings.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "model_path": f"/{PREFIX}/models/{arm}/{seed}",
                    "model_manifest_path": f"/{PREFIX}/manifests/{arm}/{seed}.json",
                    "model_manifest_file_sha256": hashlib.sha256(
                        f"{label}:manifest-file".encode()
                    ).hexdigest(),
                    "model_manifest_sha256": hashlib.sha256(
                        f"{label}:manifest-semantic".encode()
                    ).hexdigest(),
                    "model_file_manifest_sha256": _task5_test_canonical_sha256(
                        model_files
                    ),
                    "model_files": model_files,
                }
            )
    return bindings


def _task5_evaluation_authority(
    tmp_path: Path,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    pack = tmp_path / "evaluation-agent-pack"
    _write_agent_pack(pack)
    validation = _validate_agent_pack(pack, tmp_path / "evaluation-repo")
    frozen = runner.build_dataset_freeze_documents(validation, commit_a="a" * 40)
    review_summary = frozen["blind-v2-review-summary.json"]
    manifest = json.loads(frozen["blind-v2-manifest.json"])
    construction = deepcopy(manifest["agent_construction"])
    construction["review_summary_file_sha256"] = hashlib.sha256(
        review_summary
    ).hexdigest()
    tasks = [json.loads(line) for line in frozen["blind-v2-tasks.jsonl"].splitlines()]
    placeholder_sha256 = hashlib.sha256(f"{PREFIX}:binding".encode()).hexdigest()
    input_authority = construction["construction_input_authority"]
    skill_source = input_authority["canonical_skill_projection"]["sources"][0]
    protected_sources = input_authority["protected_artifact_projections"]
    skill_index = {
        "canonical_skill_count": 16,
        "path": skill_source["path"],
        "sha256": skill_source["file_sha256"],
    }
    frozen_inputs = {
        "accepted_pairs": {
            "path": protected_sources["train"]["sources"][0]["path"],
            "sha256": protected_sources["train"]["sources"][0]["file_sha256"],
        },
        "heldout_labels": {
            "path": protected_sources["pilot-002"]["sources"][0]["path"],
            "sha256": protected_sources["pilot-002"]["sources"][0]["file_sha256"],
        },
    }
    old_phase16_prompt_files = [
        {"path": source["path"], "sha256": source["file_sha256"]}
        for source in protected_sources["phase16"]["sources"]
    ]
    preregistration = {
        "skill_index": skill_index,
        "frozen_inputs": frozen_inputs,
        "old_phase16_prompt_files": old_phase16_prompt_files,
    }
    preregistration["preregistration_sha256"] = _task5_test_canonical_sha256(
        preregistration
    )
    preregistration_bytes = _task5_test_canonical_json_bytes(preregistration)
    return (
        {
            "preregistration.json": preregistration_bytes,
            "blind-v2-tasks.jsonl": frozen["blind-v2-tasks.jsonl"],
            "blind-v2-manifest.json": frozen["blind-v2-manifest.json"],
            "review-summary.json": review_summary,
        },
        {
            "preregistration": {
                "path": "artifacts/router-v2-blind-v2/preregistration.json",
                "file_sha256": hashlib.sha256(preregistration_bytes).hexdigest(),
                "semantic_sha256": preregistration["preregistration_sha256"],
            },
            "pilot_manifest": {
                "path": "artifacts/router-v2-pilot/pilot-manifest.json",
                "sha256": placeholder_sha256,
            },
            "frozen_inputs": frozen_inputs,
            "old_phase16_prompt_files": old_phase16_prompt_files,
            "base_model": {
                "id": "test/base-model",
                "revision": "a" * 40,
                "file_manifest_sha256": placeholder_sha256,
                "model_files": [],
            },
            "evaluation_models": _task5_evaluation_models(),
            "blind_v2_dataset": {
                "commit_a": manifest["commit_a"],
                "tasks_file_sha256": hashlib.sha256(
                    frozen["blind-v2-tasks.jsonl"]
                ).hexdigest(),
                "manifest_file_sha256": hashlib.sha256(
                    frozen["blind-v2-manifest.json"]
                ).hexdigest(),
                "dataset_sha256": manifest["dataset_sha256"],
                "source_file_sha256": deepcopy(manifest["source_file_sha256"]),
                "per_row_prompt_sha256": deepcopy(manifest["per_row_prompt_sha256"]),
                "task_rows": tasks,
            },
            "agent_construction": construction,
            "skill_index": skill_index,
            "query_contract": {
                "path": "src/hermes_skilleval/router_query.py",
                "sha256": placeholder_sha256,
            },
            "skill_representation_builder": {
                "path": "src/hermes_skilleval/router_v2_pilot_candidates.py",
                "sha256": placeholder_sha256,
            },
            "gate": {"path": "gate.json", "sha256": placeholder_sha256},
            "evaluator": {"source_files": []},
        },
    )


def test_task5_evaluation_lineage_includes_canonical_frozen_task_artifact(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)

    documents = runner.build_evaluation_documents(
        _task5_evaluation_route_rows(inputs),
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings=frozen_bindings,
        input_artifacts=inputs,
        attempt_artifacts=_task5_attempt_artifacts(),
    )

    assert documents["blind-v2-tasks.jsonl"] == inputs["blind-v2-tasks.jsonl"]
    lineage = json.loads(documents["lineage-manifest.json"])
    task_binding = next(
        row for row in lineage["artifacts"] if row["path"] == "blind-v2-tasks.jsonl"
    )
    assert (
        task_binding["sha256"]
        == hashlib.sha256(inputs["blind-v2-tasks.jsonl"]).hexdigest()
    )
    assert (
        lineage["frozen_bindings"]["blind_v2_dataset"]
        == frozen_bindings["blind_v2_dataset"]
    )


def _task5_resynchronize_evaluation_manifest_and_bindings(
    inputs: dict[str, bytes],
    frozen_bindings: dict[str, Any],
    manifest: dict[str, Any],
    review_summary: dict[str, Any],
) -> None:
    inputs["review-summary.json"] = _task5_test_canonical_json_bytes(review_summary)
    inputs["blind-v2-manifest.json"] = _task5_test_canonical_json_bytes(manifest)
    construction = deepcopy(manifest["agent_construction"])
    construction["review_summary_file_sha256"] = hashlib.sha256(
        inputs["review-summary.json"]
    ).hexdigest()
    frozen_bindings["agent_construction"] = construction
    dataset_binding = frozen_bindings["blind_v2_dataset"]
    dataset_binding["manifest_file_sha256"] = hashlib.sha256(
        inputs["blind-v2-manifest.json"]
    ).hexdigest()
    dataset_binding["tasks_file_sha256"] = hashlib.sha256(
        inputs["blind-v2-tasks.jsonl"]
    ).hexdigest()
    dataset_binding["dataset_sha256"] = manifest["dataset_sha256"]
    if "source_file_sha256" in manifest:
        dataset_binding["source_file_sha256"] = deepcopy(manifest["source_file_sha256"])
    else:
        dataset_binding.pop("source_file_sha256", None)
    dataset_binding["per_row_prompt_sha256"] = deepcopy(
        manifest["per_row_prompt_sha256"]
    )
    dataset_binding["task_rows"] = [
        json.loads(line) for line in inputs["blind-v2-tasks.jsonl"].splitlines()
    ]


def _task5_resync_committed_role_evidence(
    construction: dict[str, Any], role: str
) -> None:
    records = construction["sanitized_run_records"][role]
    evidence = construction["agent_roles"][role]
    evidence["requested_models"] = sorted(
        {record["requested_model"] for record in records}
    )
    evidence["returned_models"] = sorted(
        {
            record["returned_model"]
            for record in records
            if record["returned_model"] is not None
        }
    )
    evidence["request_count"] = len(records)
    evidence["invocation_count"] = sum(
        len(record["session_or_thread_ids"]) for record in records
    )
    evidence["session_or_thread_ids"] = [
        identity for record in records for identity in record["session_or_thread_ids"]
    ]
    evidence["request_hashes_sha256"] = _task5_test_canonical_sha256(
        [record["request_sha256"] for record in records]
    )
    evidence["response_hashes_sha256"] = _task5_test_canonical_sha256(
        [
            record["response_sha256"]
            for record in records
            if record["response_sha256"] is not None
        ]
    )
    evidence["run_sha256"] = _task5_test_canonical_sha256(records)


def _task5_resync_committed_identity_authority(
    manifest: dict[str, Any], role: str
) -> None:
    construction = manifest["agent_construction"]
    source_hashes = manifest["source_file_sha256"]
    authority_role = construction["agent_run_identity_authority"]["roles"][role]
    records = construction["sanitized_run_records"][role]
    invocation_ids = [record["invocation_id"] for record in records]
    candidate_ids = [
        candidate_id for record in records for candidate_id in record["candidate_ids"]
    ]
    sessions = [
        identity for record in records for identity in record["session_or_thread_ids"]
    ]
    authority_role.update(
        {
            "invocation_ids": invocation_ids,
            "invocation_ids_sha256": _task5_test_canonical_sha256(invocation_ids),
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": _task5_test_canonical_sha256(candidate_ids),
            "request_count": len(records),
            "invocation_count": len(sessions),
            "session_or_thread_ids": sessions,
            "session_or_thread_ids_sha256": _task5_test_canonical_sha256(sessions),
            "ledger_file_sha256": source_hashes[authority_role["ledger_path"]],
        }
    )
    construction["agent_run_identity_authority"]["authority_sha256"] = (
        _task5_test_canonical_sha256(
            construction["agent_run_identity_authority"]["roles"]
        )
    )


@pytest.mark.parametrize(
    "field",
    (
        "generation_ledger",
        "agent_run_metadata",
        "contamination",
        "construction_input_authority",
        "agent_run_identity_authority",
    ),
)
def test_task5_evaluation_requires_complete_agent_construction_authority(
    tmp_path: Path,
    field: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    manifest["agent_construction"].pop(field)
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_requires_source_file_hash_authority(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    manifest.pop("source_file_sha256")
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


@pytest.mark.parametrize("projection_kind", ("skill", "protected"))
def test_task5_evaluation_rejects_resynchronized_input_projection_source_forgery(
    tmp_path: Path, projection_kind: str
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    authority = manifest["agent_construction"]["construction_input_authority"]
    projection = (
        authority["canonical_skill_projection"]
        if projection_kind == "skill"
        else authority["protected_artifact_projections"]["train"]
    )
    projection["sources"][0]["file_sha256"] = "0" * 64
    projection["source_file_manifest_sha256"] = _task5_test_canonical_sha256(
        projection["sources"]
    )
    authority["authority_sha256"] = _task5_test_canonical_sha256(
        {key: value for key, value in authority.items() if key != "authority_sha256"}
    )
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_cross_role_duplicate_session_after_resync(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    construction = manifest["agent_construction"]
    generator_session = construction["sanitized_run_records"]["generator"][0][
        "session_or_thread_ids"
    ][0]
    reviewer_record = construction["sanitized_run_records"]["reviewer_b"][0]
    reviewer_record["session_or_thread_ids"][0] = generator_session
    reviewer_record["attempts"][0]["session_or_thread_id"] = generator_session
    _task5_resync_committed_role_evidence(construction, "reviewer_b")
    _task5_resync_committed_identity_authority(manifest, "reviewer_b")
    review_summary["agent_roles"] = deepcopy(construction["agent_roles"])
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_duplicate_candidate_record_after_resync(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    construction = manifest["agent_construction"]
    duplicate = deepcopy(construction["sanitized_run_records"]["reviewer_a"][0])
    duplicate_session = f"duplicate-{duplicate['candidate_ids'][0]}"
    duplicate["session_or_thread_ids"] = [duplicate_session]
    duplicate["attempts"][0]["session_or_thread_id"] = duplicate_session
    construction["sanitized_run_records"]["reviewer_a"].append(duplicate)
    _task5_resync_committed_role_evidence(construction, "reviewer_a")
    _task5_resync_committed_identity_authority(manifest, "reviewer_a")
    review_summary["agent_roles"] = deepcopy(construction["agent_roles"])
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_missing_candidate_record_after_resync(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    construction = manifest["agent_construction"]
    records = construction["sanitized_run_records"]["reviewer_a"]
    missing_candidate_id = next(
        candidate_id
        for candidate_id, outcome in manifest["candidate_outcomes"].items()
        if outcome == "NOT_SELECTED"
    )
    records[:] = [
        record
        for record in records
        if missing_candidate_id not in record["candidate_ids"]
    ]
    _task5_resync_committed_role_evidence(construction, "reviewer_a")
    _task5_resync_committed_identity_authority(manifest, "reviewer_a")
    review_summary["agent_roles"] = deepcopy(construction["agent_roles"])
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rebinds_contamination_authority(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    manifest["agent_construction"]["contamination"]["required_semantic_model_id"] = (
        "forged/model"
    )
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


@pytest.mark.parametrize(
    "mutation",
    ("missing", "duplicate_key", "extra_key", "missing_field", "hash_drift"),
)
def test_task5_evaluation_requires_complete_exact_model_binding_grid(
    tmp_path: Path,
    mutation: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    models = frozen_bindings["evaluation_models"]
    if mutation == "missing":
        models.pop()
    elif mutation == "duplicate_key":
        models[-1]["arm"] = models[0]["arm"]
        models[-1]["seed"] = models[0]["seed"]
    elif mutation == "extra_key":
        models[0]["unexpected"] = True
    elif mutation == "missing_field":
        models[0].pop("model_manifest_sha256")
    else:
        models[0]["model_file_manifest_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="evaluation frozen task authority mismatch"):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "human_review",
        "source_file_bytes",
        "source_bytes",
        "raw_source",
        "response",
        "raw_response",
        "response_body",
        "rationale",
        "reason",
        "refusal",
        "analysis",
        "reasoning",
        "chain_of_thought",
        "raw_reasoning",
        "hidden_reasoning",
    ),
)
def test_task5_evaluation_rejects_nested_legacy_or_raw_lineage_fields(
    tmp_path: Path,
    forbidden_field: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    frozen_bindings["preregistration"]["nested"] = {
        forbidden_field: f"{PREFIX} FORBIDDEN"
    }

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_extra_frozen_binding_top_level_field(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    frozen_bindings["unexpected"] = {}

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_allows_reasoning_effort_lineage_field(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)

    documents = runner.build_evaluation_documents(
        _task5_evaluation_route_rows(inputs),
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings=frozen_bindings,
        input_artifacts=inputs,
        attempt_artifacts=_task5_attempt_artifacts(),
    )

    assert b'"reasoning_effort"' in documents["blind-v2-manifest.json"]


@pytest.mark.parametrize("mutation", ("task_id", "semantic_family_id"))
def test_task5_evaluation_rejects_route_rows_drift_from_frozen_tasks(
    tmp_path: Path,
    mutation: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    route_rows = _task5_evaluation_route_rows(inputs)
    original_task_id = route_rows[0]["task_id"]
    for row in route_rows:
        if row["task_id"] != original_task_id:
            continue
        if mutation == "task_id":
            row["task_id"] = "f" * 24
        else:
            row["semantic_family_id"] = f"{PREFIX}_FORGED_FAMILY"

    with pytest.raises(ValueError, match="evaluation frozen task authority mismatch"):
        runner.build_evaluation_documents(
            route_rows,
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_commit_a_mismatch_from_frozen_authority(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)

    with pytest.raises(ValueError, match="evaluation frozen task authority mismatch"):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="e" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_resynchronized_task_manifest_and_binding_drift(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    task_rows = [
        json.loads(line) for line in inputs["blind-v2-tasks.jsonl"].splitlines()
    ]
    old_task_id = task_rows[0]["task_id"]
    forged_task_id = "f" * 24
    task_rows[0]["task_id"] = forged_task_id
    task_rows[0]["semantic_family_id"] = f"{PREFIX}_FORGED_FAMILY"
    inputs["blind-v2-tasks.jsonl"] = _jsonl_bytes(task_rows)

    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    task_file_sha256 = hashlib.sha256(inputs["blind-v2-tasks.jsonl"]).hexdigest()
    manifest["dataset_sha256"] = task_file_sha256
    manifest["tasks_file_sha256"] = task_file_sha256
    selection = manifest["agent_construction"]["deterministic_selection"]
    selection["selected_candidate_ids"][0] = forged_task_id
    selection["selected_candidate_ids_sha256"] = _task5_test_canonical_sha256(
        selection["selected_candidate_ids"]
    )
    for strata in selection["selected_by_stratum"].values():
        for candidate_ids in strata.values():
            if old_task_id in candidate_ids:
                candidate_ids[candidate_ids.index(old_task_id)] = forged_task_id
    manifest["agent_construction"]["deterministic_selection_sha256"] = (
        _task5_test_canonical_sha256(selection)
    )
    for document in (manifest, manifest["agent_construction"], review_summary):
        outcomes = document["candidate_outcomes"]
        outcomes[forged_task_id] = outcomes.pop(old_task_id)
        document["candidate_outcomes"] = dict(sorted(outcomes.items()))
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(ValueError, match="evaluation frozen task authority mismatch"):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_resynchronized_candidate_outcome_drift(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    candidate_id = next(
        candidate_id
        for candidate_id, outcome in manifest["candidate_outcomes"].items()
        if outcome == "NOT_SELECTED"
    )
    for document in (manifest, manifest["agent_construction"], review_summary):
        document["candidate_outcomes"][candidate_id] = "REJECTED_INVOCATION"
        document["exact_three_way_agreement_count"] = 255
        document["selection_not_selected_count"] = 127
        document["pipeline_rejected_candidate_count"] = 1
    _task5_resynchronize_evaluation_manifest_and_bindings(
        inputs, frozen_bindings, manifest, review_summary
    )

    with pytest.raises(
        ValueError,
        match="evaluation (?:Agent construction lineage|frozen task authority) mismatch",
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def _task5_attempt_artifacts() -> dict[str, bytes]:
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
    return {
        "attempt-1.started.json": runner._canonical_json_bytes(started),
        "attempt-1.terminal.json": runner._canonical_json_bytes(terminal),
    }


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


@pytest.mark.parametrize("lineage_case", ("empty", "mismatched"))
def test_task5_evaluation_claims_require_manifest_bound_agent_construction(
    tmp_path: Path,
    lineage_case: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    if lineage_case == "empty":
        frozen_bindings = {}
    else:
        frozen_bindings["agent_construction"]["review_mode"] = "UNBOUND_REVIEW"

    with pytest.raises(
        ValueError,
        match="evaluation (?:Agent construction lineage|frozen task authority) mismatch",
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


def test_task5_evaluation_rejects_synchronized_manifest_tamper_with_stale_hash(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    manifest["agent_construction"]["deterministic_selection"][
        "selected_candidate_ids_sha256"
    ] = "0" * 64
    inputs["blind-v2-manifest.json"] = _task5_test_canonical_json_bytes(manifest)
    construction = deepcopy(manifest["agent_construction"])
    construction["review_summary_file_sha256"] = hashlib.sha256(
        inputs["review-summary.json"]
    ).hexdigest()
    frozen_bindings["agent_construction"] = construction

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


@pytest.mark.parametrize("agreement_count", (0, 127))
def test_task5_evaluation_rejects_non_128_three_way_agreement_authority(
    tmp_path: Path,
    agreement_count: int,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    manifest = json.loads(inputs["blind-v2-manifest.json"])
    review_summary = json.loads(inputs["review-summary.json"])
    manifest["exact_three_way_agreement_count"] = agreement_count
    manifest["agent_construction"]["exact_three_way_agreement_count"] = agreement_count
    review_summary["exact_three_way_agreement_count"] = agreement_count
    inputs["review-summary.json"] = _task5_test_canonical_json_bytes(review_summary)
    inputs["blind-v2-manifest.json"] = _task5_test_canonical_json_bytes(manifest)
    construction = deepcopy(manifest["agent_construction"])
    construction["review_summary_file_sha256"] = hashlib.sha256(
        inputs["review-summary.json"]
    ).hexdigest()
    frozen_bindings["agent_construction"] = construction
    frozen_bindings["blind_v2_dataset"]["manifest_file_sha256"] = hashlib.sha256(
        inputs["blind-v2-manifest.json"]
    ).hexdigest()

    with pytest.raises(
        ValueError, match="evaluation Agent construction lineage mismatch"
    ):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


@pytest.mark.parametrize(
    ("malformed_case", "message"),
    (
        ("input_artifacts", "evaluation input artifact set mismatch"),
        ("attempt_artifacts", "attempt artifact set mismatch"),
        ("frozen_bindings", "evaluation frozen task authority mismatch"),
    ),
)
def test_task5_evaluation_normalizes_malformed_authority_containers(
    tmp_path: Path,
    malformed_case: str,
    message: str,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    attempt_artifacts = _task5_attempt_artifacts()
    if malformed_case == "input_artifacts":
        inputs = cast(Any, None)
    elif malformed_case == "attempt_artifacts":
        attempt_artifacts = cast(Any, None)
    else:
        frozen_bindings = cast(Any, None)

    with pytest.raises(ValueError, match=message):
        runner.build_evaluation_documents(
            _task5_evaluation_route_rows(inputs),
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=attempt_artifacts,
        )


def test_evaluate_routes_produces_complete_a_c_grid_without_arm_b(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    tasks = [
        json.loads(line)
        for line in inputs["blind-v2-tasks.jsonl"].decode("utf-8").splitlines()
    ]
    bindings = _task5_evaluation_models()

    calls: list[str] = []
    gold_by_query = {task["prompt_text"]: task["gold_skill_id"] for task in tasks}
    rows = runner.evaluate_routes(
        tasks,
        _skills(),
        bindings,
        scorer_factory=lambda arm, seed, path: _FakeScorer(calls, gold_by_query),
        clock_ns=iter(range(1, 1537)).__next__,
    )

    assert len(rows) == 768
    assert {(row["arm"], row["seed"]) for row in rows} == {
        (arm, seed) for arm in ("A", "C") for seed in (7170, 7171, 7172)
    }
    assert all(row["gold_rank"] == 1 for row in rows)
    assert {row["model_grid_authority_sha256"] for row in rows} == {
        _task5_test_canonical_sha256(bindings)
    }
    assert all(row["latency_ns"] == 1 for row in rows)
    assert len(calls) == 1536
    assert all(calls.count(task["prompt_text"]) == 12 for task in tasks)

    documents = runner.build_evaluation_documents(
        rows,
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings=frozen_bindings,
        input_artifacts=inputs,
        attempt_artifacts=_task5_attempt_artifacts(),
    )
    regenerated = runner.build_evaluation_documents(
        rows,
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings=frozen_bindings,
        input_artifacts=inputs,
        attempt_artifacts=_task5_attempt_artifacts(),
    )
    assert documents == regenerated
    assert set(documents) == set(runner.EVALUATION_OUTPUT_FILENAMES)
    lineage = json.loads(documents["lineage-manifest.json"])
    lineage_paths = {row["path"] for row in lineage["artifacts"]}
    assert lineage_paths == (
        set(runner.EVALUATION_OUTPUT_FILENAMES) - {"lineage-manifest.json"}
        | {"attempt-1.started.json", "attempt-1.terminal.json"}
    )
    assert lineage["frozen_bindings"]["evaluation_models"] == _task5_evaluation_models()
    summary = json.loads(documents["evaluation-summary.json"])
    assert summary["task_count"] == 128
    assert summary["negative_labeled_task_count"] == 96
    assert summary["same_provider_limitation"] == (
        "Generator gpt-5.6-sol/max, Reviewer A gpt-5.6-sol/ultra, and Reviewer B "
        "gpt-5.6-luna/max are OpenAI configurations, so their review judgments are "
        "not statistically independent."
    )
    report = documents["result-report.md"].decode("utf-8")
    assert "128 tasks" in report
    assert "96 negative-labeled" in report
    assert "same provider" in report.lower()
    assert "human-reviewed" not in report.lower()
    assert "generalization" not in report.lower()


def test_evaluate_routes_rejects_duplicate_model_binding_key(tmp_path: Path) -> None:
    inputs, _ = _task5_evaluation_authority(tmp_path)
    tasks = [
        json.loads(line)
        for line in inputs["blind-v2-tasks.jsonl"].decode("utf-8").splitlines()
    ]
    bindings = _task5_evaluation_models()
    bindings.append(deepcopy(bindings[0]))

    with pytest.raises(ValueError, match="complete A/C seed grid"):
        runner.evaluate_routes(
            tasks,
            _skills(),
            bindings,
            scorer_factory=lambda arm, seed, path: _FakeScorer([], {}),
        )


def test_task5_evaluation_rejects_scoring_model_grid_lineage_mismatch(
    tmp_path: Path,
) -> None:
    inputs, frozen_bindings = _task5_evaluation_authority(tmp_path)
    tasks = [
        json.loads(line)
        for line in inputs["blind-v2-tasks.jsonl"].decode("utf-8").splitlines()
    ]
    scoring_bindings = deepcopy(_task5_evaluation_models())
    scoring_bindings[0]["model_path"] += "-different-scoring-authority"
    gold_by_query = {task["prompt_text"]: task["gold_skill_id"] for task in tasks}
    rows = runner.evaluate_routes(
        tasks,
        _skills(),
        scoring_bindings,
        scorer_factory=lambda arm, seed, path: _FakeScorer(None, gold_by_query),
        clock_ns=iter(range(1, 1537)).__next__,
    )

    with pytest.raises(ValueError, match="evaluation frozen task authority mismatch"):
        runner.build_evaluation_documents(
            rows,
            commit_a="a" * 40,
            commit_b="b" * 40,
            evaluator_commit="c" * 40,
            attempt_token_sha256="d" * 64,
            frozen_bindings=frozen_bindings,
            input_artifacts=inputs,
            attempt_artifacts=_task5_attempt_artifacts(),
        )


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
