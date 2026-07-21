"""Run002-only blind-v2 Generator response and host identity contract."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, cast


RUN_ID = "router-v2-v4-successor-blind-v2-002"
RUN001_RUN_ID = "router-v2-v4-successor-blind-v2-001"
RUN001_COMMIT_A = "a7052b067178ddcbf60d303b7844fe5966bb2a71"
RUN001_TERMINAL_SHA256 = (
    "74b8e9fb01e008ee40c1f38c65c73a9fde371c615e4689f847ab88887cefa6ea"
)
RUN001_PRIVATE_EVIDENCE_ROOT = (
    Path.home() / ".codex/private/hermes-blind-v2-successor" / RUN001_COMMIT_A
)
PRIVATE_EVIDENCE_BASE = (
    Path.home() / ".codex/private/hermes-blind-v2-successor-run002" / RUN_ID
)
OUTPUT_NAMESPACE = Path("artifacts/router-v2-blind-v2") / RUN_ID
DATASET_FREEZE_RELATIVE = Path("data/router-v2-blind-v2-successor-002")
DATASET_FREEZE_FILENAMES = (
    "blind-v2-tasks.jsonl",
    "blind-v2-review-summary.json",
    "blind-v2-manifest.json",
)
AUTHORITY_MANIFEST_FILENAME = "run002-authority-manifest.json"
REPLACEMENT_REASON = "HOST_ASSIGNED_CANDIDATE_IDENTITY"
FORMAL_GENERATOR_MAX_CONCURRENCY = 4
GENERATOR_RESPONSE_SCHEMA_VERSION = "router-v2-run002-generator-response-v1"
GENERATOR_RESPONSE_SIZE = 16
CANDIDATE_ID_HEX_LENGTH = 24
GENERATOR_CANDIDATE_FIELDS = frozenset(
    {
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
)

GENERATOR_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "minItems": GENERATOR_RESPONSE_SIZE,
            "maxItems": GENERATOR_RESPONSE_SIZE,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "prompt_text",
                    "semantic_family_id",
                    "proposed_gold_skill_id",
                    "proposed_negative_skill_id",
                    "language",
                    "rationale",
                ],
                "properties": {
                    "prompt_text": {"type": "string", "pattern": r"\S"},
                    "semantic_family_id": {"type": "string", "pattern": r"\S"},
                    "proposed_gold_skill_id": {
                        "type": "string",
                        "pattern": r"\S",
                    },
                    "proposed_negative_skill_id": {
                        "type": ["string", "null"],
                        "pattern": r"\S",
                    },
                    "language": {"type": "string", "const": "en"},
                    "rationale": {"type": "string", "pattern": r"\S"},
                },
            },
        }
    },
}

GENERATOR_RULES = {
    "naturalness": (
        "Each prompt must read like a genuine standalone user request, not a "
        "benchmark item, rubric, or synthetic template."
    ),
    "single_primary_skill": (
        "Exactly one canonical skill must be the clearly primary skill needed to "
        "answer the request."
    ),
    "no_label_leakage": (
        "Do not mention skill IDs, skill names, gold or negative labels, routing, "
        "evaluation, quotas, or candidate metadata in the prompt."
    ),
    "negative_confusability": (
        "A non-null negative must be plausible and confusable for the prompt but "
        "insufficient to solve it; null is reserved for positive-only candidates."
    ),
}

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
TERMINAL_TRUTH = {
    "router_decision": "KEEP_BASELINE",
    "production_ready": False,
    "release_authorized": False,
    "default_router_unchanged": True,
}
GENERATOR_SYSTEM_PROMPT = (
    "You are the Generator for the synthetic Run002 schema canary. Return exactly "
    "16 synthetic candidates that match the supplied schema. Use only the supplied "
    "synthetic skill definitions and quota. Do not inspect repositories, access "
    "memory, use tools, load Router models, or use any formal blind data."
)
FORMAL_GENERATOR_SYSTEM_PROMPT = (
    "You are the Generator for preregistered Router V2 blind-v2 Run002. Return "
    "exactly 16 natural English user requests for the supplied primary canonical "
    "skill and quota. Emit only prompt_text, semantic_family_id, "
    "proposed_gold_skill_id, proposed_negative_skill_id, language, and rationale "
    "for each candidate. Every prompt must be natural, have exactly one single "
    "primary skill, contain no label leakage, and use a plausible, confusable but "
    "insufficient negative when the negative is non-null. Do not emit candidate "
    "identity, position, order, round, or hashes. Do not inspect repositories, use "
    "tools, access memory, or use training, pilot, Router-score, review, or "
    "model-result data."
)


def _nonempty_string(value: object) -> bool:
    return type(value) is str and bool(cast(str, value).strip())


def _lowercase_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 64
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


def _lowercase_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 40
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")
    return hashlib.sha256(payload).hexdigest()


def _request_authority(
    *,
    role: str,
    commit_a: str,
    system_prompt: str,
    response_schema: dict[str, Any],
) -> dict[str, str]:
    if role not in AGENT_CONFIGS or not _lowercase_commit(commit_a):
        raise ValueError("Run002 request authority mismatch")
    return {
        "run_id": RUN_ID,
        "commit_a": commit_a,
        "system_prompt_sha256": canonical_sha256(system_prompt),
        "response_schema_sha256": canonical_sha256(response_schema),
        "agent_config_sha256": canonical_sha256(AGENT_CONFIGS[role]),
    }


def _synthetic_canary_skills() -> list[dict[str, Any]]:
    return [
        {
            "id": f"synthetic-skill-{index:02d}",
            "name": f"Synthetic Skill {index:02d}",
            "category": "synthetic-canary",
            "description": f"Synthetic canary definition {index:02d}",
            "trigger_terms": [f"synthetic-trigger-{index:02d}"],
            "body": f"Synthetic canary body {index:02d}",
        }
        for index in range(16)
    ]


def build_generator_canary_request() -> dict[str, Any]:
    config = AGENT_CONFIGS["generator"]
    payload = {
        "schema_version": "router-v2-run002-generation-request-v1",
        "role": "generator",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": GENERATOR_SYSTEM_PROMPT,
        "response_schema": deepcopy(GENERATOR_RESPONSE_SCHEMA),
        "input": {
            "run_id": RUN_ID,
            "synthetic_canary": True,
            "formal_data": False,
            "canonical_skills": _synthetic_canary_skills(),
            "quota": {
                "gold_skill_id": "synthetic-skill-00",
                "negative_quota": 12,
                "positive_only_quota": 4,
                "response_candidate_count": GENERATOR_RESPONSE_SIZE,
                "round_number": 0,
            },
        },
    }
    return {**payload, "request_sha256": canonical_sha256(payload)}


def build_formal_generator_request(
    canonical_skills: list[dict[str, Any]],
    *,
    commit_a: str,
    gold_skill_id: str,
    negative_quota: int,
    positive_only_quota: int,
    round_number: int,
) -> dict[str, Any]:
    if (
        type(canonical_skills) is not list
        or len(canonical_skills) != 16
        or type(gold_skill_id) is not str
        or type(negative_quota) is not int
        or type(positive_only_quota) is not int
        or negative_quota < 0
        or positive_only_quota < 0
        or negative_quota + positive_only_quota != GENERATOR_RESPONSE_SIZE
        or round_number not in {1, 2}
        or not _lowercase_commit(commit_a)
    ):
        raise ValueError("Run002 formal Generator request quota mismatch")
    config = AGENT_CONFIGS["generator"]
    payload = {
        "schema_version": "router-v2-run002-generation-request-v1",
        "role": "generator",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": FORMAL_GENERATOR_SYSTEM_PROMPT,
        "response_schema": deepcopy(GENERATOR_RESPONSE_SCHEMA),
        "authority": _request_authority(
            role="generator",
            commit_a=commit_a,
            system_prompt=FORMAL_GENERATOR_SYSTEM_PROMPT,
            response_schema=GENERATOR_RESPONSE_SCHEMA,
        ),
        "input": {
            "run_id": RUN_ID,
            "synthetic_canary": False,
            "formal_data": True,
            "canonical_skills": deepcopy(canonical_skills),
            "rules": deepcopy(GENERATOR_RULES),
            "quota": {
                "gold_skill_id": gold_skill_id,
                "negative_quota": negative_quota,
                "positive_only_quota": positive_only_quota,
                "response_candidate_count": GENERATOR_RESPONSE_SIZE,
                "round_number": round_number,
            },
        },
    }
    return {**payload, "request_sha256": canonical_sha256(payload)}


def build_reviewer_request(
    candidate: dict[str, Any],
    canonical_skills: list[dict[str, Any]],
    *,
    role: str,
    commit_a: str,
) -> dict[str, Any]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    request = workflow.build_reviewer_request(
        candidate,
        canonical_skills,
        role=role,
        successor_output_schema=True,
    )
    payload = {
        key: deepcopy(value)
        for key, value in request.items()
        if key != "request_sha256"
    }
    payload["schema_version"] = "router-v2-run002-review-request-v1"
    payload["authority"] = _request_authority(
        role=role,
        commit_a=commit_a,
        system_prompt=cast(str, payload["system_prompt"]),
        response_schema=cast(dict[str, Any], payload["response_schema"]),
    )
    return {**payload, "request_sha256": canonical_sha256(payload)}


def validate_generator_response_structure(response: object) -> dict[str, Any]:
    if type(response) is not dict or set(response) != {"candidates"}:
        raise ValueError("Run002 Generator response fields mismatch")
    candidates = cast(dict[str, Any], response)["candidates"]
    if type(candidates) is not list or len(candidates) != GENERATOR_RESPONSE_SIZE:
        raise ValueError("Run002 Generator response must contain exactly 16 candidates")
    for candidate in candidates:
        if type(candidate) is not dict or set(candidate) != GENERATOR_CANDIDATE_FIELDS:
            raise ValueError("Run002 Generator candidate fields mismatch")
        row = cast(dict[str, Any], candidate)
        for field in (
            "prompt_text",
            "semantic_family_id",
            "proposed_gold_skill_id",
            "language",
            "rationale",
        ):
            if not _nonempty_string(row[field]):
                raise ValueError(f"Run002 Generator candidate {field} is invalid")
        negative = row["proposed_negative_skill_id"]
        if negative is not None and not _nonempty_string(negative):
            raise ValueError("Run002 Generator candidate negative is invalid")
    return deepcopy(cast(dict[str, Any], response))


def host_candidate_id(
    *,
    run_id: str,
    request_id: str,
    position: int,
    prompt_text: str,
) -> str:
    """Derive an opaque ID only from Run002 host-owned identity inputs."""

    if not _nonempty_string(run_id):
        raise ValueError("run_id must be a non-empty string")
    if not _lowercase_sha256(request_id):
        raise ValueError("request_id must be a lowercase SHA-256")
    if type(position) is not int or not 0 <= position < GENERATOR_RESPONSE_SIZE:
        raise ValueError("position must be an integer from 0 through 15")
    if not _nonempty_string(prompt_text):
        raise ValueError("prompt_text must be a non-empty string")
    identity = json.dumps(
        [run_id, request_id, position, prompt_text],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")
    return hashlib.sha256(identity).hexdigest()[:CANDIDATE_ID_HEX_LENGTH]


def _candidate_rejection_reasons(
    candidate: object,
    *,
    expected_gold_skill_id: str,
    canonical_skill_ids: set[str],
) -> list[str]:
    if type(candidate) is not dict or set(candidate) != GENERATOR_CANDIDATE_FIELDS:
        return ["CANDIDATE_FIELDS_MISMATCH"]
    row = cast(dict[str, Any], candidate)
    reasons: list[str] = []
    if not _nonempty_string(row["prompt_text"]):
        reasons.append("PROMPT_TEXT_INVALID")
    if not _nonempty_string(row["semantic_family_id"]):
        reasons.append("SEMANTIC_FAMILY_INVALID")
    gold = row["proposed_gold_skill_id"]
    if gold != expected_gold_skill_id:
        reasons.append("PROPOSED_GOLD_MISMATCH")
    elif gold not in canonical_skill_ids:
        reasons.append("PROPOSED_GOLD_NONCANONICAL")
    negative = row["proposed_negative_skill_id"]
    if negative is not None and (
        type(negative) is not str
        or not negative.strip()
        or negative not in canonical_skill_ids
        or negative == gold
    ):
        reasons.append("PROPOSED_NEGATIVE_INVALID")
    if row["language"] != "en":
        reasons.append("LANGUAGE_INVALID")
    if not _nonempty_string(row["rationale"]):
        reasons.append("RATIONALE_INVALID")
    return reasons


def _import_generator_response_for_run(
    response: object,
    *,
    run_id: str,
    expected_run_id: str,
    schema_version: str,
    request_id: str,
    expected_gold_skill_id: str,
    expected_negative_quota: int,
    expected_positive_only_quota: int,
    canonical_skill_ids: set[str],
) -> dict[str, Any]:
    """Pure host importer shared by separately bound successor runs."""

    if run_id != expected_run_id:
        raise ValueError("successor import requires the frozen run_id")
    if not _lowercase_sha256(request_id):
        raise ValueError("request_id must be a lowercase SHA-256")
    if (
        type(canonical_skill_ids) is not set
        or len(canonical_skill_ids) != 16
        or not all(_nonempty_string(value) for value in canonical_skill_ids)
    ):
        raise ValueError("canonical_skill_ids must contain exactly 16 skill IDs")
    if expected_gold_skill_id not in canonical_skill_ids:
        raise ValueError("expected gold skill must be canonical")
    if (
        type(expected_negative_quota) is not int
        or type(expected_positive_only_quota) is not int
        or expected_negative_quota < 0
        or expected_positive_only_quota < 0
        or expected_negative_quota + expected_positive_only_quota
        != GENERATOR_RESPONSE_SIZE
    ):
        raise ValueError("Run002 import quota authority mismatch")

    if type(response) is not dict or set(response) != {"candidates"}:
        return {
            "schema_version": schema_version,
            "run_id": run_id,
            "request_id": request_id,
            "request_outcome": "REJECTED_RESPONSE_SCHEMA",
            "observed_candidate_count": None,
            "accepted_candidates": [],
            "candidate_outcomes": [],
            "retry_allowed": False,
        }
    candidates = cast(dict[str, Any], response)["candidates"]
    if type(candidates) is not list or len(candidates) != GENERATOR_RESPONSE_SIZE:
        observed_count = len(candidates) if type(candidates) is list else None
        return {
            "schema_version": schema_version,
            "run_id": run_id,
            "request_id": request_id,
            "request_outcome": "REJECTED_CANDIDATE_COUNT",
            "observed_candidate_count": observed_count,
            "accepted_candidates": [],
            "candidate_outcomes": [],
            "retry_allowed": False,
        }
    negative_count = sum(
        type(candidate) is dict
        and candidate.get("proposed_negative_skill_id") is not None
        for candidate in candidates
    )
    positive_only_count = GENERATOR_RESPONSE_SIZE - negative_count
    if (
        negative_count != expected_negative_quota
        or positive_only_count != expected_positive_only_quota
    ):
        return {
            "schema_version": schema_version,
            "run_id": run_id,
            "request_id": request_id,
            "request_outcome": "REJECTED_QUOTA_STRATA",
            "observed_candidate_count": GENERATOR_RESPONSE_SIZE,
            "observed_negative_count": negative_count,
            "observed_positive_only_count": positive_only_count,
            "accepted_candidates": [],
            "candidate_outcomes": [],
            "retry_allowed": False,
        }

    accepted_candidates: list[dict[str, Any]] = []
    candidate_outcomes: list[dict[str, Any]] = []
    for position, raw_candidate in enumerate(candidates):
        reasons = _candidate_rejection_reasons(
            raw_candidate,
            expected_gold_skill_id=expected_gold_skill_id,
            canonical_skill_ids=canonical_skill_ids,
        )
        prompt_text = (
            cast(dict[str, Any], raw_candidate).get("prompt_text")
            if type(raw_candidate) is dict
            else None
        )
        candidate_id = (
            host_candidate_id(
                run_id=run_id,
                request_id=request_id,
                position=position,
                prompt_text=cast(str, prompt_text),
            )
            if _nonempty_string(prompt_text)
            else None
        )
        outcome = {
            "position": position,
            "candidate_index": position,
            "candidate_id": candidate_id,
            "outcome": "REJECTED_SEMANTIC" if reasons else "ACCEPTED",
            "reasons": reasons,
        }
        candidate_outcomes.append(outcome)
        if reasons:
            continue
        accepted_candidates.append(
            {
                "candidate_index": position,
                "candidate_id": candidate_id,
                **deepcopy(cast(dict[str, Any], raw_candidate)),
            }
        )

    return {
        "schema_version": schema_version,
        "run_id": run_id,
        "request_id": request_id,
        "request_outcome": (
            "ACCEPTED"
            if len(accepted_candidates) == GENERATOR_RESPONSE_SIZE
            else "ACCEPTED_WITH_CANDIDATE_REJECTIONS"
        ),
        "observed_candidate_count": GENERATOR_RESPONSE_SIZE,
        "accepted_candidates": accepted_candidates,
        "candidate_outcomes": candidate_outcomes,
        "retry_allowed": False,
    }


def import_generator_response(
    response: object,
    *,
    run_id: str,
    request_id: str,
    expected_gold_skill_id: str,
    expected_negative_quota: int,
    expected_positive_only_quota: int,
    canonical_skill_ids: set[str],
) -> dict[str, Any]:
    """Import one response without allowing one bad candidate to abort Run002."""

    return _import_generator_response_for_run(
        response,
        run_id=run_id,
        expected_run_id=RUN_ID,
        schema_version=GENERATOR_RESPONSE_SCHEMA_VERSION,
        request_id=request_id,
        expected_gold_skill_id=expected_gold_skill_id,
        expected_negative_quota=expected_negative_quota,
        expected_positive_only_quota=expected_positive_only_quota,
        canonical_skill_ids=canonical_skill_ids,
    )


def retry_allowed(
    failure_kind: str,
    *,
    retry_count: int,
    transport_failure_no_response: bool,
    syntactically_valid_response: bool,
) -> bool:
    if type(retry_count) is not int or retry_count not in {0, 1}:
        raise ValueError("retry_count must be zero or one")
    if (
        type(transport_failure_no_response) is not bool
        or type(syntactically_valid_response) is not bool
    ):
        raise ValueError("retry evidence flags must be booleans")
    return (
        retry_count == 0
        and not syntactically_valid_response
        and (
            (failure_kind == "INVALID_JSON")
            or (failure_kind == "TRANSPORT_FAILURE" and transport_failure_no_response)
        )
    )


def round_one_quota_plan(canonical_skill_ids: list[str]) -> list[dict[str, Any]]:
    if (
        type(canonical_skill_ids) is not list
        or len(canonical_skill_ids) != 16
        or len(set(canonical_skill_ids)) != 16
        or canonical_skill_ids != sorted(canonical_skill_ids)
        or not all(_nonempty_string(value) for value in canonical_skill_ids)
    ):
        raise ValueError("round-one skill IDs must be 16 unique sorted strings")
    return [
        {
            "gold_skill_id": skill_id,
            "negative_quota": 12,
            "positive_only_quota": 4,
            "response_candidate_count": GENERATOR_RESPONSE_SIZE,
            "round_number": 1,
        }
        for skill_id in canonical_skill_ids
    ]


def supplement_quota_plan(
    deficits: dict[str, dict[str, int]], *, canonical_skill_ids: set[str]
) -> list[dict[str, Any]]:
    if (
        type(deficits) is not dict
        or type(canonical_skill_ids) is not set
        or len(canonical_skill_ids) != 16
    ):
        raise ValueError("supplement authority mismatch")
    plan: list[dict[str, Any]] = []
    for skill_id, raw_counts in sorted(deficits.items()):
        if skill_id not in canonical_skill_ids or type(raw_counts) is not dict:
            raise ValueError("supplement skill authority mismatch")
        if set(raw_counts) != {"negative", "positive_only"}:
            raise ValueError("supplement deficit fields mismatch")
        negative_deficit = raw_counts["negative"]
        positive_deficit = raw_counts["positive_only"]
        if (
            type(negative_deficit) is not int
            or negative_deficit < 0
            or type(positive_deficit) is not int
            or positive_deficit < 0
        ):
            raise ValueError("supplement deficits must be non-negative integers")
        total_deficit = negative_deficit + positive_deficit
        if total_deficit == 0:
            continue
        if negative_deficit == 0:
            negative_quota = 0
        elif positive_deficit == 0:
            negative_quota = GENERATOR_RESPONSE_SIZE
        else:
            negative_quota = max(
                1,
                min(
                    GENERATOR_RESPONSE_SIZE - 1,
                    GENERATOR_RESPONSE_SIZE * negative_deficit // total_deficit,
                ),
            )
        plan.append(
            {
                "gold_skill_id": skill_id,
                "negative_quota": negative_quota,
                "positive_only_quota": GENERATOR_RESPONSE_SIZE - negative_quota,
                "response_candidate_count": GENERATOR_RESPONSE_SIZE,
                "round_number": 2,
            }
        )
    return plan


def synthetic_canary_response() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "prompt_text": f"Synthetic Run002 Generator canary request {index}",
                "semantic_family_id": f"synthetic-run002-family-{index:02d}",
                "proposed_gold_skill_id": "synthetic-skill-00",
                "proposed_negative_skill_id": (
                    "synthetic-skill-01" if index < 12 else None
                ),
                "language": "en",
                "rationale": f"Synthetic schema validation rationale {index}",
            }
            for index in range(GENERATOR_RESPONSE_SIZE)
        ]
    }


def run_generator_canary(response: object | None = None) -> dict[str, Any]:
    request_id = canonical_sha256(
        {
            "schema_version": "router-v2-run002-generator-canary-request-v1",
            "run_id": RUN_ID,
            "synthetic": True,
            "response_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
        }
    )
    imported = import_generator_response(
        synthetic_canary_response() if response is None else response,
        run_id=RUN_ID,
        request_id=request_id,
        expected_gold_skill_id="synthetic-skill-00",
        expected_negative_quota=12,
        expected_positive_only_quota=4,
        canonical_skill_ids={f"synthetic-skill-{index:02d}" for index in range(16)},
    )
    if imported["request_outcome"] != "ACCEPTED":
        raise ValueError("Run002 Generator canary response is invalid")
    accepted = cast(list[dict[str, Any]], imported["accepted_candidates"])
    return {
        "status": "RUN002_GENERATOR_CANARY_PASSED",
        "run_id": RUN_ID,
        "candidate_count": len(accepted),
        "candidate_indexes": [row["candidate_index"] for row in accepted],
        "candidate_ids": [row["candidate_id"] for row in accepted],
        "request_id": request_id,
        "generator_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
        "formal_data_written": False,
        "router_loaded": False,
    }


def private_evidence_root(commit_a: str) -> Path:
    if not _lowercase_commit(commit_a):
        raise ValueError("Run002 Commit A must be 40 lowercase hex characters")
    if commit_a == RUN001_COMMIT_A:
        raise ValueError("Run002 cannot reuse Run001 Commit A authority")
    root = PRIVATE_EVIDENCE_BASE / commit_a
    if root == RUN001_PRIVATE_EVIDENCE_ROOT:
        raise ValueError("Run002 cannot reuse the Run001 private root")
    return root


def build_authority_manifest(
    *,
    commit_a: str,
    current_git_commit: str,
    private_evidence_root: Path | None = None,
) -> dict[str, Any]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if not _lowercase_commit(commit_a) or commit_a == RUN001_COMMIT_A:
        raise ValueError("Run002 Commit A authority mismatch")
    root = (
        PRIVATE_EVIDENCE_BASE / commit_a
        if private_evidence_root is None
        else private_evidence_root
    )
    if not root.is_absolute():
        raise ValueError("Run002 private evidence root must be absolute")
    if not _lowercase_commit(current_git_commit):
        raise ValueError("current Git commit must be 40 lowercase hex characters")
    return {
        "schema_version": "router-v2-run002-authority-manifest-v1",
        "run_id": RUN_ID,
        "commit_a": commit_a,
        "current_git_commit": current_git_commit,
        "private_evidence_root": str(root),
        "output_namespace": OUTPUT_NAMESPACE.as_posix(),
        "predecessor_run_id": RUN001_RUN_ID,
        "predecessor_terminal_sha256": RUN001_TERMINAL_SHA256,
        "replacement_reason": REPLACEMENT_REASON,
        "run001_model_scores_observed": False,
        "run001_candidates_reused": False,
        "generator_schema_version": GENERATOR_RESPONSE_SCHEMA_VERSION,
        "generator_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
        "system_prompt_sha256": {
            "generator": canonical_sha256(FORMAL_GENERATOR_SYSTEM_PROMPT),
            "reviewer_a": canonical_sha256(workflow.REVIEWER_SYSTEM_PROMPT),
            "reviewer_b": canonical_sha256(workflow.REVIEWER_SYSTEM_PROMPT),
        },
        "response_schema_sha256": {
            "generator": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
            "reviewer_a": canonical_sha256(
                workflow._successor_response_schema("reviewer_a")
            ),
            "reviewer_b": canonical_sha256(
                workflow._successor_response_schema("reviewer_b")
            ),
        },
        "agent_config_sha256": {
            role: canonical_sha256(config) for role, config in AGENT_CONFIGS.items()
        },
        "generator_rules_sha256": canonical_sha256(GENERATOR_RULES),
        "selection_authority_sha256": canonical_sha256(
            dict(workflow.SELECTION_AUTHORITY)
        ),
        "candidate_identity_fields": [
            "run_id",
            "request_id",
            "position",
            "prompt_text",
        ],
        "agent_configs": deepcopy(AGENT_CONFIGS),
        "router_decision": "KEEP_BASELINE",
        "default_router_unchanged": True,
        "production_ready": False,
        "release_authorized": False,
        "release_eligible": False,
    }


def validate_authority_manifest(
    manifest: object, *, expected_root: Path | None = None
) -> dict[str, Any]:
    if type(manifest) is not dict:
        raise ValueError("Run002 authority manifest must be an object")
    value = cast(dict[str, Any], manifest)
    commit_a = value.get("commit_a")
    current_git_commit = value.get("current_git_commit")
    if type(commit_a) is not str or type(current_git_commit) is not str:
        raise ValueError("Run002 authority manifest commit binding is missing")
    expected = build_authority_manifest(
        commit_a=commit_a,
        current_git_commit=current_git_commit,
        private_evidence_root=expected_root,
    )
    if value != expected:
        raise ValueError("Run002 authority manifest mismatch")
    return deepcopy(value)


def persist_authority_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    validated = validate_authority_manifest(manifest, expected_root=root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Run002 authority root mismatch")
    path = root / AUTHORITY_MANIFEST_FILENAME
    payload = _canonical_json_bytes(validated)
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise ValueError("Run002 persisted authority manifest mismatch")
        return path
    with path.open("xb") as handle:
        handle.write(payload)
    return path


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_reject_duplicate_pairs)
    if type(value) is not dict:
        raise ValueError(f"Run002 JSON object mismatch: {path.name}")
    return cast(dict[str, Any], value)


def _jsonl_objects(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        value = json.loads(line, object_pairs_hook=_reject_duplicate_pairs)
        if type(value) is not dict:
            raise ValueError(f"Run002 JSONL row mismatch: {path.name}")
        rows.append(cast(dict[str, Any], value))
    return rows


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _successful_response(
    row: dict[str, Any], *, request: dict[str, Any]
) -> dict[str, Any] | None:
    if row.get("valid") is not True:
        return None
    invocations = row.get("invocations")
    if type(invocations) is not list or not invocations:
        raise ValueError("Run002 valid ledger row requires an invocation")
    invocation = invocations[-1]
    if type(invocation) is not dict or type(invocation.get("envelope")) is not dict:
        raise ValueError("Run002 valid invocation envelope is missing")
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    return workflow.validate_agent_invocation_envelope(
        cast(dict[str, Any], invocation["envelope"]), request=request
    )


def _validated_ledger_attempts(
    row: dict[str, Any],
    *,
    request: dict[str, Any],
    role: str,
    commit_a: str,
    seen_thread_ids: set[str],
    run003_mode: bool = False,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    """Replay one sealed request, its retry authority, and host lineage."""

    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if run003_mode:
        from hermes_skilleval import router_v2_blind_v2_run003 as run003

        active_run_id = run003.RUN_ID
        active_agent_configs = run003.AGENT_CONFIGS
    else:
        active_run_id = RUN_ID
        active_agent_configs = AGENT_CONFIGS

    retry_count = row.get("retry_count")
    statuses = row.get("attempt_statuses")
    attempts = row.get("attempt_records")
    if (
        type(retry_count) is not int
        or retry_count not in {0, 1}
        or type(statuses) is not list
        or type(attempts) is not list
        or len(statuses) != retry_count + 1
        or len(attempts) != retry_count + 1
    ):
        raise ValueError("Run002 retry lineage mismatch")
    normalized_attempts: list[dict[str, Any]] = []
    for ordinal, (status, raw_attempt) in enumerate(
        zip(statuses, attempts, strict=True), start=1
    ):
        if type(raw_attempt) is not dict:
            raise ValueError("Run002 retry attempt must be an object")
        attempt = cast(dict[str, Any], raw_attempt)
        expected_fields = {
            "attempt_ordinal",
            "status",
            "failure_kind",
            "request_sha256",
            "transport_failure_no_response",
            "syntactically_valid_response",
            "retry_authorized",
        }
        if set(attempt) != expected_fields:
            raise ValueError("Run002 retry attempt fields mismatch")
        if (
            attempt["attempt_ordinal"] != ordinal
            or attempt["status"] != status
            or attempt["request_sha256"] != request["request_sha256"]
            or type(attempt["transport_failure_no_response"]) is not bool
            or type(attempt["syntactically_valid_response"]) is not bool
            or type(attempt["retry_authorized"]) is not bool
        ):
            raise ValueError("Run002 byte-identical retry authority mismatch")
        should_retry = ordinal <= retry_count
        if attempt["retry_authorized"] is not should_retry:
            raise ValueError("Run002 retry authorization sequence mismatch")
        if should_retry:
            failure_kind = attempt["failure_kind"]
            if type(failure_kind) is not str or not retry_allowed(
                failure_kind,
                retry_count=ordinal - 1,
                transport_failure_no_response=attempt["transport_failure_no_response"],
                syntactically_valid_response=attempt["syntactically_valid_response"],
            ):
                raise ValueError("Run002 retry reason is not authorized")
        normalized_attempts.append(deepcopy(attempt))

    invocations = row.get("invocations")
    if type(invocations) is not list:
        raise ValueError("Run002 invocation ledger mismatch")
    response: dict[str, Any] | None = None
    threads: list[str] = []
    for invocation in invocations:
        if type(invocation) is not dict or type(invocation.get("envelope")) is not dict:
            raise ValueError("Run002 invocation envelope is missing")
        envelope = cast(dict[str, Any], invocation["envelope"])
        validated = workflow.validate_agent_invocation_envelope(
            envelope,
            request=request,
            seen_session_ids=seen_thread_ids,
        )
        thread_id = cast(str, envelope["thread_id"])
        seen_thread_ids.add(thread_id)
        threads.append(thread_id)
        response = validated
    valid = row.get("valid") is True
    if valid:
        if (
            len(invocations) != 1
            or response is None
            or statuses[-1] != "VALID"
            or row.get("status") != "VALID"
        ):
            raise ValueError("Run002 valid response lineage mismatch")
    elif invocations or response is not None or statuses[-1] == "VALID":
        raise ValueError("Run002 rejected response lineage mismatch")
    evidence = {
        "role": role,
        "run_id": active_run_id,
        "commit_a": commit_a,
        "request_sha256": request["request_sha256"],
        "response_sha256": None if response is None else canonical_sha256(response),
        "system_prompt_sha256": canonical_sha256(request["system_prompt"]),
        "response_schema_sha256": canonical_sha256(request["response_schema"]),
        "agent_config_sha256": canonical_sha256(active_agent_configs[role]),
        "session_or_thread_ids": threads,
        "retry_count": retry_count,
    }
    if run003_mode:
        diagnostic_count = sum(
            cast(
                int,
                cast(dict[str, Any], invocation["envelope"])[
                    "transport_diagnostic_count"
                ],
            )
            for invocation in invocations
        )
        evidence.update(
            {
                "event_policy_version": run003.EVENT_POLICY_VERSION,
                "transport_diagnostic_count": diagnostic_count,
                "transport_diagnostic_types": sorted(
                    {
                        cast(str, diagnostic_type)
                        for invocation in invocations
                        for diagnostic_type in cast(
                            list[str],
                            cast(dict[str, Any], invocation["envelope"])[
                                "transport_diagnostic_types"
                            ],
                        )
                    }
                ),
                "transport_diagnostics_observed": diagnostic_count > 0,
            }
        )
    retry_records = [
        attempt for attempt in normalized_attempts if attempt["retry_authorized"]
    ]
    return response, retry_records, evidence


def validate_agent_pack(
    root: Path,
    *,
    canonical_skills: list[dict[str, Any]],
    contamination_replayer: Any,
    expected_commit_a: str,
    run003_mode: bool = False,
) -> dict[str, Any]:
    """Rebuild the sealed Run002 or explicit Run003 selection from ledgers."""

    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if run003_mode:
        from hermes_skilleval import router_v2_blind_v2_run003 as run003

        active_run_id = run003.RUN_ID
        active_manifest_filename = run003.AUTHORITY_MANIFEST_FILENAME
        active_generator_schema = run003.GENERATOR_RESPONSE_SCHEMA
        active_agent_configs = run003.AGENT_CONFIGS
        active_metadata_schema = "router-v2-run003-agent-run-metadata-v1"
        active_manifest_validator = run003.validate_authority_manifest
    else:
        active_run_id = RUN_ID
        active_manifest_filename = AUTHORITY_MANIFEST_FILENAME
        active_generator_schema = GENERATOR_RESPONSE_SCHEMA
        active_agent_configs = AGENT_CONFIGS
        active_metadata_schema = "router-v2-run002-agent-run-metadata-v1"
        active_manifest_validator = validate_authority_manifest

    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Run002 Agent pack root mismatch")
    required = {
        "blind-v2-generation.jsonl",
        "blind-v2-review-a.jsonl",
        "blind-v2-review-b.jsonl",
        "blind-v2-contamination.jsonl",
        "agent-run-metadata.json",
        active_manifest_filename,
    }
    actual = {path.name for path in root.iterdir() if path.is_file()}
    if actual != required:
        raise ValueError("Run002 Agent pack must contain exactly six files")
    skills = workflow._project_canonical_skills(canonical_skills)
    canonical_ids = {cast(str, row["id"]) for row in skills}
    if len(canonical_ids) != 16:
        raise ValueError("Run002 requires exactly 16 canonical skills")

    source_file_sha256 = {
        filename: hashlib.sha256((root / filename).read_bytes()).hexdigest()
        for filename in sorted(required)
    }
    authority_manifest = active_manifest_validator(
        _json_object(root / active_manifest_filename), expected_root=root
    )
    if (
        authority_manifest["commit_a"] != expected_commit_a
        or authority_manifest["current_git_commit"] != expected_commit_a
    ):
        raise ValueError("Run002 private authority Commit A mismatch")
    if not callable(contamination_replayer):
        raise ValueError("Run002 contamination replayer is required")
    metadata = _json_object(root / "agent-run-metadata.json")
    first_read_timestamp = metadata.get("first_read_timestamp")
    if type(first_read_timestamp) is not str or not first_read_timestamp:
        raise ValueError("Run002 first-read timestamp is missing")

    generation_rows = _jsonl_objects(root / "blind-v2-generation.jsonl")
    candidates: dict[str, dict[str, Any]] = {}
    seen_thread_ids: set[str] = set()
    retry_records: list[dict[str, Any]] = []
    agent_run_evidence: list[dict[str, Any]] = []
    generation_keys: list[tuple[int, str]] = []
    candidate_import_rejection_count = 0
    generated_candidate_count = 0
    for row in generation_rows:
        if set(row) != {
            "generation_round",
            "gold_skill_id",
            "request",
            "invocations",
            "request_outcome",
            "candidate_outcomes",
            "status",
            "valid",
            "retry_count",
            "attempt_statuses",
            "attempt_records",
        }:
            raise ValueError("Run002 generation ledger row fields mismatch")
        request = workflow.validate_agent_request(cast(dict[str, Any], row["request"]))
        if request["response_schema"] != active_generator_schema:
            raise ValueError("Run002 generation ledger schema mismatch")
        quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
        if (
            row.get("generation_round") != quota["round_number"]
            or row.get("gold_skill_id") != quota["gold_skill_id"]
        ):
            raise ValueError("Run002 generation request binding mismatch")
        round_number = cast(int, quota["round_number"])
        gold_skill_id = cast(str, quota["gold_skill_id"])
        generation_keys.append((round_number, gold_skill_id))
        request_builder = (
            run003.build_formal_generator_request
            if run003_mode
            else build_formal_generator_request
        )
        expected_request = request_builder(
            skills,
            commit_a=expected_commit_a,
            gold_skill_id=gold_skill_id,
            negative_quota=cast(int, quota["negative_quota"]),
            positive_only_quota=cast(int, quota["positive_only_quota"]),
            round_number=round_number,
        )
        if request != expected_request:
            raise ValueError("Run002 formal Generator request authority mismatch")
        response, row_retries, lineage = _validated_ledger_attempts(
            row,
            request=request,
            role="generator",
            commit_a=expected_commit_a,
            seen_thread_ids=seen_thread_ids,
            run003_mode=run003_mode,
        )
        retry_records.extend({"role": "generator", **item} for item in row_retries)
        agent_run_evidence.append(lineage)
        if response is None:
            if (
                row["candidate_outcomes"] != []
                or row["request_outcome"] != row["status"]
            ):
                raise ValueError("Run002 rejected Generator outcome mismatch")
            continue
        imported = (
            run003.import_generator_response(
                response,
                request_id=cast(str, request["request_sha256"]),
                expected_gold_skill_id=cast(str, quota["gold_skill_id"]),
                expected_negative_quota=cast(int, quota["negative_quota"]),
                expected_positive_only_quota=cast(int, quota["positive_only_quota"]),
                canonical_skill_ids=canonical_ids,
            )
            if run003_mode
            else import_generator_response(
                response,
                run_id=RUN_ID,
                request_id=cast(str, request["request_sha256"]),
                expected_gold_skill_id=cast(str, quota["gold_skill_id"]),
                expected_negative_quota=cast(int, quota["negative_quota"]),
                expected_positive_only_quota=cast(int, quota["positive_only_quota"]),
                canonical_skill_ids=canonical_ids,
            )
        )
        if row.get("candidate_outcomes") != imported["candidate_outcomes"]:
            raise ValueError("Run002 candidate import outcome mismatch")
        observed = imported["observed_candidate_count"]
        if type(observed) is int:
            generated_candidate_count += observed
        candidate_import_rejection_count += sum(
            outcome["outcome"] != "ACCEPTED"
            for outcome in cast(list[dict[str, Any]], imported["candidate_outcomes"])
        )
        for candidate in cast(list[dict[str, Any]], imported["accepted_candidates"]):
            candidate_id = cast(str, candidate["candidate_id"])
            if candidate_id in candidates:
                raise ValueError("Run002 candidate ID collision")
            prompt_text = cast(str, candidate["prompt_text"])
            candidates[candidate_id] = {
                **candidate,
                "generation_round": quota["round_number"],
                "prompt_text_sha256": hashlib.sha256(
                    prompt_text.encode("utf-8")
                ).hexdigest(),
            }

    expected_round_one_keys = [(1, skill_id) for skill_id in sorted(canonical_ids)]
    round_two_keys = [key for key in generation_keys if key[0] == 2]
    if (
        generation_keys != expected_round_one_keys + sorted(round_two_keys)
        or len(round_two_keys) != len(set(round_two_keys))
        or any(round_number != 2 for round_number, _skill_id in round_two_keys)
    ):
        raise ValueError("Run002 generation schedule authority mismatch")
    for row in generation_rows[:16]:
        quota = cast(
            dict[str, Any], cast(dict[str, Any], row["request"]["input"])["quota"]
        )
        if quota["negative_quota"] != 12 or quota["positive_only_quota"] != 4:
            raise ValueError("Run002 round-one quota authority mismatch")

    contamination_rows = _jsonl_objects(root / "blind-v2-contamination.jsonl")
    replayed_contamination = contamination_replayer(list(candidates.values()))
    if (
        type(replayed_contamination) is not dict
        or replayed_contamination.get("rows") != contamination_rows
        or type(replayed_contamination.get("clean_candidate_ids")) is not list
    ):
        raise ValueError("Run002 contamination ledger evidence mismatch")
    clean_ids = set(cast(list[str], replayed_contamination["clean_candidate_ids"]))
    if clean_ids - set(candidates):
        raise ValueError("Run002 contamination replay returned unknown candidates")

    review_responses: dict[str, dict[str, dict[str, Any] | None]] = {
        "reviewer_a": {},
        "reviewer_b": {},
    }
    review_request_count = 0
    reviewer_valid_count = 0
    review_rows_by_role = {
        "reviewer_a": _jsonl_objects(root / "blind-v2-review-a.jsonl"),
        "reviewer_b": _jsonl_objects(root / "blind-v2-review-b.jsonl"),
    }
    for role in ("reviewer_a", "reviewer_b"):
        role_rows = review_rows_by_role[role]
        actual_order: list[str] = []
        for row in role_rows:
            if set(row) != {
                "candidate_id",
                "request",
                "invocations",
                "valid",
                "status",
                "retry_count",
                "attempt_statuses",
                "attempt_records",
            }:
                raise ValueError("Run002 reviewer ledger row fields mismatch")
            review_candidate_id = row.get("candidate_id")
            if (
                review_candidate_id not in clean_ids
                or review_candidate_id in review_responses[role]
            ):
                raise ValueError("Run002 quarantined or duplicate review candidate")
            candidate = candidates[cast(str, review_candidate_id)]
            reviewer_builder = (
                run003.build_reviewer_request if run003_mode else build_reviewer_request
            )
            expected = reviewer_builder(
                candidate,
                skills,
                role=role,
                commit_a=expected_commit_a,
            )
            request = workflow.validate_agent_request(
                cast(dict[str, Any], row["request"])
            )
            if request != expected:
                raise ValueError("Run002 opaque reviewer request mismatch")
            response, row_retries, lineage = _validated_ledger_attempts(
                row,
                request=request,
                role=role,
                commit_a=expected_commit_a,
                seen_thread_ids=seen_thread_ids,
                run003_mode=run003_mode,
            )
            retry_records.extend({"role": role, **item} for item in row_retries)
            agent_run_evidence.append(lineage)
            review_responses[role][cast(str, review_candidate_id)] = response
            actual_order.append(cast(str, review_candidate_id))
            review_request_count += 1
            reviewer_valid_count += response is not None
        expected_order = sorted(
            clean_ids, key=lambda value: workflow.review_schedule_key(role, value)
        )
        if actual_order != expected_order:
            raise ValueError("Run002 clean-only reviewer schedule mismatch")
        if set(review_responses[role]) != clean_ids:
            raise ValueError("Run002 clean-only reviewer schedule is incomplete")

    metadata_fields = {
        "schema_version",
        "first_read_timestamp",
        "roles",
        "review_schedule_sha256",
        "selection_authority",
        "source_file_sha256",
        "run_id",
        "commit_a",
        "authority_manifest_sha256",
    }
    if run003_mode:
        metadata_fields.update(
            {
                "event_policy_version",
                "transport_diagnostic_count",
                "transport_diagnostic_types",
                "transport_diagnostics_observed",
            }
        )
    if set(metadata) != metadata_fields:
        raise ValueError("Run002 Agent metadata fields mismatch")
    source_ledger_names = {
        "blind-v2-generation.jsonl",
        "blind-v2-review-a.jsonl",
        "blind-v2-review-b.jsonl",
        "blind-v2-contamination.jsonl",
    }
    expected_source_hashes = {
        filename: source_file_sha256[filename] for filename in source_ledger_names
    }
    if (
        metadata["schema_version"] != active_metadata_schema
        or metadata["run_id"] != active_run_id
        or metadata["commit_a"] != expected_commit_a
        or metadata["authority_manifest_sha256"]
        != source_file_sha256[active_manifest_filename]
        or metadata["source_file_sha256"] != expected_source_hashes
        or metadata["selection_authority"] != workflow.SELECTION_AUTHORITY
    ):
        raise ValueError("Run002 Agent metadata authority mismatch")
    role_rows_by_name = {
        "generator": generation_rows,
        **review_rows_by_role,
    }
    evidence_by_role = {
        role: [item for item in agent_run_evidence if item["role"] == role]
        for role in active_agent_configs
    }
    metadata_roles = metadata.get("roles")
    if type(metadata_roles) is not dict or set(metadata_roles) != set(
        active_agent_configs
    ):
        raise ValueError("Run002 Agent role metadata mismatch")
    all_envelopes: list[dict[str, Any]] = []
    for role in active_agent_configs:
        role_metadata = metadata_roles[role]
        if type(role_metadata) is not dict:
            raise ValueError("Run002 Agent role metadata must be an object")
        expected_threads = [
            thread
            for item in evidence_by_role[role]
            for thread in item["session_or_thread_ids"]
        ]
        envelopes = [
            cast(dict[str, Any], invocation["envelope"])
            for row in role_rows_by_name[role]
            for invocation in cast(list[dict[str, Any]], row["invocations"])
        ]
        all_envelopes.extend(envelopes)
        provider_models: list[str | None] = []
        for envelope in envelopes:
            model = cast(str | None, envelope["returned_model"])
            if model not in provider_models:
                provider_models.append(model)
        expected_role_metadata = {
            "config": deepcopy(active_agent_configs[role]),
            "request_count": len(role_rows_by_name[role]),
            "invocation_count": len(envelopes),
            "session_or_thread_ids": expected_threads,
            "fork_context": False,
            "history_message_count": 0,
            "imported_memory_count": 0,
            "model_identity_evidence": "HOST_REQUEST_ENVELOPE",
            "provider_returned_models": provider_models,
            "provider_returned_model_statuses": sorted(
                {
                    cast(str, envelope["provider_returned_model_status"])
                    for envelope in envelopes
                }
            ),
            "lineage_observed": bool(envelopes)
            and all(envelope["lineage_observed"] is True for envelope in envelopes),
            "tool_call_count": sum(
                cast(int, envelope["tool_call_count"]) for envelope in envelopes
            ),
            "descendant_agent_count": sum(
                cast(int, envelope["descendant_agent_count"]) for envelope in envelopes
            ),
        }
        if run003_mode:
            role_diagnostic_count = sum(
                cast(int, envelope["transport_diagnostic_count"])
                for envelope in envelopes
            )
            expected_role_metadata.update(
                {
                    "event_policy_version": run003.EVENT_POLICY_VERSION,
                    "transport_diagnostic_count": role_diagnostic_count,
                    "transport_diagnostic_types": sorted(
                        {
                            cast(str, diagnostic_type)
                            for envelope in envelopes
                            for diagnostic_type in cast(
                                list[str], envelope["transport_diagnostic_types"]
                            )
                        }
                    ),
                    "transport_diagnostics_observed": role_diagnostic_count > 0,
                }
            )
        if role_metadata != expected_role_metadata:
            raise ValueError("Run002 Agent role metadata binding mismatch")
    if run003_mode:
        diagnostic_count = sum(
            cast(int, envelope["transport_diagnostic_count"])
            for envelope in all_envelopes
        )
        if (
            metadata["event_policy_version"] != run003.EVENT_POLICY_VERSION
            or metadata["transport_diagnostic_count"] != diagnostic_count
            or metadata["transport_diagnostic_types"]
            != sorted(
                {
                    cast(str, diagnostic_type)
                    for envelope in all_envelopes
                    for diagnostic_type in cast(
                        list[str], envelope["transport_diagnostic_types"]
                    )
                }
            )
            or metadata["transport_diagnostics_observed"] is not (diagnostic_count > 0)
        ):
            raise ValueError("Run003 Agent diagnostic metadata mismatch")
    schedules = metadata.get("review_schedule_sha256")
    if type(schedules) is not dict or schedules != {
        role: canonical_sha256(
            [cast(str, row["candidate_id"]) for row in review_rows_by_role[role]]
        )
        for role in ("reviewer_a", "reviewer_b")
    }:
        raise ValueError("Run002 review schedule metadata mismatch")

    accepted, outcomes = workflow._derive_candidate_pipeline_semantics(
        candidates,
        clean_candidate_ids=clean_ids,
        review_responses=review_responses,
    )
    round_one_accepted = [
        candidate for candidate in accepted if candidate["generation_round"] == 1
    ]
    round_one_deficits: dict[str, dict[str, int]] = {}
    for skill_id in sorted(canonical_ids):
        negative_count = sum(
            candidate["proposed_gold_skill_id"] == skill_id
            and candidate["proposed_negative_skill_id"] is not None
            for candidate in round_one_accepted
        )
        positive_count = sum(
            candidate["proposed_gold_skill_id"] == skill_id
            and candidate["proposed_negative_skill_id"] is None
            for candidate in round_one_accepted
        )
        deficit = {
            "negative": max(0, 6 - negative_count),
            "positive_only": max(0, 2 - positive_count),
        }
        if any(deficit.values()):
            round_one_deficits[skill_id] = deficit
    expected_supplement_plan = supplement_quota_plan(
        round_one_deficits, canonical_skill_ids=canonical_ids
    )
    observed_supplement_plan = [
        deepcopy(
            cast(dict[str, Any], cast(dict[str, Any], row["request"])["input"])["quota"]
        )
        for row in generation_rows[16:]
    ]
    if observed_supplement_plan != expected_supplement_plan:
        raise ValueError("Run002 deficit-only supplement authority mismatch")
    selected = workflow._deterministically_select_candidates(accepted, canonical_ids)
    workflow._finalized_candidate_outcomes(outcomes, selected)
    gold_counts = Counter(row["proposed_gold_skill_id"] for row in selected)
    negative_counts_by_gold = Counter(
        row["proposed_gold_skill_id"]
        for row in selected
        if row["proposed_negative_skill_id"] is not None
    )
    positive_counts_by_gold = Counter(
        row["proposed_gold_skill_id"]
        for row in selected
        if row["proposed_negative_skill_id"] is None
    )
    families = {cast(str, row["semantic_family_id"]) for row in selected}
    complete = (
        len(selected) == 128
        and set(gold_counts) == canonical_ids
        and set(gold_counts.values()) == {8}
        and all(negative_counts_by_gold[skill_id] == 6 for skill_id in canonical_ids)
        and all(positive_counts_by_gold[skill_id] == 2 for skill_id in canonical_ids)
        and len(families) == 128
    )
    if not complete:
        raise ValueError("Run002 selected dataset does not meet 128/96 quotas")
    negative_labeled_count = sum(negative_counts_by_gold.values())
    if negative_labeled_count != 96:
        raise ValueError("Run002 negative-labeled task count mismatch")
    supplement_request_count = sum(
        row.get("generation_round") == 2 for row in generation_rows
    )
    retry_records.sort(
        key=lambda row: (
            cast(str, row["role"]),
            cast(str, row["request_sha256"]),
            cast(int, row["attempt_ordinal"]),
        )
    )
    deterministic_selection_authority = {
        "selection_authority": dict(workflow.SELECTION_AUTHORITY),
        "selected_candidate_ids": [row["candidate_id"] for row in selected],
        "selected_candidate_ids_sha256": canonical_sha256(
            [row["candidate_id"] for row in selected]
        ),
    }
    validation = {
        "status": "VALID",
        "run_id": active_run_id,
        "first_read_timestamp": first_read_timestamp,
        "tasks": selected,
        "task_count": 128,
        "negative_labeled_task_count": 96,
        "family_count": 128,
        "gold_distribution": dict(sorted(gold_counts.items())),
        "negative_per_gold": dict(sorted(negative_counts_by_gold.items())),
        "positive_only_per_gold": dict(sorted(positive_counts_by_gold.items())),
        "candidate_generation_count": generated_candidate_count,
        "candidate_import_rejection_count": candidate_import_rejection_count,
        "accepted_candidate_count": len(accepted),
        "rejected_candidate_count": sum(
            type(value) is str and value.startswith("REJECTED")
            for value in outcomes.values()
        ),
        "review_request_count": review_request_count,
        "reviewer_valid_count": reviewer_valid_count,
        "reviewer_unanimous_agreement_count": sum(
            value in {"SELECTED", "NOT_SELECTED"} for value in outcomes.values()
        ),
        "supplement_request_count": supplement_request_count,
        "transport_retry_count": len(retry_records),
        "retry_records": retry_records,
        "agent_run_evidence": agent_run_evidence,
        "authority_manifest": authority_manifest,
        "authority_manifest_sha256": source_file_sha256[active_manifest_filename],
        "deterministic_selection_authority": deterministic_selection_authority,
        "candidate_outcomes": dict(sorted(outcomes.items())),
        "source_file_sha256": source_file_sha256,
        "source_skill_index_sha256": canonical_sha256(skills),
        "agent_configs": deepcopy(active_agent_configs),
        "system_prompt_sha256": {
            role: canonical_sha256(
                role_rows_by_name[role][0]["request"]["system_prompt"]
            )
            for role in active_agent_configs
        },
        "response_schema_sha256": {
            role: canonical_sha256(
                role_rows_by_name[role][0]["request"]["response_schema"]
            )
            for role in active_agent_configs
        },
        "agent_config_sha256": {
            role: canonical_sha256(active_agent_configs[role])
            for role in active_agent_configs
        },
        "contamination_checked_candidate_count": len(contamination_rows),
        "duplicate_and_contamination_checks_passed": True,
    }
    if run003_mode:
        validation.update(
            {
                "event_policy_version": run003.EVENT_POLICY_VERSION,
                "transport_diagnostic_count": metadata["transport_diagnostic_count"],
                "transport_diagnostic_types": deepcopy(
                    metadata["transport_diagnostic_types"]
                ),
                "transport_diagnostics_observed": metadata[
                    "transport_diagnostics_observed"
                ],
            }
        )
    return validation


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8", errors="strict")


def build_dataset_freeze_documents(
    validation: dict[str, Any], *, commit_a: str
) -> dict[str, bytes]:
    if validation.get("status") != "VALID" or validation.get("run_id") != RUN_ID:
        raise ValueError("Run002 valid Agent pack is required")
    if not _lowercase_commit(commit_a) or commit_a == RUN001_COMMIT_A:
        raise ValueError("Run002 freeze Commit A mismatch")
    selected = cast(list[dict[str, Any]], validation["tasks"])
    if len(selected) != 128:
        raise ValueError("Run002 freeze requires exactly 128 tasks")
    task_rows = [
        {
            "task_id": row["candidate_id"],
            "prompt_text": row["prompt_text"],
            "prompt_text_sha256": row["prompt_text_sha256"],
            "semantic_family_id": row["semantic_family_id"],
            "gold_skill_id": row["proposed_gold_skill_id"],
            "negative_skill_id": row["proposed_negative_skill_id"],
            "source_type": "AGENT_GENERATED",
        }
        for row in selected
    ]
    task_bytes = b"".join(_canonical_json_bytes(row) for row in task_rows)
    review_summary = {
        "schema_version": "router-v2-run002-review-summary-v1",
        "run_id": RUN_ID,
        "review_mode": "DUAL_AGENT_UNANIMOUS_REVIEWED",
        "source_type": "AGENT_GENERATED",
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "review_request_count": validation["review_request_count"],
        "reviewer_valid_count": validation["reviewer_valid_count"],
        "reviewer_unanimous_agreement_count": validation[
            "reviewer_unanimous_agreement_count"
        ],
        "candidate_outcomes": validation["candidate_outcomes"],
        "source_review_file_sha256": {
            key: value
            for key, value in validation["source_file_sha256"].items()
            if key.startswith("blind-v2-review-")
        },
    }
    review_bytes = _canonical_json_bytes(review_summary)
    manifest = {
        "schema_version": "router-v2-run002-dataset-manifest-v1",
        "run_id": RUN_ID,
        "commit_a": commit_a,
        "predecessor_run_id": RUN001_RUN_ID,
        "predecessor_terminal_sha256": RUN001_TERMINAL_SHA256,
        "replacement_reason": REPLACEMENT_REASON,
        "task_count": 128,
        "negative_labeled_task_count": 96,
        "skill_count": 16,
        "tasks_per_skill": 8,
        "negative_per_skill": 6,
        "positive_only_per_skill": 2,
        "semantic_family_count": 128,
        "candidate_generation_count": validation["candidate_generation_count"],
        "candidate_import_rejection_count": validation[
            "candidate_import_rejection_count"
        ],
        "accepted_candidate_count": validation["accepted_candidate_count"],
        "rejected_candidate_count": validation["rejected_candidate_count"],
        "reviewer_unanimous_agreement_count": validation[
            "reviewer_unanimous_agreement_count"
        ],
        "supplement_request_count": validation["supplement_request_count"],
        "duplicate_and_contamination_checks_passed": validation[
            "duplicate_and_contamination_checks_passed"
        ],
        "contamination_checked_candidate_count": validation[
            "contamination_checked_candidate_count"
        ],
        "generator_reviewer_configs": validation["agent_configs"],
        "authority_manifest_sha256": validation["authority_manifest_sha256"],
        "retry_records": validation["retry_records"],
        "agent_run_evidence": validation["agent_run_evidence"],
        "deterministic_selection_authority": validation[
            "deterministic_selection_authority"
        ],
        "source_skill_index_sha256": validation["source_skill_index_sha256"],
        "source_agent_file_sha256": validation["source_file_sha256"],
        "tasks_file_sha256": hashlib.sha256(task_bytes).hexdigest(),
        "review_summary_file_sha256": hashlib.sha256(review_bytes).hexdigest(),
        "source_type": "AGENT_GENERATED",
        "review_mode": "DUAL_AGENT_UNANIMOUS_REVIEWED",
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "model_scores_observed": False,
        "evaluation_started": False,
        "training_after_data_access": False,
        "router_decision": "KEEP_BASELINE",
        "default_router_unchanged": True,
        "production_ready": False,
        "release_authorized": False,
        "release_eligible": False,
        "run001_candidates_reused": False,
    }
    return {
        "blind-v2-tasks.jsonl": task_bytes,
        "blind-v2-review-summary.json": review_bytes,
        "blind-v2-manifest.json": _canonical_json_bytes(manifest),
    }


def write_dataset_freeze(
    documents: dict[str, bytes],
    output_dir: Path,
    *,
    repository_root: Path,
) -> None:
    repository = repository_root.resolve(strict=True)
    expected = repository / DATASET_FREEZE_RELATIVE
    if output_dir != expected or set(documents) != set(DATASET_FREEZE_FILENAMES):
        raise ValueError("Run002 frozen dataset destination mismatch")
    unresolved = output_dir.resolve(strict=False)
    if unresolved.exists() or output_dir.is_symlink():
        raise ValueError("Run002 frozen dataset destination must be new")
    if not unresolved.is_relative_to(repository):
        raise ValueError("Run002 frozen dataset must remain in the repository")
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for filename in DATASET_FREEZE_FILENAMES:
        with (output_dir / filename).open("xb") as handle:
            handle.write(documents[filename])


def read_frozen_dataset_documents(repository_root: Path) -> dict[str, bytes]:
    repository = repository_root.resolve(strict=True)
    root = repository / DATASET_FREEZE_RELATIVE
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Run002 frozen dataset root mismatch")
    if {path.name for path in root.iterdir()} != set(DATASET_FREEZE_FILENAMES):
        raise ValueError("Run002 frozen dataset must contain exactly three files")
    return {
        filename: (root / filename).read_bytes()
        for filename in DATASET_FREEZE_FILENAMES
    }


def _validated_evaluation_tasks(
    frozen_documents: dict[str, bytes], *, commit_a: str, run003_mode: bool = False
) -> list[dict[str, Any]]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if run003_mode:
        from hermes_skilleval import router_v2_blind_v2_run003 as run003

        active_run_id = run003.RUN_ID
        active_manifest_schema = "router-v2-run003-dataset-manifest-v1"
    else:
        active_run_id = RUN_ID
        active_manifest_schema = "router-v2-run002-dataset-manifest-v1"

    if set(frozen_documents) != set(DATASET_FREEZE_FILENAMES):
        raise ValueError("Run002 evaluation dataset file set mismatch")
    manifest = cast(
        dict[str, Any],
        json.loads(
            frozen_documents["blind-v2-manifest.json"],
            object_pairs_hook=_reject_duplicate_pairs,
        ),
    )
    raw_tasks = [
        cast(
            dict[str, Any],
            json.loads(line, object_pairs_hook=_reject_duplicate_pairs),
        )
        for line in frozen_documents["blind-v2-tasks.jsonl"].splitlines()
    ]
    if len(raw_tasks) != 128:
        raise ValueError("Run002 evaluation requires exactly 128 tasks")
    tasks: list[dict[str, Any]] = []
    expected_fields = {
        "task_id",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "gold_skill_id",
        "negative_skill_id",
        "source_type",
    }
    for raw_task in raw_tasks:
        if type(raw_task) is not dict or set(raw_task) != expected_fields:
            raise ValueError("Run002 evaluation task fields mismatch")
        prompt = raw_task["prompt_text"]
        task_id = raw_task["task_id"]
        family = raw_task["semantic_family_id"]
        gold = raw_task["gold_skill_id"]
        negative = raw_task["negative_skill_id"]
        if (
            type(task_id) is not str
            or len(task_id) != CANDIDATE_ID_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in task_id)
            or not _nonempty_string(prompt)
            or raw_task["prompt_text_sha256"]
            != hashlib.sha256(cast(str, prompt).encode("utf-8")).hexdigest()
            or not _nonempty_string(family)
            or not _nonempty_string(gold)
            or (
                negative is not None
                and (not _nonempty_string(negative) or negative == gold)
            )
            or raw_task["source_type"] != "AGENT_GENERATED"
        ):
            raise ValueError("Run002 evaluation task semantics mismatch")
        tasks.append(deepcopy(raw_task))
    gold_counts = Counter(task["gold_skill_id"] for task in tasks)
    if (
        len({task["task_id"] for task in tasks}) != 128
        or len({task["prompt_text"] for task in tasks}) != 128
        or len({task["semantic_family_id"] for task in tasks}) != 128
        or len(gold_counts) != 16
        or set(gold_counts.values()) != {8}
        or any(
            sum(
                task["gold_skill_id"] == skill_id
                and task["negative_skill_id"] is not None
                for task in tasks
            )
            != 6
            or sum(
                task["gold_skill_id"] == skill_id and task["negative_skill_id"] is None
                for task in tasks
            )
            != 2
            for skill_id in gold_counts
        )
    ):
        raise ValueError("Run002 evaluation task distribution mismatch")
    task_sha256 = hashlib.sha256(frozen_documents["blind-v2-tasks.jsonl"]).hexdigest()
    review_sha256 = hashlib.sha256(
        frozen_documents["blind-v2-review-summary.json"]
    ).hexdigest()
    if (
        manifest.get("schema_version") != active_manifest_schema
        or manifest.get("run_id") != active_run_id
        or manifest.get("commit_a") != commit_a
        or manifest.get("task_count") != 128
        or manifest.get("negative_labeled_task_count") != 96
        or manifest.get("skill_count") != 16
        or manifest.get("tasks_per_skill") != 8
        or manifest.get("negative_per_skill") != 6
        or manifest.get("positive_only_per_skill") != 2
        or manifest.get("semantic_family_count") != 128
        or manifest.get("tasks_file_sha256") != task_sha256
        or manifest.get("review_summary_file_sha256") != review_sha256
        or manifest.get("source_type") != "AGENT_GENERATED"
        or manifest.get("review_mode") != "DUAL_AGENT_UNANIMOUS_REVIEWED"
        or manifest.get("human_author_count") != 0
        or manifest.get("human_reviewer_count") != 0
        or manifest.get("model_scores_observed") is not False
        or manifest.get("evaluation_started") is not False
        or manifest.get("training_after_data_access") is not False
        or manifest.get("router_decision") != "KEEP_BASELINE"
        or manifest.get("default_router_unchanged") is not True
        or manifest.get("production_ready") is not False
        or manifest.get("release_authorized") is not False
        or type(manifest.get("retry_records")) is not list
        or type(manifest.get("agent_run_evidence")) is not list
        or type(manifest.get("deterministic_selection_authority")) is not dict
        or not _lowercase_sha256(manifest.get("authority_manifest_sha256"))
    ):
        raise ValueError(
            f"{'Run003' if run003_mode else 'Run002'} evaluation manifest mismatch"
        )
    if run003_mode:
        diagnostic_count = manifest.get("transport_diagnostic_count")
        diagnostic_types = manifest.get("transport_diagnostic_types")
        if (
            manifest.get("run001_terminal_sha256") != run003.RUN001_TERMINAL_SHA256
            or manifest.get("run002_terminal_evidence_bundle_sha256")
            != run003.RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256
            or manifest.get("replacement_reason") != run003.REPLACEMENT_REASON
            or manifest.get("run001_candidates_reused") is not False
            or manifest.get("run002_candidates_reused") is not False
            or manifest.get("run001_model_scores_observed") is not False
            or manifest.get("run002_model_scores_observed") is not False
            or manifest.get("model_scores_observed") is not False
            or manifest.get("event_policy_version") != run003.EVENT_POLICY_VERSION
            or type(diagnostic_count) is not int
            or diagnostic_count < 0
            or type(diagnostic_types) is not list
            or any(type(value) is not str or not value for value in diagnostic_types)
            or diagnostic_types != sorted(set(diagnostic_types))
            or type(manifest.get("transport_diagnostics_observed")) is not bool
            or manifest.get("transport_diagnostics_observed")
            is not (diagnostic_count > 0)
        ):
            raise ValueError("Run003 evaluation diagnostic manifest mismatch")
    workflow._jsonl_no_duplicate_keys(
        frozen_documents["blind-v2-tasks.jsonl"], "Run002 blind-v2 tasks"
    )
    return tasks


def build_evaluation_bindings(
    *,
    preregistration: dict[str, Any],
    preregistration_bytes: bytes,
    canonical_skills: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
    frozen_documents: dict[str, bytes],
    commit_a: str,
    run003_mode: bool = False,
) -> dict[str, Any]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if run003_mode:
        from hermes_skilleval import router_v2_blind_v2_run003 as run003

        active_run_id = run003.RUN_ID
        active_schema = "router-v2-run003-evaluation-bindings-v1"
        active_output_namespace = run003.OUTPUT_NAMESPACE
    else:
        active_run_id = RUN_ID
        active_schema = "router-v2-run002-evaluation-bindings-v1"
        active_output_namespace = OUTPUT_NAMESPACE

    if not _lowercase_commit(commit_a):
        raise ValueError("Run002 evaluation Commit A mismatch")
    unhashed = {
        key: value
        for key, value in preregistration.items()
        if key != "preregistration_sha256"
    }
    if preregistration.get("preregistration_sha256") != canonical_sha256(unhashed):
        raise ValueError("Run002 preregistration semantic hash mismatch")
    skills = workflow._project_canonical_skills(canonical_skills)
    models = workflow._validated_evaluation_model_bindings(model_bindings)
    tasks = _validated_evaluation_tasks(
        frozen_documents, commit_a=commit_a, run003_mode=run003_mode
    )
    manifest = cast(
        dict[str, Any],
        json.loads(
            frozen_documents["blind-v2-manifest.json"],
            object_pairs_hook=_reject_duplicate_pairs,
        ),
    )
    return {
        "schema_version": active_schema,
        "run_id": active_run_id,
        "commit_a": commit_a,
        "preregistration_file_sha256": hashlib.sha256(
            preregistration_bytes
        ).hexdigest(),
        "preregistration_sha256": preregistration["preregistration_sha256"],
        "canonical_skills": skills,
        "source_skill_index_sha256": canonical_sha256(skills),
        "evaluation_models": models,
        "blind_v2_dataset": {
            "tasks_file_sha256": hashlib.sha256(
                frozen_documents["blind-v2-tasks.jsonl"]
            ).hexdigest(),
            "manifest_file_sha256": hashlib.sha256(
                frozen_documents["blind-v2-manifest.json"]
            ).hexdigest(),
            "review_summary_file_sha256": hashlib.sha256(
                frozen_documents["blind-v2-review-summary.json"]
            ).hexdigest(),
            "task_rows": tasks,
            "source_agent_file_sha256": manifest["source_agent_file_sha256"],
        },
        "gate": deepcopy(preregistration["pilot_002_gate_artifact"]),
        "metric_definitions": deepcopy(preregistration["metric_definitions"]),
        "query_contract": deepcopy(preregistration["query_contract"]),
        "skill_representation_builder": deepcopy(
            preregistration["skill_representation_builder"]
        ),
        "evaluator": deepcopy(preregistration["evaluator"]),
        "router_decision": "KEEP_BASELINE",
        "default_router_unchanged": True,
        "output_namespace": active_output_namespace.as_posix(),
        "evaluation_kernel": "UNCHANGED_ROUTER_V2_BLIND_V2",
    }


def validate_evaluation_inputs(
    *,
    commit_a: str,
    commit_b: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_started_artifact: bytes,
    run003_mode: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    if run003_mode:
        from hermes_skilleval import router_v2_blind_v2_run003 as run003

        active_run_id = run003.RUN_ID
        active_schema = "router-v2-run003-evaluation-bindings-v1"
        active_output_namespace = run003.OUTPUT_NAMESPACE
    else:
        active_run_id = RUN_ID
        active_schema = "router-v2-run002-evaluation-bindings-v1"
        active_output_namespace = OUTPUT_NAMESPACE

    if (
        not _lowercase_commit(commit_a)
        or not _lowercase_commit(commit_b)
        or commit_a == commit_b
        or not _lowercase_sha256(attempt_token_sha256)
        or set(input_artifacts)
        != {
            "preregistration.json",
            "blind-v2-tasks.jsonl",
            "blind-v2-manifest.json",
            "review-summary.json",
        }
        or frozen_bindings.get("schema_version") != active_schema
        or frozen_bindings.get("run_id") != active_run_id
        or frozen_bindings.get("commit_a") != commit_a
        or frozen_bindings.get("router_decision") != "KEEP_BASELINE"
        or frozen_bindings.get("default_router_unchanged") is not True
        or frozen_bindings.get("output_namespace") != active_output_namespace.as_posix()
        or frozen_bindings.get("evaluation_kernel") != "UNCHANGED_ROUTER_V2_BLIND_V2"
    ):
        raise ValueError("Run002 pre-scoring authority mismatch")
    frozen_documents = {
        "blind-v2-tasks.jsonl": input_artifacts["blind-v2-tasks.jsonl"],
        "blind-v2-manifest.json": input_artifacts["blind-v2-manifest.json"],
        "blind-v2-review-summary.json": input_artifacts["review-summary.json"],
    }
    tasks = _validated_evaluation_tasks(
        frozen_documents, commit_a=commit_a, run003_mode=run003_mode
    )
    dataset = cast(dict[str, Any], frozen_bindings["blind_v2_dataset"])
    preregistration = cast(
        dict[str, Any],
        json.loads(
            input_artifacts["preregistration.json"],
            object_pairs_hook=_reject_duplicate_pairs,
        ),
    )
    if (
        frozen_bindings.get("preregistration_file_sha256")
        != hashlib.sha256(input_artifacts["preregistration.json"]).hexdigest()
        or dataset.get("tasks_file_sha256")
        != hashlib.sha256(input_artifacts["blind-v2-tasks.jsonl"]).hexdigest()
        or dataset.get("manifest_file_sha256")
        != hashlib.sha256(input_artifacts["blind-v2-manifest.json"]).hexdigest()
        or dataset.get("review_summary_file_sha256")
        != hashlib.sha256(input_artifacts["review-summary.json"]).hexdigest()
        or dataset.get("task_rows") != tasks
        or frozen_bindings.get("gate") != preregistration.get("pilot_002_gate_artifact")
        or frozen_bindings.get("metric_definitions")
        != preregistration.get("metric_definitions")
    ):
        raise ValueError("Run002 frozen dataset binding mismatch")
    started = cast(
        dict[str, Any],
        json.loads(
            attempt_started_artifact,
            object_pairs_hook=_reject_duplicate_pairs,
        ),
    )
    if (
        started.get("schema_version") != "router-v2-blind-v2-attempt-started-v1"
        or started.get("attempt_number") != 1
        or started.get("maximum_attempts") != 1
        or started.get("commit_a") != commit_a
        or started.get("commit_b") != commit_b
        or started.get("attempt_token_sha256") != attempt_token_sha256
    ):
        raise ValueError("Run002 attempt marker authority mismatch")
    skills = workflow._project_canonical_skills(frozen_bindings["canonical_skills"])
    models = workflow._validated_evaluation_model_bindings(
        frozen_bindings["evaluation_models"]
    )
    if (
        frozen_bindings.get("source_skill_index_sha256") != canonical_sha256(skills)
        or len(skills) != 16
    ):
        raise ValueError("Run002 skill authority mismatch")
    return deepcopy(tasks), deepcopy(skills), deepcopy(models)


def validate_evaluation_routes(
    route_rows: list[dict[str, Any]],
    *,
    tasks: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
) -> None:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    task_authority = {
        cast(str, task["task_id"]): (
            task["semantic_family_id"],
            task["gold_skill_id"],
            task["negative_skill_id"],
        )
        for task in tasks
    }
    expected_grid = {(arm, seed) for seed in workflow.SEEDS for arm in workflow.ARMS}
    model_hash = canonical_sha256(model_bindings)
    observed_grid: dict[str, set[tuple[str, int]]] = {
        task_id: set() for task_id in task_authority
    }
    for row in route_rows:
        task_id = row.get("task_id")
        if (
            task_id not in task_authority
            or (
                row.get("semantic_family_id"),
                row.get("gold_skill_id"),
                row.get("tempting_negative_skill_id"),
            )
            != task_authority[cast(str, task_id)]
            or (row.get("arm"), row.get("seed")) not in expected_grid
            or row.get("model_grid_authority_sha256") != model_hash
        ):
            raise ValueError("Run002 evaluation route authority mismatch")
        observed_grid[cast(str, task_id)].add(
            (cast(str, row["arm"]), cast(int, row["seed"]))
        )
    if len(route_rows) != 128 * len(expected_grid) or any(
        grid != expected_grid for grid in observed_grid.values()
    ):
        raise ValueError("Run002 evaluation route grid mismatch")
