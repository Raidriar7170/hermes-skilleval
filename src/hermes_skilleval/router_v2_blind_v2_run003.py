"""Run003-only authority for validated transient transport diagnostics."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from hermes_skilleval import router_v2_blind_v2_output_schema_preflight as preflight
from hermes_skilleval import router_v2_blind_v2_run002 as run002


RUN_ID = "router-v2-v4-successor-blind-v2-003"
RUN001_RUN_ID = run002.RUN001_RUN_ID
RUN001_TERMINAL_SHA256 = run002.RUN001_TERMINAL_SHA256
RUN002_RUN_ID = run002.RUN_ID
RUN002_TERMINAL_GIT_COMMIT = "8a34995f85954777b1130c4be8c94a2e5e3e950b"
RUN002_TERMINAL_EVIDENCE_BUNDLE = {
    "schema_version": "router-v2-run002-terminal-evidence-bundle-v1",
    "run_id": RUN002_RUN_ID,
    "git_commit": RUN002_TERMINAL_GIT_COMMIT,
    "standalone_terminal_json_present": False,
    "authority_manifest_sha256": (
        "936877c62c452370906c693be4d92abad23e99bdb24b4c7cd86397ddc3435a32"
    ),
    "generator_canary_prompt_sha256": (
        "5fc04bf46e83e5dc9549879728f31d453d6590d031738b1a39b5ef21ffa276ab"
    ),
    "generator_canary_response_schema_sha256": (
        "ef75d30acaeec87bbe1b300ff10b59f599a60c40dc3cddb51e3f7129dfc1bf3a"
    ),
    "generator_canary_events_sha256": (
        "a1d17f4e174ff8082b485d0d97f5e183036114a6feebdd697255296f0d2841e3"
    ),
    "generator_canary_response_sha256": (
        "65bab0ff3805bcac82d9102bbcb4ebefe1f8f7115c2a2803cdba8d3fd07cfbe6"
    ),
}
RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256 = run002.canonical_sha256(
    RUN002_TERMINAL_EVIDENCE_BUNDLE
)
REPLACEMENT_REASON = "ALLOW_VALIDATED_TRANSIENT_TRANSPORT_DIAGNOSTICS"
EVENT_POLICY_VERSION = preflight.RUN003_EVENT_POLICY_VERSION
PRIVATE_EVIDENCE_BASE = (
    Path.home() / ".codex/private/hermes-blind-v2-successor-run003" / RUN_ID
)
OUTPUT_NAMESPACE = Path("artifacts/router-v2-blind-v2") / RUN_ID
DATASET_FREEZE_RELATIVE = Path("data/router-v2-blind-v2-successor-003")
DATASET_FREEZE_FILENAMES = run002.DATASET_FREEZE_FILENAMES
AUTHORITY_MANIFEST_FILENAME = "run003-authority-manifest.json"
FORMAL_GENERATOR_MAX_CONCURRENCY = run002.FORMAL_GENERATOR_MAX_CONCURRENCY
GENERATOR_RESPONSE_SCHEMA_VERSION = "router-v2-run003-generator-response-v1"
GENERATOR_RESPONSE_SIZE = run002.GENERATOR_RESPONSE_SIZE
GENERATOR_CANDIDATE_FIELDS = run002.GENERATOR_CANDIDATE_FIELDS
GENERATOR_RESPONSE_SCHEMA = deepcopy(run002.GENERATOR_RESPONSE_SCHEMA)
GENERATOR_RULES = deepcopy(run002.GENERATOR_RULES)
AGENT_CONFIGS = deepcopy(run002.AGENT_CONFIGS)
TERMINAL_TRUTH = deepcopy(run002.TERMINAL_TRUTH)
GENERATOR_SYSTEM_PROMPT = run002.GENERATOR_SYSTEM_PROMPT.replace("Run002", "Run003")
FORMAL_GENERATOR_SYSTEM_PROMPT = run002.FORMAL_GENERATOR_SYSTEM_PROMPT.replace(
    "Run002", "Run003"
)


def canonical_sha256(value: object) -> str:
    return run002.canonical_sha256(value)


def _lowercase_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 40
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


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


def _request_authority(
    *,
    role: str,
    commit_a: str,
    system_prompt: str,
    response_schema: dict[str, Any],
) -> dict[str, str]:
    if role not in AGENT_CONFIGS or not _lowercase_commit(commit_a):
        raise ValueError("Run003 request authority mismatch")
    return {
        "run_id": RUN_ID,
        "commit_a": commit_a,
        "system_prompt_sha256": canonical_sha256(system_prompt),
        "response_schema_sha256": canonical_sha256(response_schema),
        "agent_config_sha256": canonical_sha256(AGENT_CONFIGS[role]),
        "event_policy_version": EVENT_POLICY_VERSION,
    }


def build_generator_canary_request() -> dict[str, Any]:
    base = run002.build_generator_canary_request()
    payload = {
        key: deepcopy(value) for key, value in base.items() if key != "request_sha256"
    }
    payload["schema_version"] = "router-v2-run003-generation-request-v1"
    payload["system_prompt"] = GENERATOR_SYSTEM_PROMPT
    payload["response_schema"] = deepcopy(GENERATOR_RESPONSE_SCHEMA)
    cast(dict[str, Any], payload["input"])["run_id"] = RUN_ID
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
    base = run002.build_formal_generator_request(
        canonical_skills,
        commit_a=commit_a,
        gold_skill_id=gold_skill_id,
        negative_quota=negative_quota,
        positive_only_quota=positive_only_quota,
        round_number=round_number,
    )
    payload = {
        key: deepcopy(value) for key, value in base.items() if key != "request_sha256"
    }
    payload["schema_version"] = "router-v2-run003-generation-request-v1"
    payload["system_prompt"] = FORMAL_GENERATOR_SYSTEM_PROMPT
    payload["response_schema"] = deepcopy(GENERATOR_RESPONSE_SCHEMA)
    payload["authority"] = _request_authority(
        role="generator",
        commit_a=commit_a,
        system_prompt=FORMAL_GENERATOR_SYSTEM_PROMPT,
        response_schema=GENERATOR_RESPONSE_SCHEMA,
    )
    cast(dict[str, Any], payload["input"])["run_id"] = RUN_ID
    return {**payload, "request_sha256": canonical_sha256(payload)}


def build_reviewer_request(
    candidate: dict[str, Any],
    canonical_skills: list[dict[str, Any]],
    *,
    role: str,
    commit_a: str,
) -> dict[str, Any]:
    from hermes_skilleval import router_v2_blind_v2_evaluation_runner as workflow

    base = workflow.build_reviewer_request(
        candidate,
        canonical_skills,
        role=role,
        successor_output_schema=True,
    )
    payload = {
        key: deepcopy(value) for key, value in base.items() if key != "request_sha256"
    }
    payload["schema_version"] = "router-v2-run003-review-request-v1"
    payload["authority"] = _request_authority(
        role=role,
        commit_a=commit_a,
        system_prompt=cast(str, payload["system_prompt"]),
        response_schema=cast(dict[str, Any], payload["response_schema"]),
    )
    return {**payload, "request_sha256": canonical_sha256(payload)}


def validate_generator_response_structure(response: object) -> dict[str, Any]:
    return run002.validate_generator_response_structure(response)


def import_generator_response(
    response: object,
    *,
    request_id: str,
    expected_gold_skill_id: str,
    expected_negative_quota: int,
    expected_positive_only_quota: int,
    canonical_skill_ids: set[str],
) -> dict[str, Any]:
    return run002._import_generator_response_for_run(
        response,
        run_id=RUN_ID,
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
    transport_failure_no_response: bool = False,
    syntactically_valid_response: bool = False,
) -> bool:
    return run002.retry_allowed(
        failure_kind,
        retry_count=retry_count,
        transport_failure_no_response=transport_failure_no_response,
        syntactically_valid_response=syntactically_valid_response,
    )


round_one_quota_plan = run002.round_one_quota_plan
supplement_quota_plan = run002.supplement_quota_plan
synthetic_canary_response = run002.synthetic_canary_response


def run_generator_canary(response: object | None = None) -> dict[str, Any]:
    request_id = canonical_sha256(
        {
            "schema_version": "router-v2-run003-generator-canary-request-v1",
            "run_id": RUN_ID,
            "synthetic": True,
            "response_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
            "event_policy_version": EVENT_POLICY_VERSION,
        }
    )
    imported = import_generator_response(
        synthetic_canary_response() if response is None else response,
        request_id=request_id,
        expected_gold_skill_id="synthetic-skill-00",
        expected_negative_quota=12,
        expected_positive_only_quota=4,
        canonical_skill_ids={f"synthetic-skill-{index:02d}" for index in range(16)},
    )
    if imported["request_outcome"] != "ACCEPTED":
        raise ValueError("Run003 Generator canary response is invalid")
    accepted = cast(list[dict[str, Any]], imported["accepted_candidates"])
    return {
        "status": "RUN003_GENERATOR_CANARY_PASSED",
        "run_id": RUN_ID,
        "candidate_count": len(accepted),
        "candidate_indexes": [row["candidate_index"] for row in accepted],
        "candidate_ids": [row["candidate_id"] for row in accepted],
        "request_id": request_id,
        "generator_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
        "event_policy_version": EVENT_POLICY_VERSION,
        "formal_data_written": False,
        "router_loaded": False,
    }


def private_evidence_root(commit_a: str) -> Path:
    if not _lowercase_commit(commit_a):
        raise ValueError("Run003 Commit A must be 40 lowercase hex characters")
    root = PRIVATE_EVIDENCE_BASE / commit_a
    if root in {
        run002.private_evidence_root(commit_a),
        run002.RUN001_PRIVATE_EVIDENCE_ROOT,
    }:
        raise ValueError("Run003 cannot reuse predecessor private evidence")
    return root


def build_authority_manifest(
    *,
    commit_a: str,
    current_git_commit: str,
    commit_a_parent_git_commits: list[str],
    private_evidence_root: Path | None = None,
) -> dict[str, Any]:
    if (
        not _lowercase_commit(commit_a)
        or not _lowercase_commit(current_git_commit)
        or commit_a != current_git_commit
    ):
        raise ValueError("Run003 Git authority mismatch")
    if commit_a_parent_git_commits != [RUN002_TERMINAL_GIT_COMMIT]:
        raise ValueError("Run003 Commit A single parent authority mismatch")
    root = (
        PRIVATE_EVIDENCE_BASE / commit_a
        if private_evidence_root is None
        else private_evidence_root
    )
    if not root.is_absolute():
        raise ValueError("Run003 private evidence root must be absolute")
    manifest = run002.build_authority_manifest(
        commit_a=commit_a,
        current_git_commit=current_git_commit,
        private_evidence_root=root,
    )
    for predecessor_key in (
        "predecessor_run_id",
        "predecessor_terminal_sha256",
        "run001_model_scores_observed",
    ):
        manifest.pop(predecessor_key)
    manifest.update(
        {
            "schema_version": "router-v2-run003-authority-manifest-v1",
            "run_id": RUN_ID,
            "commit_a_parent_git_commits": deepcopy(commit_a_parent_git_commits),
            "output_namespace": OUTPUT_NAMESPACE.as_posix(),
            "dataset_freeze_relative": DATASET_FREEZE_RELATIVE.as_posix(),
            "replacement_reason": REPLACEMENT_REASON,
            "event_policy_version": EVENT_POLICY_VERSION,
            "generator_schema_version": GENERATOR_RESPONSE_SCHEMA_VERSION,
            "generator_schema_sha256": canonical_sha256(GENERATOR_RESPONSE_SCHEMA),
            "system_prompt_sha256": {
                **cast(dict[str, str], manifest["system_prompt_sha256"]),
                "generator": canonical_sha256(FORMAL_GENERATOR_SYSTEM_PROMPT),
            },
            "run001_run_id": RUN001_RUN_ID,
            "run001_terminal_sha256": RUN001_TERMINAL_SHA256,
            "run002_terminal_evidence_bundle": deepcopy(
                RUN002_TERMINAL_EVIDENCE_BUNDLE
            ),
            "run002_terminal_evidence_bundle_sha256": (
                RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256
            ),
            "run001_candidates_reused": False,
            "run002_candidates_reused": False,
            "run001_model_scores_observed": False,
            "run002_model_scores_observed": False,
            "model_scores_observed": False,
        }
    )
    return manifest


def validate_authority_manifest(
    manifest: object, *, expected_root: Path | None = None
) -> dict[str, Any]:
    if type(manifest) is not dict:
        raise ValueError("Run003 authority manifest must be an object")
    value = cast(dict[str, Any], manifest)
    commit_a = value.get("commit_a")
    current_git_commit = value.get("current_git_commit")
    commit_a_parent_git_commits = value.get("commit_a_parent_git_commits")
    if (
        type(commit_a) is not str
        or type(current_git_commit) is not str
        or type(commit_a_parent_git_commits) is not list
    ):
        raise ValueError("Run003 authority manifest commit binding is missing")
    expected = build_authority_manifest(
        commit_a=commit_a,
        current_git_commit=current_git_commit,
        commit_a_parent_git_commits=cast(list[str], commit_a_parent_git_commits),
        private_evidence_root=expected_root,
    )
    if value != expected:
        raise ValueError("Run003 authority manifest mismatch")
    return deepcopy(value)


def persist_authority_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    validated = validate_authority_manifest(manifest, expected_root=root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Run003 authority root mismatch")
    path = root / AUTHORITY_MANIFEST_FILENAME
    payload = _canonical_json_bytes(validated)
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise ValueError("Run003 persisted authority manifest mismatch")
        return path
    with path.open("xb") as handle:
        handle.write(payload)
    return path


def _validated_diagnostic_summary(validation: dict[str, Any]) -> dict[str, Any]:
    count = validation.get("transport_diagnostic_count")
    types = validation.get("transport_diagnostic_types")
    observed = validation.get("transport_diagnostics_observed")
    if (
        type(count) is not int
        or count < 0
        or type(types) is not list
        or any(type(value) is not str or not value for value in types)
        or types != sorted(set(types))
        or type(observed) is not bool
        or observed is not (count > 0)
        or validation.get("event_policy_version") != EVENT_POLICY_VERSION
    ):
        raise ValueError("Run003 transport diagnostic summary mismatch")
    return {
        "event_policy_version": EVENT_POLICY_VERSION,
        "transport_diagnostic_count": count,
        "transport_diagnostic_types": deepcopy(types),
        "transport_diagnostics_observed": observed,
    }


def build_dataset_freeze_documents(
    validation: dict[str, Any], *, commit_a: str
) -> dict[str, bytes]:
    if validation.get("status") != "VALID" or validation.get("run_id") != RUN_ID:
        raise ValueError("Run003 valid Agent pack is required")
    if not _lowercase_commit(commit_a):
        raise ValueError("Run003 freeze Commit A mismatch")
    base_validation = {**validation, "run_id": run002.RUN_ID}
    documents = run002.build_dataset_freeze_documents(
        base_validation, commit_a=commit_a
    )
    task_rows = [
        cast(dict[str, Any], json.loads(line))
        for line in documents["blind-v2-tasks.jsonl"].splitlines()
    ]
    per_gold = Counter(cast(str, row["gold_skill_id"]) for row in task_rows)
    negative_per_gold = Counter(
        cast(str, row["gold_skill_id"])
        for row in task_rows
        if row["negative_skill_id"] is not None
    )
    if (
        len(task_rows) != 128
        or len({row["task_id"] for row in task_rows}) != 128
        or len({row["semantic_family_id"] for row in task_rows}) != 128
        or sum(row["negative_skill_id"] is not None for row in task_rows) != 96
        or len(per_gold) != 16
        or set(per_gold.values()) != {8}
        or negative_per_gold != Counter({gold: 6 for gold in per_gold})
    ):
        raise ValueError("Run003 frozen task invariants mismatch")
    diagnostic_summary = _validated_diagnostic_summary(validation)
    task_bytes = documents["blind-v2-tasks.jsonl"]
    review_summary = cast(
        dict[str, Any], json.loads(documents["blind-v2-review-summary.json"])
    )
    review_summary.update(
        {
            "schema_version": "router-v2-run003-review-summary-v1",
            "run_id": RUN_ID,
            **diagnostic_summary,
        }
    )
    review_bytes = _canonical_json_bytes(review_summary)
    manifest = cast(dict[str, Any], json.loads(documents["blind-v2-manifest.json"]))
    for predecessor_key in (
        "predecessor_run_id",
        "predecessor_terminal_sha256",
    ):
        manifest.pop(predecessor_key)
    manifest.update(
        {
            "schema_version": "router-v2-run003-dataset-manifest-v1",
            "run_id": RUN_ID,
            "run001_terminal_sha256": RUN001_TERMINAL_SHA256,
            "run002_terminal_evidence_bundle_sha256": (
                RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256
            ),
            "replacement_reason": REPLACEMENT_REASON,
            "review_request_count": validation["review_request_count"],
            "reviewer_valid_count": validation["reviewer_valid_count"],
            **diagnostic_summary,
            "system_prompt_sha256": validation["system_prompt_sha256"],
            "response_schema_sha256": validation["response_schema_sha256"],
            "agent_config_sha256": validation["agent_config_sha256"],
            "review_summary_file_sha256": hashlib.sha256(review_bytes).hexdigest(),
            "run001_candidates_reused": False,
            "run002_candidates_reused": False,
            "run001_model_scores_observed": False,
            "run002_model_scores_observed": False,
            "model_scores_observed": False,
        }
    )
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
        raise ValueError("Run003 frozen dataset destination mismatch")
    unresolved = output_dir.resolve(strict=False)
    if unresolved.exists() or output_dir.is_symlink():
        raise ValueError("Run003 frozen dataset destination must be new")
    if not unresolved.is_relative_to(repository):
        raise ValueError("Run003 frozen dataset must remain in the repository")
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for filename in DATASET_FREEZE_FILENAMES:
        with (output_dir / filename).open("xb") as handle:
            handle.write(documents[filename])


def read_frozen_dataset_documents(repository_root: Path) -> dict[str, bytes]:
    repository = repository_root.resolve(strict=True)
    root = repository / DATASET_FREEZE_RELATIVE
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Run003 frozen dataset root mismatch")
    if {path.name for path in root.iterdir()} != set(DATASET_FREEZE_FILENAMES):
        raise ValueError("Run003 frozen dataset must contain exactly three files")
    return {
        filename: (root / filename).read_bytes()
        for filename in DATASET_FREEZE_FILENAMES
    }


def build_evaluation_bindings(**kwargs: Any) -> dict[str, Any]:
    return run002.build_evaluation_bindings(**kwargs, run003_mode=True)


def validate_evaluation_inputs(
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return run002.validate_evaluation_inputs(**kwargs, run003_mode=True)


def validate_evaluation_routes(
    route_rows: list[dict[str, Any]],
    *,
    tasks: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
) -> None:
    run002.validate_evaluation_routes(
        route_rows,
        tasks=tasks,
        model_bindings=model_bindings,
    )
