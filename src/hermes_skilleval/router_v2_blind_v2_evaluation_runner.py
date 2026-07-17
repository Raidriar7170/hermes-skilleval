from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from copy import deepcopy
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, cast

from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.router_v2_blind_v2_evaluation import (
    ARMS,
    POSITIVE_TASK_COUNT,
    SEEDS,
    TEMPTING_NEGATIVE_COUNT,
    apply_preregistered_gate,
    build_aggregate_results,
    build_failure_slices,
    build_lineage_manifest,
    build_paired_results,
    build_per_seed_result,
    build_statistics,
    canonical_sha256,
    preregistered_evaluation_contract,
    validate_preregistration_truth,
)
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_evaluation import quantize8


MODEL_LOAD_SMOKE_TEXTS = (
    "synthetic blind-v2 model load query",
    "synthetic blind-v2 skill description",
)
QUERY_CONTRACT_VERSION = "router-v2-prompt-only-query-v1"
SKILL_REPRESENTATION_BUILDER_VERSION = (
    "router-v2-id-name-category-description-trigger-terms-body-v1"
)
FINAL_NAMESPACE_RELATIVE = Path(
    "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001"
)
DATASET_FREEZE_RELATIVE = Path("data/router-v2-blind-v2")
PREREGISTRATION_RELATIVE = Path("artifacts/router-v2-blind-v2/preregistration.json")
DATASET_FREEZE_FILENAMES = (
    "blind-v2-tasks.jsonl",
    "blind-v2-review-summary.json",
    "blind-v2-manifest.json",
)
PILOT_MANIFEST_RELATIVE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-002-eval-replay/pilot-manifest.json"
)
EVALUATION_OUTPUT_FILENAMES = (
    "preregistration.json",
    "blind-v2-manifest.json",
    "review-summary.json",
    "per-seed.json",
    "aggregate.json",
    "paired.json",
    "statistics.json",
    "failure-slices.json",
    "evaluation-summary.json",
    "result-report.md",
    "lineage-manifest.json",
)
SMOKE_RECEIPT_ROOT = Path("/tmp/hermes-router-v2-blind-v2-smoke-receipts")
AUTHORING_TEMPLATE_ROOT = Path("/tmp/hermes-blind-v2-authoring-pack")
PREREGISTRATION_PARENT_COMMIT = "8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552"
EVALUATOR_SOURCE_PATHS = (
    "src/hermes_skilleval/router_v2_blind_v2_evaluation.py",
    "src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py",
    "src/hermes_skilleval/router_v2_pilot_evaluation.py",
    "scripts/run_router_v2_blind_v2_final.py",
)
REQUIRED_AGENT_PACK_FILES = (
    "blind-v2-generation.jsonl",
    "blind-v2-review-a.jsonl",
    "blind-v2-review-b.jsonl",
    "blind-v2-contamination.jsonl",
    "agent-run-metadata.json",
)
AGENT_CONFIGS = {
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
SEMANTIC_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
SEMANTIC_MODEL_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
TOKEN_5GRAM_JACCARD_MAX = Decimal("0.80")
CHARACTER_5GRAM_JACCARD_MAX = Decimal("0.85")
SEMANTIC_COSINE_MAX = Decimal("0.90")
CONTAMINATION_SCOPES = ("train", "pilot-002", "phase16", "prior_candidate")
_SELECTION_AUTHORITY: Mapping[str, int | str] = MappingProxyType(
    {
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
)
SELECTION_AUTHORITY = _SELECTION_AUTHORITY
SELECTION_SEED = cast(int, _SELECTION_AUTHORITY["selection_seed"])


def _selection_authority_document() -> dict[str, int | str]:
    return dict(_SELECTION_AUTHORITY)


GENERATOR_SYSTEM_PROMPT = (
    "You are the Generator for a preregistered Router V2 blind evaluation. "
    "Create natural English user requests for exactly one primary canonical skill. "
    "Do not mention skill IDs, skill names, gold labels, negative labels, benchmarks, "
    "routers, training, pilot data, Phase 16, Arm A, Arm C, or model behavior. For a "
    "negative-labeled candidate, choose one plausible but insufficient canonical "
    "negative skill. Use only the supplied skill definitions and quota. Do not use "
    "external memory or prior conversation. Return only JSON matching the supplied "
    "schema."
)
REVIEWER_SYSTEM_PROMPT = (
    "You are a role-isolated reviewer for one preregistered Router V2 blind candidate. "
    "Use only the supplied task text, canonical skill definitions, and rubric. "
    "Independently decide the single primary gold skill and one "
    "plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural "
    "wording, label leakage, invalid negatives, and tasks with more than one equally "
    "primary skill. Do not use external memory, prior conversation, quotas, other "
    "reviews, generator labels, Router models, or model results. Return only JSON "
    "matching the supplied schema."
)
GENERATOR_RULES = {
    "language": "natural English",
    "primary_skill": "exactly one primary canonical skill",
    "label_leakage": "do not expose canonical labels in the request text",
    "negative_skill": "one plausible but insufficient canonical skill or null",
    "source_boundary": "use only the supplied canonical skill definitions and quota",
}
REVIEW_RUBRIC = {
    "natural": "The request is natural English user wording.",
    "single_primary_skill": "Exactly one canonical skill is clearly primary.",
    "no_label_leakage": "The request does not expose skill or evaluation labels.",
    "negative_confusable": (
        "A non-null negative is plausible for the wording but insufficient to fulfill "
        "the request; use null when no such negative exists."
    ),
}
AGENT_REVIEW_DECISIONS = (
    "ACCEPT",
    "REJECT_AMBIGUOUS",
    "REJECT_NOT_CONFUSABLE",
    "REJECT_UNNATURAL",
    "REJECT_LABEL_LEAKAGE",
)
AGENT_REVIEW_CONFIDENCE = ("LOW", "MEDIUM", "HIGH")
CANONICAL_SKILL_FIELDS_IN_ORDER = (
    "id",
    "name",
    "category",
    "description",
    "trigger_terms",
    "body",
)
GENERATOR_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_index",
                    "prompt_text",
                    "semantic_family_id",
                    "proposed_gold_skill_id",
                    "proposed_negative_skill_id",
                    "language",
                    "rationale",
                ],
                "properties": {
                    "candidate_index": {"type": "integer", "minimum": 0},
                    "prompt_text": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "semantic_family_id": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "proposed_gold_skill_id": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "proposed_negative_skill_id": {
                        "type": ["string", "null"],
                        "pattern": r"\S",
                    },
                    "language": {"const": "en"},
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                },
            },
        }
    },
}
REVIEWER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "natural",
        "single_primary_skill",
        "no_label_leakage",
        "negative_confusable",
        "confidence",
        "reason",
    ],
    "properties": {
        "decision": {"enum": list(AGENT_REVIEW_DECISIONS)},
        "reviewed_gold_skill_id": {
            "type": "string",
            "minLength": 1,
            "pattern": r"\S",
        },
        "reviewed_negative_skill_id": {
            "type": ["string", "null"],
            "pattern": r"\S",
        },
        "natural": {"type": "boolean"},
        "single_primary_skill": {"type": "boolean"},
        "no_label_leakage": {"type": "boolean"},
        "negative_confusable": {"type": ["boolean", "null"]},
        "confidence": {"enum": list(AGENT_REVIEW_CONFIDENCE)},
        "reason": {"type": "string", "minLength": 1, "pattern": r"\S"},
    },
    "allOf": [
        {
            "if": {
                "properties": {"reviewed_negative_skill_id": {"type": "null"}},
                "required": ["reviewed_negative_skill_id"],
            },
            "then": {"properties": {"negative_confusable": {"type": "null"}}},
            "else": {"properties": {"negative_confusable": {"type": "boolean"}}},
        }
    ],
    "oneOf": [
        {
            "properties": {
                "decision": {"const": "ACCEPT"},
                "natural": {"const": True},
                "single_primary_skill": {"const": True},
                "no_label_leakage": {"const": True},
            },
            "if": {
                "properties": {"reviewed_negative_skill_id": {"type": "string"}},
                "required": ["reviewed_negative_skill_id"],
            },
            "then": {"properties": {"negative_confusable": {"const": True}}},
        },
        {
            "properties": {
                "decision": {"const": "REJECT_AMBIGUOUS"},
                "single_primary_skill": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_NOT_CONFUSABLE"},
                "reviewed_negative_skill_id": {
                    "type": "string",
                    "pattern": r"\S",
                },
                "negative_confusable": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_UNNATURAL"},
                "natural": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_LABEL_LEAKAGE"},
                "no_label_leakage": {"const": False},
            }
        },
    ],
}
LEGACY_REQUIRED_HUMAN_PACK_FILES = (
    "blind-v2-authored.csv",
    "blind-v2-independent-review.csv",
    "reviewer-metadata.json",
)
AUTHORED_FIELDS = (
    "task_id",
    "prompt_text",
    "semantic_family_id",
    "gold_skill_id",
    "negative_skill_id",
    "author_id",
    "author_reason",
    "language",
    "source_type",
)
REVIEW_FIELDS = (
    "task_id",
    "prompt_text_sha256",
    "reviewer_id",
    "review_decision",
    "reviewed_gold_skill_id",
    "reviewed_negative_skill_id",
    "review_confidence",
    "review_reason",
)
REVIEW_DECISIONS = {
    "ACCEPT",
    "REJECT_AMBIGUOUS",
    "REJECT_WRONG_GOLD",
    "REJECT_WRONG_NEGATIVE",
    "REJECT_NOT_CONFUSABLE",
    "REJECT_NEAR_DUPLICATE",
    "REJECT_UNNATURAL",
    "REJECT_LABEL_LEAKAGE",
}
_LEAKAGE_MARKERS = (
    "gold skill",
    "negative skill",
    "benchmark",
    "router",
)
_PROTECTED_MARKERS = (
    "phase16",
    "phase-16",
    "phase_16",
    "pilot-002",
    "pilot_002",
    "heldout-labels",
)


class EvaluationEncoder(Protocol):
    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]: ...


class RouteScorer(Protocol):
    def rank(self, query: str, skill_ids: list[str]) -> list[str]: ...


EncoderFactory = Callable[[str, int, Path], EvaluationEncoder]
ScorerFactory = Callable[[str, int, Path], RouteScorer]
AuthorityValidator = Callable[..., dict[str, Any]]
SemanticSimilarity = Callable[[str, str], int | float | Decimal]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class _DeterministicSelectionProtocolViolation(Exception):
    pass


def _require_deterministic_selection(condition: bool, message: str) -> None:
    if not condition:
        raise _DeterministicSelectionProtocolViolation(message)


def _exact_object_fields(
    value: Any, expected: set[str] | frozenset[str], label: str
) -> dict[str, Any]:
    _require(type(value) is dict, f"{label} must be an object")
    _require(set(value) == expected, f"{label} fields mismatch")
    return cast(dict[str, Any], value)


def _nonempty_string(value: Any, label: str) -> str:
    _require(type(value) is str and bool(value.strip()), f"{label} must be non-empty")
    return cast(str, value)


def _validated_canonical_skill_rows(
    canonical_skills: Any, *, exact_fields: bool
) -> list[dict[str, Any]]:
    _require(type(canonical_skills) is list, "canonical skills must be a list")
    _require(
        len(canonical_skills) == 16,
        "canonical skills must contain exactly 16 entries",
    )
    required_fields = set(CANONICAL_SKILL_FIELDS_IN_ORDER)
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, raw_skill in enumerate(canonical_skills):
        if exact_fields:
            skill = _exact_object_fields(
                raw_skill,
                required_fields,
                f"canonical skill {index}",
            )
        else:
            _require(
                type(raw_skill) is dict,
                f"canonical skill {index} must be an object",
            )
            _require(
                required_fields.issubset(raw_skill),
                f"canonical skill {index} fields mismatch",
            )
            skill = cast(dict[str, Any], raw_skill)
        for field in ("id", "name", "category", "description", "body"):
            _nonempty_string(skill[field], f"canonical skill {index} {field}")
        trigger_terms = skill["trigger_terms"]
        _require(
            type(trigger_terms) is list,
            f"canonical skill {index} trigger_terms must be a list",
        )
        for term_index, term in enumerate(trigger_terms):
            _nonempty_string(
                term,
                f"canonical skill {index} trigger_terms item {term_index}",
            )
        skill_id = cast(str, skill["id"])
        ids.append(skill_id)
        rows.append(skill)
    _require(len(ids) == len(set(ids)), "canonical skill ids must be unique")
    return rows


def _canonical_skill_ids(canonical_skills: Any) -> set[str]:
    rows = _validated_canonical_skill_rows(canonical_skills, exact_fields=True)
    return {cast(str, skill["id"]) for skill in rows}


def _project_canonical_skills(canonical_skills: Any) -> list[dict[str, Any]]:
    rows = _validated_canonical_skill_rows(canonical_skills, exact_fields=False)
    return [
        {field: deepcopy(skill[field]) for field in CANONICAL_SKILL_FIELDS_IN_ORDER}
        for skill in rows
    ]


def _validate_canonical_json_value(value: Any, active_ids: set[int]) -> None:
    value_type = type(value)
    if value is None or value_type in {bool, int}:
        return
    if value_type is float:
        _require(math.isfinite(value), "canonical JSON numbers must be finite")
        return
    if value_type is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("canonical JSON strings must be valid UTF-8") from exc
        return
    if value_type not in {list, dict}:
        raise ValueError("canonical JSON contains a non-JSON value")
    identity = id(value)
    _require(identity not in active_ids, "canonical JSON must not contain a cycle")
    active_ids.add(identity)
    try:
        if value_type is list:
            for item in value:
                _validate_canonical_json_value(item, active_ids)
        else:
            for key, item in value.items():
                _require(
                    type(key) is str,
                    "canonical JSON object keys must be strings",
                )
                _validate_canonical_json_value(key, active_ids)
                _validate_canonical_json_value(item, active_ids)
    finally:
        active_ids.remove(identity)


def _canonical_contract_json_bytes(value: Any) -> bytes:
    try:
        _validate_canonical_json_value(value, set())
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (OverflowError, RecursionError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("value must be valid canonical JSON") from exc


def _canonical_contract_json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_contract_json_bytes(value)).hexdigest()


def _canonical_contract_json_equal(actual: Any, expected: Any) -> bool:
    return _canonical_contract_json_bytes(actual) == _canonical_contract_json_bytes(
        expected
    )


def _exact_lowercase_hex(value: Any, *, length: int, label: str) -> str:
    _require(
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value),
        f"{label} must be exactly {length} lowercase hex characters",
    )
    return cast(str, value)


def _request_sha256(request: dict[str, Any]) -> str:
    payload = {key: value for key, value in request.items() if key != "request_sha256"}
    return _canonical_contract_json_sha256(payload)


def opaque_candidate_id(
    round_number: int, skill_id: str, index: int, response_sha256: str
) -> str:
    _require(
        type(round_number) is int and round_number > 0,
        "round number must be a positive integer",
    )
    _nonempty_string(skill_id, "skill id")
    _require(type(index) is int and index >= 0, "candidate index must be an integer")
    response_sha256 = _exact_lowercase_hex(
        response_sha256, length=64, label="response SHA-256"
    )
    raw = f"{round_number}:{skill_id}:{index}:{response_sha256}"
    candidate_id = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return _exact_lowercase_hex(candidate_id, length=24, label="candidate id")


def selection_key(candidate_id: str) -> str:
    candidate_id = _exact_lowercase_hex(candidate_id, length=24, label="candidate id")
    seed = cast(int, _SELECTION_AUTHORITY["selection_seed"])
    return hashlib.sha256(f"{seed}:{candidate_id}".encode()).hexdigest()


def review_schedule_key(role: str, candidate_id: str) -> str:
    _require(
        type(role) is str and role in {"reviewer_a", "reviewer_b"},
        "reviewer role mismatch",
    )
    candidate_id = _exact_lowercase_hex(candidate_id, length=24, label="candidate id")
    prefix = {"reviewer_a": "review-a:7170", "reviewer_b": "review-b:7171"}[role]
    return hashlib.sha256(f"{prefix}:{candidate_id}".encode()).hexdigest()


def build_generator_request(
    canonical_skills: list[dict[str, Any]],
    *,
    gold_skill_id: str,
    negative_quota: int,
    positive_only_quota: int,
    round_number: int = 1,
) -> dict[str, Any]:
    projected_canonical_skills = _project_canonical_skills(canonical_skills)
    canonical_ids = {cast(str, skill["id"]) for skill in projected_canonical_skills}
    _nonempty_string(gold_skill_id, "generator gold skill")
    _require(gold_skill_id in canonical_ids, "generator gold skill must be canonical")
    for label, value in (
        ("negative quota", negative_quota),
        ("positive-only quota", positive_only_quota),
    ):
        _require(type(value) is int and value >= 0, f"{label} must be an integer")
    _require(
        negative_quota + positive_only_quota > 0,
        "generator quota must request at least one candidate",
    )
    _require(
        type(round_number) is int and round_number > 0,
        "round number must be a positive integer",
    )
    config = AGENT_CONFIGS["generator"]
    payload = {
        "schema_version": "router-v2-blind-v2-generation-request-v1",
        "role": "generator",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": GENERATOR_SYSTEM_PROMPT,
        "response_schema": deepcopy(GENERATOR_RESPONSE_SCHEMA),
        "input": {
            "canonical_skills": projected_canonical_skills,
            "rules": deepcopy(GENERATOR_RULES),
            "quota": {
                "gold_skill_id": gold_skill_id,
                "negative_quota": negative_quota,
                "positive_only_quota": positive_only_quota,
                "round_number": round_number,
            },
        },
    }
    request = {**payload, "request_sha256": _canonical_contract_json_sha256(payload)}
    return validate_agent_request(request)


def build_reviewer_request(
    candidate: dict[str, Any],
    canonical_skills: list[dict[str, Any]],
    *,
    role: str,
) -> dict[str, Any]:
    _require(
        type(role) is str and role in {"reviewer_a", "reviewer_b"},
        "reviewer role mismatch",
    )
    projected_canonical_skills = _project_canonical_skills(canonical_skills)
    _require(type(candidate) is dict, "candidate must be an object")
    candidate_id = _exact_lowercase_hex(
        candidate.get("candidate_id"), length=24, label="candidate id"
    )
    prompt_text = _nonempty_string(candidate.get("prompt_text"), "prompt text")
    config = AGENT_CONFIGS[role]
    payload = {
        "schema_version": "router-v2-blind-v2-review-request-v1",
        "role": role,
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": REVIEWER_SYSTEM_PROMPT,
        "response_schema": deepcopy(REVIEWER_RESPONSE_SCHEMA),
        "input": {
            "task_id": candidate_id,
            "prompt_text": prompt_text,
            "canonical_skills": projected_canonical_skills,
            "rubric": deepcopy(REVIEW_RUBRIC),
        },
    }
    request = {**payload, "request_sha256": _canonical_contract_json_sha256(payload)}
    return validate_agent_request(request)


def validate_agent_request(request: dict[str, Any]) -> dict[str, Any]:
    request = _exact_object_fields(
        request,
        {
            "schema_version",
            "role",
            "model",
            "reasoning_effort",
            "timeout_seconds",
            "system_prompt",
            "response_schema",
            "input",
            "request_sha256",
        },
        "request",
    )
    _require(
        type(request["request_sha256"]) is str
        and request["request_sha256"] == _request_sha256(request),
        "request hash mismatch",
    )
    role = request["role"]
    _require(
        type(role) is str and role in AGENT_CONFIGS,
        "agent role mismatch",
    )
    config = AGENT_CONFIGS[cast(str, role)]
    _require(request["model"] == config["model"], "request model mismatch")
    _require(
        request["reasoning_effort"] == config["reasoning_effort"],
        "request reasoning effort mismatch",
    )
    _require(
        type(request["timeout_seconds"]) is int
        and request["timeout_seconds"] == config["timeout_seconds"],
        "request timeout mismatch",
    )
    request_input = _exact_object_fields(
        request["input"],
        (
            {"canonical_skills", "rules", "quota"}
            if role == "generator"
            else {"task_id", "prompt_text", "canonical_skills", "rubric"}
        ),
        "generator input" if role == "generator" else "reviewer input",
    )
    canonical_ids = _canonical_skill_ids(request_input["canonical_skills"])
    if role == "generator":
        _require(
            request["schema_version"] == "router-v2-blind-v2-generation-request-v1",
            "generator request schema mismatch",
        )
        _require(
            request["system_prompt"] == GENERATOR_SYSTEM_PROMPT,
            "generator system prompt mismatch",
        )
        _require(
            _canonical_contract_json_equal(
                request["response_schema"], GENERATOR_RESPONSE_SCHEMA
            ),
            "generator response schema mismatch",
        )
        _require(request_input["rules"] == GENERATOR_RULES, "generator rules mismatch")
        quota = _exact_object_fields(
            request_input["quota"],
            {
                "gold_skill_id",
                "negative_quota",
                "positive_only_quota",
                "round_number",
            },
            "generator quota",
        )
        _nonempty_string(quota["gold_skill_id"], "generator gold skill")
        _require(
            quota["gold_skill_id"] in canonical_ids,
            "generator gold skill must be canonical",
        )
        for label in ("negative_quota", "positive_only_quota"):
            _require(
                type(quota[label]) is int and quota[label] >= 0,
                f"generator {label} must be an integer",
            )
        _require(
            quota["negative_quota"] + quota["positive_only_quota"] > 0,
            "generator quota must request at least one candidate",
        )
        _require(
            type(quota["round_number"]) is int and quota["round_number"] > 0,
            "generator round number must be a positive integer",
        )
    else:
        _require(
            request["schema_version"] == "router-v2-blind-v2-review-request-v1",
            "reviewer request schema mismatch",
        )
        _require(
            request["system_prompt"] == REVIEWER_SYSTEM_PROMPT,
            "reviewer system prompt mismatch",
        )
        _require(
            _canonical_contract_json_equal(
                request["response_schema"], REVIEWER_RESPONSE_SCHEMA
            ),
            "reviewer response schema mismatch",
        )
        _require(request_input["rubric"] == REVIEW_RUBRIC, "review rubric mismatch")
        _exact_lowercase_hex(request_input["task_id"], length=24, label="candidate id")
        _nonempty_string(request_input["prompt_text"], "reviewer prompt text")
    return request


def _validate_generator_response(
    response: Any, request: dict[str, Any]
) -> dict[str, Any]:
    response = _exact_object_fields(response, {"candidates"}, "generator response")
    candidates = response["candidates"]
    _require(type(candidates) is list, "generator candidates must be a list")
    quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
    expected_count = quota["negative_quota"] + quota["positive_only_quota"]
    _require(len(candidates) == expected_count, "generator candidate count mismatch")
    canonical_ids = _canonical_skill_ids(
        cast(dict[str, Any], request["input"])["canonical_skills"]
    )
    indexes: list[int] = []
    negative_count = 0
    fields = {
        "candidate_index",
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    for raw_candidate in candidates:
        candidate = _exact_object_fields(raw_candidate, fields, "generator candidate")
        index = candidate["candidate_index"]
        _require(
            type(index) is int and index >= 0,
            "generator candidate index must be an integer",
        )
        indexes.append(cast(int, index))
        _nonempty_string(candidate["prompt_text"], "generator prompt text")
        _nonempty_string(
            candidate["semantic_family_id"], "generator semantic family id"
        )
        gold = candidate["proposed_gold_skill_id"]
        _require(
            type(gold) is str
            and gold in canonical_ids
            and gold == quota["gold_skill_id"],
            "generator proposed gold skill mismatch",
        )
        negative = candidate["proposed_negative_skill_id"]
        _require(
            negative is None or (type(negative) is str and negative in canonical_ids),
            "generator proposed negative skill mismatch",
        )
        _require(negative != gold, "generator negative skill must differ from gold")
        negative_count += negative is not None
        _require(candidate["language"] == "en", "generator language mismatch")
        _nonempty_string(candidate["rationale"], "generator rationale")
    _require(
        set(indexes) == set(range(expected_count))
        and len(indexes) == len(set(indexes)),
        "generator candidate indexes mismatch",
    )
    _require(
        negative_count == quota["negative_quota"],
        "generator negative quota mismatch",
    )
    return response


def _validate_reviewer_response(
    response: Any, request: dict[str, Any]
) -> dict[str, Any]:
    fields = {
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
    response = _exact_object_fields(response, fields, "reviewer response")
    _require(
        type(response["decision"]) is str
        and response["decision"] in AGENT_REVIEW_DECISIONS,
        "reviewer decision mismatch",
    )
    canonical_ids = _canonical_skill_ids(
        cast(dict[str, Any], request["input"])["canonical_skills"]
    )
    gold = response["reviewed_gold_skill_id"]
    _require(
        type(gold) is str and gold in canonical_ids,
        "reviewed gold skill must be canonical",
    )
    negative = response["reviewed_negative_skill_id"]
    _require(
        negative is None or (type(negative) is str and negative in canonical_ids),
        "reviewed negative skill must be canonical or null",
    )
    _require(negative != gold, "reviewed negative skill must differ from gold")
    for field in ("natural", "single_primary_skill", "no_label_leakage"):
        _require(type(response[field]) is bool, f"reviewer {field} must be boolean")
    _require(
        (negative is None and response["negative_confusable"] is None)
        or (negative is not None and type(response["negative_confusable"]) is bool),
        "reviewer negative confusability mismatch",
    )
    decision = cast(str, response["decision"])
    decision_rubric_consistent = {
        "ACCEPT": (
            response["natural"] is True
            and response["single_primary_skill"] is True
            and response["no_label_leakage"] is True
            and (negative is None or response["negative_confusable"] is True)
        ),
        "REJECT_AMBIGUOUS": response["single_primary_skill"] is False,
        "REJECT_NOT_CONFUSABLE": (
            negative is not None and response["negative_confusable"] is False
        ),
        "REJECT_UNNATURAL": response["natural"] is False,
        "REJECT_LABEL_LEAKAGE": response["no_label_leakage"] is False,
    }[decision]
    _require(decision_rubric_consistent, "reviewer decision/rubric mismatch")
    _require(
        type(response["confidence"]) is str
        and response["confidence"] in AGENT_REVIEW_CONFIDENCE,
        "reviewer confidence mismatch",
    )
    _nonempty_string(response["reason"], "reviewer reason")
    return response


def validate_agent_response(
    response: dict[str, Any], *, request: dict[str, Any]
) -> dict[str, Any]:
    request = validate_agent_request(request)
    if request["role"] == "generator":
        return _validate_generator_response(response, request)
    return _validate_reviewer_response(response, request)


def validate_agent_invocation_envelope(
    envelope: dict[str, Any],
    *,
    request: dict[str, Any],
    seen_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    request = validate_agent_request(request)
    _require(type(envelope) is dict, "agent invocation envelope must be an object")
    identity_fields = {"session_id", "thread_id"}.intersection(envelope)
    _require(
        len(identity_fields) == 1,
        "exactly one session/thread id is required",
    )
    expected_fields = {
        "role",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "timeout_seconds",
        "transport_retry_count",
        "request_sha256",
        "response",
        *identity_fields,
    }
    envelope = _exact_object_fields(
        envelope, expected_fields, "agent invocation envelope"
    )
    identity = _nonempty_string(
        envelope[next(iter(identity_fields))], "session/thread id"
    )
    if seen_session_ids is not None:
        _require(type(seen_session_ids) is set, "seen session ids must be a set")
        _require(identity not in seen_session_ids, "session/thread id must be unique")
    role = cast(str, request["role"])
    config = AGENT_CONFIGS[role]
    _require(envelope["role"] == role, "agent invocation role mismatch")
    _require(envelope["fork_context"] is False, "fork context must be false")
    _require(
        type(envelope["history_message_count"]) is int
        and envelope["history_message_count"] == 0,
        "history message count must be integer zero",
    )
    _require(
        type(envelope["imported_memory_count"]) is int
        and envelope["imported_memory_count"] == 0,
        "imported memory count must be integer zero",
    )
    _require(
        envelope["requested_model"] == config["model"],
        "requested model mismatch",
    )
    _require(
        envelope["returned_model"] == config["model"],
        "returned model mismatch",
    )
    _require(
        envelope["reasoning_effort"] == config["reasoning_effort"],
        "reasoning effort mismatch",
    )
    _require(
        type(envelope["timeout_seconds"]) is int
        and envelope["timeout_seconds"] == config["timeout_seconds"],
        "timeout mismatch",
    )
    retry_count = envelope["transport_retry_count"]
    _require(
        type(retry_count) is int and retry_count in {0, 1},
        "transport retry count must be integer zero or one",
    )
    _require(
        envelope["request_sha256"] == request["request_sha256"],
        "request SHA-256 mismatch",
    )
    response = validate_agent_response(envelope["response"], request=request)
    if seen_session_ids is not None:
        seen_session_ids.add(identity)
    return response


def validate_agent_response_envelope(
    envelope: dict[str, Any],
    *,
    request: dict[str, Any],
    seen_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    return validate_agent_invocation_envelope(
        envelope,
        request=request,
        seen_session_ids=seen_session_ids,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _jaccard(left: set[str], right: set[str]) -> Decimal:
    # Task 4.2 freezes two empty sets as full overlap.
    if not left and not right:
        return Decimal("1")
    context = Context(
        prec=50,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    with localcontext(context):
        return Decimal(len(left & right)) / Decimal(len(left | right))


def _token_5grams(value: str) -> set[str]:
    tokens = _normalize(value).split()
    return {
        "\u241f".join(tokens[index : index + 5])
        for index in range(max(0, len(tokens) - 4))
    }


def _character_5grams(value: str) -> set[str]:
    normalized = _normalize(value)
    return {
        normalized[index : index + 5] for index in range(max(0, len(normalized) - 4))
    }


def _canonical_decimal(value: Decimal) -> str:
    _require(type(value) is Decimal and value.is_finite(), "decimal must be finite")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"-0", ""}:
        return "0"
    return rendered


def _validate_deterministic_selection(
    selected: list[dict[str, Any]],
    *,
    selected_ids: set[str],
    selected_prompt_bytes: set[bytes],
    selected_normalized_prompts: set[str],
    selected_families: set[str],
    selected_negative_rows: list[dict[str, Any]],
    canonical_ids: set[str],
) -> None:
    _require_deterministic_selection(
        type(selected) is list and all(type(row) is dict for row in selected),
        "deterministic selection input must be a task list",
    )
    _require_deterministic_selection(
        len(selected) == 128, "deterministic selection must produce 128 tasks"
    )
    _require_deterministic_selection(
        len(selected_negative_rows) == 96,
        "deterministic selection must produce 96 negative-labeled tasks",
    )
    _require_deterministic_selection(
        len(selected_ids)
        == len(selected_prompt_bytes)
        == len(selected_normalized_prompts)
        == len(selected_families)
        == 128,
        "selected task, prompt, normalized prompt, and family values must be unique",
    )
    _require_deterministic_selection(
        all(row["proposed_gold_skill_id"] in canonical_ids for row in selected),
        "selected gold skills must be canonical",
    )
    for skill_id in sorted(canonical_ids):
        negative_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is not None
            for row in selected
        )
        positive_only_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is None
            for row in selected
        )
        _require_deterministic_selection(
            negative_count
            == cast(int, _SELECTION_AUTHORITY["final_negative_per_skill"]),
            "deterministic negative stratum quota mismatch",
        )
        _require_deterministic_selection(
            positive_only_count
            == cast(int, _SELECTION_AUTHORITY["final_positive_only_per_skill"]),
            "deterministic positive-only stratum quota mismatch",
        )


def _semantic_decimal(
    semantic_similarity: SemanticSimilarity, left: str, right: str
) -> Decimal:
    raw = semantic_similarity(left, right)
    _require(
        type(raw) in {int, float, Decimal} and type(raw) is not bool,
        "semantic similarity must be numeric",
    )
    value = Decimal(str(raw))
    _require(value.is_finite(), "semantic similarity must be finite")
    _require(
        Decimal("-1") <= value <= Decimal("1"),
        "semantic similarity must be between -1 and 1",
    )
    return value


def _protected_authority_summary(
    protected_prompts: dict[str, tuple[str, ...]],
    protected_family_ids: dict[str, frozenset[str]],
) -> dict[str, dict[str, int | str]]:
    summary: dict[str, dict[str, int | str]] = {}
    for scope in CONTAMINATION_SCOPES:
        prompt_bytes = sorted(
            prompt.encode("utf-8", errors="strict")
            for prompt in protected_prompts[scope]
        )
        prompt_digest = hashlib.sha256()
        for value in prompt_bytes:
            prompt_digest.update(len(value).to_bytes(8, byteorder="big"))
            prompt_digest.update(value)
        normalized_prompts = sorted(
            _normalize(prompt) for prompt in protected_prompts[scope]
        )
        family_ids = sorted(protected_family_ids[scope])
        summary[scope] = {
            "prompt_count": len(prompt_bytes),
            "prompt_bytes_sha256": prompt_digest.hexdigest(),
            "normalized_prompt_list_sha256": canonical_sha256(normalized_prompts),
            "family_count": len(family_ids),
            "family_ids_sha256": canonical_sha256(family_ids),
        }
    return summary


def _validated_semantic_model_authority(authority: Any) -> dict[str, Any]:
    document = _exact_object_fields(
        authority,
        {"materialized_model_files", "materialized_model_files_sha256"},
        "semantic model authority",
    )
    raw_files = document["materialized_model_files"]
    _require(
        type(raw_files) is list and bool(raw_files),
        "semantic model files must be a non-empty list",
    )
    files: list[dict[str, str]] = []
    paths: list[str] = []
    for raw_file in raw_files:
        row = _exact_object_fields(raw_file, {"path", "sha256"}, "semantic model file")
        path = _nonempty_string(row["path"], "semantic model file path")
        _require(
            path == path.strip()
            and path == unicodedata.normalize("NFC", path)
            and not path.startswith("/")
            and "\0" not in path
            and "\\" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            "semantic model file path must be normalized relative POSIX",
        )
        path.encode("utf-8", errors="strict")
        sha256 = _exact_lowercase_hex(
            row["sha256"], length=64, label="semantic model file SHA-256"
        )
        paths.append(path)
        files.append({"path": path, "sha256": sha256})
    _require(
        len(paths) == len(set(paths)),
        "semantic model file paths must be unique",
    )
    _require(
        paths == sorted(paths, key=lambda value: value.encode("utf-8")),
        "semantic model files must be sorted by UTF-8 path",
    )
    aggregate = _exact_lowercase_hex(
        document["materialized_model_files_sha256"],
        length=64,
        label="semantic model file aggregate SHA-256",
    )
    _require(
        aggregate == canonical_sha256(files),
        "semantic model file aggregate hash mismatch",
    )
    return {
        "materialized_model_files": files,
        "materialized_model_files_sha256": aggregate,
    }


def _scan_contamination(
    candidates: list[dict[str, Any]],
    *,
    protected_prompts: dict[str, list[str]],
    protected_family_ids: dict[str, set[str]],
    semantic_similarity: SemanticSimilarity,
    semantic_model_authority: dict[str, Any],
) -> dict[str, Any]:
    """Build deterministic non-voting contamination evidence from prompt text."""

    _require(type(candidates) is list, "scan candidates must be a list")
    _require(
        type(protected_prompts) is dict
        and set(protected_prompts) == set(CONTAMINATION_SCOPES),
        "protected prompt scopes mismatch",
    )
    _require(
        type(protected_family_ids) is dict
        and set(protected_family_ids) == set(CONTAMINATION_SCOPES),
        "protected family scopes mismatch",
    )
    _require(callable(semantic_similarity), "semantic similarity must be callable")
    model_authority = _validated_semantic_model_authority(semantic_model_authority)

    for scope in CONTAMINATION_SCOPES:
        prompts = protected_prompts[scope]
        family_ids = protected_family_ids[scope]
        _require(
            type(prompts) is list and all(type(prompt) is str for prompt in prompts),
            f"{scope} protected prompts must be a string list",
        )
        _require(
            type(family_ids) is set
            and all(type(family_id) is str for family_id in family_ids),
            f"{scope} protected family ids must be a string set",
        )

    protected_prompt_snapshot = {
        scope: tuple(protected_prompts[scope]) for scope in CONTAMINATION_SCOPES
    }
    protected_family_snapshot = {
        scope: frozenset(protected_family_ids[scope]) for scope in CONTAMINATION_SCOPES
    }
    prompt_references: dict[str, list[dict[str, Any]]] = {}
    for scope in CONTAMINATION_SCOPES:
        prompt_references[scope] = [
            {
                "prompt_text": prompt,
                "prompt_bytes": prompt.encode("utf-8", errors="strict"),
                "prompt_sha256": _sha256_bytes(prompt.encode("utf-8", errors="strict")),
                "normalized": _normalize(prompt),
                "token_5grams": _token_5grams(prompt),
                "character_5grams": _character_5grams(prompt),
            }
            for prompt in sorted(
                protected_prompt_snapshot[scope],
                key=lambda value: value.encode("utf-8"),
            )
        ]

    protected_authority = _protected_authority_summary(
        protected_prompt_snapshot, protected_family_snapshot
    )

    projected: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for raw_candidate in candidates:
        _require(type(raw_candidate) is dict, "scan candidate must be an object")
        candidate_id = _exact_lowercase_hex(
            raw_candidate.get("candidate_id"), length=24, label="candidate id"
        )
        _require(candidate_id not in seen_candidate_ids, "candidate ids must be unique")
        seen_candidate_ids.add(candidate_id)
        generation_round = raw_candidate.get("generation_round")
        _require(
            type(generation_round) is int and generation_round > 0,
            "generation round must be a positive integer",
        )
        prompt_text = _nonempty_string(
            raw_candidate.get("prompt_text"), "candidate prompt"
        )
        prompt_bytes = prompt_text.encode("utf-8", errors="strict")
        prompt_hash = _exact_lowercase_hex(
            raw_candidate.get("prompt_text_sha256"),
            length=64,
            label="candidate prompt hash",
        )
        _require(
            prompt_hash == _sha256_bytes(prompt_bytes),
            "candidate prompt hash mismatch",
        )
        family_id = _nonempty_string(
            raw_candidate.get("semantic_family_id"), "semantic family id"
        )
        projected.append(
            {
                "candidate_id": candidate_id,
                "generation_round": generation_round,
                "prompt_text": prompt_text,
                "prompt_bytes": prompt_bytes,
                "prompt_text_sha256": prompt_hash,
                "prompt_sha256": prompt_hash,
                "normalized": _normalize(prompt_text),
                "token_5grams": _token_5grams(prompt_text),
                "character_5grams": _character_5grams(prompt_text),
                "semantic_family_id": family_id,
            }
        )

    scanner_config = {
        "required_semantic_model_id": SEMANTIC_MODEL_ID,
        "required_semantic_model_revision": SEMANTIC_MODEL_REVISION,
        **model_authority,
        "semantic_scorer_runtime_verified": False,
        "semantic_scorer_receipt_sha256": None,
        "token_5gram_jaccard_reject_at_or_above": str(TOKEN_5GRAM_JACCARD_MAX),
        "character_5gram_jaccard_reject_at_or_above": str(CHARACTER_5GRAM_JACCARD_MAX),
        "semantic_cosine_reject_at_or_above": str(SEMANTIC_COSINE_MAX),
        "normalization": "NFKC-casefold-collapse-whitespace",
        "selection_seed": _SELECTION_AUTHORITY["selection_seed"],
        "protected_authority": protected_authority,
        "protected_authority_sha256": canonical_sha256(protected_authority),
    }

    def prompt_events(
        candidate: dict[str, Any], reference: dict[str, Any], scope: str
    ) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        reference_hash = cast(str, reference["prompt_sha256"])
        if candidate["prompt_bytes"] == reference["prompt_bytes"]:
            events.append(
                {
                    "code": f"exact_prompt_bytes:{scope}",
                    "reference_sha256": reference_hash,
                }
            )
        if candidate["normalized"] == reference["normalized"]:
            events.append(
                {
                    "code": f"normalized_prompt:{scope}",
                    "reference_sha256": reference_hash,
                }
            )
        token_jaccard = _jaccard(
            cast(set[str], candidate["token_5grams"]),
            cast(set[str], reference["token_5grams"]),
        )
        if token_jaccard >= TOKEN_5GRAM_JACCARD_MAX:
            events.append(
                {
                    "code": f"token_5gram_jaccard:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(token_jaccard),
                }
            )
        character_jaccard = _jaccard(
            cast(set[str], candidate["character_5grams"]),
            cast(set[str], reference["character_5grams"]),
        )
        if character_jaccard >= CHARACTER_5GRAM_JACCARD_MAX:
            events.append(
                {
                    "code": f"character_5gram_jaccard:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(character_jaccard),
                }
            )
        semantic_cosine = _semantic_decimal(
            semantic_similarity,
            cast(str, candidate["prompt_text"]),
            cast(str, reference["prompt_text"]),
        )
        if semantic_cosine >= SEMANTIC_COSINE_MAX:
            events.append(
                {
                    "code": f"semantic_cosine:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(semantic_cosine),
                }
            )
        return events

    events_by_id: dict[str, list[dict[str, str]]] = {
        cast(str, candidate["candidate_id"]): [] for candidate in projected
    }
    earlier_candidates: list[dict[str, Any]] = []
    for candidate in sorted(
        projected,
        key=lambda row: (
            cast(int, row["generation_round"]),
            selection_key(cast(str, row["candidate_id"])),
        ),
    ):
        candidate_id = cast(str, candidate["candidate_id"])
        events = events_by_id[candidate_id]
        for scope in CONTAMINATION_SCOPES:
            if candidate["semantic_family_id"] in protected_family_snapshot[scope]:
                family_hash = _sha256_bytes(
                    cast(str, candidate["semantic_family_id"]).encode("utf-8")
                )
                events.append(
                    {
                        "code": f"protected_family:{scope}",
                        "reference_sha256": family_hash,
                    }
                )
            for reference in prompt_references[scope]:
                events.extend(prompt_events(candidate, reference, scope))
        for winner in earlier_candidates:
            pair_events = prompt_events(candidate, winner, "current_candidate")
            if candidate["semantic_family_id"] == winner["semantic_family_id"]:
                pair_events.append(
                    {
                        "code": "protected_family:current_candidate",
                        "reference_sha256": _sha256_bytes(
                            cast(str, winner["semantic_family_id"]).encode("utf-8")
                        ),
                    }
                )
            if pair_events:
                winner_id = cast(str, winner["candidate_id"])
                events.extend(
                    {
                        **event,
                        "code": f"current_candidate:{winner_id}:{event['code']}",
                    }
                    for event in pair_events
                )
                break
        earlier_candidates.append(candidate)

    rows = []
    for candidate in projected:
        candidate_id = cast(str, candidate["candidate_id"])
        events = events_by_id[candidate_id]
        rejection_codes = sorted({event["code"] for event in events})
        decision = "REJECT" if rejection_codes else "PASS"
        evidence = {
            "candidate_id": candidate_id,
            "generation_round": candidate["generation_round"],
            "prompt_text_sha256": candidate["prompt_text_sha256"],
            "semantic_family_sha256": _sha256_bytes(
                cast(str, candidate["semantic_family_id"]).encode("utf-8")
            ),
            "scanner_config": scanner_config,
            "events": events,
        }
        rows.append(
            {
                "candidate_id": candidate_id,
                "scanner_decision": decision,
                "rejection_codes": rejection_codes,
                "evidence_sha256": canonical_sha256(evidence),
            }
        )
    return {
        "rows": rows,
        "clean_candidate_ids": [
            cast(str, candidate["candidate_id"])
            for candidate in projected
            if not events_by_id[cast(str, candidate["candidate_id"])]
        ],
        "scanner_config": scanner_config,
    }


def _json_no_duplicate_keys(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in values:
            if key in output:
                raise ValueError(f"{label} contains duplicate key: {key}")
            output[key] = value
        return output

    try:
        decoded = payload.decode("utf-8", errors="strict")
        value = json.loads(decoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    _require(type(value) is dict, f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonl_no_duplicate_keys(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(payload.splitlines(), start=1):
        if line.strip():
            rows.append(_json_no_duplicate_keys(line, f"{label} line {index}"))
    return rows


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        result.returncode == 0,
        f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
    )
    return result.stdout.strip()


def validate_commit_a_repository(
    repository_root: Path | str, preregistration: dict[str, Any]
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit A worktree must be clean",
    )
    head = _git(repository, "rev-parse", "HEAD")
    parent = _git(repository, "rev-parse", "HEAD^")
    origin_main = _git(repository, "rev-parse", "origin/main")
    expected_parent = preregistration.get("preregistration_parent_git_commit")
    _require(
        parent == expected_parent and origin_main == expected_parent,
        "Commit A must be based directly on the preregistered origin/main",
    )
    _require(
        _git(repository, "rev-list", "--count", f"{parent}..{head}") == "1",
        "Commit A must be exactly one commit above origin/main",
    )
    return {"commit_a": head, "parent": parent, "origin_main": origin_main}


def validate_commit_b_repository(
    repository_root: Path | str, *, commit_a: str
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit B worktree must be clean",
    )
    head = _git(repository, "rev-parse", "HEAD")
    head_parent = _git(repository, "rev-parse", "HEAD^")
    commit_a_parent = _git(repository, "rev-parse", f"{commit_a}^")
    origin_main = _git(repository, "rev-parse", "origin/main")
    _require(
        commit_a_parent == PREREGISTRATION_PARENT_COMMIT
        and origin_main == PREREGISTRATION_PARENT_COMMIT,
        "Commit B lineage no longer matches preregistered origin/main",
    )
    _require(head != commit_a, "Commit B must differ from Commit A")
    _require(head_parent == commit_a, "Commit B must be a direct child of Commit A")
    _require(
        _git(repository, "rev-list", "--count", f"{commit_a}..{head}") == "1",
        "Commit B must be exactly one commit above Commit A",
    )
    changed = set(
        _git(repository, "diff", "--name-only", f"{commit_a}..{head}").splitlines()
    )
    expected = {
        (DATASET_FREEZE_RELATIVE / filename).as_posix()
        for filename in DATASET_FREEZE_FILENAMES
    }
    _require(changed == expected, "Commit B may contain only frozen blind-v2 data")
    return {
        "commit_a": commit_a,
        "commit_b": head,
        "origin_main": origin_main,
        "changed_files": sorted(changed),
    }


def _read_csv(
    path: Path, required_fields: tuple[str, ...]
) -> tuple[bytes, list[dict[str, str]]]:
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} must be UTF-8") from exc
    reader = csv.DictReader(text.splitlines())
    fields = reader.fieldnames
    if fields is None:
        raise ValueError(f"{path.name} is missing a header")
    _require(len(fields) == len(set(fields)), f"{path.name} contains duplicate keys")
    _require(
        set(required_fields).issubset(fields),
        f"{path.name} schema is missing required fields",
    )
    rows = [dict(row) for row in reader]
    return payload, rows


def _outside_repository(root: Path, repository_root: Path) -> None:
    resolved = root.resolve(strict=True)
    repository = repository_root.resolve(strict=False)
    _require(resolved.is_dir(), "agent pack root must be a directory")
    _require(
        not resolved.is_relative_to(repository),
        "agent pack root must stay outside the repository",
    )


def _required_agent_pack_file(path: Path, repository_root: Path) -> Path:
    _require(path.exists(), f"missing required agent pack file: {path.name}")
    resolved = path.resolve(strict=True)
    repository = repository_root.resolve(strict=False)
    _require(
        not resolved.is_relative_to(repository),
        f"required agent pack file must stay outside the repository: {path.name}",
    )
    _require(
        not path.is_symlink() and path.is_file() and resolved.is_file(),
        f"required agent pack path must be a regular file: {path.name}",
    )
    return resolved


def _agent_pack_protocol_invalid(
    *,
    failure_stage: str,
    failure_reason: str,
    first_read_timestamp: str,
    source_file_sha256: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "router-v2-blind-v2-agent-pack-validation-v1",
        "status": "INVALID",
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "research_conclusion": "AGENT_BLIND_V2_PROTOCOL_INVALID",
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
        "first_read_timestamp": first_read_timestamp,
        "source_file_sha256": source_file_sha256,
        "model_scores_observed": False,
        "tasks": [],
    }


def _pack_invocation_identities(invocations: Any) -> list[str]:
    if type(invocations) is not list:
        return []
    identities: list[str] = []
    for invocation in invocations:
        if type(invocation) is not dict:
            continue
        envelope = invocation.get("envelope")
        identity_source = envelope if type(envelope) is dict else invocation
        fields = {"session_id", "thread_id"}.intersection(identity_source)
        if len(fields) != 1:
            continue
        identity = identity_source[next(iter(fields))]
        if type(identity) is str and identity.strip():
            identities.append(identity)
    return identities


def _sanitized_agent_run_record(
    *,
    role: str,
    candidate_id: str,
    request: dict[str, Any],
    response: dict[str, Any] | None,
    invocations: Any,
    retry_count: int,
) -> dict[str, Any]:
    identities = _pack_invocation_identities(invocations)
    config = AGENT_CONFIGS[role]
    return {
        "candidate_id": candidate_id,
        "request_sha256": request["request_sha256"],
        "response_sha256": canonical_sha256(response) if response is not None else None,
        "requested_model": config["model"],
        "returned_model": config["model"] if response is not None else None,
        "reasoning_effort": config["reasoning_effort"],
        "session_or_thread_ids": identities,
        "transport_retry_count": retry_count,
    }


def _transport_retry_record(
    run_record: dict[str, Any], *, role: str
) -> dict[str, Any] | None:
    if run_record["transport_retry_count"] == 0:
        return None
    identities = cast(list[str], run_record["session_or_thread_ids"])
    _require(len(identities) == 2, "transport retry must bind two sessions")
    return {
        "role": role,
        "candidate_id": run_record["candidate_id"],
        "request_sha256": run_record["request_sha256"],
        "response_sha256": run_record["response_sha256"],
        "failed_session_or_thread_id": identities[0],
        "retry_session_or_thread_id": identities[1],
        "failed_attempt_ordinal": 1,
        "retry_attempt_ordinal": 2,
        "retry_count": 1,
    }


def _agent_role_run_evidence(
    role: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    config = AGENT_CONFIGS[role]
    prompt = GENERATOR_SYSTEM_PROMPT if role == "generator" else REVIEWER_SYSTEM_PROMPT
    response_schema = (
        GENERATOR_RESPONSE_SCHEMA if role == "generator" else REVIEWER_RESPONSE_SCHEMA
    )
    return {
        "config": deepcopy(config),
        "requested_models": [config["model"]],
        "returned_models": sorted(
            {
                cast(str, record["returned_model"])
                for record in records
                if record["returned_model"] is not None
            }
        ),
        "reasoning_effort": config["reasoning_effort"],
        "system_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "response_schema_sha256": canonical_sha256(response_schema),
        "request_count": len(records),
        "invocation_count": sum(
            len(cast(list[str], record["session_or_thread_ids"])) for record in records
        ),
        "session_or_thread_ids": [
            identity
            for record in records
            for identity in cast(list[str], record["session_or_thread_ids"])
        ],
        "request_hashes_sha256": canonical_sha256(
            [record["request_sha256"] for record in records]
        ),
        "response_hashes_sha256": canonical_sha256(
            [
                record["response_sha256"]
                for record in records
                if record["response_sha256"] is not None
            ]
        ),
        "run_sha256": canonical_sha256(records),
    }


_AGENT_ROLE_LEDGER_PATHS = {
    "generator": "blind-v2-generation.jsonl",
    "reviewer_a": "blind-v2-review-a.jsonl",
    "reviewer_b": "blind-v2-review-b.jsonl",
}


def _agent_run_identity_authority(
    records_by_role: dict[str, list[dict[str, Any]]],
    metadata_roles: dict[str, Any],
    source_file_sha256: dict[str, Any],
) -> dict[str, Any]:
    roles: dict[str, dict[str, Any]] = {}
    all_sessions: list[str] = []
    for role, config in AGENT_CONFIGS.items():
        records = records_by_role[role]
        metadata = _exact_object_fields(
            metadata_roles[role],
            {
                "config",
                "request_count",
                "invocation_count",
                "session_or_thread_ids",
                "fork_context",
                "history_message_count",
                "imported_memory_count",
            },
            f"{role} metadata",
        )
        candidate_ids = [cast(str, record["candidate_id"]) for record in records]
        sessions = [
            identity
            for record in records
            for identity in cast(list[str], record["session_or_thread_ids"])
        ]
        _require(metadata["config"] == config, f"{role} metadata config mismatch")
        _require(
            metadata["request_count"] == len(records),
            f"{role} metadata request count mismatch",
        )
        _require(
            metadata["invocation_count"] == len(sessions),
            f"{role} metadata invocation count mismatch",
        )
        _require(
            metadata["session_or_thread_ids"] == sessions,
            f"{role} metadata session binding mismatch",
        )
        _require(
            len(candidate_ids) == len(set(candidate_ids)),
            f"{role} candidate identities must be unique",
        )
        all_sessions.extend(sessions)
        ledger_path = _AGENT_ROLE_LEDGER_PATHS[role]
        ledger_hash = _exact_lowercase_hex(
            source_file_sha256[ledger_path],
            length=64,
            label=f"{role} ledger file SHA-256",
        )
        roles[role] = {
            "ledger_path": ledger_path,
            "ledger_file_sha256": ledger_hash,
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": canonical_sha256(candidate_ids),
            "request_count": len(records),
            "invocation_count": len(sessions),
            "session_or_thread_ids": sessions,
            "session_or_thread_ids_sha256": canonical_sha256(sessions),
        }
    _require(
        len(all_sessions) == len(set(all_sessions)),
        "Agent run sessions must be globally unique",
    )
    _require(
        {record["candidate_id"] for record in records_by_role["reviewer_a"]}
        == {record["candidate_id"] for record in records_by_role["reviewer_b"]},
        "reviewer candidate identity sets mismatch",
    )
    _require(
        {record["candidate_id"] for record in records_by_role["reviewer_a"]}
        <= {record["candidate_id"] for record in records_by_role["generator"]},
        "reviewer candidate identities must come from generation",
    )
    return {"roles": roles, "authority_sha256": canonical_sha256(roles)}


class _AgentPackProtocolViolation(Exception):
    pass


_PACK_PROTOCOL_FIELDS = frozenset(
    {
        "role",
        "session_id",
        "thread_id",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "timeout_seconds",
        "transport_retry_count",
        "request_sha256",
    }
)


def _pack_protocol_require(condition: bool, message: str) -> None:
    if not condition:
        raise _AgentPackProtocolViolation(message)


def _validate_pack_protocol_fields(
    value: dict[str, Any],
    *,
    request: dict[str, Any],
    require_returned_model: bool,
    require_transport_retry_count: bool,
    non_protocol_fields: set[str],
) -> set[str]:
    identity_fields = {"session_id", "thread_id"}.intersection(value)
    _pack_protocol_require(
        len(identity_fields) == 1,
        "exactly one session/thread id is required",
    )
    required_fields = {
        "role",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "reasoning_effort",
        "timeout_seconds",
        "request_sha256",
        *identity_fields,
    }
    if require_returned_model:
        required_fields.add("returned_model")
    if require_transport_retry_count:
        required_fields.add("transport_retry_count")
    _pack_protocol_require(
        set(value) == required_fields | non_protocol_fields,
        "agent invocation protocol fields mismatch",
    )
    identity = value[next(iter(identity_fields))]
    _pack_protocol_require(
        type(identity) is str and bool(identity.strip()),
        "session/thread id must be non-empty",
    )
    role = cast(str, request["role"])
    config = AGENT_CONFIGS[role]
    _pack_protocol_require(value["role"] == role, "agent invocation role mismatch")
    _pack_protocol_require(value["fork_context"] is False, "fork context must be false")
    _pack_protocol_require(
        type(value["history_message_count"]) is int
        and value["history_message_count"] == 0,
        "history message count must be integer zero",
    )
    _pack_protocol_require(
        type(value["imported_memory_count"]) is int
        and value["imported_memory_count"] == 0,
        "imported memory count must be integer zero",
    )
    _pack_protocol_require(
        value["requested_model"] == config["model"],
        "requested model mismatch",
    )
    if "returned_model" in value:
        _pack_protocol_require(
            value["returned_model"] == config["model"],
            "returned model mismatch",
        )
    _pack_protocol_require(
        value["reasoning_effort"] == config["reasoning_effort"],
        "reasoning effort mismatch",
    )
    _pack_protocol_require(
        type(value["timeout_seconds"]) is int
        and value["timeout_seconds"] == config["timeout_seconds"],
        "timeout mismatch",
    )
    _pack_protocol_require(
        value["request_sha256"] == request["request_sha256"],
        "request SHA-256 mismatch",
    )
    if "transport_retry_count" in value:
        _pack_protocol_require(
            type(value["transport_retry_count"]) is int
            and value["transport_retry_count"] in {0, 1},
            "transport retry count must be integer zero or one",
        )
    return identity_fields


def _audit_pack_invocation_protocol(
    invocation: dict[str, Any],
    *,
    request: dict[str, Any],
) -> None:
    top_level_protocol_fields = _PACK_PROTOCOL_FIELDS.intersection(invocation)
    if "envelope" in invocation and not top_level_protocol_fields:
        _pack_protocol_require(
            set(invocation)
            == {"transport_failure", "response_bytes_present", "envelope"},
            "successful invocation fields mismatch",
        )
        _pack_protocol_require(
            invocation["transport_failure"] is False,
            "successful invocation transport_failure must be false",
        )
        _pack_protocol_require(
            invocation["response_bytes_present"] is True,
            "successful invocation response_bytes_present must be true",
        )
        envelope = invocation["envelope"]
        _pack_protocol_require(
            type(envelope) is dict,
            "successful invocation envelope must be an object",
        )
        _validate_pack_protocol_fields(
            cast(dict[str, Any], envelope),
            request=request,
            require_returned_model=True,
            require_transport_retry_count=True,
            non_protocol_fields={"response"},
        )
        return
    if top_level_protocol_fields:
        _validate_pack_protocol_fields(
            invocation,
            request=request,
            require_returned_model=False,
            require_transport_retry_count=False,
            non_protocol_fields={"transport_failure", "response_bytes_present"},
        )
        _pack_protocol_require(
            invocation["transport_failure"] is True,
            "transport failure record transport_failure must be true",
        )
        _pack_protocol_require(
            invocation["response_bytes_present"] is False,
            "transport failure record response_bytes_present must be false",
        )
        return
    raise _AgentPackProtocolViolation("invocation record schema mismatch")


def _validate_pack_invocations(
    invocations: Any, *, request: dict[str, Any]
) -> tuple[dict[str, Any] | None, int]:
    if type(invocations) is not list:
        raise _AgentPackProtocolViolation("invocations must be a list")
    try:
        for invocation in invocations:
            _pack_protocol_require(
                type(invocation) is dict,
                "invocation record must be an object",
            )
            _audit_pack_invocation_protocol(
                cast(dict[str, Any], invocation),
                request=request,
            )
        if len(invocations) not in {1, 2}:
            return None, 0
        first = cast(dict[str, Any], invocations[0])
        success = cast(dict[str, Any], invocations[-1])
        if "envelope" not in success:
            return None, 0
        if len(invocations) == 2 and "envelope" in first:
            return None, 0
        retry_count = len(invocations) - 1
        envelope = cast(dict[str, Any], success["envelope"])
        _pack_protocol_require(
            envelope["transport_retry_count"] == retry_count,
            "transport retry count does not match allowed invocation combination",
        )
        try:
            response = validate_agent_invocation_envelope(envelope, request=request)
        except (KeyError, TypeError, ValueError):
            return None, retry_count
        return response, retry_count
    except _AgentPackProtocolViolation:
        raise
    except (KeyError, TypeError, ValueError):
        return None, 0


def validate_agent_pack(
    root: Path | str,
    *,
    repository_root: Path | str,
    canonical_skills: list[dict[str, Any]],
    train_prompts: list[str],
    pilot_prompts: list[str],
    phase16_prompts: list[str],
    train_family_ids: set[str],
    pilot_family_ids: set[str],
    phase16_family_ids: set[str],
    prior_candidate_prompts: list[str],
    prior_candidate_family_ids: set[str],
    first_read_timestamp: str,
    semantic_similarity: SemanticSimilarity,
    semantic_model_authority: dict[str, Any],
) -> dict[str, Any]:
    """Validate sealed Agent ledgers without loading Arm A/C or scoring routes."""

    projected_skills = _project_canonical_skills(canonical_skills)
    canonical_ids = _canonical_skill_ids(projected_skills)
    for label, prompts in (
        ("train prompts", train_prompts),
        ("pilot prompts", pilot_prompts),
        ("Phase 16 prompts", phase16_prompts),
        ("prior candidate prompts", prior_candidate_prompts),
    ):
        _require(
            type(prompts) is list and all(type(prompt) is str for prompt in prompts),
            f"{label} must be a string list",
        )
    for label, family_ids in (
        ("train family ids", train_family_ids),
        ("pilot family ids", pilot_family_ids),
        ("Phase 16 family ids", phase16_family_ids),
        ("prior candidate family ids", prior_candidate_family_ids),
    ):
        _require(
            type(family_ids) is set
            and all(type(family_id) is str for family_id in family_ids),
            f"{label} must be a string set",
        )
    _nonempty_string(first_read_timestamp, "first read timestamp")
    _require(callable(semantic_similarity), "semantic similarity must be callable")

    pack_root = Path(root)
    repository_path = Path(repository_root)
    _outside_repository(pack_root, repository_path)
    required_paths = {
        filename: _required_agent_pack_file(
            pack_root / filename,
            repository_path,
        )
        for filename in REQUIRED_AGENT_PACK_FILES
    }

    source_hashes: dict[str, str] = {}
    try:
        payloads = {
            filename: required_paths[filename].read_bytes()
            for filename in REQUIRED_AGENT_PACK_FILES
        }
        source_hashes = {
            filename: _sha256_bytes(payload) for filename, payload in payloads.items()
        }
        generation_rows = _jsonl_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[0]], REQUIRED_AGENT_PACK_FILES[0]
        )
        review_rows_by_role = {
            "reviewer_a": _jsonl_no_duplicate_keys(
                payloads[REQUIRED_AGENT_PACK_FILES[1]],
                REQUIRED_AGENT_PACK_FILES[1],
            ),
            "reviewer_b": _jsonl_no_duplicate_keys(
                payloads[REQUIRED_AGENT_PACK_FILES[2]],
                REQUIRED_AGENT_PACK_FILES[2],
            ),
        }
        contamination_rows = _jsonl_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[3]],
            REQUIRED_AGENT_PACK_FILES[3],
        )
        metadata = _json_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[4]],
            REQUIRED_AGENT_PACK_FILES[4],
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="ledger_structure",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        metadata = _exact_object_fields(
            metadata,
            {
                "schema_version",
                "first_read_timestamp",
                "roles",
                "review_schedule_sha256",
                "selection_authority",
                "source_file_sha256",
            },
            "agent run metadata",
        )
        _require(
            metadata["schema_version"] == "router-v2-blind-v2-agent-run-metadata-v1",
            "agent run metadata schema mismatch",
        )
        _require(
            metadata["first_read_timestamp"] == first_read_timestamp,
            "first read timestamp mismatch",
        )
        metadata_source_hashes = _exact_object_fields(
            metadata["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES[:-1]),
            "metadata source hashes",
        )
        for filename in REQUIRED_AGENT_PACK_FILES[:-1]:
            _exact_lowercase_hex(
                metadata_source_hashes[filename],
                length=64,
                label=f"{filename} source hash",
            )
            _require(
                metadata_source_hashes[filename] == source_hashes[filename],
                f"{filename} source hash mismatch",
            )
        metadata_roles = _exact_object_fields(
            metadata["roles"], set(AGENT_CONFIGS), "metadata roles"
        )
        role_fields = {
            "config",
            "request_count",
            "invocation_count",
            "session_or_thread_ids",
            "fork_context",
            "history_message_count",
            "imported_memory_count",
        }
        for role, config in AGENT_CONFIGS.items():
            role_metadata = _exact_object_fields(
                metadata_roles[role], role_fields, f"{role} metadata"
            )
            role_config = _exact_object_fields(
                role_metadata["config"],
                {"model", "reasoning_effort", "timeout_seconds"},
                f"{role} config",
            )
            for field in ("model", "reasoning_effort"):
                _nonempty_string(role_config[field], f"{role} config {field}")
                _require(
                    role_config[field] == config[field],
                    f"{role} config {field} mismatch",
                )
            _require(
                type(role_config["timeout_seconds"]) is int
                and role_config["timeout_seconds"] == config["timeout_seconds"],
                f"{role} config timeout_seconds mismatch",
            )
            for field in ("request_count", "invocation_count"):
                _require(
                    type(role_metadata[field]) is int and role_metadata[field] >= 0,
                    f"{role} {field} must be a non-negative integer",
                )
            session_ids = role_metadata["session_or_thread_ids"]
            _require(
                type(session_ids) is list
                and all(type(value) is str and value.strip() for value in session_ids)
                and len(session_ids) == len(set(session_ids)),
                f"{role} session/thread metadata mismatch",
            )
            _require(role_metadata["fork_context"] is False, "fork context mismatch")
            _require(
                type(role_metadata["history_message_count"]) is int
                and role_metadata["history_message_count"] == 0,
                "history metadata mismatch",
            )
            _require(
                type(role_metadata["imported_memory_count"]) is int
                and role_metadata["imported_memory_count"] == 0,
                "memory metadata mismatch",
            )
        metadata_schedules = _exact_object_fields(
            metadata["review_schedule_sha256"],
            {"reviewer_a", "reviewer_b"},
            "review schedules",
        )
        for role in ("reviewer_a", "reviewer_b"):
            _exact_lowercase_hex(
                metadata_schedules[role], length=64, label=f"{role} schedule hash"
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="agent_run_metadata",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        selection_authority_document = _selection_authority_document()
        metadata_selection_authority = _exact_object_fields(
            metadata["selection_authority"],
            set(selection_authority_document),
            "selection authority",
        )
        _require(
            _canonical_contract_json_equal(
                metadata_selection_authority, selection_authority_document
            ),
            "selection authority drift",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="selection_authority",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    generation_fields = {
        "candidate_id",
        "generation_round",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
        "request",
        "invocations",
    }
    candidate_fields = generation_fields - {"request", "invocations"}
    candidates: dict[str, dict[str, Any]] = {}
    generation_responses: dict[str, dict[str, Any] | None] = {}
    generation_request_quota_counts: Counter[tuple[int, str, str]] = Counter()
    actual_sessions: dict[str, list[str]] = {
        "generator": [],
        "reviewer_a": [],
        "reviewer_b": [],
    }
    actual_invocation_counts = dict.fromkeys(actual_sessions, 0)
    valid_transport_retry_count = 0
    sanitized_run_records: dict[str, list[dict[str, Any]]] = {
        "generator": [],
        "reviewer_a": [],
        "reviewer_b": [],
    }
    retry_records: list[dict[str, Any]] = []
    try:
        for raw_row in generation_rows:
            row = _exact_object_fields(raw_row, generation_fields, "generation row")
            candidate_id = _exact_lowercase_hex(
                row["candidate_id"], length=24, label="candidate id"
            )
            _require(candidate_id not in candidates, "candidate ids must be unique")
            _require(
                type(row["generation_round"]) is int and row["generation_round"] > 0,
                "generation round must be a positive integer",
            )
            prompt_text = _nonempty_string(row["prompt_text"], "candidate prompt")
            prompt_hash = _exact_lowercase_hex(
                row["prompt_text_sha256"], length=64, label="candidate prompt hash"
            )
            _require(
                prompt_hash == _sha256_bytes(prompt_text.encode("utf-8")),
                "candidate prompt hash mismatch",
            )
            _nonempty_string(row["semantic_family_id"], "semantic family id")
            gold = row["proposed_gold_skill_id"]
            negative = row["proposed_negative_skill_id"]
            _require(gold in canonical_ids, "generator gold must be canonical")
            _require(
                negative is None or negative in canonical_ids,
                "generator negative must be canonical or null",
            )
            _require(negative != gold, "generator negative must differ from gold")
            _require(row["language"] == "en", "generator language mismatch")
            _nonempty_string(row["rationale"], "generator rationale")
            candidate = {field: deepcopy(row[field]) for field in candidate_fields}
            candidates[candidate_id] = candidate

            request = validate_agent_request(row["request"])
            _require(request["role"] == "generator", "generation role mismatch")
            quota = cast(dict[str, Any], request["input"])["quota"]
            _require(quota["gold_skill_id"] == gold, "generation request gold mismatch")
            _require(
                quota["round_number"] == row["generation_round"],
                "generation request round mismatch",
            )
            expected_quota = {
                "negative_quota": int(negative is not None),
                "positive_only_quota": int(negative is None),
            }
            _require(
                all(quota[field] == value for field, value in expected_quota.items()),
                "generator request quota must match sealed candidate type",
            )
            generation_request_quota_counts[
                (row["generation_round"], gold, "negative")
            ] += quota["negative_quota"]
            generation_request_quota_counts[
                (row["generation_round"], gold, "positive_only")
            ] += quota["positive_only_quota"]
            expected_request = build_generator_request(
                projected_skills,
                gold_skill_id=gold,
                negative_quota=quota["negative_quota"],
                positive_only_quota=quota["positive_only_quota"],
                round_number=row["generation_round"],
            )
            _require(
                _canonical_contract_json_equal(request, expected_request),
                "generator request must match sealed canonical skill authority",
            )
            invocations = row["invocations"]
            actual_sessions["generator"].extend(
                _pack_invocation_identities(invocations)
            )
            if type(invocations) is list:
                actual_invocation_counts["generator"] += len(invocations)
            response, retry_count = _validate_pack_invocations(
                invocations, request=request
            )
            run_record = _sanitized_agent_run_record(
                role="generator",
                candidate_id=candidate_id,
                request=request,
                response=response,
                invocations=invocations,
                retry_count=retry_count,
            )
            sanitized_run_records["generator"].append(run_record)
            retry_record = _transport_retry_record(run_record, role="generator")
            if retry_record is not None:
                retry_records.append(retry_record)
            valid_transport_retry_count += retry_count
            if response is not None:
                generated_rows = response["candidates"]
                _require(
                    len(generated_rows) == 1,
                    "candidate ledger requires one generated candidate per row",
                )
                generated = generated_rows[0]
                for field in (
                    "prompt_text",
                    "semantic_family_id",
                    "proposed_gold_skill_id",
                    "proposed_negative_skill_id",
                    "language",
                    "rationale",
                ):
                    _require(
                        generated[field] == candidate[field],
                        f"generated candidate {field} mismatch",
                    )
                expected_id = opaque_candidate_id(
                    row["generation_round"],
                    gold,
                    generated["candidate_index"],
                    canonical_sha256(response),
                )
                _require(candidate_id == expected_id, "candidate id binding mismatch")
            generation_responses[candidate_id] = response
    except _AgentPackProtocolViolation as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="invocation_protocol",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_ledger",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    def candidate_stratum(candidate: dict[str, Any]) -> str:
        return (
            "negative"
            if candidate["proposed_negative_skill_id"] is not None
            else "positive_only"
        )

    def stratum_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        counts = {
            skill_id: {"negative": 0, "positive_only": 0}
            for skill_id in sorted(canonical_ids)
        }
        for row in rows:
            counts[cast(str, row["proposed_gold_skill_id"])][
                candidate_stratum(row)
            ] += 1
        return counts

    def request_quota_distribution(
        round_number: int,
    ) -> dict[str, dict[str, int]]:
        return {
            skill_id: {
                stratum: generation_request_quota_counts[
                    (round_number, skill_id, stratum)
                ]
                for stratum in ("negative", "positive_only")
            }
            for skill_id in sorted(canonical_ids)
        }

    try:
        _require(
            all(
                candidate["generation_round"] in {1, 2}
                for candidate in candidates.values()
            ),
            "generation is limited to rounds one and two",
        )
        round_one_candidates = [
            candidate
            for candidate in candidates.values()
            if candidate["generation_round"] == 1
        ]
        round_two_candidates = [
            candidate
            for candidate in candidates.values()
            if candidate["generation_round"] == 2
        ]
        _require(
            len(round_one_candidates)
            == _SELECTION_AUTHORITY["round_1_candidate_count"],
            "round 1 must contain exactly 256 candidates",
        )
        round_one_distribution = stratum_counts(round_one_candidates)
        round_one_request_quota_distribution = request_quota_distribution(1)
        _require(
            all(
                counts
                == {
                    "negative": _SELECTION_AUTHORITY["round_1_negative_per_skill"],
                    "positive_only": _SELECTION_AUTHORITY[
                        "round_1_positive_only_per_skill"
                    ],
                }
                for counts in round_one_distribution.values()
            ),
            "round 1 per-skill stratum distribution mismatch",
        )
        _require(
            round_one_request_quota_distribution == round_one_distribution,
            "round 1 request quota authority mismatch",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_rounds",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        for raw_row in contamination_rows:
            row = _exact_object_fields(
                raw_row,
                {
                    "candidate_id",
                    "scanner_decision",
                    "rejection_codes",
                    "evidence_sha256",
                },
                "contamination row",
            )
            _exact_lowercase_hex(
                row["candidate_id"], length=24, label="contamination candidate id"
            )
            _require(
                row["scanner_decision"] in {"PASS", "REJECT"},
                "contamination scanner decision mismatch",
            )
            _require(
                type(row["rejection_codes"]) is list
                and all(type(code) is str for code in row["rejection_codes"]),
                "contamination rejection codes mismatch",
            )
            _exact_lowercase_hex(
                row["evidence_sha256"],
                length=64,
                label="contamination evidence hash",
            )
        contamination_scan = _scan_contamination(
            list(candidates.values()),
            protected_prompts={
                "train": train_prompts,
                "pilot-002": pilot_prompts,
                "phase16": phase16_prompts,
                "prior_candidate": prior_candidate_prompts,
            },
            protected_family_ids={
                "train": train_family_ids,
                "pilot-002": pilot_family_ids,
                "phase16": phase16_family_ids,
                "prior_candidate": prior_candidate_family_ids,
            },
            semantic_similarity=semantic_similarity,
            semantic_model_authority=semantic_model_authority,
        )
        _require(
            _canonical_contract_json_equal(
                contamination_rows, contamination_scan["rows"]
            ),
            "contamination ledger evidence mismatch",
        )
        clean_candidate_ids = set(contamination_scan["clean_candidate_ids"])
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="contamination_ledger",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    review_responses: dict[str, dict[str, dict[str, Any] | None]] = {
        "reviewer_a": {},
        "reviewer_b": {},
    }
    actual_review_orders: dict[str, list[str]] = {
        "reviewer_a": [],
        "reviewer_b": [],
    }
    for role, role_rows in review_rows_by_role.items():
        try:
            for raw_row in role_rows:
                row = _exact_object_fields(
                    raw_row,
                    {"candidate_id", "request", "invocations"},
                    f"{role} row",
                )
                candidate_id = _exact_lowercase_hex(
                    row["candidate_id"], length=24, label="review candidate id"
                )
                _require(
                    candidate_id in candidates, "review references unknown candidate"
                )
                _require(
                    candidate_id in clean_candidate_ids,
                    "contamination-rejected candidate must not be reviewed",
                )
                _require(
                    candidate_id not in review_responses[role],
                    "review candidate ids must be unique",
                )
                actual_review_orders[role].append(candidate_id)
                request = validate_agent_request(row["request"])
                expected_request = build_reviewer_request(
                    candidates[candidate_id], projected_skills, role=role
                )
                _require(
                    _canonical_contract_json_equal(request, expected_request),
                    "reviewer request must contain only sealed candidate input",
                )
                invocations = row["invocations"]
                actual_sessions[role].extend(_pack_invocation_identities(invocations))
                if type(invocations) is list:
                    actual_invocation_counts[role] += len(invocations)
                response, retry_count = _validate_pack_invocations(
                    invocations, request=request
                )
                run_record = _sanitized_agent_run_record(
                    role=role,
                    candidate_id=candidate_id,
                    request=request,
                    response=response,
                    invocations=invocations,
                    retry_count=retry_count,
                )
                sanitized_run_records[role].append(run_record)
                retry_record = _transport_retry_record(run_record, role=role)
                if retry_record is not None:
                    retry_records.append(retry_record)
                valid_transport_retry_count += retry_count
                review_responses[role][candidate_id] = response
            _require(
                set(review_responses[role]) == clean_candidate_ids,
                f"{role} must review every contamination-clean candidate",
            )
        except _AgentPackProtocolViolation as exc:
            return _agent_pack_protocol_invalid(
                failure_stage="invocation_protocol",
                failure_reason=str(exc),
                first_read_timestamp=first_read_timestamp,
                source_file_sha256=source_hashes,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _agent_pack_protocol_invalid(
                failure_stage="reviewer_request",
                failure_reason=str(exc),
                first_read_timestamp=first_read_timestamp,
                source_file_sha256=source_hashes,
            )

    try:
        request_counts = {
            "generator": len(generation_rows),
            "reviewer_a": len(review_rows_by_role["reviewer_a"]),
            "reviewer_b": len(review_rows_by_role["reviewer_b"]),
        }
        all_actual_sessions = [
            session
            for role in ("generator", "reviewer_a", "reviewer_b")
            for session in actual_sessions[role]
        ]
        _require(
            len(all_actual_sessions) == len(set(all_actual_sessions)),
            "session/thread ids must be globally unique",
        )
        all_metadata_sessions: list[str] = []
        for role in ("generator", "reviewer_a", "reviewer_b"):
            role_metadata = cast(dict[str, Any], metadata_roles[role])
            _require(
                role_metadata["request_count"] == request_counts[role],
                f"{role} request count mismatch",
            )
            _require(
                role_metadata["invocation_count"] == actual_invocation_counts[role],
                f"{role} invocation count mismatch",
            )
            _require(
                role_metadata["session_or_thread_ids"] == actual_sessions[role],
                f"{role} session/thread binding mismatch",
            )
            all_metadata_sessions.extend(role_metadata["session_or_thread_ids"])
        _require(
            len(all_metadata_sessions) == len(set(all_metadata_sessions)),
            "metadata session/thread ids must be globally unique",
        )
        for role in ("reviewer_a", "reviewer_b"):
            expected_schedule_order = sorted(
                clean_candidate_ids,
                key=lambda value: review_schedule_key(role, value),
            )
            _require(
                actual_review_orders[role] == expected_schedule_order,
                f"{role} ledger schedule mismatch",
            )
            _require(
                metadata_schedules[role]
                == canonical_sha256(actual_review_orders[role]),
                f"{role} schedule hash mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="agent_run_metadata",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    accepted: list[dict[str, Any]] = []
    candidate_outcomes: dict[str, str] = {}
    for candidate_id, candidate in candidates.items():
        if candidate_id not in clean_candidate_ids:
            candidate_outcomes[candidate_id] = "REJECTED_CONTAMINATION"
            continue
        reviewer_a = review_responses["reviewer_a"][candidate_id]
        reviewer_b = review_responses["reviewer_b"][candidate_id]
        if (
            generation_responses[candidate_id] is None
            or reviewer_a is None
            or reviewer_b is None
        ):
            candidate_outcomes[candidate_id] = "REJECTED_INVOCATION"
            continue
        expected_labels = (
            candidate["proposed_gold_skill_id"],
            candidate["proposed_negative_skill_id"],
        )
        reviews = (reviewer_a, reviewer_b)
        if not all(
            review["decision"] == "ACCEPT"
            and review["natural"] is True
            and review["single_primary_skill"] is True
            and review["no_label_leakage"] is True
            and (
                review["negative_confusable"] is True
                if review["reviewed_negative_skill_id"] is not None
                else review["negative_confusable"] is None
            )
            and (
                review["reviewed_gold_skill_id"],
                review["reviewed_negative_skill_id"],
            )
            == expected_labels
            for review in reviews
        ):
            candidate_outcomes[candidate_id] = "REJECTED_REVIEW"
            continue
        accepted.append(deepcopy(candidate))
        candidate_outcomes[candidate_id] = "ELIGIBLE"

    def deficit_document(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        counts = stratum_counts(rows)
        output: dict[str, dict[str, int]] = {}
        for skill_id, skill_counts in counts.items():
            deficits = {
                "negative": max(
                    0,
                    cast(int, _SELECTION_AUTHORITY["final_negative_per_skill"])
                    - skill_counts["negative"],
                ),
                "positive_only": max(
                    0,
                    cast(int, _SELECTION_AUTHORITY["final_positive_only_per_skill"])
                    - skill_counts["positive_only"],
                ),
            }
            if any(deficits.values()):
                output[skill_id] = deficits
        return output

    round_one_accepted = [
        candidate for candidate in accepted if candidate["generation_round"] == 1
    ]
    round_one_deficits = deficit_document(round_one_accepted)
    round_two_distribution = stratum_counts(round_two_candidates)
    round_two_request_quota_distribution = request_quota_distribution(2)
    try:
        for skill_id in sorted(canonical_ids):
            deficits = round_one_deficits.get(
                skill_id, {"negative": 0, "positive_only": 0}
            )
            _require(
                round_two_distribution[skill_id]
                == {
                    stratum: deficit
                    * cast(int, _SELECTION_AUTHORITY["round_2_deficit_multiplier"])
                    for stratum, deficit in deficits.items()
                },
                "round 2 candidate count must equal twice each post-pipeline deficit",
            )
            _require(
                round_two_request_quota_distribution[skill_id]
                == round_two_distribution[skill_id],
                "round 2 request quota authority mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_rounds",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    accepted.sort(key=lambda row: cast(str, row["candidate_id"]))
    final_deficits = deficit_document(accepted)
    contamination_audit = {
        "required_semantic_model_id": contamination_scan["scanner_config"][
            "required_semantic_model_id"
        ],
        "required_semantic_model_revision": contamination_scan["scanner_config"][
            "required_semantic_model_revision"
        ],
        "materialized_model_files": deepcopy(
            contamination_scan["scanner_config"]["materialized_model_files"]
        ),
        "materialized_model_files_sha256": contamination_scan["scanner_config"][
            "materialized_model_files_sha256"
        ],
        "semantic_scorer_runtime_verified": False,
        "semantic_scorer_receipt_sha256": None,
        "token_5gram_jaccard_reject_at_or_above": str(TOKEN_5GRAM_JACCARD_MAX),
        "character_5gram_jaccard_reject_at_or_above": str(CHARACTER_5GRAM_JACCARD_MAX),
        "semantic_cosine_reject_at_or_above": str(SEMANTIC_COSINE_MAX),
        "candidate_count": len(candidates),
        "clean_candidate_count": len(clean_candidate_ids),
        "rejected_candidate_count": len(candidates) - len(clean_candidate_ids),
        "ledger_sha256": source_hashes["blind-v2-contamination.jsonl"],
        "scanner_config_sha256": canonical_sha256(contamination_scan["scanner_config"]),
        "protected_authority": deepcopy(
            contamination_scan["scanner_config"]["protected_authority"]
        ),
        "protected_authority_sha256": contamination_scan["scanner_config"][
            "protected_authority_sha256"
        ],
        "evidence_sha256": canonical_sha256(contamination_scan["rows"]),
    }

    def selection_audit(selected: list[dict[str, Any]]) -> dict[str, Any]:
        authority_document = _selection_authority_document()
        selected_ids = [cast(str, row["candidate_id"]) for row in selected]
        selected_by_stratum = {
            skill_id: {
                stratum: [
                    cast(str, row["candidate_id"])
                    for row in selected
                    if row["proposed_gold_skill_id"] == skill_id
                    and candidate_stratum(row) == stratum
                ]
                for stratum in ("negative", "positive_only")
            }
            for skill_id in sorted(canonical_ids)
        }
        return {
            "selection_authority": authority_document,
            "selection_authority_sha256": canonical_sha256(authority_document),
            "accepted_pool_sha256": canonical_sha256(accepted),
            "round_1_candidate_count": len(round_one_candidates),
            "round_2_candidate_count": len(round_two_candidates),
            "round_1_distribution": round_one_distribution,
            "round_2_distribution": round_two_distribution,
            "round_1_request_quota_distribution": (
                round_one_request_quota_distribution
            ),
            "round_2_request_quota_distribution": (
                round_two_request_quota_distribution
            ),
            "round_1_post_pipeline_deficits": round_one_deficits,
            "selected_candidate_ids": selected_ids,
            "selected_candidate_ids_sha256": canonical_sha256(selected_ids),
            "selected_by_stratum": selected_by_stratum,
        }

    pipeline_rejected_count = sum(
        outcome.startswith("REJECTED") for outcome in candidate_outcomes.values()
    )
    agent_run_identity_authority = _agent_run_identity_authority(
        sanitized_run_records,
        cast(dict[str, Any], metadata_roles),
        source_hashes,
    )

    common_result = {
        "schema_version": "router-v2-blind-v2-agent-pack-validation-v1",
        "transport_retry_count": valid_transport_retry_count,
        "retry_records": sorted(
            retry_records,
            key=lambda row: (cast(str, row["role"]), cast(str, row["candidate_id"])),
        ),
        "agent_roles": deepcopy(metadata_roles),
        "agent_run_records": deepcopy(sanitized_run_records),
        "agent_run_evidence": {
            role: _agent_role_run_evidence(role, sanitized_run_records[role])
            for role in AGENT_CONFIGS
        },
        "agent_run_identity_authority": agent_run_identity_authority,
        "review_schedule_sha256": deepcopy(metadata_schedules),
        "source_file_sha256": source_hashes,
        "first_read_timestamp": first_read_timestamp,
        "model_scores_observed": False,
        "contamination_audit": contamination_audit,
        "exact_three_way_agreement_count": len(accepted),
        "pipeline_rejected_candidate_count": pipeline_rejected_count,
    }
    if final_deficits:
        insufficient_selection_audit = selection_audit([])
        return {
            **common_result,
            "status": "INSUFFICIENT",
            "failure_stage": "deterministic_selection",
            "research_conclusion": "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
            "router_decision": "KEEP_BASELINE",
            "production_ready": False,
            "release_authorized": False,
            "default_router_unchanged": True,
            "task_count": 0,
            "negative_labeled_task_count": 0,
            "family_count": 0,
            "excluded_candidate_count": len(candidates),
            "candidate_outcomes": dict(sorted(candidate_outcomes.items())),
            "deficits": final_deficits,
            "ledger_sha256": deepcopy(source_hashes),
            "selection_audit": insufficient_selection_audit,
            "selection_audit_sha256": canonical_sha256(insufficient_selection_audit),
            "tasks": [],
        }

    try:
        selected: list[dict[str, Any]] = []
        for skill_id in sorted(canonical_ids):
            for stratum, quota_field in (
                ("negative", "final_negative_per_skill"),
                ("positive_only", "final_positive_only_per_skill"),
            ):
                pool = sorted(
                    (
                        row
                        for row in accepted
                        if row["proposed_gold_skill_id"] == skill_id
                        and candidate_stratum(row) == stratum
                    ),
                    key=lambda row: selection_key(cast(str, row["candidate_id"])),
                )
                selected.extend(
                    deepcopy(pool[: cast(int, _SELECTION_AUTHORITY[quota_field])])
                )

        selected_ids = {cast(str, row["candidate_id"]) for row in selected}
        for candidate_id, outcome in tuple(candidate_outcomes.items()):
            if outcome == "ELIGIBLE":
                candidate_outcomes[candidate_id] = (
                    "SELECTED" if candidate_id in selected_ids else "NOT_SELECTED"
                )
        selected_prompt_bytes = {
            cast(str, row["prompt_text"]).encode("utf-8") for row in selected
        }
        selected_normalized_prompts = {
            _normalize(cast(str, row["prompt_text"])) for row in selected
        }
        selected_families = {cast(str, row["semantic_family_id"]) for row in selected}
        selected_negative_rows = [
            row for row in selected if row["proposed_negative_skill_id"] is not None
        ]
        _validate_deterministic_selection(
            selected,
            selected_ids=selected_ids,
            selected_prompt_bytes=selected_prompt_bytes,
            selected_normalized_prompts=selected_normalized_prompts,
            selected_families=selected_families,
            selected_negative_rows=selected_negative_rows,
            canonical_ids=canonical_ids,
        )
        gold_counts = Counter(row["proposed_gold_skill_id"] for row in selected)
        negative_counts = Counter(
            row["proposed_negative_skill_id"] for row in selected_negative_rows
        )
        selected_selection_audit = selection_audit(selected)
        return {
            **common_result,
            "status": "VALID",
            "task_count": len(selected),
            "negative_labeled_task_count": len(selected_negative_rows),
            "family_count": len(selected_families),
            "gold_distribution": dict(sorted(gold_counts.items())),
            "negative_distribution": dict(
                sorted(
                    (cast(str, key), value) for key, value in negative_counts.items()
                )
            ),
            "negative_target_coverage_count": len(negative_counts),
            "excluded_candidate_count": len(candidates) - len(selected),
            "selection_not_selected_count": sum(
                outcome == "NOT_SELECTED" for outcome in candidate_outcomes.values()
            ),
            "candidate_outcomes": dict(sorted(candidate_outcomes.items())),
            "selection_audit": selected_selection_audit,
            "selection_audit_sha256": canonical_sha256(selected_selection_audit),
            "tasks": selected,
        }
    except _DeterministicSelectionProtocolViolation as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="deterministic_selection",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )


def _validate_legacy_human_pack(
    root: Path | str,
    *,
    repository_root: Path | str,
    canonical_skills: list[dict[str, Any]],
    train_prompts: list[str],
    pilot_prompts: list[str],
    train_family_ids: set[str],
    pilot_family_ids: set[str],
    first_read_timestamp: str,
    phase16_prompts: list[str] | None = None,
) -> dict[str, Any]:
    pack_root = Path(root)
    _outside_repository(pack_root, Path(repository_root))
    for filename in LEGACY_REQUIRED_HUMAN_PACK_FILES:
        _require(
            (pack_root / filename).is_file(),
            f"missing required human pack file: {filename}",
        )

    authored_bytes, authored_rows = _read_csv(
        pack_root / LEGACY_REQUIRED_HUMAN_PACK_FILES[0], AUTHORED_FIELDS
    )
    review_bytes, review_rows = _read_csv(
        pack_root / LEGACY_REQUIRED_HUMAN_PACK_FILES[1], REVIEW_FIELDS
    )
    metadata_bytes = (pack_root / LEGACY_REQUIRED_HUMAN_PACK_FILES[2]).read_bytes()
    metadata = _json_no_duplicate_keys(
        metadata_bytes, LEGACY_REQUIRED_HUMAN_PACK_FILES[2]
    )

    _require(
        len(canonical_skills) == 16, "canonical skill index must contain 16 skills"
    )
    skill_ids = [row.get("id") for row in canonical_skills]
    _require(
        all(type(skill_id) is str and skill_id for skill_id in skill_ids)
        and len(set(skill_ids)) == 16,
        "canonical skill ids must be unique",
    )
    canonical_ids = {cast(str, skill_id) for skill_id in skill_ids}
    normalized_phase16_prompts = {
        _normalize(prompt) for prompt in (phase16_prompts or [])
    }
    leakage_terms = {
        _normalize(cast(str, row[field]))
        for row in canonical_skills
        for field in ("id", "name")
        if type(row.get(field)) is str and row[field]
    }

    authored_by_id: dict[str, dict[str, Any]] = {}
    prompt_bytes_seen: set[bytes] = set()
    normalized_prompts_seen: set[str] = set()
    family_ids_seen: set[str] = set()
    for raw in authored_rows:
        _require(
            all(
                raw.get(field, "").strip()
                for field in AUTHORED_FIELDS
                if field != "negative_skill_id"
            ),
            "authored row contains empty required field",
        )
        task_id = raw["task_id"].strip()
        _require(task_id not in authored_by_id, "task ids must be unique")
        prompt = raw["prompt_text"]
        prompt_bytes = prompt.encode("utf-8")
        normalized = _normalize(prompt)
        family = raw["semantic_family_id"].strip()
        gold = raw["gold_skill_id"].strip()
        negative = raw["negative_skill_id"].strip() or None
        _require(prompt_bytes not in prompt_bytes_seen, "prompt bytes must be unique")
        _require(
            normalized not in normalized_prompts_seen,
            "normalized prompts must be unique",
        )
        _require(
            normalized not in normalized_phase16_prompts,
            "Phase 16 prompt overlap detected",
        )
        _require(family not in family_ids_seen, "semantic families must be unique")
        _require(gold in canonical_ids, "gold skill must be canonical")
        _require(
            negative is None or negative in canonical_ids,
            "negative skill must be canonical",
        )
        _require(negative != gold, "negative skill must differ from gold")
        _require(
            raw["source_type"] == "HUMAN_AUTHORED", "source_type must be HUMAN_AUTHORED"
        )
        normalized_with_spaces = f" {normalized.replace('-', ' ')} "
        _require(
            not any(
                f" {marker} " in normalized_with_spaces for marker in _LEAKAGE_MARKERS
            ),
            "prompt contains label leakage",
        )
        _require(
            not any(marker in normalized for marker in _PROTECTED_MARKERS),
            "prompt contains protected old-data marker",
        )
        for term in leakage_terms:
            expanded = term.replace("-", " ")
            _require(
                f" {expanded} " not in normalized_with_spaces,
                "prompt contains a skill id or name",
            )
        authored_by_id[task_id] = {
            "task_id": task_id,
            "prompt_text": prompt,
            "prompt_text_sha256": _sha256_bytes(prompt_bytes),
            "semantic_family_id": family,
            "gold_skill_id": gold,
            "negative_skill_id": negative,
            "author_id": raw["author_id"].strip(),
            "author_reason": raw["author_reason"].strip(),
            "language": raw["language"].strip(),
            "source_type": raw["source_type"],
        }
        prompt_bytes_seen.add(prompt_bytes)
        normalized_prompts_seen.add(normalized)
        family_ids_seen.add(family)

    review_by_id: dict[str, dict[str, str]] = {}
    for row in review_rows:
        _require(
            all(
                row.get(field, "").strip()
                for field in REVIEW_FIELDS
                if field != "reviewed_negative_skill_id"
            ),
            "review row contains empty required field",
        )
        task_id = row["task_id"].strip()
        _require(task_id not in review_by_id, "review task ids must be unique")
        _require(task_id in authored_by_id, "review references unknown task")
        _require(row["review_decision"] in REVIEW_DECISIONS, "review decision mismatch")
        _require(
            row["prompt_text_sha256"] == authored_by_id[task_id]["prompt_text_sha256"],
            "review prompt hash mismatch",
        )
        _require(
            row["reviewer_id"].strip() != authored_by_id[task_id]["author_id"],
            "author and reviewer must differ",
        )
        review_by_id[task_id] = {key: value.strip() for key, value in row.items()}

    _require(
        set(review_by_id) == set(authored_by_id), "every authored task must be reviewed"
    )
    accepted = []
    excluded = 0
    for task_id, authored in authored_by_id.items():
        review = review_by_id[task_id]
        if review["review_decision"] != "ACCEPT":
            excluded += 1
            continue
        reviewed_negative = review["reviewed_negative_skill_id"] or None
        _require(
            review["reviewed_gold_skill_id"] == authored["gold_skill_id"]
            and reviewed_negative == authored["negative_skill_id"],
            "accepted review must exactly agree with author labels",
        )
        accepted.append(
            {
                **authored,
                "reviewer_id": review["reviewer_id"],
                "review_confidence": review["review_confidence"],
                "review_reason": review["review_reason"],
            }
        )

    _require(len(accepted) == 64, "human agreement must leave exactly 64 tasks")
    negative_rows = [row for row in accepted if row["negative_skill_id"] is not None]
    _require(
        len(negative_rows) == 48,
        "human agreement must leave exactly 48 negative-labeled tasks",
    )
    gold_counts = Counter(row["gold_skill_id"] for row in accepted)
    _require(
        set(gold_counts) == canonical_ids and set(gold_counts.values()) == {4},
        "gold distribution must be 16 skills x 4 tasks",
    )
    negative_by_gold = Counter(row["gold_skill_id"] for row in negative_rows)
    _require(
        set(negative_by_gold) == canonical_ids
        and set(negative_by_gold.values()) == {3},
        "each gold skill must have three negative-labeled tasks",
    )
    target_counts = Counter(row["negative_skill_id"] for row in negative_rows)
    _require(len(target_counts) >= 12, "negative targets must cover at least 12 skills")
    _require(
        max(target_counts.values(), default=0) <= 6,
        "negative target count may not exceed six",
    )
    _require(
        len({row["semantic_family_id"] for row in accepted}) == 64,
        "final pack must contain 64 semantic families",
    )

    train_normalized = {_normalize(prompt) for prompt in train_prompts}
    pilot_normalized = {_normalize(prompt) for prompt in pilot_prompts}
    for row in accepted:
        normalized = _normalize(row["prompt_text"])
        _require(normalized not in train_normalized, "train prompt overlap detected")
        _require(
            normalized not in pilot_normalized, "pilot-002 prompt overlap detected"
        )
        _require(
            row["semantic_family_id"] not in train_family_ids,
            "train family overlap detected",
        )
        _require(
            row["semantic_family_id"] not in pilot_family_ids,
            "pilot-002 family overlap detected",
        )

    author_ids = {row["author_id"] for row in accepted}
    reviewer_ids = {row["reviewer_id"] for row in accepted}
    _require(
        author_ids.isdisjoint(reviewer_ids),
        "author and reviewer identities must be disjoint",
    )
    _require(
        metadata.get("authors_and_reviewers_are_different_people") is True,
        "metadata must confirm different humans",
    )
    _require(
        metadata.get("reviewer_saw_model_rankings") is False,
        "reviewer must not see model rankings",
    )
    _require(
        metadata.get("reviewer_saw_pilot_002_task_level_results") is False,
        "reviewer must not see pilot-002 task-level results",
    )
    _require(
        metadata.get("human_author_count") == len(author_ids),
        "human author count mismatch",
    )
    _require(
        metadata.get("independent_human_reviewer_count") == len(reviewer_ids),
        "human reviewer count mismatch",
    )
    for field in ("review_date", "reviewer_qualification", "dataset_license"):
        _require(
            type(metadata.get(field)) is str and bool(metadata[field].strip()),
            f"metadata {field} is required",
        )
    for field in (
        "reviewer_used_ai_assistance",
        "publication_permission",
        "prompts_may_be_public_after_evaluation",
    ):
        _require(type(metadata.get(field)) is bool, f"metadata {field} must be boolean")
    _require(
        metadata.get("author_ids") == sorted(author_ids), "metadata author ids mismatch"
    )
    _require(
        metadata.get("reviewer_ids") == sorted(reviewer_ids),
        "metadata reviewer ids mismatch",
    )

    accepted.sort(key=lambda row: row["task_id"])
    source_hashes = {
        LEGACY_REQUIRED_HUMAN_PACK_FILES[0]: _sha256_bytes(authored_bytes),
        LEGACY_REQUIRED_HUMAN_PACK_FILES[1]: _sha256_bytes(review_bytes),
        LEGACY_REQUIRED_HUMAN_PACK_FILES[2]: _sha256_bytes(metadata_bytes),
    }
    return {
        "schema_version": "router-v2-blind-v2-human-pack-validation-v1",
        "status": "VALID",
        "task_count": 64,
        "negative_labeled_task_count": 48,
        "family_count": 64,
        "gold_distribution": dict(sorted(gold_counts.items())),
        "negative_distribution": dict(
            sorted((str(key), value) for key, value in target_counts.items())
        ),
        "negative_target_coverage_count": len(target_counts),
        "human_author_count": len(author_ids),
        "independent_human_reviewer_count": len(reviewer_ids),
        "exact_review_agreement_count": len(accepted),
        "excluded_candidate_count": excluded,
        "ai_assistance_disclosure": metadata["reviewer_used_ai_assistance"],
        "publication_permission": metadata["publication_permission"],
        "prompts_may_be_public_after_evaluation": metadata[
            "prompts_may_be_public_after_evaluation"
        ],
        "dataset_license": metadata["dataset_license"],
        "review_date": metadata["review_date"],
        "reviewer_qualification": metadata["reviewer_qualification"],
        "source_file_sha256": source_hashes,
        "first_read_timestamp": first_read_timestamp,
        "duplicate_checks": {
            "task_ids_unique": True,
            "prompt_bytes_unique": True,
            "nfkc_casefold_prompts_unique": True,
            "semantic_families_unique": True,
        },
        "train_overlap_checks": {"prompt_overlap_count": 0, "family_overlap_count": 0},
        "pilot_002_overlap_checks": {
            "prompt_overlap_count": 0,
            "family_overlap_count": 0,
        },
        "phase16_overlap_checks": {"prompt_overlap_count": 0},
        "model_scores_observed": False,
        "tasks": accepted,
    }


def _validated_agent_lineage_evidence(
    validation: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    records_by_role = validation.get("agent_run_records")
    _require(
        type(records_by_role) is dict and set(records_by_role) == set(AGENT_CONFIGS),
        "Agent run or retry evidence mismatch",
    )
    role_records = cast(dict[str, Any], records_by_role)
    validated_records: dict[str, list[dict[str, Any]]] = {}
    record_fields = {
        "candidate_id",
        "request_sha256",
        "response_sha256",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "session_or_thread_ids",
        "transport_retry_count",
    }
    for role, config in AGENT_CONFIGS.items():
        raw_records = role_records[role]
        _require(type(raw_records) is list, "Agent run or retry evidence mismatch")
        records: list[dict[str, Any]] = []
        candidate_ids: set[str] = set()
        for raw_record in raw_records:
            try:
                record = _exact_object_fields(
                    raw_record, record_fields, f"{role} sanitized run record"
                )
                candidate_id = _exact_lowercase_hex(
                    record["candidate_id"], length=24, label="run candidate id"
                )
                request_sha256 = _exact_lowercase_hex(
                    record["request_sha256"], length=64, label="run request hash"
                )
                raw_response_sha256 = record["response_sha256"]
                response_sha256 = (
                    None
                    if raw_response_sha256 is None
                    else _exact_lowercase_hex(
                        raw_response_sha256,
                        length=64,
                        label="run response hash",
                    )
                )
                identities = record["session_or_thread_ids"]
                retry_count = record["transport_retry_count"]
                _require(candidate_id not in candidate_ids, "duplicate run candidate")
                _require(
                    record["requested_model"] == config["model"]
                    and record["reasoning_effort"] == config["reasoning_effort"],
                    "run Agent configuration mismatch",
                )
                _require(
                    (response_sha256 is None and record["returned_model"] is None)
                    or (
                        response_sha256 is not None
                        and record["returned_model"] == config["model"]
                    ),
                    "run response model binding mismatch",
                )
                _require(
                    type(identities) is list
                    and all(
                        type(identity) is str
                        and bool(identity)
                        and identity.strip() == identity
                        for identity in identities
                    )
                    and len(set(identities)) == len(identities),
                    "run session binding mismatch",
                )
                _require(
                    type(retry_count) is int
                    and retry_count in {0, 1}
                    and len(identities) == retry_count + 1,
                    "run retry binding mismatch",
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Agent run or retry evidence mismatch") from exc
            candidate_ids.add(candidate_id)
            records.append(
                {
                    **deepcopy(record),
                    "candidate_id": candidate_id,
                    "request_sha256": request_sha256,
                    "response_sha256": response_sha256,
                }
            )
        validated_records[role] = records

    expected_evidence = {
        role: _agent_role_run_evidence(role, validated_records[role])
        for role in AGENT_CONFIGS
    }
    expected_retries = sorted(
        [
            retry
            for role, records in validated_records.items()
            for record in records
            if (retry := _transport_retry_record(record, role=role)) is not None
        ],
        key=lambda row: (cast(str, row["role"]), cast(str, row["candidate_id"])),
    )
    try:
        metadata_roles = _exact_object_fields(
            validation["agent_roles"], set(AGENT_CONFIGS), "Agent role metadata"
        )
        source_file_sha256 = _exact_object_fields(
            validation["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file hashes",
        )
        identity_authority = _agent_run_identity_authority(
            validated_records, metadata_roles, source_file_sha256
        )
        review_schedules = _exact_object_fields(
            validation["review_schedule_sha256"],
            {"reviewer_a", "reviewer_b"},
            "review schedule hashes",
        )
        for role in ("reviewer_a", "reviewer_b"):
            schedule_candidate_ids = [
                record["candidate_id"] for record in validated_records[role]
            ]
            _require(
                review_schedules[role] == canonical_sha256(schedule_candidate_ids),
                f"{role} schedule identity mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Agent run identity authority mismatch") from exc
    _require(
        validation.get("agent_run_evidence") == expected_evidence
        and validation.get("retry_records") == expected_retries
        and validation.get("transport_retry_count") == len(expected_retries),
        "Agent run or retry evidence mismatch",
    )
    _require(
        validation.get("agent_run_identity_authority") == identity_authority,
        "Agent run identity authority mismatch",
    )
    return validated_records, expected_evidence, expected_retries, identity_authority


def _validated_dataset_freeze_tasks(
    validation: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    message = "Agent dataset selection validation mismatch"
    try:
        raw_tasks = validation["tasks"]
        _require(
            type(raw_tasks) is list and len(raw_tasks) == POSITIVE_TASK_COUNT,
            "selected task count mismatch",
        )
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
        selected: list[dict[str, Any]] = []
        for raw_task in raw_tasks:
            task = _exact_object_fields(
                raw_task, candidate_fields, "selected Agent task"
            )
            candidate_id = _exact_lowercase_hex(
                task["candidate_id"], length=24, label="selected candidate id"
            )
            _require(
                type(task["generation_round"]) is int
                and task["generation_round"] in {1, 2},
                "selected generation round mismatch",
            )
            prompt_text = _nonempty_string(task["prompt_text"], "selected prompt")
            prompt_bytes = prompt_text.encode("utf-8", errors="strict")
            prompt_hash = _exact_lowercase_hex(
                task["prompt_text_sha256"],
                length=64,
                label="selected prompt SHA-256",
            )
            _require(
                prompt_hash == _sha256_bytes(prompt_bytes),
                "selected prompt SHA-256 mismatch",
            )
            family_id = _nonempty_string(
                task["semantic_family_id"], "selected semantic family"
            )
            gold = _nonempty_string(
                task["proposed_gold_skill_id"], "selected gold skill"
            )
            negative = task["proposed_negative_skill_id"]
            _require(
                negative is None
                or (
                    type(negative) is str
                    and bool(negative.strip())
                    and negative != gold
                ),
                "selected negative skill mismatch",
            )
            _require(task["language"] == "en", "selected task language mismatch")
            _nonempty_string(task["rationale"], "selected task rationale")
            selected.append(
                {
                    **deepcopy(task),
                    "candidate_id": candidate_id,
                    "prompt_text": prompt_text,
                    "prompt_text_sha256": prompt_hash,
                    "semantic_family_id": family_id,
                    "proposed_gold_skill_id": gold,
                }
            )

        selected_ids = [cast(str, task["candidate_id"]) for task in selected]
        selected_prompt_bytes = [
            cast(str, task["prompt_text"]).encode("utf-8") for task in selected
        ]
        normalized_prompts = [
            _normalize(cast(str, task["prompt_text"])) for task in selected
        ]
        family_ids = [cast(str, task["semantic_family_id"]) for task in selected]
        _require(
            len(set(selected_ids)) == POSITIVE_TASK_COUNT,
            "selected candidate ids must be unique",
        )
        _require(
            len(set(selected_prompt_bytes)) == POSITIVE_TASK_COUNT
            and len(set(normalized_prompts)) == POSITIVE_TASK_COUNT,
            "selected prompts must be unique",
        )
        _require(
            len(set(family_ids)) == POSITIVE_TASK_COUNT,
            "selected semantic families must be unique",
        )

        gold_counts = Counter(task["proposed_gold_skill_id"] for task in selected)
        _require(
            len(gold_counts) == 16 and set(gold_counts.values()) == {8},
            "selected per-gold task distribution mismatch",
        )
        gold_ids = sorted(cast(str, gold) for gold in gold_counts)
        selected_by_stratum = {
            gold: {
                "negative": [
                    cast(str, task["candidate_id"])
                    for task in selected
                    if task["proposed_gold_skill_id"] == gold
                    and task["proposed_negative_skill_id"] is not None
                ],
                "positive_only": [
                    cast(str, task["candidate_id"])
                    for task in selected
                    if task["proposed_gold_skill_id"] == gold
                    and task["proposed_negative_skill_id"] is None
                ],
            }
            for gold in gold_ids
        }
        _require(
            all(
                len(strata["negative"]) == 6 and len(strata["positive_only"]) == 2
                for strata in selected_by_stratum.values()
            ),
            "selected per-gold stratum distribution mismatch",
        )
        negative_tasks = [
            task for task in selected if task["proposed_negative_skill_id"] is not None
        ]
        _require(
            len(negative_tasks) == TEMPTING_NEGATIVE_COUNT,
            "selected negative task count mismatch",
        )
        expected_order = [
            task
            for gold in gold_ids
            for has_negative in (True, False)
            for task in sorted(
                (
                    row
                    for row in selected
                    if row["proposed_gold_skill_id"] == gold
                    and (row["proposed_negative_skill_id"] is not None) is has_negative
                ),
                key=lambda row: selection_key(cast(str, row["candidate_id"])),
            )
        ]
        _require(
            selected_ids
            == [cast(str, task["candidate_id"]) for task in expected_order],
            "selected candidate order mismatch",
        )

        expected_gold_distribution = dict(sorted(gold_counts.items()))
        negative_counts = Counter(
            cast(str, task["proposed_negative_skill_id"]) for task in negative_tasks
        )
        expected_negative_distribution = dict(sorted(negative_counts.items()))
        _require(
            type(validation["task_count"]) is int
            and validation["task_count"] == POSITIVE_TASK_COUNT
            and type(validation["negative_labeled_task_count"]) is int
            and validation["negative_labeled_task_count"] == len(negative_tasks)
            and type(validation["family_count"]) is int
            and validation["family_count"] == len(set(family_ids)),
            "selected task summary count mismatch",
        )
        _require(
            validation["gold_distribution"] == expected_gold_distribution
            and validation["negative_distribution"] == expected_negative_distribution
            and validation["negative_target_coverage_count"] == len(negative_counts),
            "selected task summary distribution mismatch",
        )

        candidate_outcomes = validation["candidate_outcomes"]
        _require(
            type(candidate_outcomes) is dict, "candidate outcomes must be an object"
        )
        _require(
            all(
                candidate_outcomes.get(candidate_id) == "SELECTED"
                for candidate_id in selected_ids
            ),
            "selected candidates must have SELECTED outcomes",
        )
        _require(
            validation["excluded_candidate_count"]
            == len(candidate_outcomes) - POSITIVE_TASK_COUNT,
            "excluded candidate count mismatch",
        )
        _require(
            validation["selection_not_selected_count"]
            == sum(
                outcome == "NOT_SELECTED" for outcome in candidate_outcomes.values()
            ),
            "not-selected candidate count mismatch",
        )
        _require(
            validation["pipeline_rejected_candidate_count"]
            == sum(
                type(outcome) is str and outcome.startswith("REJECTED")
                for outcome in candidate_outcomes.values()
            ),
            "pipeline rejected candidate count mismatch",
        )
        _require(
            validation["exact_three_way_agreement_count"]
            == sum(
                outcome in {"SELECTED", "NOT_SELECTED"}
                for outcome in candidate_outcomes.values()
            ),
            "three-way agreement pool count mismatch",
        )

        selection = _exact_object_fields(
            validation["selection_audit"],
            {
                "selection_authority",
                "selection_authority_sha256",
                "accepted_pool_sha256",
                "round_1_candidate_count",
                "round_2_candidate_count",
                "round_1_distribution",
                "round_2_distribution",
                "round_1_request_quota_distribution",
                "round_2_request_quota_distribution",
                "round_1_post_pipeline_deficits",
                "selected_candidate_ids",
                "selected_candidate_ids_sha256",
                "selected_by_stratum",
            },
            "selection audit",
        )
        selection_authority = _selection_authority_document()
        _require(
            selection["selection_authority"] == selection_authority
            and selection["selection_authority_sha256"]
            == canonical_sha256(selection_authority),
            "selection authority mismatch",
        )
        _exact_lowercase_hex(
            selection["accepted_pool_sha256"],
            length=64,
            label="accepted pool SHA-256",
        )
        expected_round_one_distribution = {
            gold: {
                "negative": _SELECTION_AUTHORITY["round_1_negative_per_skill"],
                "positive_only": _SELECTION_AUTHORITY[
                    "round_1_positive_only_per_skill"
                ],
            }
            for gold in gold_ids
        }
        _require(
            selection["round_1_candidate_count"]
            == _SELECTION_AUTHORITY["round_1_candidate_count"]
            and selection["round_1_distribution"] == expected_round_one_distribution
            and selection["round_1_request_quota_distribution"]
            == expected_round_one_distribution,
            "round-one selection audit mismatch",
        )
        round_two_distribution = _exact_object_fields(
            selection["round_2_distribution"], set(gold_ids), "round-two distribution"
        )
        round_two_count = 0
        for gold in gold_ids:
            counts = _exact_object_fields(
                round_two_distribution[gold],
                {"negative", "positive_only"},
                f"{gold} round-two distribution",
            )
            _require(
                all(type(value) is int and value >= 0 for value in counts.values()),
                "round-two distribution count mismatch",
            )
            round_two_count += sum(cast(int, value) for value in counts.values())
        _require(
            type(selection["round_2_candidate_count"]) is int
            and selection["round_2_candidate_count"] == round_two_count
            and selection["round_2_request_quota_distribution"]
            == round_two_distribution,
            "round-two selection audit mismatch",
        )
        deficits = selection["round_1_post_pipeline_deficits"]
        _require(type(deficits) is dict, "round-one deficits must be an object")
        for gold, raw_counts in deficits.items():
            _require(gold in gold_ids, "round-one deficit gold mismatch")
            counts = _exact_object_fields(
                raw_counts, {"negative", "positive_only"}, "round-one deficit"
            )
            _require(
                all(type(value) is int and value >= 0 for value in counts.values()),
                "round-one deficit count mismatch",
            )
        _require(
            selection["selected_candidate_ids"] == selected_ids
            and selection["selected_candidate_ids_sha256"]
            == canonical_sha256(selected_ids)
            and selection["selected_by_stratum"] == selected_by_stratum,
            "selected identity audit mismatch",
        )
        selection_audit_sha256 = _exact_lowercase_hex(
            validation["selection_audit_sha256"],
            length=64,
            label="selection audit SHA-256",
        )
        _require(
            selection_audit_sha256 == canonical_sha256(selection),
            "selection audit aggregate mismatch",
        )
        task_rows = [
            {
                "task_id": task["candidate_id"],
                "prompt_text": task["prompt_text"],
                "prompt_text_sha256": task["prompt_text_sha256"],
                "semantic_family_id": task["semantic_family_id"],
                "gold_skill_id": task["proposed_gold_skill_id"],
                "negative_skill_id": task["proposed_negative_skill_id"],
                "source_type": "AGENT_GENERATED",
            }
            for task in selected
        ]
        return task_rows, deepcopy(selection)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def build_dataset_freeze_documents(
    validation: dict[str, Any], *, commit_a: str
) -> dict[str, bytes]:
    _require(
        type(validation) is dict,
        "Agent dataset freeze validation container mismatch",
    )
    _require(validation.get("status") == "VALID", "validated Agent pack is required")
    commit_a = _exact_lowercase_hex(
        commit_a,
        length=40,
        label="Commit A",
    )
    task_rows, deterministic_selection = _validated_dataset_freeze_tasks(validation)
    (
        sanitized_run_records,
        agent_run_evidence,
        retry_records,
        agent_run_identity_authority,
    ) = _validated_agent_lineage_evidence(validation)
    task_bytes = b"".join(_canonical_json_bytes(row) for row in task_rows)

    reviewer_ledgers = {
        role: {
            "path": f"blind-v2-review-{'a' if role == 'reviewer_a' else 'b'}.jsonl",
            "sha256": validation["source_file_sha256"][
                f"blind-v2-review-{'a' if role == 'reviewer_a' else 'b'}.jsonl"
            ],
            "schedule_sha256": validation["review_schedule_sha256"][role],
        }
        for role in ("reviewer_a", "reviewer_b")
    }
    contamination = {
        **deepcopy(validation["contamination_audit"]),
        "ledger_file_sha256": validation["source_file_sha256"][
            "blind-v2-contamination.jsonl"
        ],
    }
    selected_three_way_agreement_count = len(task_rows)
    agent_construction = {
        "review_mode": "ISOLATED_AGENT_REVIEW",
        "source_type": "AGENT_GENERATED",
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": selected_three_way_agreement_count,
        "generation_ledger": {
            "path": "blind-v2-generation.jsonl",
            "sha256": validation["source_file_sha256"]["blind-v2-generation.jsonl"],
        },
        "reviewer_ledgers": reviewer_ledgers,
        "agent_run_metadata": {
            "path": "agent-run-metadata.json",
            "sha256": validation["source_file_sha256"]["agent-run-metadata.json"],
        },
        "sanitized_run_records": deepcopy(sanitized_run_records),
        "agent_run_identity_authority": deepcopy(agent_run_identity_authority),
        "agent_roles": deepcopy(agent_run_evidence),
        "transport_retry_count": validation["transport_retry_count"],
        "retry_records": deepcopy(retry_records),
        "contamination": contamination,
        "deterministic_selection": deterministic_selection,
        "deterministic_selection_sha256": canonical_sha256(deterministic_selection),
    }
    review_summary = {
        "schema_version": "router-v2-agent-blind-v2-review-summary-v1",
        "review_mode": "ISOLATED_AGENT_REVIEW",
        "source_type": "AGENT_GENERATED",
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "family_count": POSITIVE_TASK_COUNT,
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": selected_three_way_agreement_count,
        "excluded_candidate_count": validation["excluded_candidate_count"],
        "agent_roles": deepcopy(agent_run_evidence),
        "reviewer_ledgers": reviewer_ledgers,
        "transport_retry_count": validation["transport_retry_count"],
        "retry_records": deepcopy(retry_records),
    }
    review_bytes = _canonical_json_bytes(review_summary)
    manifest = {
        "schema_version": "router-v2-agent-blind-v2-manifest-v1",
        "commit_a": commit_a,
        "dataset_sha256": _sha256_bytes(task_bytes),
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "gold_distribution": validation["gold_distribution"],
        "negative_distribution": validation["negative_distribution"],
        "family_count": POSITIVE_TASK_COUNT,
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": selected_three_way_agreement_count,
        "excluded_candidate_count": validation["excluded_candidate_count"],
        "source_file_sha256": validation["source_file_sha256"],
        "per_row_prompt_sha256": [row["prompt_text_sha256"] for row in task_rows],
        "blind_v2_data_first_read_timestamp": validation["first_read_timestamp"],
        "prompts_committed": True,
        "agent_construction": agent_construction,
        "model_scores_observed": False,
        "evaluation_started": False,
        "retraining_after_data_access": False,
        "gate_changed_after_data_access": False,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    return {
        "blind-v2-tasks.jsonl": task_bytes,
        "blind-v2-review-summary.json": review_bytes,
        "blind-v2-manifest.json": manifest_bytes,
    }


def validate_frozen_dataset_documents(
    validation: dict[str, Any], documents: dict[str, bytes]
) -> list[dict[str, Any]]:
    _require(
        set(documents)
        == {
            "blind-v2-tasks.jsonl",
            "blind-v2-review-summary.json",
            "blind-v2-manifest.json",
        },
        "frozen dataset document set mismatch",
    )
    manifest = _json_no_duplicate_keys(
        documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    commit_a = manifest.get("commit_a")
    _require(type(commit_a) is str, "frozen dataset Commit A binding is missing")
    rebuilt = build_dataset_freeze_documents(validation, commit_a=cast(str, commit_a))
    for name, expected in rebuilt.items():
        _require(documents[name] == expected, f"frozen dataset bytes mismatch: {name}")
    return cast(list[dict[str, Any]], validation["tasks"])


def write_dataset_freeze(documents: dict[str, bytes], output_dir: Path | str) -> None:
    root = Path(output_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in (
        "blind-v2-tasks.jsonl",
        "blind-v2-review-summary.json",
        "blind-v2-manifest.json",
    ):
        payload = documents[name]
        with (root / name).open("xb") as handle:
            handle.write(payload)


def write_authoring_templates() -> list[Path]:
    root = AUTHORING_TEMPLATE_ROOT
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    authored = root / "blind-v2-authored.template.csv"
    review = root / "blind-v2-independent-review.template.csv"
    metadata = root / "reviewer-metadata.template.json"
    guide = root / "blind-v2-human-authoring-guide.md"
    authored.write_text(",".join(AUTHORED_FIELDS) + "\n", encoding="utf-8")
    review.write_text(",".join(REVIEW_FIELDS) + "\n", encoding="utf-8")
    metadata.write_bytes(
        _canonical_json_bytes(
            {
                "author_ids": [],
                "reviewer_ids": [],
                "human_author_count": 0,
                "independent_human_reviewer_count": 0,
                "authors_and_reviewers_are_different_people": False,
                "review_date": "",
                "reviewer_saw_model_rankings": False,
                "reviewer_saw_pilot_002_task_level_results": False,
                "reviewer_used_ai_assistance": False,
                "reviewer_qualification": "",
                "dataset_license": "",
                "publication_permission": False,
                "prompts_may_be_public_after_evaluation": False,
            }
        )
    )
    guide.write_text(
        "# Router V2 blind-v2 human authoring guide\n\n"
        "Humans must author candidate tasks and a different human must independently "
        "review labels. Do not include model scores, rankings, skill ids/names, benchmark "
        "metadata, old prompts, or AI-generated replacement rows. Freeze exactly 64 "
        "accepted tasks, 48 negative labels, 16 skills x 4 tasks, and 64 disjoint families.\n",
        encoding="utf-8",
    )
    return [authored, review, metadata, guide]


def _manifest_rows_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return _sha256_bytes(payload)


def _verify_model_files(
    model_root: Path, rows: list[dict[str, Any]], expected_hash: str
) -> None:
    _require(
        _manifest_rows_hash(rows) == expected_hash, "model file manifest hash mismatch"
    )
    for row in rows:
        relative = Path(row["path"])
        _require(
            not relative.is_absolute() and ".." not in relative.parts,
            "model file path is unsafe",
        )
        target = model_root / relative
        _require(target.is_file(), f"missing model file: {relative}")
        _require(
            target.stat().st_size == row["size"],
            f"model file size mismatch: {relative}",
        )
        _require(
            _sha256_file(target) == row["sha256"],
            f"model file hash mismatch: {relative}",
        )


def _repository_file(repository_root: Path, relative_value: Any, *, label: str) -> Path:
    _require(
        type(relative_value) is str and bool(relative_value), f"{label} path mismatch"
    )
    relative = Path(relative_value)
    _require(
        not relative.is_absolute() and ".." not in relative.parts,
        f"{label} path must be repository-relative",
    )
    resolved = (repository_root / relative).resolve(strict=True)
    _require(
        resolved.is_relative_to(repository_root.resolve(strict=True)),
        f"{label} path escapes repository",
    )
    _require(resolved.is_file(), f"{label} path must be a file")
    return resolved


def _artifact_binding(
    artifacts: list[dict[str, Any]], arm: str, seed: int
) -> dict[str, Any]:
    matches = [
        row for row in artifacts if row.get("arm") == arm and row.get("seed") == seed
    ]
    _require(len(matches) == 1, f"pilot {arm}/{seed} artifact binding mismatch")
    return matches[0]


def validate_preregistration_authority(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    verify_model_files: bool = True,
    canonical_path_required: bool = True,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    if canonical_path_required:
        _require(
            preregistration_file
            == (repository / PREREGISTRATION_RELATIVE).resolve(strict=True),
            "preregistration must use the canonical repository path",
        )
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    semantic_sha256 = preregistration.get("preregistration_sha256")
    _require(type(semantic_sha256) is str, "preregistration semantic hash is missing")
    unhashed = {
        key: value
        for key, value in preregistration.items()
        if key != "preregistration_sha256"
    }
    _require(
        canonical_sha256(unhashed) == semantic_sha256,
        "preregistration semantic hash mismatch",
    )
    validate_preregistration_truth(preregistration)

    contract = preregistered_evaluation_contract()
    _require(
        preregistration.get("preregistration_parent_git_commit")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("current_git_commit_before_commit_a")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("origin_main_git_commit")
        == PREREGISTRATION_PARENT_COMMIT,
        "preregistration parent Git binding mismatch",
    )
    _require(
        preregistration.get("blind_v2_expected_task_count") == 64
        and preregistration.get("blind_v2_expected_negative_labeled_task_count") == 48,
        "blind-v2 count binding mismatch",
    )
    _require(
        preregistration.get("statistics") == contract["statistics"],
        "statistics binding mismatch",
    )
    _require(
        preregistration.get("latency_measurement_protocol") == contract["latency"],
        "latency protocol binding mismatch",
    )
    _require(
        preregistration.get("evaluation_output_namespace")
        == str(FINAL_NAMESPACE_RELATIVE),
        "canonical namespace binding mismatch",
    )
    expected_metric_definitions = {
        "raw_count_first": True,
        "positive_denominator": 64,
        "negative_denominator": 48,
        "fields": [
            "recall_at_1",
            "recall_at_5",
            "mrr",
            "ndcg_at_5",
            "negative_hit_at_1",
            "negative_hit_at_5",
            "first_negative_rank",
            "latency_p50_ms",
            "latency_p95_ms",
        ],
        "aggregate_mean": "arithmetic",
        "aggregate_std": "sample_n_minus_1",
    }
    _require(
        preregistration.get("metric_definitions") == expected_metric_definitions,
        "metric definition binding mismatch",
    )
    for field, expected_truth in (
        ("retraining_allowed", False),
        ("threshold_change_allowed", False),
        ("best_seed_selection_allowed", False),
        ("posthoc_tuning_allowed", False),
        ("blind_v3_allowed", False),
        ("default_router_unchanged", True),
        ("production_ready", False),
        ("release_eligible", False),
        ("router_promotion_requires_separate_human_decision", True),
    ):
        _require(
            preregistration.get(field) is expected_truth,
            f"preregistration truth binding mismatch: {field}",
        )
    _require(preregistration.get("gate") == contract["gate"], "gate binding mismatch")
    evaluator = preregistration.get("evaluator")
    _require(type(evaluator) is dict, "evaluator binding is missing")
    evaluator = cast(dict[str, Any], evaluator)
    _require(
        evaluator.get("contract_sha256") == canonical_sha256(contract),
        "evaluator contract hash mismatch",
    )
    gate_artifact = preregistration.get("pilot_002_gate_artifact")
    _require(type(gate_artifact) is dict, "pilot-002 gate artifact binding is missing")
    gate_artifact = cast(dict[str, Any], gate_artifact)
    _require(
        gate_artifact.get("gate_semantic_sha256") == canonical_sha256(contract["gate"]),
        "gate binding mismatch",
    )
    gate_file = _repository_file(
        repository, gate_artifact.get("path"), label="gate artifact"
    )
    _require(
        _sha256_file(gate_file) == gate_artifact.get("file_sha256"),
        "gate artifact file hash mismatch",
    )
    gate_document = _json_no_duplicate_keys(gate_file.read_bytes(), "gate artifact")
    _require(gate_document.get("gate") == contract["gate"], "gate binding mismatch")
    _require(
        gate_document.get("plan_sha256") == gate_artifact.get("plan_semantic_sha256"),
        "gate plan semantic hash mismatch",
    )

    query = preregistration.get("query_contract")
    _require(type(query) is dict, "query contract binding is missing")
    query = cast(dict[str, Any], query)
    _require(
        query.get("version") == QUERY_CONTRACT_VERSION,
        "query contract version mismatch",
    )
    query_file = _repository_file(repository, query.get("path"), label="query contract")
    _require(
        _sha256_file(query_file) == query.get("sha256"),
        "query contract source hash mismatch",
    )
    skill_index = preregistration.get("skill_index")
    _require(type(skill_index) is dict, "skill index binding is missing")
    skill_index = cast(dict[str, Any], skill_index)
    skill_index_file = _repository_file(
        repository, skill_index.get("path"), label="skill index"
    )
    _require(
        _sha256_file(skill_index_file) == skill_index.get("sha256"),
        "skill index hash mismatch",
    )
    skill_builder = preregistration.get("skill_representation_builder")
    _require(type(skill_builder) is dict, "skill builder binding is missing")
    skill_builder = cast(dict[str, Any], skill_builder)
    _require(
        skill_builder.get("version") == SKILL_REPRESENTATION_BUILDER_VERSION,
        "skill builder version mismatch",
    )
    skill_builder_file = _repository_file(
        repository, skill_builder.get("path"), label="skill builder"
    )
    _require(
        _sha256_file(skill_builder_file) == skill_builder.get("sha256"),
        "skill builder source hash mismatch",
    )
    source_files = evaluator.get("source_files")
    _require(
        type(source_files) is list and bool(source_files),
        "evaluator sources are missing",
    )
    _require(
        {cast(dict[str, Any], row).get("path") for row in cast(list[Any], source_files)}
        == set(EVALUATOR_SOURCE_PATHS),
        "evaluator source set mismatch",
    )
    for raw_row in cast(list[Any], source_files):
        row = cast(dict[str, Any], raw_row)
        _require(type(row) is dict, "evaluator source binding mismatch")
        source = _repository_file(repository, row.get("path"), label="evaluator source")
        _require(
            _sha256_file(source) == row.get("sha256"),
            "evaluator source hash mismatch",
        )

    frozen_inputs = preregistration.get("frozen_inputs")
    _require(type(frozen_inputs) is dict, "frozen input bindings are missing")
    frozen_inputs = cast(dict[str, Any], frozen_inputs)
    for key in (
        "training_data_manifest",
        "accepted_pairs",
        "heldout_labels",
        "pilot_002_manifest",
        "pilot_002_truth_erratum",
        "pilot_002_evaluation_summary",
        "pilot_002_per_seed",
        "pilot_002_result_report",
        "pilot_002_route_results",
    ):
        binding = frozen_inputs.get(key)
        _require(type(binding) is dict, f"frozen {key} binding is missing")
        binding = cast(dict[str, Any], binding)
        frozen_file = _repository_file(
            repository, binding.get("path"), label=f"frozen {key}"
        )
        _require(
            _sha256_file(frozen_file) == binding.get("sha256"),
            f"frozen {key} hash mismatch",
        )

    phase16_files = preregistration.get("old_phase16_prompt_files")
    _require(
        type(phase16_files) is list and len(phase16_files) == 16,
        "old Phase 16 prompt bindings are missing",
    )
    phase16_paths: set[str] = set()
    for raw_binding in cast(list[Any], phase16_files):
        _require(type(raw_binding) is dict, "old Phase 16 prompt binding mismatch")
        binding = cast(dict[str, Any], raw_binding)
        phase16_file = _repository_file(
            repository, binding.get("path"), label="old Phase 16 prompt"
        )
        relative = phase16_file.relative_to(repository).as_posix()
        _require(relative not in phase16_paths, "old Phase 16 prompt path duplicated")
        phase16_paths.add(relative)
        _require(
            _sha256_file(phase16_file) == binding.get("sha256"),
            "old Phase 16 prompt hash mismatch",
        )

    pilot_binding = cast(dict[str, Any], frozen_inputs["pilot_002_manifest"])
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    _require(
        pilot_file
        == (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
        == _repository_file(
            repository, pilot_binding.get("path"), label="pilot-002 manifest"
        ),
        "pilot-002 manifest path is not preregistered",
    )
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    _require(
        pilot.get("manifest_sha256") == pilot_binding.get("semantic_sha256"),
        "pilot-002 manifest semantic hash mismatch",
    )

    base_binding = preregistration.get("base_model")
    _require(type(base_binding) is dict, "base model binding is missing")
    base_binding = cast(dict[str, Any], base_binding)
    base = pilot.get("base_model")
    _require(type(base) is dict, "pilot base model binding is missing")
    base = cast(dict[str, Any], base)
    _require(
        base_binding.get("model_id") == base.get("id")
        and base_binding.get("revision") == base.get("revision")
        and base_binding.get("checkpoint_path") == base.get("path")
        and base_binding.get("model_file_manifest_sha256")
        == base.get("file_manifest_sha256")
        and base_binding.get("model_files") == base.get("file_manifest_rows"),
        "base model binding mismatch",
    )
    artifacts = pilot.get("training_artifacts")
    _require(type(artifacts) is list, "pilot training artifacts are missing")
    artifacts = cast(list[dict[str, Any]], artifacts)
    arm_a_bindings = base_binding.get("per_seed_model_manifest_bindings")
    _require(
        type(arm_a_bindings) is list
        and {
            cast(dict[str, Any], row).get("seed")
            for row in cast(list[Any], arm_a_bindings)
        }
        == set(SEEDS),
        "Arm A model manifest grid mismatch",
    )
    for raw_preregistered in cast(list[Any], arm_a_bindings):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "A", preregistered["seed"])
        for field in (
            "model_path",
            "model_manifest_path",
            "model_manifest_file_sha256",
            "model_manifest_sha256",
            "model_file_manifest_sha256",
        ):
            _require(
                preregistered.get(field) == actual.get(field),
                "Arm A model manifest binding mismatch",
            )
    arm_c = preregistration.get("arm_c_checkpoints")
    _require(type(arm_c) is list and len(arm_c) == 3, "Arm C bindings are missing")
    for raw_preregistered in cast(list[Any], arm_c):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "C", preregistered["seed"])
        expected_checkpoint = {
            "checkpoint_path": actual["model_path"],
            "model_manifest_path": actual["model_manifest_path"],
            "model_manifest_file_sha256": actual["model_manifest_file_sha256"],
            "model_manifest_sha256": actual["model_manifest_sha256"],
            "model_file_manifest_sha256": actual["model_file_manifest_sha256"],
            "model_files": actual["model_file_manifest"],
        }
        _require(
            all(
                preregistered.get(field) == value
                for field, value in expected_checkpoint.items()
            ),
            "Arm C checkpoint binding mismatch",
        )

    if verify_model_files:
        base_path = Path(cast(str, base["path"]))
        _verify_model_files(
            base_path,
            cast(list[dict[str, Any]], base["file_manifest_rows"]),
            cast(str, base["file_manifest_sha256"]),
        )
        for arm in ARMS:
            for seed in SEEDS:
                artifact = _artifact_binding(artifacts, arm, seed)
                model_path = Path(artifact["model_path"])
                _verify_model_files(
                    model_path,
                    artifact["model_file_manifest"],
                    artifact["model_file_manifest_sha256"],
                )
                model_manifest = Path(artifact["model_manifest_path"])
                _require(
                    model_manifest.is_file()
                    and _sha256_file(model_manifest)
                    == artifact["model_manifest_file_sha256"],
                    f"{arm}/{seed} model manifest file hash mismatch",
                )
    return {
        "status": "VALID",
        "preregistration_sha256": semantic_sha256,
        "pilot_manifest_sha256": pilot_binding["sha256"],
        "preregistration_file_sha256": _sha256_file(preregistration_file),
        "model_files_verified": verify_model_files,
    }


def load_preregistered_human_validation_inputs(
    preregistration_path: Path | str, *, repository_root: Path | str
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    frozen = cast(dict[str, Any], preregistration["frozen_inputs"])
    skills_binding = cast(dict[str, Any], preregistration["skill_index"])
    skills = _json_no_duplicate_keys(
        b'{"skills":'
        + _repository_file(
            repository, skills_binding["path"], label="skill index"
        ).read_bytes()
        + b"}",
        "skill index wrapper",
    )["skills"]
    _require(type(skills) is list, "skill index must be a JSON array")

    accepted_binding = cast(dict[str, Any], frozen["accepted_pairs"])
    accepted_rows = _jsonl_no_duplicate_keys(
        _repository_file(
            repository, accepted_binding["path"], label="accepted pairs"
        ).read_bytes(),
        "accepted pairs",
    )
    heldout_binding = cast(dict[str, Any], frozen["heldout_labels"])
    heldout_rows = _jsonl_no_duplicate_keys(
        _repository_file(
            repository, heldout_binding["path"], label="heldout labels"
        ).read_bytes(),
        "heldout labels",
    )
    phase16_prompts = [
        _repository_file(
            repository,
            cast(dict[str, Any], raw_binding)["path"],
            label="old Phase 16 prompt",
        ).read_text(encoding="utf-8")
        for raw_binding in cast(list[Any], preregistration["old_phase16_prompt_files"])
    ]
    return {
        "preregistration": preregistration,
        "canonical_skills": cast(list[dict[str, Any]], skills),
        "train_prompts": [str(row["query_text"]) for row in accepted_rows],
        "pilot_prompts": [str(row["query_text"]) for row in heldout_rows],
        "train_family_ids": {
            str(row["positive_source_record_id"]) for row in accepted_rows
        },
        "pilot_family_ids": {
            str(row["positive_source_record_id"]) for row in heldout_rows
        },
        "phase16_prompts": phase16_prompts,
    }


def read_frozen_dataset_documents(repository_root: Path | str) -> dict[str, bytes]:
    repository = Path(repository_root).resolve(strict=True)
    root = (repository / DATASET_FREEZE_RELATIVE).resolve(strict=True)
    _require(root.is_relative_to(repository), "frozen dataset root escapes repository")
    actual = {path.name for path in root.iterdir() if path.is_file()}
    _require(
        actual == set(DATASET_FREEZE_FILENAMES),
        "frozen dataset directory must contain exactly three files",
    )
    return {
        filename: (root / filename).read_bytes()
        for filename in DATASET_FREEZE_FILENAMES
    }


def build_authoritative_lineage_bindings(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    frozen_documents: dict[str, bytes],
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    authority = validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    blind_manifest = _json_no_duplicate_keys(
        frozen_documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    agent_construction = deepcopy(blind_manifest["agent_construction"])
    _require(
        type(agent_construction) is dict,
        "blind-v2 Agent construction lineage is missing",
    )
    agent_construction["review_summary_file_sha256"] = _sha256_bytes(
        frozen_documents["blind-v2-review-summary.json"]
    )
    artifacts = cast(list[dict[str, Any]], pilot["training_artifacts"])
    model_bindings = []
    for seed in SEEDS:
        for arm in ARMS:
            artifact = _artifact_binding(artifacts, arm, seed)
            model_bindings.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "model_path": artifact["model_path"],
                    "model_manifest_path": artifact["model_manifest_path"],
                    "model_manifest_file_sha256": artifact[
                        "model_manifest_file_sha256"
                    ],
                    "model_manifest_sha256": artifact["model_manifest_sha256"],
                    "model_file_manifest_sha256": artifact[
                        "model_file_manifest_sha256"
                    ],
                    "model_files": artifact["model_file_manifest"],
                }
            )
    return {
        "preregistration": {
            "path": preregistration_file.relative_to(repository).as_posix(),
            "file_sha256": authority["preregistration_file_sha256"],
            "semantic_sha256": authority["preregistration_sha256"],
        },
        "pilot_manifest": cast(dict[str, Any], preregistration["frozen_inputs"])[
            "pilot_002_manifest"
        ],
        "frozen_inputs": preregistration["frozen_inputs"],
        "old_phase16_prompt_files": preregistration["old_phase16_prompt_files"],
        "base_model": {
            "id": cast(dict[str, Any], pilot["base_model"])["id"],
            "revision": cast(dict[str, Any], pilot["base_model"])["revision"],
            "file_manifest_sha256": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_sha256"
            ],
            "model_files": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_rows"
            ],
        },
        "evaluation_models": model_bindings,
        "blind_v2_dataset": {
            "tasks_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-tasks.jsonl"]
            ),
            "manifest_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-manifest.json"]
            ),
            "dataset_sha256": blind_manifest["dataset_sha256"],
            "source_file_sha256": blind_manifest["source_file_sha256"],
            "per_row_prompt_sha256": blind_manifest["per_row_prompt_sha256"],
        },
        "agent_construction": agent_construction,
        "skill_index": preregistration["skill_index"],
        "query_contract": preregistration["query_contract"],
        "skill_representation_builder": preregistration["skill_representation_builder"],
        "gate": preregistration["pilot_002_gate_artifact"],
        "evaluator": preregistration["evaluator"],
    }


class _LocalSentenceTransformerEncoder:
    def __init__(self, model_path: Path) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real model smoke"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        value = self._model.encode(texts, normalize_embeddings=normalize_embeddings)
        if hasattr(value, "tolist"):
            value = value.tolist()
        return cast(list[list[float]], value)


def run_model_load_smoke(
    pilot_manifest_path: Path | str,
    *,
    preregistration_path: Path | str,
    repository_root: Path | str,
    encoder_factory: EncoderFactory | None = None,
    authority_validator: AuthorityValidator = validate_preregistration_authority,
) -> dict[str, Any]:
    authority_validator(
        preregistration_path,
        repository_root=repository_root,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    manifest = _json_no_duplicate_keys(
        Path(pilot_manifest_path).read_bytes(), "pilot manifest"
    )
    base = manifest["base_model"]
    base_path = Path(base["path"])
    _verify_model_files(
        base_path, base["file_manifest_rows"], base["file_manifest_sha256"]
    )
    c_artifacts = sorted(
        [row for row in manifest["training_artifacts"] if row.get("arm") == "C"],
        key=lambda row: row["seed"],
    )
    _require(
        [row["seed"] for row in c_artifacts] == list(SEEDS), "Arm C smoke grid mismatch"
    )
    for artifact in c_artifacts:
        model_path = Path(artifact["model_path"])
        _verify_model_files(
            model_path,
            artifact["model_file_manifest"],
            artifact["model_file_manifest_sha256"],
        )
        manifest_path = Path(artifact["model_manifest_path"])
        _require(manifest_path.is_file(), "missing model manifest")
        _require(
            _sha256_file(manifest_path) == artifact["model_manifest_file_sha256"],
            "model manifest file hash mismatch",
        )
    factory = encoder_factory or (
        lambda arm, seed, model_path: _LocalSentenceTransformerEncoder(model_path)
    )
    temporary = Path(tempfile.mkdtemp(prefix="hermes-blind-v2-model-smoke-"))
    os.chmod(temporary, 0o700)
    dimensions = []
    models = []
    try:
        materialized = temporary / "arm-A"
        shutil.copytree(base_path, materialized, symlinks=False)
        smoke_bindings = [
            {"arm": "A", "seed": 7170, "model_path": materialized},
            *[
                {
                    "arm": "C",
                    "seed": artifact["seed"],
                    "model_path": Path(artifact["model_path"]),
                }
                for artifact in c_artifacts
            ],
        ]
        for binding in smoke_bindings:
            encoder = factory(binding["arm"], binding["seed"], binding["model_path"])
            embeddings = encoder.encode(
                list(MODEL_LOAD_SMOKE_TEXTS), normalize_embeddings=True
            )
            if hasattr(embeddings, "tolist"):
                embeddings = embeddings.tolist()
            _require(
                type(embeddings) is list and len(embeddings) == 2,
                "smoke embedding row count mismatch",
            )
            _require(
                all(type(row) is list and row for row in embeddings),
                "smoke embeddings must be non-empty vectors",
            )
            dimension = len(embeddings[0])
            _require(
                all(len(row) == dimension for row in embeddings),
                "smoke embedding dimensions differ",
            )
            _require(
                all(math.isfinite(float(value)) for row in embeddings for value in row),
                "smoke embeddings must be finite",
            )
            dimensions.append(dimension)
            models.append({"arm": binding["arm"], "seed": binding["seed"]})
        _require(len(set(dimensions)) == 1, "model embedding dimensions differ")
        return {
            "schema_version": "router-v2-blind-v2-model-load-smoke-v1",
            "smoke_status": "PASS",
            "models": models,
            "embedding_dimension": dimensions[0],
            "device": "cpu",
            "synthetic_strings": list(MODEL_LOAD_SMOKE_TEXTS),
            "benchmark_metrics_computed": False,
            "blind_v2_data_read": False,
        }
    finally:
        shutil.rmtree(temporary)


def build_model_load_smoke_receipt(
    smoke: dict[str, Any], *, commit_a: str, preregistration_sha256: str
) -> dict[str, Any]:
    _require(
        set(smoke)
        == {
            "schema_version",
            "smoke_status",
            "models",
            "embedding_dimension",
            "device",
            "synthetic_strings",
            "benchmark_metrics_computed",
            "blind_v2_data_read",
        },
        "smoke result structure mismatch",
    )
    _require(
        smoke.get("schema_version") == "router-v2-blind-v2-model-load-smoke-v1",
        "smoke schema mismatch",
    )
    _require(smoke.get("smoke_status") == "PASS", "passing smoke is required")
    _require(smoke.get("blind_v2_data_read") is False, "smoke read blind-v2 data")
    _require(
        smoke.get("benchmark_metrics_computed") is False,
        "smoke computed benchmark metrics",
    )
    _require(
        smoke.get("models")
        == [
            {"arm": "A", "seed": 7170},
            {"arm": "C", "seed": 7170},
            {"arm": "C", "seed": 7171},
            {"arm": "C", "seed": 7172},
        ],
        "smoke model grid mismatch",
    )
    _require(
        smoke.get("synthetic_strings") == list(MODEL_LOAD_SMOKE_TEXTS),
        "smoke strings mismatch",
    )
    _require(
        type(commit_a) is str and len(commit_a) == 40,
        "smoke Commit A binding mismatch",
    )
    _require(
        type(preregistration_sha256) is str and len(preregistration_sha256) == 64,
        "smoke preregistration binding mismatch",
    )
    document = {
        "schema_version": "router-v2-blind-v2-model-load-smoke-receipt-v1",
        "commit_a": commit_a,
        "preregistration_sha256": preregistration_sha256,
        "smoke": smoke,
    }
    return {**document, "receipt_sha256": canonical_sha256(document)}


def model_load_smoke_receipt_path(commit_a: str) -> Path:
    _require(type(commit_a) is str and len(commit_a) == 40, "Commit A SHA mismatch")
    return SMOKE_RECEIPT_ROOT / f"{commit_a}.json"


def write_model_load_smoke_receipt(receipt: dict[str, Any]) -> Path:
    commit_a = receipt.get("commit_a")
    _require(type(commit_a) is str, "smoke receipt Commit A is missing")
    path = model_load_smoke_receipt_path(cast(str, commit_a))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(receipt))
    return path


def validate_model_load_smoke_receipt(
    *, commit_a: str, preregistration_sha256: str
) -> dict[str, Any]:
    path = model_load_smoke_receipt_path(commit_a)
    receipt = _json_no_duplicate_keys(path.read_bytes(), "model-load smoke receipt")
    receipt_sha256 = receipt.get("receipt_sha256")
    unhashed = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(
        receipt_sha256 == canonical_sha256(unhashed),
        "model-load smoke receipt hash mismatch",
    )
    _require(
        receipt.get("commit_a") == commit_a
        and receipt.get("preregistration_sha256") == preregistration_sha256,
        "model-load smoke receipt authority mismatch",
    )
    smoke = receipt.get("smoke")
    _require(type(smoke) is dict, "model-load smoke receipt structure mismatch")
    rebuilt = build_model_load_smoke_receipt(
        cast(dict[str, Any], smoke),
        commit_a=commit_a,
        preregistration_sha256=preregistration_sha256,
    )
    _require(receipt == rebuilt, "model-load smoke receipt structure mismatch")
    return receipt


class _SentenceTransformerScorer:
    def __init__(self, model_path: Path, skills: list[dict[str, Any]]) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real evaluation"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )
        self._skill_ids = [str(row["id"]) for row in skills]
        value = self._model.encode(
            [_skill_text(row) for row in skills], normalize_embeddings=True
        )
        if hasattr(value, "tolist"):
            value = value.tolist()
        self._skill_vectors = cast(list[list[float]], value)

    def rank(self, query: str, skill_ids: list[str]) -> list[str]:
        _require(skill_ids == self._skill_ids, "skill order changed during evaluation")
        value = self._model.encode([query], normalize_embeddings=True)
        if hasattr(value, "tolist"):
            value = value.tolist()
        query_vector = cast(list[list[float]], value)[0]
        scores = [
            quantize8(
                sum(
                    float(left) * float(right)
                    for left, right in zip(query_vector, vector, strict=True)
                )
            )
            for vector in self._skill_vectors
        ]
        return [
            skill_id
            for skill_id, _ in sorted(
                zip(self._skill_ids, scores, strict=True),
                key=lambda item: (-Decimal(item[1]), item[0]),
            )
        ]


def evaluate_routes(
    tasks: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
    *,
    scorer_factory: ScorerFactory | None = None,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> list[dict[str, Any]]:
    _require(
        len(tasks) == POSITIVE_TASK_COUNT,
        f"evaluation requires {POSITIVE_TASK_COUNT} tasks",
    )
    ordered_tasks = sorted(tasks, key=lambda row: row["task_id"])
    _require(
        len({row["task_id"] for row in ordered_tasks}) == POSITIVE_TASK_COUNT,
        "evaluation task ids must be unique",
    )
    ordered_skills = sorted(skills, key=lambda row: row["id"])
    skill_ids = [str(row["id"]) for row in ordered_skills]
    _require(
        len(skill_ids) == 16 and len(set(skill_ids)) == 16,
        "evaluation requires 16 skills",
    )
    binding_grid = {(row.get("arm"), row.get("seed")): row for row in model_bindings}
    _require(
        set(binding_grid) == {(arm, seed) for seed in SEEDS for arm in ARMS},
        "evaluation model bindings must be the complete A/C seed grid",
    )
    routes = []
    for seed in SEEDS:
        for arm in ARMS:
            binding = binding_grid[(arm, seed)]
            model_path = Path(binding["model_path"])
            scorer = (
                scorer_factory(arm, seed, model_path)
                if scorer_factory is not None
                else _SentenceTransformerScorer(model_path, ordered_skills)
            )
            for task in ordered_tasks:
                query = router_query_text(task["prompt_text"])
                scorer.rank(query, skill_ids)
                start = clock_ns()
                ranked = scorer.rank(query, skill_ids)
                end = clock_ns()
                _require(
                    len(ranked) == 16 and set(ranked) == set(skill_ids),
                    "scorer ranking must contain every skill once",
                )
                gold = task["gold_skill_id"]
                negative = task.get("negative_skill_id")
                routes.append(
                    {
                        "arm": arm,
                        "seed": seed,
                        "task_id": task["task_id"],
                        "gold_skill_id": gold,
                        "tempting_negative_skill_id": negative,
                        "semantic_family_id": task["semantic_family_id"],
                        "gold_rank": ranked.index(gold) + 1,
                        "tempting_negative_rank": (
                            ranked.index(negative) + 1 if negative is not None else None
                        ),
                        "latency_ns": end - start,
                    }
                )
    return routes


def _validate_evaluation_agent_construction_authority(
    frozen_bindings: dict[str, Any], input_artifacts: dict[str, bytes]
) -> None:
    message = "evaluation Agent construction lineage mismatch"
    try:
        _require(type(frozen_bindings) is dict, message)
        _require(type(input_artifacts) is dict, message)
        manifest_bytes = input_artifacts["blind-v2-manifest.json"]
        review_summary_bytes = input_artifacts["review-summary.json"]
        dataset_binding = frozen_bindings.get("blind_v2_dataset")
        _require(type(dataset_binding) is dict, message)
        dataset_document = cast(dict[str, Any], dataset_binding)
        manifest_file_sha256 = _exact_lowercase_hex(
            dataset_document.get("manifest_file_sha256"),
            length=64,
            label="evaluation blind-v2 manifest file SHA-256",
        )
        _require(
            manifest_file_sha256 == _sha256_bytes(manifest_bytes),
            message,
        )
        manifest = _json_no_duplicate_keys(manifest_bytes, "blind-v2 manifest")
        review_summary = _json_no_duplicate_keys(
            review_summary_bytes, "blind-v2 review summary"
        )
        for document in (manifest, review_summary):
            for field, expected in (
                ("task_count", POSITIVE_TASK_COUNT),
                ("negative_labeled_task_count", TEMPTING_NEGATIVE_COUNT),
                ("family_count", POSITIVE_TASK_COUNT),
                ("human_author_count", 0),
                ("human_reviewer_count", 0),
                ("exact_three_way_agreement_count", POSITIVE_TASK_COUNT),
            ):
                _require(
                    type(document.get(field)) is int and document[field] == expected,
                    message,
                )
        construction = manifest.get("agent_construction")
        _require(type(construction) is dict, message)
        manifest_construction = cast(dict[str, Any], construction)
        _require(
            manifest_construction.get("review_mode") == "ISOLATED_AGENT_REVIEW"
            and manifest_construction.get("source_type") == "AGENT_GENERATED"
            and type(manifest_construction.get("human_author_count")) is int
            and manifest_construction["human_author_count"] == 0
            and type(manifest_construction.get("human_reviewer_count")) is int
            and manifest_construction["human_reviewer_count"] == 0
            and type(manifest_construction.get("exact_three_way_agreement_count"))
            is int
            and manifest_construction["exact_three_way_agreement_count"]
            == POSITIVE_TASK_COUNT,
            message,
        )
        _require(
            review_summary.get("review_mode") == "ISOLATED_AGENT_REVIEW"
            and review_summary.get("source_type") == "AGENT_GENERATED",
            message,
        )

        agent_roles = manifest_construction.get("agent_roles")
        _require(
            type(agent_roles) is dict and set(agent_roles) == set(AGENT_CONFIGS),
            message,
        )
        role_evidence = cast(dict[str, Any], agent_roles)
        for role, config in AGENT_CONFIGS.items():
            evidence = role_evidence.get(role)
            _require(type(evidence) is dict, message)
            role_document = cast(dict[str, Any], evidence)
            _require(
                role_document.get("config") == config
                and role_document.get("requested_models") == [config["model"]]
                and role_document.get("returned_models") == [config["model"]]
                and role_document.get("reasoning_effort") == config["reasoning_effort"],
                message,
            )
            for hash_field in (
                "system_prompt_sha256",
                "response_schema_sha256",
                "request_hashes_sha256",
                "response_hashes_sha256",
                "run_sha256",
            ):
                _exact_lowercase_hex(
                    role_document.get(hash_field),
                    length=64,
                    label=f"evaluation {role} {hash_field}",
                )
            sessions = role_document.get("session_or_thread_ids")
            _require(
                type(sessions) is list
                and bool(sessions)
                and all(
                    type(identity) is str and bool(identity.strip())
                    for identity in sessions
                ),
                message,
            )

        reviewer_ledgers = manifest_construction.get("reviewer_ledgers")
        _require(
            type(reviewer_ledgers) is dict
            and set(reviewer_ledgers) == {"reviewer_a", "reviewer_b"},
            message,
        )
        ledger_evidence = cast(dict[str, Any], reviewer_ledgers)
        for role, suffix in (("reviewer_a", "a"), ("reviewer_b", "b")):
            raw_ledger = ledger_evidence[role]
            _require(type(raw_ledger) is dict, message)
            ledger = cast(dict[str, Any], raw_ledger)
            _require(
                ledger.get("path") == f"blind-v2-review-{suffix}.jsonl",
                message,
            )
            _exact_lowercase_hex(
                ledger.get("sha256"), length=64, label=f"evaluation {role} ledger"
            )
            _exact_lowercase_hex(
                ledger.get("schedule_sha256"),
                length=64,
                label=f"evaluation {role} schedule",
            )

        _require(
            review_summary.get("agent_roles") == role_evidence
            and review_summary.get("reviewer_ledgers") == ledger_evidence
            and review_summary.get("transport_retry_count")
            == manifest_construction.get("transport_retry_count")
            and review_summary.get("retry_records")
            == manifest_construction.get("retry_records"),
            message,
        )

        expected_binding = deepcopy(manifest_construction)
        expected_binding["review_summary_file_sha256"] = _sha256_bytes(
            review_summary_bytes
        )
        _require(
            frozen_bindings.get("agent_construction") == expected_binding,
            message,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def build_evaluation_documents(
    route_rows: list[dict[str, Any]],
    *,
    commit_a: str,
    commit_b: str,
    evaluator_commit: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_artifacts: dict[str, bytes],
) -> dict[str, bytes]:
    _require(
        type(input_artifacts) is dict
        and set(input_artifacts)
        == {"preregistration.json", "blind-v2-manifest.json", "review-summary.json"},
        "evaluation input artifact set mismatch",
    )
    _require(
        type(attempt_artifacts) is dict
        and set(attempt_artifacts)
        == {"attempt-1.started.json", "attempt-1.terminal.json"},
        "attempt artifact set mismatch",
    )
    _validate_evaluation_agent_construction_authority(frozen_bindings, input_artifacts)
    per_seed = [
        build_per_seed_result(
            [row for row in route_rows if row["arm"] == arm and row["seed"] == seed]
        )
        for seed in SEEDS
        for arm in ARMS
    ]
    aggregate = build_aggregate_results(per_seed)
    paired = build_paired_results(route_rows)
    statistics = build_statistics(route_rows)
    failures = build_failure_slices(route_rows)
    gate = apply_preregistered_gate(per_seed)
    summary = {
        "schema_version": "router-v2-blind-v2-evaluation-summary-v1",
        **gate,
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "claim_scope": "AGENT_CONSTRUCTED_DUAL_AGENT_UNANIMOUS_BLIND_SET_ONLY",
        "same_provider_limitation": (
            "Generator gpt-5.6-sol/max, Reviewer A gpt-5.6-sol/ultra, and "
            "Reviewer B gpt-5.6-luna/max are OpenAI configurations, so their "
            "review judgments are not statistically independent."
        ),
    }
    report = (
        "# Router V2 final blind-v2\n\n"
        f"Research conclusion: `{gate['research_conclusion']}`\n\n"
        f"Dataset: {POSITIVE_TASK_COUNT} tasks, including "
        f"{TEMPTING_NEGATIVE_COUNT} negative-labeled tasks, constructed by one Agent "
        "generator and accepted only by two role-isolated Agent reviewers with unanimous "
        "labels.\n\n"
        "Limitation: Generator gpt-5.6-sol/max, Reviewer A gpt-5.6-sol/ultra, and "
        "Reviewer B gpt-5.6-luna/max are OpenAI configurations from the same provider; "
        "their judgments are not statistically independent. Scope is limited to this "
        "Agent-constructed distribution.\n\n"
        "Default router remains unchanged. This is not a production, release, or SOTA claim.\n"
    ).encode("utf-8")
    result_documents = {
        "per-seed.json": _canonical_json_bytes(per_seed),
        "aggregate.json": _canonical_json_bytes(aggregate),
        "paired.json": _canonical_json_bytes(paired),
        "statistics.json": _canonical_json_bytes(statistics),
        "failure-slices.json": _canonical_json_bytes(failures),
        "evaluation-summary.json": _canonical_json_bytes(summary),
        "result-report.md": report,
    }
    documents = {**input_artifacts, **result_documents}
    lineage = build_lineage_manifest(
        commit_a=commit_a,
        commit_b=commit_b,
        evaluator_commit=evaluator_commit,
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=frozen_bindings,
        artifacts={**documents, **attempt_artifacts},
    )
    return {**documents, "lineage-manifest.json": _canonical_json_bytes(lineage)}


def _write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(value))


def build_attempt_started_document(started_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "router-v2-blind-v2-attempt-started-v1",
        "attempt_number": 1,
        "maximum_attempts": 1,
        **started_payload,
    }


def build_attempt_terminal_document(artifact_count: int) -> dict[str, Any]:
    _require(
        artifact_count == len(EVALUATION_OUTPUT_FILENAMES), "artifact count mismatch"
    )
    return {
        "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
        "attempt_number": 1,
        "status": "COMPLETED",
        "artifact_count": artifact_count,
    }


def _assert_output_safe(
    output_root: Path, repository_root: Path, protected_roots: list[Path]
) -> Path:
    repository = repository_root.resolve(strict=True)
    resolved = output_root.resolve(strict=False)
    canonical = (repository / FINAL_NAMESPACE_RELATIVE).resolve(strict=False)
    _require(
        resolved == canonical,
        "evaluation output must use the canonical namespace",
    )
    for root in protected_roots:
        protected = root.resolve(strict=False)
        _require(
            not resolved.is_relative_to(protected),
            "evaluation output may not be inside a protected root",
        )
    return resolved


def run_single_attempt(
    output_root: Path | str,
    *,
    repository_root: Path | str,
    started_payload: dict[str, Any],
    evaluate: Callable[[], dict[str, bytes]],
    protected_roots: list[Path],
) -> dict[str, Any]:
    output = _assert_output_safe(
        Path(output_root), Path(repository_root), protected_roots
    )
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    started = build_attempt_started_document(started_payload)
    _write_exclusive_json(output / "attempt-1.started.json", started)
    try:
        documents = evaluate()
        _require(type(documents) is dict, "evaluation must return artifact bytes")
        for name, payload in sorted(documents.items()):
            _require(
                type(name) is str
                and "/" not in name
                and name not in {"attempt-1.started.json", "attempt-1.terminal.json"},
                "evaluation artifact path is invalid",
            )
            _require(
                type(payload) is bytes, "evaluation artifact payload must be bytes"
            )
            with (output / name).open("xb") as handle:
                handle.write(payload)
        _require(
            set(documents) == set(EVALUATION_OUTPUT_FILENAMES),
            "evaluation output artifact set mismatch",
        )
        terminal = build_attempt_terminal_document(len(documents))
        _write_exclusive_json(output / "attempt-1.terminal.json", terminal)
        return terminal
    except Exception as exc:
        terminal = {
            "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
            "attempt_number": 1,
            "status": "INFRASTRUCTURE_FAILURE",
            "research_conclusion": "BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_allowed": False,
        }
        terminal_path = output / "attempt-1.terminal.json"
        if not terminal_path.exists():
            _write_exclusive_json(terminal_path, terminal)
        raise


def human_pack_root_from_environment(repository_root: Path | str) -> Path | None:
    value = os.environ.get("HERMES_BLIND_V2_ROOT")
    if not value:
        return None
    root = Path(value)
    _require(root.is_absolute(), "HERMES_BLIND_V2_ROOT must be absolute")
    if not root.exists() or any(
        not (root / name).is_file() for name in LEGACY_REQUIRED_HUMAN_PACK_FILES
    ):
        return None
    _outside_repository(root, Path(repository_root))
    return root
