from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Sequence, cast

from hermes_skilleval.router_v2_blind_v2_evaluation import canonical_sha256
from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AGENT_STAGING_ROOT = Path.home() / ".codex/private/hermes-blind-v2"
SEMANTIC_MODEL_SNAPSHOT = (
    Path.home()
    / ".cache/huggingface/hub"
    / "models--sentence-transformers--all-mpnet-base-v2"
    / "snapshots"
    / workflow.SEMANTIC_MODEL_REVISION
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(type(value) is dict, f"{path.name} must contain a JSON object")
    return cast(dict[str, Any], value)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        _require(
            type(value) is dict,
            f"{path.name} line {line_number} must contain a JSON object",
        )
        rows.append(cast(dict[str, Any], value))
    return rows


def _write_stdout(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _repository_file(repository: Path, raw_path: Any, *, label: str) -> Path:
    _require(type(raw_path) is str and bool(raw_path), f"{label} path is missing")
    relative = Path(cast(str, raw_path))
    _require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and relative.as_posix() == raw_path,
        f"{label} path must be canonical and repository-relative",
    )
    unresolved = repository / relative
    _require(not unresolved.is_symlink(), f"{label} must not be a symlink")
    resolved = unresolved.resolve(strict=True)
    _require(
        resolved.is_relative_to(repository) and resolved.is_file(),
        f"{label} must be a repository file",
    )
    return resolved


def _bound_file(
    repository: Path, binding: dict[str, Any], *, label: str
) -> tuple[Path, bytes]:
    path = _repository_file(repository, binding.get("path"), label=label)
    payload = path.read_bytes()
    _require(
        _sha256_bytes(payload) == binding.get("sha256"),
        f"{label} hash mismatch",
    )
    return path, payload


def _load_preregistered_agent_inputs(
    preregistration_path: Path, *, repository_root: Path
) -> dict[str, Any]:
    preregistration = _json(preregistration_path)
    frozen = cast(dict[str, Any], preregistration["frozen_inputs"])
    skill_binding = cast(dict[str, Any], preregistration["skill_index"])
    _, skill_payload = _bound_file(
        repository_root, skill_binding, label="canonical skill index"
    )
    canonical_skills = json.loads(skill_payload)
    _require(
        type(canonical_skills) is list,
        "canonical skill index must contain a JSON array",
    )

    train_binding = cast(dict[str, Any], frozen["accepted_pairs"])
    _, train_payload = _bound_file(
        repository_root, train_binding, label="frozen train source"
    )
    train_rows = [
        json.loads(line) for line in train_payload.splitlines() if line.strip()
    ]
    pilot_binding = cast(dict[str, Any], frozen["heldout_labels"])
    _, pilot_payload = _bound_file(
        repository_root, pilot_binding, label="frozen pilot source"
    )
    pilot_rows = [
        json.loads(line) for line in pilot_payload.splitlines() if line.strip()
    ]

    phase16_bindings = cast(
        list[dict[str, Any]], preregistration["old_phase16_prompt_files"]
    )
    phase16_sources = [
        _bound_file(repository_root, binding, label="frozen Phase 16 source")
        for binding in phase16_bindings
    ]
    return {
        "preregistration": preregistration,
        "canonical_skills": cast(list[dict[str, Any]], canonical_skills),
        "train_prompts": [str(row["query_text"]) for row in train_rows],
        "pilot_prompts": [str(row["query_text"]) for row in pilot_rows],
        "phase16_prompts": [payload.decode("utf-8") for _, payload in phase16_sources],
        "train_family_ids": {
            str(row["positive_source_record_id"]) for row in train_rows
        },
        "pilot_family_ids": {
            str(row["positive_source_record_id"]) for row in pilot_rows
        },
        "phase16_family_ids": set(),
        "prior_candidate_prompts": [],
        "prior_candidate_family_ids": set(),
        "construction_input_bindings": {
            "canonical_skill_source": {
                "path": skill_binding["path"],
                "file_sha256": skill_binding["sha256"],
                "source_bytes_hex": skill_payload.hex(),
            },
            "protected_scope_sources": {
                "train": [
                    {
                        "path": train_binding["path"],
                        "file_sha256": train_binding["sha256"],
                        "source_bytes_hex": train_payload.hex(),
                    }
                ],
                "pilot-002": [
                    {
                        "path": pilot_binding["path"],
                        "file_sha256": pilot_binding["sha256"],
                        "source_bytes_hex": pilot_payload.hex(),
                    }
                ],
                "phase16": [
                    {
                        "path": binding["path"],
                        "file_sha256": binding["sha256"],
                        "source_bytes_hex": payload.hex(),
                    }
                    for binding, (_, payload) in zip(
                        phase16_bindings, phase16_sources, strict=True
                    )
                ],
            },
        },
    }


def _canonical_agent_staging_root(repository: Path, commit_a: str) -> Path:
    expected = (AGENT_STAGING_ROOT / commit_a).resolve(strict=False)
    configured = os.environ.get("HERMES_BLIND_V2_ROOT")
    if configured is not None:
        configured_path = Path(configured)
        _require(
            configured_path.is_absolute(),
            "HERMES_BLIND_V2_ROOT must be absolute",
        )
        _require(
            configured_path.resolve(strict=False) == expected,
            "HERMES_BLIND_V2_ROOT must match the Commit A-agent staging authority",
        )
    _require(
        not expected.is_relative_to(repository),
        "Agent staging root must remain outside the repository",
    )
    return expected


def _commit_a_context(*, require_config_smoke: bool) -> dict[str, Any]:
    repository = REPOSITORY_ROOT.resolve(strict=True)
    preregistration_path = _repository_file(
        repository,
        workflow.PREREGISTRATION_RELATIVE.as_posix(),
        label="preregistration",
    )
    pilot_manifest_path = _repository_file(
        repository,
        workflow.PILOT_MANIFEST_RELATIVE.as_posix(),
        label="pilot manifest",
    )
    workflow.validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=False,
    )
    inputs = _load_preregistered_agent_inputs(
        preregistration_path, repository_root=repository
    )
    state = workflow.validate_commit_a_repository(repository, inputs["preregistration"])
    commit_a = cast(str, state["commit_a"])
    preregistration_file_sha256 = _sha256_bytes(preregistration_path.read_bytes())
    receipt: dict[str, Any] | None = None
    if require_config_smoke:
        receipt = workflow.validate_agent_config_smoke_receipt(
            commit_a=commit_a,
            preregistration_sha256=preregistration_file_sha256,
        )
    return {
        **inputs,
        "repository": repository,
        "preregistration_path": preregistration_path,
        "pilot_manifest_path": pilot_manifest_path,
        "commit_a": commit_a,
        "preregistration_file_sha256": preregistration_file_sha256,
        "agent_config_receipt": receipt,
        "staging_root": _canonical_agent_staging_root(repository, commit_a),
    }


def _agent_config_status(_args: argparse.Namespace) -> int:
    context = _commit_a_context(require_config_smoke=True)
    receipt = cast(dict[str, Any], context["agent_config_receipt"])
    _write_stdout(
        {
            "status": "AGENT_BLIND_V2_READY_FOR_GENERATION",
            "commit_a": context["commit_a"],
            "staging_root": str(context["staging_root"]),
            "agent_config_receipt_sha256": receipt["receipt_sha256"],
        }
    )
    return 0


def _request_round_1(_args: argparse.Namespace) -> int:
    context = _commit_a_context(require_config_smoke=True)
    selection = workflow.SELECTION_AUTHORITY
    canonical_skills = cast(list[dict[str, Any]], context["canonical_skills"])
    requests = [
        workflow.build_generator_request(
            canonical_skills,
            gold_skill_id=cast(str, skill["id"]),
            negative_quota=cast(int, selection["round_1_negative_per_skill"]),
            positive_only_quota=cast(int, selection["round_1_positive_only_per_skill"]),
            repository_root=cast(Path, context["repository"]),
            round_number=1,
        )
        for skill in sorted(canonical_skills, key=lambda row: cast(str, row["id"]))
    ]
    _write_stdout(
        {
            "status": "AGENT_BLIND_V2_ROUND_1_REQUESTS_READY",
            "stage": "round-1",
            "staging_root": str(context["staging_root"]),
            "request_count": len(requests),
            "requests": requests,
        }
    )
    return 0


def _agent_pack_file(context: dict[str, Any], filename: str) -> Path:
    _require(
        filename in workflow.REQUIRED_AGENT_PACK_FILES,
        "Agent staging filename is not preregistered",
    )
    root = cast(Path, context["staging_root"])
    _require(root.is_dir() and not root.is_symlink(), "Agent staging root is missing")
    path = root / filename
    _require(
        path.is_file() and not path.is_symlink(), f"missing Agent ledger: {filename}"
    )
    return path


def _successful_response(
    invocations: Any,
    *,
    request: dict[str, Any],
    seen_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    identities = workflow._pack_invocation_identities(invocations)
    _require(
        type(invocations) is list and len(identities) == len(invocations),
        "Agent invocation identity sequence mismatch",
    )
    _require(
        len(set(identities)) == len(identities),
        "retry sequence must use unique session/thread ids",
    )
    if seen_session_ids is not None:
        _require(
            all(identity not in seen_session_ids for identity in identities),
            "session/thread ids must be globally unique",
        )
    try:
        response, _retry_count = workflow._validate_pack_invocations(
            invocations, request=request
        )
    except workflow._AgentPackProtocolViolation as exc:
        raise ValueError("Agent invocation retry ordering mismatch") from exc
    if seen_session_ids is not None:
        seen_session_ids.update(identities)
    _require(
        response is not None,
        "Agent request requires exactly one substantive response",
    )
    return cast(dict[str, Any], response)


def _generation_candidates(
    context: dict[str, Any],
    *,
    stage: str,
    seen_session_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    round_number = {"round-1": 1, "round-2": 2}[stage]
    canonical_skills = cast(list[dict[str, Any]], context["canonical_skills"])
    selection = workflow.SELECTION_AUTHORITY
    active_session_ids = seen_session_ids if seen_session_ids is not None else set()
    validated_rows: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for index, row in enumerate(
        _jsonl(_agent_pack_file(context, "blind-v2-generation.jsonl")), start=1
    ):
        _require(
            set(row) == {"generation_round", "gold_skill_id", "request", "invocations"},
            f"generation row {index} fields mismatch",
        )
        _require(
            type(row["generation_round"]) is int and row["generation_round"] in {1, 2},
            "generation round must be 1 or 2",
        )
        request = workflow.validate_agent_request(cast(dict[str, Any], row["request"]))
        _require(request["role"] == "generator", "generation request role mismatch")
        quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
        _require(
            type(quota["round_number"]) is int and quota["round_number"] in {1, 2},
            "generation round must be 1 or 2",
        )
        _require(
            row["generation_round"] == quota["round_number"]
            and row["gold_skill_id"] == quota["gold_skill_id"],
            "generation row sealed identity mismatch",
        )
        validated_rows.append((row, request, quota))
    round_two_deficits = (
        _round_one_post_pipeline_deficits(
            context,
            seen_session_ids=active_session_ids,
            allow_later_round_reviews=True,
        )
        if round_number == 2
        else {}
    )
    expected_round_two_skills = sorted(round_two_deficits)
    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_request_skills: list[str] = []
    for row, request, quota in validated_rows:
        if quota["round_number"] != round_number:
            continue
        gold_skill_id = cast(str, quota["gold_skill_id"])
        if round_number == 1:
            negative_quota = cast(int, selection["round_1_negative_per_skill"])
            positive_only_quota = cast(
                int, selection["round_1_positive_only_per_skill"]
            )
            authority_label = "sealed round-1 request authority"
        else:
            _require(
                gold_skill_id in round_two_deficits,
                "sealed round-2 request authority mismatch",
            )
            multiplier = cast(int, selection["round_2_deficit_multiplier"])
            counts = round_two_deficits[gold_skill_id]
            negative_quota = counts["negative"] * multiplier
            positive_only_quota = counts["positive_only"] * multiplier
            authority_label = "sealed round-2 request authority"
        expected = workflow.build_generator_request(
            canonical_skills,
            gold_skill_id=gold_skill_id,
            negative_quota=negative_quota,
            positive_only_quota=positive_only_quota,
            repository_root=cast(Path, context["repository"]),
            round_number=round_number,
        )
        _require(request == expected, f"{authority_label} mismatch")
        _require(
            gold_skill_id not in seen_request_skills,
            f"{authority_label} duplicated",
        )
        seen_request_skills.append(gold_skill_id)
        response = _successful_response(
            row["invocations"],
            request=request,
            seen_session_ids=active_session_ids,
        )
        response_sha256 = canonical_sha256(response)
        for generated in sorted(
            cast(list[dict[str, Any]], response["candidates"]),
            key=lambda candidate: cast(int, candidate["candidate_index"]),
        ):
            candidate_id = workflow.opaque_candidate_id(
                round_number,
                cast(str, quota["gold_skill_id"]),
                cast(int, generated["candidate_index"]),
                response_sha256,
            )
            _require(candidate_id not in seen_ids, "candidate id duplicated")
            seen_ids.add(candidate_id)
            prompt_text = cast(str, generated["prompt_text"])
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "generation_round": round_number,
                    "prompt_text": prompt_text,
                    "prompt_text_sha256": _sha256_bytes(prompt_text.encode("utf-8")),
                    "semantic_family_id": generated["semantic_family_id"],
                    "proposed_gold_skill_id": generated["proposed_gold_skill_id"],
                    "proposed_negative_skill_id": generated[
                        "proposed_negative_skill_id"
                    ],
                    "language": generated["language"],
                    "rationale": generated["rationale"],
                }
            )
    expected_request_skills = (
        sorted(cast(str, skill["id"]) for skill in canonical_skills)
        if round_number == 1
        else expected_round_two_skills
    )
    _require(
        seen_request_skills == expected_request_skills,
        f"sealed {stage} request schedule mismatch",
    )
    _require(bool(candidates), f"{stage} generator responses are missing")
    return candidates


def _validated_contamination_clean_ids(
    context: dict[str, Any], candidates: list[dict[str, Any]]
) -> set[str]:
    similarity, semantic_model_authority = _semantic_validation_components()
    replay = workflow._scan_contamination(
        candidates,
        protected_prompts={
            "train": cast(list[str], context["train_prompts"]),
            "pilot-002": cast(list[str], context["pilot_prompts"]),
            "phase16": cast(list[str], context["phase16_prompts"]),
            "prior_candidate": cast(list[str], context["prior_candidate_prompts"]),
        },
        protected_family_ids={
            "train": cast(set[str], context["train_family_ids"]),
            "pilot-002": cast(set[str], context["pilot_family_ids"]),
            "phase16": cast(set[str], context["phase16_family_ids"]),
            "prior_candidate": cast(set[str], context["prior_candidate_family_ids"]),
        },
        semantic_similarity=similarity,
        semantic_model_authority=semantic_model_authority,
    )
    staged_rows = _jsonl(_agent_pack_file(context, "blind-v2-contamination.jsonl"))
    _require(
        staged_rows == replay["rows"],
        "contamination ledger authority mismatch",
    )
    return set(cast(list[str], replay["clean_candidate_ids"]))


def _review_candidates(context: dict[str, Any], *, stage: str) -> list[dict[str, Any]]:
    stage_candidates = _generation_candidates(context, stage=stage)
    scan_candidates = (
        _generation_candidates(context, stage="round-1") + stage_candidates
        if stage == "round-2"
        else stage_candidates
    )
    clean = _validated_contamination_clean_ids(context, scan_candidates)
    selected = [row for row in stage_candidates if row["candidate_id"] in clean]
    _require(bool(selected), f"{stage} has no contamination-clean candidates")
    return selected


def _validate_existing_review_sequences(context: dict[str, Any], *, stage: str) -> None:
    round_one = _generation_candidates(context, stage="round-1")
    round_two = (
        _generation_candidates(context, stage="round-2") if stage == "round-2" else []
    )
    if stage == "round-1":
        raw_generation_rows = _jsonl(
            _agent_pack_file(context, "blind-v2-generation.jsonl")
        )
        _require(
            all(row.get("generation_round") == 1 for row in raw_generation_rows),
            "round-1 reviews must precede round-2 generation",
        )
    all_candidates = round_one + round_two
    candidates_by_id = {
        cast(str, candidate["candidate_id"]): candidate for candidate in all_candidates
    }
    clean_ids = _validated_contamination_clean_ids(context, all_candidates)
    seen_session_ids: set[str] = set()
    for row in _jsonl(_agent_pack_file(context, "blind-v2-generation.jsonl")):
        identities = workflow._pack_invocation_identities(row.get("invocations"))
        _require(
            type(row.get("invocations")) is list
            and len(identities) == len(cast(list[Any], row["invocations"])),
            "generator invocation identity sequence mismatch",
        )
        _require(
            all(identity not in seen_session_ids for identity in identities),
            "session/thread ids must be globally unique",
        )
        seen_session_ids.update(identities)

    projected_skills = workflow._project_canonical_skills(
        cast(list[dict[str, Any]], context["canonical_skills"])
    )
    for role, filename in (
        ("reviewer_a", "blind-v2-review-a.jsonl"),
        ("reviewer_b", "blind-v2-review-b.jsonl"),
    ):
        actual_by_round: dict[int, list[str]] = {1: [], 2: []}
        seen_candidates: set[str] = set()
        for raw_row in _jsonl(_agent_pack_file(context, filename)):
            row, candidate_id, request = workflow._validated_reviewer_source_row(
                raw_row,
                role=role,
                candidates=candidates_by_id,
                projected_skills=projected_skills,
                clean_candidate_ids=clean_ids,
                label=f"{role} staged row",
            )
            _require(
                candidate_id not in seen_candidates,
                f"{role} candidate duplicated",
            )
            seen_candidates.add(candidate_id)
            candidate_round = cast(
                int, candidates_by_id[candidate_id]["generation_round"]
            )
            actual_by_round[candidate_round].append(candidate_id)
            _successful_response(
                row["invocations"],
                request=request,
                seen_session_ids=seen_session_ids,
            )

        expected_by_round = {
            round_number: sorted(
                (
                    candidate_id
                    for candidate_id in clean_ids
                    if candidates_by_id[candidate_id]["generation_round"]
                    == round_number
                ),
                key=lambda candidate_id: workflow.review_schedule_key(
                    role, candidate_id
                ),
            )
            for round_number in (1, 2)
        }
        _require(
            actual_by_round[1]
            == (
                expected_by_round[1]
                if stage == "round-2"
                else expected_by_round[1][: len(actual_by_round[1])]
            ),
            f"{role} round-1 ledger schedule mismatch",
        )
        _require(
            actual_by_round[2] == expected_by_round[2][: len(actual_by_round[2])],
            f"{role} round-2 ledger schedule mismatch",
        )


def _request_reviews(args: argparse.Namespace) -> int:
    context = _commit_a_context(require_config_smoke=True)
    candidates = sorted(
        _review_candidates(context, stage=args.stage),
        key=lambda candidate: workflow.review_schedule_key(
            args.role, cast(str, candidate["candidate_id"])
        ),
    )
    _validate_existing_review_sequences(context, stage=args.stage)
    requests = [
        workflow.build_reviewer_request(
            candidate,
            cast(list[dict[str, Any]], context["canonical_skills"]),
            role=args.role,
        )
        for candidate in candidates
    ]
    _write_stdout(
        {
            "status": "AGENT_BLIND_V2_REVIEW_REQUESTS_READY",
            "stage": args.stage,
            "role": args.role,
            "staging_root": str(context["staging_root"]),
            "request_count": len(requests),
            "requests": requests,
        }
    )
    return 0


def _review_responses(
    context: dict[str, Any],
    *,
    role: str,
    candidates: dict[str, dict[str, Any]],
    seen_session_ids: set[str],
    allow_later_round_rows: bool = False,
) -> dict[str, dict[str, Any]]:
    filename = {
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    responses: dict[str, dict[str, Any]] = {}
    actual_order: list[str] = []
    skills = cast(list[dict[str, Any]], context["canonical_skills"])
    for row in _jsonl(_agent_pack_file(context, filename)):
        _require(
            set(row) == {"candidate_id", "request", "invocations"},
            f"{role} source row fields mismatch",
        )
        candidate_id = row.get("candidate_id")
        if candidate_id not in candidates and allow_later_round_rows:
            continue
        _require(candidate_id in candidates, "review references unknown candidate")
        _require(candidate_id not in responses, f"{role} candidate duplicated")
        actual_order.append(cast(str, candidate_id))
        expected = workflow.build_reviewer_request(
            candidates[cast(str, candidate_id)], skills, role=role
        )
        request = workflow.validate_agent_request(cast(dict[str, Any], row["request"]))
        _require(request == expected, f"{role} request authority mismatch")
        responses[cast(str, candidate_id)] = _successful_response(
            row["invocations"],
            request=request,
            seen_session_ids=seen_session_ids,
        )
    expected_order = sorted(
        candidates,
        key=lambda candidate_id: workflow.review_schedule_key(role, candidate_id),
    )
    _require(actual_order == expected_order, f"{role} ledger schedule mismatch")
    return responses


def _unanimously_accepted(
    candidate: dict[str, Any],
    review_a: dict[str, Any],
    review_b: dict[str, Any],
) -> bool:
    return workflow._reviewers_unanimously_accept(
        (review_a, review_b),
        expected_labels=(
            cast(str, candidate["proposed_gold_skill_id"]),
            cast(str | None, candidate["proposed_negative_skill_id"]),
        ),
    )


def _round_one_post_pipeline_deficits(
    context: dict[str, Any],
    *,
    seen_session_ids: set[str] | None = None,
    allow_later_round_reviews: bool = False,
) -> dict[str, dict[str, int]]:
    active_session_ids = seen_session_ids if seen_session_ids is not None else set()
    round_one_candidates = _generation_candidates(
        context,
        stage="round-1",
        seen_session_ids=active_session_ids,
    )
    clean_candidate_ids = _validated_contamination_clean_ids(
        context, round_one_candidates
    )
    candidates = {
        cast(str, row["candidate_id"]): row
        for row in round_one_candidates
        if row["candidate_id"] in clean_candidate_ids
    }
    review_a = _review_responses(
        context,
        role="reviewer_a",
        candidates=candidates,
        seen_session_ids=active_session_ids,
        allow_later_round_rows=allow_later_round_reviews,
    )
    review_b = _review_responses(
        context,
        role="reviewer_b",
        candidates=candidates,
        seen_session_ids=active_session_ids,
        allow_later_round_rows=allow_later_round_reviews,
    )
    _require(
        set(review_a) == set(candidates) == set(review_b),
        "round 1 reviews must be complete before round 2",
    )
    accepted = [
        candidate
        for candidate_id, candidate in candidates.items()
        if _unanimously_accepted(
            candidate, review_a[candidate_id], review_b[candidate_id]
        )
    ]
    selection = workflow.SELECTION_AUTHORITY
    skill_ids = sorted(
        cast(str, skill["id"])
        for skill in cast(list[dict[str, Any]], context["canonical_skills"])
    )
    deficits: dict[str, dict[str, int]] = {}
    for skill_id in skill_ids:
        negative_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is not None
            for row in accepted
        )
        positive_only_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is None
            for row in accepted
        )
        skill_deficits = {
            "negative": max(
                0,
                cast(int, selection["final_negative_per_skill"]) - negative_count,
            ),
            "positive_only": max(
                0,
                cast(int, selection["final_positive_only_per_skill"])
                - positive_only_count,
            ),
        }
        if any(skill_deficits.values()):
            deficits[skill_id] = skill_deficits
    return deficits


def _round_two_deficits(context: dict[str, Any]) -> dict[str, dict[str, int]]:
    generation_rows = _jsonl(_agent_pack_file(context, "blind-v2-generation.jsonl"))
    _require(
        all(
            row.get("generation_round") == 1
            and type(row.get("request")) is dict
            and cast(dict[str, Any], row["request"])
            .get("input", {})
            .get("quota", {})
            .get("round_number")
            == 1
            for row in generation_rows
        ),
        "round 2 has already been generated",
    )
    return _round_one_post_pipeline_deficits(context)


def _request_round_2(_args: argparse.Namespace) -> int:
    context = _commit_a_context(require_config_smoke=True)
    deficits = _round_two_deficits(context)
    multiplier = cast(int, workflow.SELECTION_AUTHORITY["round_2_deficit_multiplier"])
    requests = [
        workflow.build_generator_request(
            cast(list[dict[str, Any]], context["canonical_skills"]),
            gold_skill_id=skill_id,
            negative_quota=counts["negative"] * multiplier,
            positive_only_quota=counts["positive_only"] * multiplier,
            repository_root=cast(Path, context["repository"]),
            round_number=2,
        )
        for skill_id, counts in sorted(deficits.items())
    ]
    _write_stdout(
        {
            "status": (
                "AGENT_BLIND_V2_ROUND_2_REQUESTS_READY"
                if requests
                else "AGENT_BLIND_V2_ROUND_2_NOT_REQUIRED"
            ),
            "stage": "round-2",
            "staging_root": str(context["staging_root"]),
            "deficits": deficits,
            "request_count": len(requests),
            "requests": requests,
        }
    )
    return 0


class _SemanticSimilarity:
    def __init__(self, model_path: Path) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for contamination replay"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )
        self._cache: dict[str, list[float]] = {}

    def _embedding(self, text: str) -> list[float]:
        if text not in self._cache:
            value = self._model.encode([text], normalize_embeddings=True)
            if hasattr(value, "tolist"):
                value = value.tolist()
            rows = cast(list[list[float]], value)
            _require(len(rows) == 1 and bool(rows[0]), "semantic embedding mismatch")
            self._cache[text] = rows[0]
        return self._cache[text]

    def __call__(self, left: str, right: str) -> float:
        left_embedding = self._embedding(left)
        right_embedding = self._embedding(right)
        _require(
            len(left_embedding) == len(right_embedding),
            "semantic embedding dimensions differ",
        )
        value = sum(
            left_value * right_value
            for left_value, right_value in zip(
                left_embedding, right_embedding, strict=True
            )
        )
        _require(math.isfinite(value), "semantic similarity must be finite")
        return value


def _semantic_validation_components() -> tuple[_SemanticSimilarity, dict[str, Any]]:
    snapshot = SEMANTIC_MODEL_SNAPSHOT.resolve(strict=True)
    _require(snapshot.is_dir(), "preregistered semantic model snapshot is missing")
    files = [
        {
            "path": path.relative_to(snapshot).as_posix(),
            "sha256": _sha256_bytes(path.read_bytes()),
        }
        for path in sorted(snapshot.rglob("*"))
        if path.is_file()
    ]
    _require(bool(files), "preregistered semantic model files are missing")
    authority = {
        "materialized_model_files": files,
        "materialized_model_files_sha256": canonical_sha256(files),
    }
    return _SemanticSimilarity(snapshot), authority


def _validated_pack_context() -> tuple[
    dict[str, Any], dict[str, Any], _SemanticSimilarity
]:
    context = _commit_a_context(require_config_smoke=True)
    for filename in workflow.REQUIRED_AGENT_PACK_FILES:
        _agent_pack_file(context, filename)
    metadata = _json(_agent_pack_file(context, "agent-run-metadata.json"))
    first_read_timestamp = metadata.get("first_read_timestamp")
    _require(
        type(first_read_timestamp) is str and bool(first_read_timestamp),
        "Agent metadata first-read timestamp is missing",
    )
    similarity, semantic_model_authority = _semantic_validation_components()
    validation = workflow.validate_agent_pack(
        cast(Path, context["staging_root"]),
        repository_root=cast(Path, context["repository"]),
        canonical_skills=cast(list[dict[str, Any]], context["canonical_skills"]),
        train_prompts=cast(list[str], context["train_prompts"]),
        pilot_prompts=cast(list[str], context["pilot_prompts"]),
        phase16_prompts=cast(list[str], context["phase16_prompts"]),
        train_family_ids=cast(set[str], context["train_family_ids"]),
        pilot_family_ids=cast(set[str], context["pilot_family_ids"]),
        phase16_family_ids=cast(set[str], context["phase16_family_ids"]),
        prior_candidate_prompts=cast(list[str], context["prior_candidate_prompts"]),
        prior_candidate_family_ids=cast(
            set[str], context["prior_candidate_family_ids"]
        ),
        first_read_timestamp=cast(str, first_read_timestamp),
        semantic_similarity=similarity,
        semantic_model_authority=semantic_model_authority,
        construction_input_bindings=cast(
            dict[str, Any], context["construction_input_bindings"]
        ),
    )
    return context, validation, similarity


def _pack_status(_args: argparse.Namespace) -> int:
    context, validation, _similarity = _validated_pack_context()
    _write_stdout(
        {
            "status": validation["status"],
            "research_conclusion": validation.get("research_conclusion"),
            "commit_a": context["commit_a"],
            "task_count": validation.get("task_count", 0),
            "negative_labeled_task_count": validation.get(
                "negative_labeled_task_count", 0
            ),
            "family_count": validation.get("family_count", 0),
            "deficits": validation.get("deficits", {}),
            "model_scores_observed": validation.get("model_scores_observed", False),
        }
    )
    return 0 if validation["status"] == "VALID" else 3


def _freeze(_args: argparse.Namespace) -> int:
    context, validation, similarity = _validated_pack_context()
    _require(validation["status"] == "VALID", "valid Agent pack is required")
    documents = workflow.build_dataset_freeze_documents(
        validation,
        commit_a=cast(str, context["commit_a"]),
        semantic_similarity=similarity,
    )
    output_dir = cast(Path, context["repository"]) / workflow.DATASET_FREEZE_RELATIVE
    workflow.write_dataset_freeze(documents, output_dir)
    _write_stdout(
        {
            "status": "AGENT_BLIND_V2_DATASET_FROZEN",
            "commit_a": context["commit_a"],
            "output_dir": str(output_dir),
            "task_count": validation["task_count"],
            "negative_labeled_task_count": validation["negative_labeled_task_count"],
            "family_count": validation["family_count"],
        }
    )
    return 0


def _model_smoke(_args: argparse.Namespace) -> int:
    repository = REPOSITORY_ROOT.resolve(strict=False)
    pilot_manifest_path = repository / workflow.PILOT_MANIFEST_RELATIVE
    receipt = workflow.run_model_load_smoke(
        pilot_manifest_path, repository_root=repository
    )
    receipt_path = workflow.write_model_load_smoke_receipt(receipt)
    _write_stdout({**receipt, "receipt_path": str(receipt_path)})
    return 0


def _commit_b_context(*, require_model_smoke: bool) -> dict[str, Any]:
    repository = REPOSITORY_ROOT.resolve(strict=True)
    preregistration_path = _repository_file(
        repository,
        workflow.PREREGISTRATION_RELATIVE.as_posix(),
        label="preregistration",
    )
    pilot_manifest_path = _repository_file(
        repository,
        workflow.PILOT_MANIFEST_RELATIVE.as_posix(),
        label="pilot manifest",
    )
    workflow.validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=False,
    )
    inputs = _load_preregistered_agent_inputs(
        preregistration_path, repository_root=repository
    )
    frozen_documents = workflow.read_frozen_dataset_documents(repository)
    blind_manifest = json.loads(
        frozen_documents["blind-v2-manifest.json"].decode("utf-8")
    )
    _require(type(blind_manifest) is dict, "frozen dataset manifest mismatch")
    state = workflow.validate_commit_b_repository(
        repository, commit_a=cast(str, blind_manifest["commit_a"])
    )
    preregistration_file_sha256 = _sha256_bytes(preregistration_path.read_bytes())
    frozen_manifest_file_sha256 = _sha256_bytes(
        frozen_documents["blind-v2-manifest.json"]
    )
    receipt: dict[str, Any] | None = None
    if require_model_smoke:
        receipt = workflow.validate_model_load_smoke_receipt(
            commit_a=cast(str, state["commit_a"]),
            commit_b=cast(str, state["commit_b"]),
            preregistration_sha256=preregistration_file_sha256,
            frozen_dataset_manifest_sha256=frozen_manifest_file_sha256,
        )
    return {
        **inputs,
        **state,
        "repository": repository,
        "preregistration_path": preregistration_path,
        "pilot_manifest_path": pilot_manifest_path,
        "frozen_documents": frozen_documents,
        "blind_manifest": blind_manifest,
        "preregistration_file_sha256": preregistration_file_sha256,
        "frozen_manifest_file_sha256": frozen_manifest_file_sha256,
        "model_smoke_receipt": receipt,
    }


def _model_bindings(pilot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "arm": row["arm"],
            "seed": row["seed"],
            "model_path": row["model_path"],
            "model_manifest_path": row["model_manifest_path"],
            "model_manifest_file_sha256": row["model_manifest_file_sha256"],
            "model_manifest_sha256": row["model_manifest_sha256"],
            "model_file_manifest_sha256": row["model_file_manifest_sha256"],
            "model_files": row["model_file_manifest"],
        }
        for row in cast(list[dict[str, Any]], pilot["training_artifacts"])
        if row.get("arm") in {"A", "C"}
    ]
    _require(len(rows) == 6, "pilot manifest does not contain the A/C model grid")
    return rows


def _evaluate(_args: argparse.Namespace) -> int:
    context = _commit_b_context(require_model_smoke=True)
    repository = cast(Path, context["repository"])
    preregistration_path = cast(Path, context["preregistration_path"])
    pilot_manifest_path = cast(Path, context["pilot_manifest_path"])
    frozen_documents = cast(dict[str, bytes], context["frozen_documents"])
    authority = workflow.validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    tasks = [
        json.loads(line)
        for line in frozen_documents["blind-v2-tasks.jsonl"].splitlines()
        if line.strip()
    ]
    pilot = _json(pilot_manifest_path)
    bindings = _model_bindings(pilot)
    lineage_bindings = workflow.build_authoritative_lineage_bindings(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        frozen_documents=frozen_documents,
    )
    attempt_token_sha256 = canonical_sha256(
        {
            "schema_version": "router-v2-blind-v2-attempt-token-v1",
            "commit_a": context["commit_a"],
            "commit_b": context["commit_b"],
            "preregistration_sha256": authority["preregistration_sha256"],
            "blind_v2_manifest_file_sha256": context["frozen_manifest_file_sha256"],
            "output_namespace": str(workflow.FINAL_NAMESPACE_RELATIVE),
        }
    )
    started_payload = {
        "commit_a": context["commit_a"],
        "commit_b": context["commit_b"],
        "attempt_token_sha256": attempt_token_sha256,
    }
    attempt_artifacts = {
        "attempt-1.started.json": _canonical_bytes(
            workflow.build_attempt_started_document(started_payload)
        ),
        "attempt-1.terminal.json": _canonical_bytes(
            workflow.build_attempt_terminal_document(
                len(workflow.EVALUATION_OUTPUT_FILENAMES)
            )
        ),
    }
    input_artifacts = {
        "preregistration.json": preregistration_path.read_bytes(),
        "blind-v2-tasks.jsonl": frozen_documents["blind-v2-tasks.jsonl"],
        "blind-v2-manifest.json": frozen_documents["blind-v2-manifest.json"],
        "review-summary.json": frozen_documents["blind-v2-review-summary.json"],
    }
    tasks, validated_skills, bindings = workflow._validated_pre_scoring_authority(
        tasks=cast(list[dict[str, Any]], tasks),
        skills=cast(list[dict[str, Any]], context["canonical_skills"]),
        model_bindings=bindings,
        commit_a=cast(str, context["commit_a"]),
        commit_b=cast(str, context["commit_b"]),
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=lineage_bindings,
        input_artifacts=input_artifacts,
        attempt_started_artifact=attempt_artifacts["attempt-1.started.json"],
    )

    def evaluate() -> dict[str, bytes]:
        routes = workflow.evaluate_routes(
            tasks,
            validated_skills,
            bindings,
            commit_a=cast(str, context["commit_a"]),
            commit_b=cast(str, context["commit_b"]),
            attempt_token_sha256=attempt_token_sha256,
            frozen_bindings=lineage_bindings,
            input_artifacts=input_artifacts,
            attempt_started_artifact=attempt_artifacts["attempt-1.started.json"],
        )
        return workflow.build_evaluation_documents(
            routes,
            commit_a=cast(str, context["commit_a"]),
            commit_b=cast(str, context["commit_b"]),
            evaluator_commit=cast(str, context["commit_a"]),
            attempt_token_sha256=attempt_token_sha256,
            frozen_bindings=lineage_bindings,
            input_artifacts=input_artifacts,
            attempt_artifacts=attempt_artifacts,
        )

    protected_roots = [Path(cast(str, pilot["training_execution_root"]))]
    terminal = workflow.run_single_attempt(
        repository / workflow.FINAL_NAMESPACE_RELATIVE,
        repository_root=repository,
        started_payload=started_payload,
        evaluate=evaluate,
        protected_roots=protected_roots,
    )
    _write_stdout(terminal)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the sealed Router V2 Agent-only final blind-v2 workflow."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser(
        "agent-config-status",
        help="Validate the Commit A-agent configuration receipt.",
    )
    status.set_defaults(handler=_agent_config_status)

    round_one = commands.add_parser(
        "request-round-1",
        help="Emit the preregistered first-round generator requests.",
    )
    round_one.set_defaults(handler=_request_round_1)

    reviews = commands.add_parser(
        "request-reviews",
        help="Emit one role-isolated review schedule.",
    )
    reviews.add_argument("--stage", choices=("round-1", "round-2"), required=True)
    reviews.add_argument("--role", choices=("reviewer_a", "reviewer_b"), required=True)
    reviews.set_defaults(handler=_request_reviews)

    round_two = commands.add_parser(
        "request-round-2",
        help="Emit the one permitted deficit-only generator round.",
    )
    round_two.set_defaults(handler=_request_round_2)

    pack_status = commands.add_parser(
        "pack-status",
        help="Validate the sealed Agent construction ledgers.",
    )
    pack_status.set_defaults(handler=_pack_status)

    freeze = commands.add_parser(
        "freeze",
        help="Freeze the validated Agent-selected dataset.",
    )
    freeze.set_defaults(handler=_freeze)

    model_smoke = commands.add_parser(
        "model-smoke",
        help="Run the post-Commit-B fixed A/C model-load check.",
    )
    model_smoke.set_defaults(handler=_model_smoke)

    evaluate = commands.add_parser(
        "evaluate",
        help="Consume the only preregistered formal attempt.",
    )
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
