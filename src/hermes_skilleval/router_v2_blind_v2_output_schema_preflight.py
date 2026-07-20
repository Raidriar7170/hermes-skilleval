from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping, Protocol, cast

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as historical


HISTORICAL_TERMINAL_COMMIT = "aff4e569e90fa30f5a96b212970ad1331d5c7c6e"
HISTORICAL_PROTOCOL_STATE = "AGENT_BLIND_V2_PROTOCOL_INVALID"
HISTORICAL_TERMINAL_PATH = Path(
    "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/"
    "candidate-generation-terminal.json"
)
HISTORICAL_TERMINAL_BYTES_SHA256 = (
    "4af1eed1651eba9757b7edaa64824c315c4abdaf9919ba8e0a68ff79fea64dbf"
)
HISTORICAL_TERMINAL_SELF_SHA256 = (
    "0226edfb3ac0136e73638d38e95b71f0a82336b09c11845f081b64739cfc8fdd"
)
HISTORICAL_GENERATOR_SCHEMA_SHA256 = (
    "24e63da6d922bc7dd9af8e8eed0b64f44850fcbda70898b7784d5e89260f304e"
)
HISTORICAL_REVIEWER_SCHEMA_SHA256 = (
    "14bc1d39858bf735bfd75f3055cf0761c919aaeb7b079f97e8419a05232f80cb"
)

CODEX_EXECUTABLE = Path("/Users/raidriar/.local/bin/codex")
CODEX_EXECUTABLE_RESOLVED = Path(
    "/Users/raidriar/.codex/packages/standalone/releases/"
    "0.144.5-aarch64-apple-darwin/bin/codex"
)
CODEX_EXECUTABLE_SHA256 = (
    "5e29ab10ca1171be158f7335dd6bd8ce1aaf9af1556939db36a5ee338be6f5f2"
)
CODEX_CLI_VERSION = "codex-cli 0.144.5"
FROZEN_REPOSITORY_ROOT = Path(
    "/Users/raidriar/dev/hermes-skilleval-worktrees/"
    "router-v2-blind-v2-successor-preflight"
)
ROLE_CONFIGS = {
    "generator": {"model": "gpt-5.6-sol", "reasoning_effort": "max"},
    "reviewer_a": {"model": "gpt-5.6-sol", "reasoning_effort": "ultra"},
    "reviewer_b": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
}
ROLE_ORDER = ("generator", "reviewer_a", "reviewer_b")
ROLE_TIMEOUT_SECONDS = 1800
DISABLED_FEATURES = (
    "multi_agent",
    "memories",
    "apps",
    "browser_use",
    "computer_use",
    "chronicle",
    "image_generation",
    "in_app_browser",
    "skill_mcp_dependency_install",
)
FIXED_EXEC_FLAGS = (
    "exec",
    "--json",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--skip-git-repo-check",
)
ALLOWED_EVENT_TYPES = (
    "thread.started",
    "turn.started",
    "item.started",
    "item.updated",
    "item.completed",
    "turn.completed",
)
ALLOWED_EVENT_ITEM_TYPES = ("reasoning", "agent_message")
PRIVATE_EVIDENCE_ROOT = (
    Path("/Users/raidriar/.codex/private/hermes-blind-v2-successor-preflight")
    / HISTORICAL_TERMINAL_COMMIT
)
PUBLIC_RECEIPT_PATH = Path(
    "artifacts/router-v2-blind-v2-successor-preflight/preflight-receipt.json"
)
AUTHORIZATION_DENIALS = {
    "formal_candidate_generation_authorized": False,
    "arm_a_c_load_authorized": False,
    "scoring_authorized": False,
    "commit_b_authorized": False,
    "formal_evaluation_authorized": False,
    "training_authorized": False,
    "commit_authorized": False,
    "push_authorized": False,
    "pr_authorized": False,
    "merge_authorized": False,
    "release_authorized": False,
    "archive_authorized": False,
}
FROZEN_SUCCESSOR_AUTHORITY_SHA256 = (
    "78689960afca96437e0295fca35fa944effb6026b8f33835a6d3382cc230e0f4"
)
_PINNED_SCHEMA_SHA256 = {
    "generator": "2df2ed8493e6a6bcbbcd86b1efc0b1d2a9c76debec6032aa5b65e838ad03717c",
    "reviewer_a": "91bfa4018c88aefbbaffb1cd5ab19f622aa216ed6029a3defeea70fc39c735de",
    "reviewer_b": "91bfa4018c88aefbbaffb1cd5ab19f622aa216ed6029a3defeea70fc39c735de",
}
_PINNED_STDIN_SHA256 = {
    "generator": "c4ca536cf75e197916883c8996e01ee72355240fb9abb96af1e74012ea5b099e",
    "reviewer_a": "a0e62d72f69eee02a83edc406f8e27ef8fb081201580ec66468c072c3464f130",
    "reviewer_b": "a0e62d72f69eee02a83edc406f8e27ef8fb081201580ec66468c072c3464f130",
}
_PINNED_ARGV_TEMPLATE_SHA256 = {
    "generator": "12a1c448631eed3925bbc6268a2e2ab9c428e4b3e1eda2f3796c683acdc5a700",
    "reviewer_a": "b2feb6f67d8896b766166fb130da9d9b3aae940f70e254425220879e2ba81dac",
    "reviewer_b": "59e5ad63b57a7a6d0f519368faf3db6564e786a7320f91e71c08904af6699b8b",
}

GENERATOR_CANARY_PROMPT = (
    'Return exactly the JSON object {"candidates":[]} and nothing else. This is a '
    "synthetic output-schema transport canary. Do not inspect repositories, use tools, "
    "delegate, access memory, or use any blind prompts, candidates, skills, Router "
    "scores, model scores, or evaluation inputs."
)
REVIEWER_CANARY_RESPONSE = {
    "decision": "ACCEPT",
    "reviewed_gold_skill_id": "schema-canary-primary",
    "reviewed_negative_skill_id": "schema-canary-negative",
    "natural": True,
    "single_primary_skill": True,
    "no_label_leakage": True,
    "negative_confusable": True,
    "confidence": "HIGH",
    "reason": "Synthetic schema canary is internally consistent.",
}
REVIEWER_CANARY_PROMPT = (
    "Return exactly this synthetic JSON object and nothing else: "
    + json.dumps(REVIEWER_CANARY_RESPONSE, sort_keys=True, separators=(",", ":"))
    + ". Do not inspect repositories, use tools, delegate, access memory, or use any "
    "blind prompts, candidates, skills, Router scores, model scores, or evaluation "
    "inputs."
)
CANARY_PROMPTS = {
    "generator": GENERATOR_CANARY_PROMPT,
    "reviewer_a": REVIEWER_CANARY_PROMPT,
    "reviewer_b": REVIEWER_CANARY_PROMPT,
}
CANARY_EXPECTED_RESPONSES = {
    "generator": {"candidates": []},
    "reviewer_a": REVIEWER_CANARY_RESPONSE,
    "reviewer_b": REVIEWER_CANARY_RESPONSE,
}

SUCCESSOR_GENERATOR_RESPONSE_SCHEMA = {
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

_REVIEW_DECISIONS = (
    "ACCEPT",
    "REJECT_AMBIGUOUS",
    "REJECT_NOT_CONFUSABLE",
    "REJECT_UNNATURAL",
    "REJECT_LABEL_LEAKAGE",
)
_REVIEW_CONFIDENCE = ("LOW", "MEDIUM", "HIGH")
_REVIEW_FIELDS = frozenset(
    {
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
)
SUCCESSOR_REVIEWER_RESPONSE_SCHEMA = {
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
        "decision": {"type": "string", "enum": list(_REVIEW_DECISIONS)},
        "reviewed_gold_skill_id": {"type": "string", "pattern": r"\S"},
        "reviewed_negative_skill_id": {
            "type": ["string", "null"],
            "pattern": r"\S",
        },
        "natural": {"type": "boolean"},
        "single_primary_skill": {"type": "boolean"},
        "no_label_leakage": {"type": "boolean"},
        "negative_confusable": {"type": ["boolean", "null"]},
        "confidence": {"type": "string", "enum": list(_REVIEW_CONFIDENCE)},
        "reason": {"type": "string", "pattern": r"\S"},
    },
}

_UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "allOf",
        "oneOf",
        "not",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
        "minLength",
        "maxLength",
        "$defs",
    }
)
_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "type",
        "description",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "anyOf",
        "pattern",
        "format",
        "multipleOf",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
    }
)
_VALID_JSON_TYPES = frozenset(
    {"null", "boolean", "integer", "number", "string", "array", "object"}
)
_PATH_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def validate_no_external_experiment_inputs(external_inputs: object) -> None:
    if external_inputs is not None:
        raise ValueError("successor canaries accept no external experiment inputs")


def _path_child(path: str, key: str) -> str:
    if _PATH_IDENTIFIER.fullmatch(key):
        return f"{path}.{key}"
    escaped = key.replace("\\", "\\\\").replace("'", "\\'")
    return f"{path}['{escaped}']"


def _declared_types(schema: Mapping[str, Any]) -> tuple[str, ...] | None:
    declared = schema.get("type")
    if type(declared) is str:
        return (cast(str, declared),)
    if type(declared) is list and all(type(item) is str for item in declared):
        return tuple(cast(list[str], declared))
    return None


def _value_matches_type(value: object, declared: str) -> bool:
    return {
        "null": value is None,
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "string": type(value) is str,
        "array": type(value) is list,
        "object": type(value) is dict,
    }.get(declared, False)


def _matches_any_declared_type(value: object, declared: tuple[str, ...]) -> bool:
    return any(_value_matches_type(value, item) for item in declared)


def _schema_node_findings(schema: object, path: str) -> list[str]:
    if type(schema) is not dict:
        return [f"{path}: SCHEMA_NODE_MUST_BE_OBJECT"]
    node = cast(dict[str, Any], schema)
    findings: list[str] = []
    declared = _declared_types(node)

    for keyword in sorted(set(node) - _SUPPORTED_SCHEMA_KEYWORDS):
        findings.append(f"{_path_child(path, keyword)}: UNSUPPORTED_KEYWORD")

    if declared is None:
        if "type" in node:
            findings.append(f"{_path_child(path, 'type')}: TYPE_INVALID")
        elif "anyOf" not in node and "const" not in node and "enum" not in node:
            findings.append(f"{_path_child(path, 'type')}: TYPE_REQUIRED")
    elif (
        not declared
        or any(item not in _VALID_JSON_TYPES for item in declared)
        or len(declared) != len(set(declared))
    ):
        findings.append(f"{_path_child(path, 'type')}: TYPE_INVALID")
    elif type(node.get("type")) is list and (
        len(declared) != 2 or "null" not in declared
    ):
        findings.append(f"{_path_child(path, 'type')}: TYPE_UNION_MUST_BE_NULLABLE")

    for keyword in ("description", "pattern", "format"):
        if keyword in node and type(node[keyword]) is not str:
            findings.append(
                f"{_path_child(path, keyword)}: {keyword.upper()}_MUST_BE_STRING"
            )
    for keyword in (
        "multipleOf",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    ):
        if keyword in node and type(node[keyword]) not in {int, float}:
            findings.append(
                f"{_path_child(path, keyword)}: {keyword.upper()}_MUST_BE_NUMBER"
            )
    for keyword in ("minItems", "maxItems"):
        if keyword in node and (type(node[keyword]) is not int or node[keyword] < 0):
            findings.append(
                f"{_path_child(path, keyword)}: "
                f"{keyword.upper()}_MUST_BE_NONNEGATIVE_INTEGER"
            )

    if "const" in node:
        const_path = _path_child(path, "const")
        if declared is None:
            findings.append(f"{const_path}: CONST_TYPE_REQUIRED")
        elif not _matches_any_declared_type(node["const"], declared):
            findings.append(f"{const_path}: CONST_TYPE_MISMATCH")

    if "enum" in node:
        enum_path = _path_child(path, "enum")
        raw_enum = node["enum"]
        if declared is None:
            findings.append(f"{enum_path}: ENUM_TYPE_REQUIRED")
        elif type(raw_enum) is not list or not raw_enum:
            label = (
                "ENUM_MUST_BE_ARRAY"
                if type(raw_enum) is not list
                else "ENUM_MUST_BE_NONEMPTY_ARRAY"
            )
            findings.append(f"{enum_path}: {label}")
        else:
            for index, value in enumerate(cast(list[Any], raw_enum)):
                if not _matches_any_declared_type(value, declared):
                    findings.append(f"{enum_path}[{index}]: ENUM_TYPE_MISMATCH")

    is_object = declared is not None and "object" in declared
    if is_object:
        if node.get("additionalProperties") is not False:
            findings.append(
                f"{_path_child(path, 'additionalProperties')}: OBJECT_MUST_BE_CLOSED"
            )
        properties = node.get("properties")
        required = node.get("required")
        if type(properties) is not dict:
            findings.append(
                f"{_path_child(path, 'properties')}: OBJECT_PROPERTIES_REQUIRED"
            )
        elif (
            type(required) is not list
            or not all(type(item) is str for item in required)
            or set(cast(list[str], required)) != set(cast(dict[str, Any], properties))
            or len(cast(list[str], required)) != len(set(cast(list[str], required)))
        ):
            findings.append(
                f"{_path_child(path, 'required')}: OBJECT_REQUIRED_PROPERTIES_MISMATCH"
            )

    is_array = declared is not None and "array" in declared
    if is_array and type(node.get("items")) is not dict:
        findings.append(f"{_path_child(path, 'items')}: ARRAY_ITEMS_REQUIRED")

    properties = node.get("properties")
    if type(properties) is dict:
        for key in sorted(cast(dict[str, Any], properties)):
            child_path = _path_child(_path_child(path, "properties"), key)
            findings.extend(
                _schema_node_findings(cast(dict[str, Any], properties)[key], child_path)
            )
    if type(node.get("items")) is dict:
        findings.extend(
            _schema_node_findings(node["items"], _path_child(path, "items"))
        )
    if "anyOf" in node:
        any_of = node["anyOf"]
        any_of_path = _path_child(path, "anyOf")
        if type(any_of) is not list or not any_of:
            findings.append(f"{any_of_path}: ANYOF_MUST_BE_NONEMPTY_ARRAY")
        else:
            for index, branch in enumerate(cast(list[Any], any_of)):
                findings.extend(
                    _schema_node_findings(branch, f"{any_of_path}[{index}]")
                )
    return findings


def schema_compatibility_findings(schema: object) -> tuple[str, ...]:
    if type(schema) is not dict or cast(dict[str, Any], schema).get("type") != "object":
        return ("$: ROOT_OBJECT_REQUIRED",)
    return tuple(_schema_node_findings(schema, "$"))


def _nonblank_string(value: object, label: str) -> str:
    if type(value) is not str or not cast(str, value).strip():
        raise ValueError(f"{label} must be a nonblank string")
    return cast(str, value)


def _review_decision_is_consistent(response: Mapping[str, Any]) -> bool:
    decision = response["decision"]
    negative = response["reviewed_negative_skill_id"]
    return bool(
        {
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
        }.get(cast(str, decision), False)
    )


def validate_successor_reviewer_response(response: object) -> dict[str, Any]:
    if (
        type(response) is not dict
        or set(cast(dict[str, Any], response)) != _REVIEW_FIELDS
    ):
        raise ValueError("reviewer response fields mismatch")
    document = cast(dict[str, Any], response)
    decision = document["decision"]
    if type(decision) is not str or decision not in _REVIEW_DECISIONS:
        raise ValueError("reviewer decision mismatch")
    gold = _nonblank_string(
        document["reviewed_gold_skill_id"], "reviewed gold skill id"
    )
    negative = document["reviewed_negative_skill_id"]
    if negative is not None:
        _nonblank_string(negative, "reviewed negative skill id")
    if negative == gold:
        raise ValueError("reviewed negative skill id must differ from gold")
    for field in ("natural", "single_primary_skill", "no_label_leakage"):
        if type(document[field]) is not bool:
            raise ValueError(f"reviewer {field} must be boolean")
    if not (
        (negative is None and document["negative_confusable"] is None)
        or (negative is not None and type(document["negative_confusable"]) is bool)
    ):
        raise ValueError("reviewer negative confusability mismatch")
    if not _review_decision_is_consistent(document):
        raise ValueError("reviewer decision/rubric mismatch")
    confidence = document["confidence"]
    if type(confidence) is not str or confidence not in _REVIEW_CONFIDENCE:
        raise ValueError("reviewer confidence mismatch")
    _nonblank_string(document["reason"], "reviewer reason")
    return document


class HostProbe(Protocol):
    def __call__(self, executable: Path) -> Mapping[str, object]: ...


class RoleLauncher(Protocol):
    def __call__(
        self,
        *,
        role: str,
        argv: tuple[str, ...],
        stdin: bytes,
        cwd: Path,
        timeout_seconds: int,
    ) -> Mapping[str, object]: ...


_RECEIPT_SCHEMA_VERSION = "router-v2-blind-v2-successor-preflight-receipt.v3"
_TERMINAL_STATES = frozenset(
    {
        "PREFLIGHT_READY",
        "PREFLIGHT_INPUT_BLOCKED",
        "PREFLIGHT_SCHEMA_BLOCKED",
        "PREFLIGHT_HOST_AUTHORITY_BLOCKED",
        "PREFLIGHT_EVIDENCE_BLOCKED",
        "PREFLIGHT_TIMEOUT_BLOCKED",
        "PREFLIGHT_PROCESS_BLOCKED",
        "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED",
        "PREFLIGHT_ISOLATION_BLOCKED",
        "PREFLIGHT_OUTPUT_BLOCKED",
    }
)
_PRELAUNCH_STATES = frozenset(
    {
        "PREFLIGHT_INPUT_BLOCKED",
        "PREFLIGHT_SCHEMA_BLOCKED",
        "PREFLIGHT_HOST_AUTHORITY_BLOCKED",
    }
)
_BLOCKED_FAILURE_METADATA = {
    "PREFLIGHT_INPUT_BLOCKED": {
        ("INPUT_BOUNDARY", "EXTERNAL_EXPERIMENT_INPUT_REJECTED")
    },
    "PREFLIGHT_SCHEMA_BLOCKED": {
        ("SCHEMA_COMPATIBILITY", "SUCCESSOR_SCHEMA_INCOMPATIBLE")
    },
    "PREFLIGHT_HOST_AUTHORITY_BLOCKED": {
        ("FROZEN_AUTHORITY", "SUCCESSOR_AUTHORITY_DRIFT"),
        ("HISTORICAL_AUTHORITY", "HISTORICAL_AUTHORITY_DRIFT"),
        ("HOST_AUTHORITY", "CODEX_HOST_AUTHORITY_MISMATCH"),
    },
    "PREFLIGHT_EVIDENCE_BLOCKED": {
        ("PRIVATE_EVIDENCE_PREPARE", "PRIVATE_EVIDENCE_PREPARE_FAILED"),
        ("PRIVATE_EVIDENCE_VALIDATE", "PRIVATE_EVIDENCE_VALIDATION_FAILED"),
    },
    "PREFLIGHT_TIMEOUT_BLOCKED": {("ROLE_BATCH", "ROLE_TIMEOUT")},
    "PREFLIGHT_PROCESS_BLOCKED": {("ROLE_BATCH", "ROLE_PROCESS_FAILED")},
    "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED": {
        ("ROLE_HOST_AUTHORITY", "CODEX_HOST_AUTHORITY_DRIFT_DURING_BATCH")
    },
    "PREFLIGHT_ISOLATION_BLOCKED": {
        ("ROLE_EVENT_VALIDATE", "ROLE_ISOLATION_VIOLATION")
    },
    "PREFLIGHT_OUTPUT_BLOCKED": {("ROLE_OUTPUT_VALIDATE", "ROLE_OUTPUT_INVALID")},
}
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ROLE_RESULT_FIELDS = frozenset(
    {
        "role",
        "model",
        "reasoning_effort",
        "timeout_seconds",
        "argv_template",
        "launch_attempt_count",
        "process_count",
        "retry_count",
        "schema_sha256",
        "stdin_sha256",
        "events_sha256",
        "event_validation_result",
        "final_agent_message_sha256",
        "response_sha256",
        "response_read_error",
        "parsed_object_sha256",
        "exit_code",
        "host_authority_valid",
        "thread_id",
        "tool_call_count",
        "validation_result",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "source_commit",
        "preflight_state",
        "failure_stage",
        "failure_reason",
        "router_decision",
        "production_ready",
        "default_router_unchanged",
        "old_protocol_state",
        "codex_executable",
        "codex_executable_resolved",
        "codex_executable_sha256",
        "successor_authority_sha256",
        "expected_codex_cli_version",
        "observed_codex_cli_version",
        "launch_attempt_count",
        "process_count",
        "retry_count",
        "fallback_used",
        "fork_context",
        "role_results",
        "private_evidence",
        "public_receipt_path",
        "next_authorization_required",
        "receipt_sha256",
        *AUTHORIZATION_DENIALS,
    }
)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _receipt(
    *,
    state: str,
    failure_stage: str | None,
    failure_reason: str | None,
    executable_sha256: str | None,
    cli_version: str | None,
    role_results: list[dict[str, object]],
    process_count: int,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": _RECEIPT_SCHEMA_VERSION,
        "source_commit": HISTORICAL_TERMINAL_COMMIT,
        "preflight_state": state,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "default_router_unchanged": True,
        "old_protocol_state": HISTORICAL_PROTOCOL_STATE,
        "codex_executable": str(CODEX_EXECUTABLE),
        "codex_executable_resolved": str(CODEX_EXECUTABLE_RESOLVED),
        "codex_executable_sha256": executable_sha256,
        "successor_authority_sha256": FROZEN_SUCCESSOR_AUTHORITY_SHA256,
        "expected_codex_cli_version": CODEX_CLI_VERSION,
        "observed_codex_cli_version": cli_version,
        "launch_attempt_count": len(role_results),
        "process_count": process_count,
        "retry_count": 0,
        "fallback_used": False,
        "fork_context": False,
        "role_results": role_results,
        "private_evidence": "PRIVATE_OUTSIDE_REPOSITORY",
        "public_receipt_path": PUBLIC_RECEIPT_PATH.as_posix(),
        "next_authorization_required": True,
        **AUTHORIZATION_DENIALS,
    }
    receipt = {**document, "receipt_sha256": canonical_sha256(document)}
    return validate_receipt(receipt)


def validate_receipt(receipt: Mapping[str, object]) -> dict[str, Any]:
    if set(receipt) != _RECEIPT_FIELDS:
        raise ValueError("terminal truth receipt fields mismatch")
    document = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if receipt.get("receipt_sha256") != canonical_sha256(document):
        raise ValueError("receipt hash mismatch")
    state = receipt.get("preflight_state")
    if type(state) is not str or state not in _TERMINAL_STATES:
        raise ValueError("terminal truth state mismatch")
    for key, expected in {
        "schema_version": _RECEIPT_SCHEMA_VERSION,
        "source_commit": HISTORICAL_TERMINAL_COMMIT,
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "default_router_unchanged": True,
        "old_protocol_state": HISTORICAL_PROTOCOL_STATE,
        "codex_executable": str(CODEX_EXECUTABLE),
        "codex_executable_resolved": str(CODEX_EXECUTABLE_RESOLVED),
        "successor_authority_sha256": FROZEN_SUCCESSOR_AUTHORITY_SHA256,
        "expected_codex_cli_version": CODEX_CLI_VERSION,
        "retry_count": 0,
        "fallback_used": False,
        "fork_context": False,
        "private_evidence": "PRIVATE_OUTSIDE_REPOSITORY",
        "public_receipt_path": PUBLIC_RECEIPT_PATH.as_posix(),
        "next_authorization_required": True,
        **AUTHORIZATION_DENIALS,
    }.items():
        if receipt.get(key) != expected:
            raise ValueError(f"terminal truth mismatch: {key}")
    process_count = receipt.get("process_count")
    launch_attempt_count = receipt.get("launch_attempt_count")
    if type(launch_attempt_count) is not int or launch_attempt_count not in {0, 3}:
        raise ValueError("terminal truth launch attempt count mismatch")
    if type(process_count) is not int or not 0 <= process_count <= 3:
        raise ValueError("terminal truth process count mismatch")
    if launch_attempt_count == 0 and process_count != 0:
        raise ValueError("terminal truth unlaunched process count mismatch")
    if state in _PRELAUNCH_STATES and (process_count != 0 or launch_attempt_count != 0):
        raise ValueError("terminal truth prelaunch count mismatch")
    if (
        state
        in {
            "PREFLIGHT_READY",
            "PREFLIGHT_TIMEOUT_BLOCKED",
            "PREFLIGHT_PROCESS_BLOCKED",
            "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED",
            "PREFLIGHT_ISOLATION_BLOCKED",
            "PREFLIGHT_OUTPUT_BLOCKED",
        }
        and launch_attempt_count != 3
    ):
        raise ValueError("terminal truth batch launch count mismatch")
    role_results = receipt.get("role_results")
    if type(role_results) is not list:
        raise ValueError("terminal truth role results mismatch")
    if launch_attempt_count == 0 and role_results:
        raise ValueError("terminal truth prelaunch role results mismatch")
    if launch_attempt_count == 3:
        roles = [
            row.get("role") if type(row) is dict else None
            for row in cast(list[object], role_results)
        ]
        if roles != list(ROLE_ORDER):
            raise ValueError("terminal truth role ordering mismatch")
        validations: list[str] = []
        for role, raw_row in zip(
            ROLE_ORDER, cast(list[object], role_results), strict=True
        ):
            if type(raw_row) is not dict or set(raw_row) != _ROLE_RESULT_FIELDS:
                raise ValueError(f"role authority mismatch: {role} fields")
            row = cast(dict[str, object], raw_row)
            config = ROLE_CONFIGS[role]
            for key, expected in {
                "role": role,
                "model": config["model"],
                "reasoning_effort": config["reasoning_effort"],
                "timeout_seconds": ROLE_TIMEOUT_SECONDS,
                "launch_attempt_count": 1,
                "retry_count": 0,
                "schema_sha256": _PINNED_SCHEMA_SHA256[role],
                "stdin_sha256": _PINNED_STDIN_SHA256[role],
            }.items():
                if row.get(key) != expected:
                    raise ValueError(f"role authority mismatch: {role} {key}")
            row_process_count = row.get("process_count")
            if type(row_process_count) is not int or row_process_count not in {0, 1}:
                raise ValueError(f"role authority mismatch: {role} process count")
            if (
                canonical_sha256(row.get("argv_template"))
                != (_PINNED_ARGV_TEMPLATE_SHA256[role])
            ):
                raise ValueError(f"role authority mismatch: {role} argv_template")
            event_hash = row.get("events_sha256")
            if type(event_hash) is not str or not _HEX_SHA256.fullmatch(event_hash):
                raise ValueError(f"role authority mismatch: {role} events_sha256")
            for key in ("events_sha256", "response_sha256"):
                value = row.get(key)
                if value is not None and (
                    type(value) is not str or not _HEX_SHA256.fullmatch(value)
                ):
                    raise ValueError(f"role authority mismatch: {role} {key}")
            validation = row.get("validation_result")
            if validation not in {
                "VALID",
                "TIMEOUT",
                "PROCESS_ERROR",
                "HOST_AUTHORITY_ERROR",
                "MISSING_OUTPUT",
                "INVALID_OUTPUT",
                "ISOLATION_VIOLATION",
            }:
                raise ValueError(f"role authority mismatch: {role} validation")
            validations.append(cast(str, validation))
            parsed_hash = row.get("parsed_object_sha256")
            thread_id = row.get("thread_id")
            tool_call_count = row.get("tool_call_count")
            event_validation = row.get("event_validation_result")
            final_message_hash = row.get("final_agent_message_sha256")
            host_authority_valid = row.get("host_authority_valid")
            response_read_error = row.get("response_read_error")
            if (
                host_authority_valid is not None
                and type(host_authority_valid) is not bool
            ):
                raise ValueError(f"role authority mismatch: {role} host authority")
            if (
                response_read_error is not None
                and type(response_read_error) is not bool
            ):
                raise ValueError(f"role authority mismatch: {role} response read")
            if event_validation not in {
                "COMPLETE",
                "INCOMPLETE",
                "INVALID",
                "ISOLATION_VIOLATION",
                "UNAVAILABLE",
            }:
                raise ValueError(f"role authority mismatch: {role} event validation")
            if tool_call_count is not None and (
                type(tool_call_count) is not int or tool_call_count < 0
            ):
                raise ValueError(f"role authority mismatch: {role} tool count")
            if thread_id is not None and (type(thread_id) is not str or not thread_id):
                raise ValueError(f"role authority mismatch: {role} thread id")
            if final_message_hash is not None and (
                type(final_message_hash) is not str
                or not _HEX_SHA256.fullmatch(final_message_hash)
            ):
                raise ValueError(f"role authority mismatch: {role} final message")
            if event_validation == "COMPLETE" and (
                type(thread_id) is not str
                or not thread_id
                or tool_call_count != 0
                or type(final_message_hash) is not str
            ):
                raise ValueError(f"role authority mismatch: {role} complete event")
            if event_validation == "INCOMPLETE" and tool_call_count != 0:
                raise ValueError(f"role authority mismatch: {role} incomplete event")
            if event_validation == "INVALID" and (
                thread_id is not None
                or tool_call_count is not None
                or final_message_hash is not None
            ):
                raise ValueError(f"role authority mismatch: {role} invalid event")
            if event_validation == "UNAVAILABLE" and (
                thread_id is not None
                or tool_call_count is not None
                or final_message_hash is not None
            ):
                raise ValueError(f"role authority mismatch: {role} unavailable event")
            if validation == "VALID":
                if (
                    row_process_count != 1
                    or row.get("exit_code") != 0
                    or host_authority_valid is not True
                    or response_read_error is not False
                    or type(row.get("response_sha256")) is not str
                    or parsed_hash != canonical_sha256(CANARY_EXPECTED_RESPONSES[role])
                    or type(thread_id) is not str
                    or not thread_id
                    or tool_call_count != 0
                    or event_validation != "COMPLETE"
                    or final_message_hash != parsed_hash
                ):
                    raise ValueError(f"role authority mismatch: {role} valid result")
            elif validation == "TIMEOUT":
                if (
                    row_process_count != 1
                    or row.get("exit_code") is not None
                    or host_authority_valid is not True
                    or response_read_error is not False
                    or row.get("response_sha256") is not None
                    or parsed_hash is not None
                ):
                    raise ValueError(f"role authority mismatch: {role} timeout result")
            elif validation == "PROCESS_ERROR":
                exit_code = row.get("exit_code")
                if (
                    (
                        exit_code is not None
                        and (type(exit_code) is not int or exit_code == 0)
                    )
                    or host_authority_valid
                    is not (True if row_process_count == 1 else None)
                    or response_read_error not in {False, None}
                    or parsed_hash is not None
                ):
                    raise ValueError(f"role authority mismatch: {role} process result")
            elif validation == "HOST_AUTHORITY_ERROR":
                if (
                    host_authority_valid is not False
                    or response_read_error not in {False, True, None}
                    or parsed_hash is not None
                ):
                    raise ValueError(f"role authority mismatch: {role} host result")
            elif validation == "MISSING_OUTPUT":
                if (
                    row_process_count != 1
                    or row.get("exit_code") != 0
                    or host_authority_valid is not True
                    or response_read_error not in {False, True}
                    or row.get("response_sha256") is not None
                    or parsed_hash is not None
                    or type(thread_id) is not str
                    or tool_call_count != 0
                    or event_validation != "COMPLETE"
                ):
                    raise ValueError(f"role authority mismatch: {role} missing result")
            elif validation == "INVALID_OUTPUT":
                if (
                    row_process_count != 1
                    or row.get("exit_code") != 0
                    or host_authority_valid is not True
                    or response_read_error is not False
                    or type(row.get("response_sha256")) is not str
                    or parsed_hash is not None
                    or type(thread_id) is not str
                    or tool_call_count != 0
                    or event_validation != "COMPLETE"
                ):
                    raise ValueError(f"role authority mismatch: {role} invalid result")
            elif (
                row_process_count != 1
                or row.get("exit_code") != 0
                or host_authority_valid is not True
                or response_read_error is not False
                or parsed_hash is not None
                or (thread_id is not None and type(thread_id) is not str)
                or event_validation != "ISOLATION_VIOLATION"
            ):
                raise ValueError(f"role authority mismatch: {role} isolation result")
        if state == "PREFLIGHT_READY" and validations != ["VALID"] * 3:
            raise ValueError("terminal truth ready result mismatch")
        if process_count != sum(
            cast(int, cast(dict[str, object], row).get("process_count"))
            for row in cast(list[object], role_results)
        ):
            raise ValueError("terminal truth process count sum mismatch")
        if state == "PREFLIGHT_READY" and process_count != len(ROLE_ORDER):
            raise ValueError("terminal truth ready process count mismatch")
        if state == "PREFLIGHT_READY" and len(
            {
                cast(dict[str, object], row).get("thread_id")
                for row in cast(list[object], role_results)
            }
        ) != len(ROLE_ORDER):
            raise ValueError("terminal truth thread isolation mismatch")
        if state == "PREFLIGHT_TIMEOUT_BLOCKED" and (
            "TIMEOUT" not in validations or "HOST_AUTHORITY_ERROR" in validations
        ):
            raise ValueError("terminal truth timeout result mismatch")
        if state == "PREFLIGHT_PROCESS_BLOCKED" and (
            "TIMEOUT" in validations
            or "HOST_AUTHORITY_ERROR" in validations
            or "PROCESS_ERROR" not in validations
        ):
            raise ValueError("terminal truth process result mismatch")
        if state == "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED" and (
            "HOST_AUTHORITY_ERROR" not in validations
        ):
            raise ValueError("terminal truth role host result mismatch")
        if state == "PREFLIGHT_ISOLATION_BLOCKED" and (
            "TIMEOUT" in validations
            or "PROCESS_ERROR" in validations
            or "HOST_AUTHORITY_ERROR" in validations
            or (
                "ISOLATION_VIOLATION" not in validations
                and len(
                    {
                        cast(dict[str, object], row).get("thread_id")
                        for row in cast(list[object], role_results)
                    }
                )
                == len(ROLE_ORDER)
            )
        ):
            raise ValueError("terminal truth isolation result mismatch")
        if state == "PREFLIGHT_OUTPUT_BLOCKED" and (
            "TIMEOUT" in validations
            or "PROCESS_ERROR" in validations
            or "HOST_AUTHORITY_ERROR" in validations
            or "ISOLATION_VIOLATION" in validations
            or not {"MISSING_OUTPUT", "INVALID_OUTPUT"}.intersection(validations)
        ):
            raise ValueError("terminal truth output result mismatch")
    if state == "PREFLIGHT_READY":
        if (
            receipt.get("failure_stage") is not None
            or receipt.get("failure_reason") is not None
        ):
            raise ValueError("terminal truth ready failure metadata mismatch")
    elif (
        receipt.get("failure_stage"),
        receipt.get("failure_reason"),
    ) not in _BLOCKED_FAILURE_METADATA[cast(str, state)]:
        raise ValueError("terminal truth blocked failure metadata mismatch")
    if launch_attempt_count == 3 or state == "PREFLIGHT_EVIDENCE_BLOCKED":
        executable_sha = receipt.get("codex_executable_sha256")
        observed_version = receipt.get("observed_codex_cli_version")
        if executable_sha != CODEX_EXECUTABLE_SHA256:
            raise ValueError("terminal truth executable hash mismatch")
        if observed_version != CODEX_CLI_VERSION:
            raise ValueError("terminal truth observed CLI mismatch")
    return dict(receipt)


def _read_regular_file_no_follow(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("authority file must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _assert_no_symlink_path(path: Path, *, require_leaf: bool = True) -> None:
    absolute = path if path.is_absolute() else path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        current /= part
        is_leaf = index == len(parts) - 1
        try:
            metadata = current.stat(follow_symlinks=False)
        except FileNotFoundError:
            if is_leaf and not require_leaf:
                return
            raise
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"authority path must not contain symlinks: {current}")


def _pinned_executable_sha256() -> str:
    _assert_no_symlink_path(CODEX_EXECUTABLE_RESOLVED)
    return _bytes_sha256(_read_regular_file_no_follow(CODEX_EXECUTABLE_RESOLVED))


def historical_authority_findings() -> tuple[str, ...]:
    findings: list[str] = []
    if canonical_sha256(historical.GENERATOR_RESPONSE_SCHEMA) != (
        HISTORICAL_GENERATOR_SCHEMA_SHA256
    ):
        findings.append("HISTORICAL_GENERATOR_SCHEMA_DRIFT")
    if canonical_sha256(historical.REVIEWER_RESPONSE_SCHEMA) != (
        HISTORICAL_REVIEWER_SCHEMA_SHA256
    ):
        findings.append("HISTORICAL_REVIEWER_SCHEMA_DRIFT")

    terminal_path = FROZEN_REPOSITORY_ROOT / HISTORICAL_TERMINAL_PATH
    try:
        if FROZEN_REPOSITORY_ROOT.resolve(strict=True) != FROZEN_REPOSITORY_ROOT:
            raise ValueError("frozen repository root drift")
        _assert_no_symlink_path(terminal_path)
        terminal_bytes = _read_regular_file_no_follow(terminal_path)
        if _bytes_sha256(terminal_bytes) != HISTORICAL_TERMINAL_BYTES_SHA256:
            findings.append("HISTORICAL_TERMINAL_BYTES_DRIFT")
        terminal = _json_object_no_duplicates(terminal_bytes)
        if terminal.get("terminal_sha256") != HISTORICAL_TERMINAL_SELF_SHA256:
            findings.append("HISTORICAL_TERMINAL_SELF_HASH_DRIFT")
        if terminal.get("research_conclusion") != HISTORICAL_PROTOCOL_STATE:
            findings.append("HISTORICAL_PROTOCOL_STATE_DRIFT")
        if terminal.get("router_decision") != "KEEP_BASELINE":
            findings.append("HISTORICAL_ROUTER_DECISION_DRIFT")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        findings.append("HISTORICAL_TERMINAL_UNREADABLE")
    return tuple(findings)


def _default_host_probe(executable: Path) -> dict[str, str]:
    if not executable.is_absolute():
        raise ValueError("Codex executable authority mismatch")
    resolved = executable.resolve(strict=True)
    if resolved != CODEX_EXECUTABLE_RESOLVED or resolved.is_symlink():
        raise ValueError("Codex resolved executable authority mismatch")
    executable_sha256 = _pinned_executable_sha256()
    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError("Codex version probe failed")
    return {
        "version": completed.stdout.strip(),
        "executable_sha256": executable_sha256,
        "resolved_executable": str(resolved),
    }


def _default_launcher(
    *,
    role: str,
    argv: tuple[str, ...],
    stdin: bytes,
    cwd: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    del role
    if not argv or argv[0] != str(CODEX_EXECUTABLE_RESOLVED):
        return {
            "returncode": None,
            "event_bytes": None,
            "response_bytes": None,
            "response_read_error": None,
            "timed_out": False,
            "process_started": False,
            "host_authority_valid": False,
        }
    try:
        prelaunch_hash_valid = _pinned_executable_sha256() == CODEX_EXECUTABLE_SHA256
    except (OSError, ValueError):
        prelaunch_hash_valid = False
    if not prelaunch_hash_valid:
        return {
            "returncode": None,
            "event_bytes": None,
            "response_bytes": None,
            "response_read_error": None,
            "timed_out": False,
            "process_started": False,
            "host_authority_valid": False,
        }
    response_path = Path(argv[argv.index("-o") + 1])
    try:
        completed = subprocess.run(
            argv,
            input=stdin,
            cwd=cwd,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if type(error.stdout) is bytes else b""
        try:
            host_authority_valid = (
                _pinned_executable_sha256() == CODEX_EXECUTABLE_SHA256
            )
        except (OSError, ValueError):
            host_authority_valid = False
        return {
            "returncode": None,
            "event_bytes": stdout,
            "response_bytes": None,
            "response_read_error": False,
            "timed_out": True,
            "process_started": True,
            "host_authority_valid": host_authority_valid,
        }
    try:
        host_authority_valid = _pinned_executable_sha256() == CODEX_EXECUTABLE_SHA256
    except (OSError, ValueError):
        host_authority_valid = False
    response_bytes: bytes | None = None
    response_read_error = False
    try:
        if response_path.exists() and not response_path.is_symlink():
            response_bytes = _read_private_regular_file(
                response_path, require_mode=False
            )
    except (OSError, ValueError):
        response_read_error = True
    return {
        "returncode": completed.returncode,
        "event_bytes": completed.stdout,
        "response_bytes": response_bytes,
        "response_read_error": response_read_error,
        "timed_out": False,
        "process_started": True,
        "host_authority_valid": host_authority_valid,
    }


def _role_root(private_root: Path, role: str) -> Path:
    return private_root / role.replace("_", "-")


def _role_schema(role: str) -> dict[str, Any]:
    return (
        SUCCESSOR_GENERATOR_RESPONSE_SCHEMA
        if role == "generator"
        else SUCCESSOR_REVIEWER_RESPONSE_SCHEMA
    )


def _authority_document() -> dict[str, object]:
    template_root = Path("/private-role-root")
    return {
        "historical_terminal_commit": HISTORICAL_TERMINAL_COMMIT,
        "historical_protocol_state": HISTORICAL_PROTOCOL_STATE,
        "historical_generator_schema_sha256": HISTORICAL_GENERATOR_SCHEMA_SHA256,
        "historical_reviewer_schema_sha256": HISTORICAL_REVIEWER_SCHEMA_SHA256,
        "historical_terminal_path": HISTORICAL_TERMINAL_PATH.as_posix(),
        "historical_terminal_bytes_sha256": HISTORICAL_TERMINAL_BYTES_SHA256,
        "historical_terminal_self_sha256": HISTORICAL_TERMINAL_SELF_SHA256,
        "codex_executable": str(CODEX_EXECUTABLE),
        "codex_executable_resolved": str(CODEX_EXECUTABLE_RESOLVED),
        "codex_executable_sha256": CODEX_EXECUTABLE_SHA256,
        "codex_cli_version": CODEX_CLI_VERSION,
        "frozen_repository_root": str(FROZEN_REPOSITORY_ROOT),
        "role_configs": ROLE_CONFIGS,
        "role_order": list(ROLE_ORDER),
        "role_timeout_seconds": ROLE_TIMEOUT_SECONDS,
        "disabled_features": list(DISABLED_FEATURES),
        "fixed_exec_flags": list(FIXED_EXEC_FLAGS),
        "event_isolation_contract": {
            "allowed_event_types": list(ALLOWED_EVENT_TYPES),
            "allowed_item_types": list(ALLOWED_EVENT_ITEM_TYPES),
            "required_thread_count_per_role": 1,
            "required_distinct_thread_count": len(ROLE_ORDER),
            "required_completed_agent_message_count_per_role": 1,
            "final_agent_message_must_match_response": True,
            "unavailable_tool_count_is_null": True,
        },
        "receipt_count_contract": {
            "schema_version": _RECEIPT_SCHEMA_VERSION,
            "launch_attempt_count": "controller_to_launcher_calls",
            "process_count": "launcher_confirmed_started_subprocesses",
            "role_process_count_domain": [0, 1],
            "response_read_error_is_explicit": True,
        },
        "role_argv_template_sha256": {
            role: canonical_sha256(
                _sanitized_argv(_role_argv(role, template_root), template_root)
            )
            for role in ROLE_ORDER
        },
        "private_evidence_root": str(PRIVATE_EVIDENCE_ROOT),
        "public_receipt_path": PUBLIC_RECEIPT_PATH.as_posix(),
        "authorization_denials": AUTHORIZATION_DENIALS,
        "canary_prompt_sha256": {
            role: _bytes_sha256(CANARY_PROMPTS[role].encode("utf-8"))
            for role in ROLE_ORDER
        },
        "canary_expected_response_sha256": {
            role: canonical_sha256(CANARY_EXPECTED_RESPONSES[role])
            for role in ROLE_ORDER
        },
        "successor_schema_sha256": {
            role: canonical_sha256(_role_schema(role)) for role in ROLE_ORDER
        },
    }


def _role_argv(role: str, role_root: Path) -> tuple[str, ...]:
    config = ROLE_CONFIGS[role]
    arguments = [
        str(CODEX_EXECUTABLE_RESOLVED),
        *FIXED_EXEC_FLAGS,
        "-C",
        str(role_root),
    ]
    arguments.extend(
        [
            "-m",
            config["model"],
            "-c",
            f"model_reasoning_effort={config['reasoning_effort']}",
            "-s",
            "read-only",
        ]
    )
    for feature in DISABLED_FEATURES:
        arguments.extend(["--disable", feature])
    arguments.extend(
        [
            "--output-schema",
            str(role_root / "response-schema.json"),
            "-o",
            str(role_root / "response.json"),
            "-",
        ]
    )
    return tuple(arguments)


def _sanitized_argv(argv: tuple[str, ...], role_root: Path) -> list[str]:
    prefix = str(role_root)
    return [argument.replace(prefix, "{ROLE_ROOT}") for argument in argv]


def _argv_authority_findings() -> tuple[str, ...]:
    template_root = Path("/private-role-root")
    findings = []
    for role in ROLE_ORDER:
        observed = canonical_sha256(
            _sanitized_argv(_role_argv(role, template_root), template_root)
        )
        if observed != _PINNED_ARGV_TEMPLATE_SHA256[role]:
            findings.append(f"{role}: ARGV_TEMPLATE_DRIFT")
    return tuple(findings)


def _write_private_file(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT
    if path.exists() or path.is_symlink():
        flags |= os.O_TRUNC
    else:
        flags |= os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("private evidence must be a regular file")
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("private evidence write made no progress")
            view = view[written:]
    finally:
        os.close(descriptor)


def _prepare_private_root(private_root: Path, repository_root: Path) -> None:
    if not private_root.is_absolute():
        raise ValueError("private evidence root must be absolute")
    _assert_no_symlink_path(repository_root)
    repository = repository_root.resolve(strict=True)
    if private_root == repository or private_root.is_relative_to(repository):
        raise ValueError("private evidence root must be outside repository")
    if private_root.exists() or private_root.is_symlink():
        if private_root.is_symlink():
            raise ValueError("private evidence root must not be a symlink")
        raise ValueError("private evidence root already exists")
    missing_parents: list[Path] = []
    cursor = private_root.parent
    while not cursor.exists() and not cursor.is_symlink():
        missing_parents.append(cursor)
        cursor = cursor.parent
    _assert_no_symlink_path(cursor)
    for parent in reversed(missing_parents):
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)
    _assert_no_symlink_path(private_root.parent)
    private_root.mkdir(mode=0o700, exist_ok=False)
    private_root.chmod(0o700)
    for role in ROLE_ORDER:
        role_root = _role_root(private_root, role)
        role_root.mkdir(mode=0o700)
        role_root.chmod(0o700)
        _write_private_file(
            role_root / "response-schema.json",
            _canonical_json_bytes(_role_schema(role)),
        )
        _write_private_file(
            role_root / "prompt.txt", CANARY_PROMPTS[role].encode("utf-8")
        )


def _require_private_directory(path: Path, label: str) -> None:
    metadata = path.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be a directory")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError(f"{label} mode 0700 is required")


def _require_private_file(path: Path, label: str) -> None:
    metadata = path.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ValueError(f"{label} mode 0600 is required")


def _read_private_regular_file(path: Path, *, require_mode: bool = True) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("private evidence must be a regular file")
        if require_mode and stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ValueError("private evidence mode 0600 is required")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _validate_public_receipt_target_at(repository_root: Path) -> Path:
    _assert_no_symlink_path(repository_root)
    repository = repository_root.resolve(strict=True)
    if not repository.is_dir():
        raise ValueError("repository root must be a directory")
    relative = PUBLIC_RECEIPT_PATH
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("public receipt path must remain repository-relative")
    parent = repository
    for part in relative.parent.parts:
        parent /= part
        try:
            metadata = parent.stat(follow_symlinks=False)
        except FileNotFoundError:
            parent.mkdir(mode=0o755)
            metadata = parent.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("public receipt parent must be a real directory")
    if parent.resolve(strict=True) != parent:
        raise ValueError("public receipt parent authority mismatch")
    target = repository / relative
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"public receipt already exists: {target}")
    return target


def _write_public_receipt_at(
    receipt: Mapping[str, object], *, repository_root: Path
) -> Path:
    validated = validate_receipt(receipt)
    target = _validate_public_receipt_target_at(repository_root)
    payload = _canonical_json_bytes(validated) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o644)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("public receipt must be a regular file")
        os.fchmod(descriptor, 0o644)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("public receipt write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if target.is_symlink() or target.read_bytes() != payload:
        raise ValueError("public receipt bytes mismatch")
    return target


def write_public_receipt(receipt: Mapping[str, object]) -> Path:
    return _write_public_receipt_at(receipt, repository_root=FROZEN_REPOSITORY_ROOT)


def validate_private_evidence(
    private_root: Path, *, role_results: object = None
) -> Path:
    _require_private_directory(private_root, "private evidence root")
    results_by_role: dict[str, Mapping[str, object]] | None = None
    if role_results is not None:
        if type(role_results) is not list:
            raise ValueError("private evidence role hash authority mismatch")
        rows = cast(list[object], role_results)
        if len(rows) != len(ROLE_ORDER) or any(type(row) is not dict for row in rows):
            raise ValueError("private evidence role hash authority mismatch")
        results_by_role = {
            cast(str, cast(dict[str, object], row).get("role")): cast(
                dict[str, object], row
            )
            for row in rows
        }
        if set(results_by_role) != set(ROLE_ORDER):
            raise ValueError("private evidence role hash authority mismatch")
    for role in ROLE_ORDER:
        role_root = _role_root(private_root, role)
        _require_private_directory(role_root, f"{role} evidence root")
        for filename in ("response-schema.json", "prompt.txt", "events.jsonl"):
            path = role_root / filename
            _require_private_file(path, f"{role} {filename}")
        response_path = role_root / "response.json"
        if response_path.exists() or response_path.is_symlink():
            _require_private_file(response_path, f"{role} response.json")
        if results_by_role is not None:
            row = results_by_role[role]
            expected_hashes = {
                "response-schema.json": row.get("schema_sha256"),
                "prompt.txt": row.get("stdin_sha256"),
                "events.jsonl": row.get("events_sha256"),
            }
            for filename, expected_hash in expected_hashes.items():
                if (
                    _bytes_sha256(_read_private_regular_file(role_root / filename))
                    != expected_hash
                ):
                    raise ValueError(f"{role} {filename} hash mismatch")
            expected_response_hash = row.get("response_sha256")
            if expected_response_hash is None:
                if response_path.exists() or response_path.is_symlink():
                    raise ValueError(f"{role} response hash is unbound")
            elif (
                _bytes_sha256(_read_private_regular_file(response_path))
                != expected_response_hash
            ):
                raise ValueError(f"{role} response.json hash mismatch")
    return private_root


def _json_object_no_duplicates(payload: bytes) -> dict[str, Any]:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(payload, object_pairs_hook=object_pairs)
    if type(value) is not dict:
        raise ValueError("response must be a JSON object")
    return cast(dict[str, Any], value)


def _inspect_event_stream(
    event_bytes: bytes, *, available: bool
) -> tuple[str | None, int | None, str, dict[str, Any] | None]:
    if not available:
        return None, None, "UNAVAILABLE", None
    thread_ids: list[str] = []
    turn_started = 0
    turn_completed = 0
    completed_agent_messages: list[str] = []
    tool_items: set[str] = set()
    violated = False
    unknown_event = False
    lifecycle_state = "EXPECT_THREAD"
    allowed_event_types = set(ALLOWED_EVENT_TYPES)
    allowed_item_types = set(ALLOWED_EVENT_ITEM_TYPES)
    try:
        lines = [line for line in event_bytes.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            event = _json_object_no_duplicates(line)
            event_type = event.get("type")
            if event_type not in allowed_event_types:
                violated = True
                unknown_event = True
                continue
            if event_type == "thread.started":
                if lifecycle_state != "EXPECT_THREAD":
                    violated = True
                else:
                    lifecycle_state = "EXPECT_TURN"
                thread_id = event.get("thread_id")
                if type(thread_id) is not str or not thread_id:
                    violated = True
                else:
                    thread_ids.append(thread_id)
            elif event_type == "turn.started":
                if lifecycle_state != "EXPECT_TURN":
                    violated = True
                else:
                    lifecycle_state = "IN_TURN"
                turn_started += 1
            elif event_type == "turn.completed":
                if lifecycle_state != "IN_TURN" or len(completed_agent_messages) != 1:
                    violated = True
                else:
                    lifecycle_state = "COMPLETED"
                turn_completed += 1
            else:
                if lifecycle_state != "IN_TURN":
                    violated = True
                item = event.get("item")
                if type(item) is not dict:
                    violated = True
                    continue
                item_type = cast(dict[str, Any], item).get("type")
                if item_type not in allowed_item_types:
                    item_id = cast(dict[str, Any], item).get("id")
                    tool_items.add(
                        f"id:{item_id}"
                        if type(item_id) is str and item_id
                        else f"event:{index}"
                    )
                    violated = True
                elif event_type == "item.completed" and item_type == "agent_message":
                    message_text = cast(dict[str, Any], item).get("text")
                    if type(message_text) is not str:
                        violated = True
                    else:
                        completed_agent_messages.append(message_text)
        thread_id = thread_ids[0] if len(thread_ids) == 1 else None
        if len(thread_ids) > 1 or turn_started > 1 or turn_completed > 1:
            violated = True
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, None, "INVALID", None
    final_message: dict[str, Any] | None = None
    if len(completed_agent_messages) > 1:
        violated = True
    elif len(completed_agent_messages) == 1:
        try:
            final_message = _json_object_no_duplicates(
                completed_agent_messages[0].encode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            violated = True
    complete = (
        lifecycle_state == "COMPLETED"
        and len(thread_ids) == 1
        and turn_started == 1
        and turn_completed == 1
        and len(completed_agent_messages) == 1
        and final_message is not None
    )
    tool_call_count = None if unknown_event else len(tool_items)
    if violated:
        return thread_id, tool_call_count, "ISOLATION_VIOLATION", final_message
    if not complete:
        return thread_id, tool_call_count, "INCOMPLETE", final_message
    return thread_id, tool_call_count, "COMPLETE", final_message


def _empty_role_result(
    role: str, role_root: Path, argv: tuple[str, ...], stdin: bytes
) -> dict[str, object]:
    config = ROLE_CONFIGS[role]
    return {
        "role": role,
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": ROLE_TIMEOUT_SECONDS,
        "argv_template": _sanitized_argv(argv, role_root),
        "launch_attempt_count": 1,
        "process_count": 0,
        "retry_count": 0,
        "schema_sha256": canonical_sha256(_role_schema(role)),
        "stdin_sha256": _bytes_sha256(stdin),
        "events_sha256": _bytes_sha256(b""),
        "event_validation_result": "UNAVAILABLE",
        "final_agent_message_sha256": None,
        "response_sha256": None,
        "response_read_error": None,
        "parsed_object_sha256": None,
        "exit_code": None,
        "host_authority_valid": None,
        "thread_id": None,
        "tool_call_count": 0,
        "validation_result": "PROCESS_ERROR",
    }


def _run_successor_preflight(
    *,
    private_root: Path = PRIVATE_EVIDENCE_ROOT,
    repository_root: Path,
    host_probe: HostProbe = _default_host_probe,
    launcher: RoleLauncher = _default_launcher,
    external_inputs: object = None,
) -> dict[str, Any]:
    try:
        validate_no_external_experiment_inputs(external_inputs)
    except ValueError:
        return _receipt(
            state="PREFLIGHT_INPUT_BLOCKED",
            failure_stage="INPUT_BOUNDARY",
            failure_reason="EXTERNAL_EXPERIMENT_INPUT_REJECTED",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=0,
        )

    findings = {
        role: schema_compatibility_findings(_role_schema(role))
        for role in ("generator", "reviewer_a")
    }
    if any(findings.values()):
        return _receipt(
            state="PREFLIGHT_SCHEMA_BLOCKED",
            failure_stage="SCHEMA_COMPATIBILITY",
            failure_reason="SUCCESSOR_SCHEMA_INCOMPATIBLE",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=0,
        )

    if historical_authority_findings():
        return _receipt(
            state="PREFLIGHT_HOST_AUTHORITY_BLOCKED",
            failure_stage="HISTORICAL_AUTHORITY",
            failure_reason="HISTORICAL_AUTHORITY_DRIFT",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=0,
        )

    if (
        _argv_authority_findings()
        or canonical_sha256(_authority_document()) != FROZEN_SUCCESSOR_AUTHORITY_SHA256
    ):
        return _receipt(
            state="PREFLIGHT_HOST_AUTHORITY_BLOCKED",
            failure_stage="FROZEN_AUTHORITY",
            failure_reason="SUCCESSOR_AUTHORITY_DRIFT",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=0,
        )

    try:
        host = host_probe(CODEX_EXECUTABLE)
        cli_version = host.get("version")
        executable_sha256 = host.get("executable_sha256")
        if cli_version != CODEX_CLI_VERSION:
            raise ValueError("Codex CLI version drift")
        if executable_sha256 != CODEX_EXECUTABLE_SHA256:
            raise ValueError("Codex executable hash drift")
        if host.get("resolved_executable") not in {
            None,
            str(CODEX_EXECUTABLE_RESOLVED),
        }:
            raise ValueError("Codex resolved executable drift")
    except Exception:
        return _receipt(
            state="PREFLIGHT_HOST_AUTHORITY_BLOCKED",
            failure_stage="HOST_AUTHORITY",
            failure_reason="CODEX_HOST_AUTHORITY_MISMATCH",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=0,
        )

    try:
        _prepare_private_root(private_root, repository_root)
    except (OSError, ValueError):
        return _receipt(
            state="PREFLIGHT_EVIDENCE_BLOCKED",
            failure_stage="PRIVATE_EVIDENCE_PREPARE",
            failure_reason="PRIVATE_EVIDENCE_PREPARE_FAILED",
            executable_sha256=cast(str, executable_sha256),
            cli_version=cast(str, cli_version),
            role_results=[],
            process_count=0,
        )

    role_results: list[dict[str, object]] = []
    saw_timeout = False
    saw_process_error = False
    saw_host_authority_error = False
    saw_isolation_error = False
    saw_output_error = False
    saw_evidence_error = False
    for role in ROLE_ORDER:
        role_root = _role_root(private_root, role)
        stdin = CANARY_PROMPTS[role].encode("utf-8")
        argv = _role_argv(role, role_root)
        result = _empty_role_result(role, role_root, argv, stdin)
        event_available = True
        try:
            launched = launcher(
                role=role,
                argv=argv,
                stdin=stdin,
                cwd=role_root,
                timeout_seconds=ROLE_TIMEOUT_SECONDS,
            )
        except Exception:
            launched = {
                "returncode": None,
                "event_bytes": b"",
                "response_bytes": None,
                "response_read_error": None,
                "timed_out": False,
                "process_started": False,
                "host_authority_valid": None,
            }
            event_available = False
            saw_process_error = True
        process_started = launched.get("process_started") is True
        raw_host_authority_valid = launched.get("host_authority_valid")
        host_authority_valid = (
            raw_host_authority_valid if type(raw_host_authority_valid) is bool else None
        )
        result["process_count"] = 1 if process_started else 0
        result["host_authority_valid"] = host_authority_valid
        raw_response_read_error = launched.get("response_read_error")
        response_read_error = (
            raw_response_read_error if type(raw_response_read_error) is bool else None
        )
        result["response_read_error"] = response_read_error
        if response_read_error is True:
            saw_evidence_error = True
        if host_authority_valid is False:
            saw_host_authority_error = True
        elif not process_started or host_authority_valid is None:
            saw_process_error = True
        event_bytes = launched.get("event_bytes")
        if type(event_bytes) is not bytes:
            event_bytes = b""
            event_available = False
            saw_process_error = True
        try:
            _write_private_file(role_root / "events.jsonl", event_bytes)
        except (OSError, ValueError):
            saw_evidence_error = True
        result["events_sha256"] = _bytes_sha256(event_bytes)
        (
            thread_id,
            tool_call_count,
            event_validation,
            final_agent_message,
        ) = _inspect_event_stream(event_bytes, available=event_available)
        result["thread_id"] = thread_id
        result["tool_call_count"] = tool_call_count
        result["event_validation_result"] = event_validation
        if final_agent_message is not None:
            result["final_agent_message_sha256"] = canonical_sha256(final_agent_message)
        timed_out = launched.get("timed_out") is True
        returncode = launched.get("returncode")
        result["exit_code"] = returncode if type(returncode) is int else None
        response_bytes = launched.get("response_bytes")
        if type(response_bytes) is bytes:
            result["response_sha256"] = _bytes_sha256(response_bytes)
            try:
                _write_private_file(role_root / "response.json", response_bytes)
            except (OSError, ValueError):
                saw_evidence_error = True
        if host_authority_valid is False:
            result["validation_result"] = "HOST_AUTHORITY_ERROR"
        elif not process_started or host_authority_valid is None:
            result["validation_result"] = "PROCESS_ERROR"
        elif timed_out:
            result["validation_result"] = "TIMEOUT"
            saw_timeout = True
        elif type(returncode) is not int or returncode != 0:
            result["validation_result"] = "PROCESS_ERROR"
            saw_process_error = True
        elif event_validation != "COMPLETE":
            result["validation_result"] = "ISOLATION_VIOLATION"
            saw_isolation_error = True
        else:
            if type(response_bytes) is not bytes:
                result["validation_result"] = "MISSING_OUTPUT"
                saw_output_error = True
            else:
                try:
                    parsed = _json_object_no_duplicates(response_bytes)
                    if parsed != CANARY_EXPECTED_RESPONSES[role]:
                        raise ValueError("synthetic canary response mismatch")
                    if role != "generator":
                        validate_successor_reviewer_response(parsed)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    result["validation_result"] = "INVALID_OUTPUT"
                    saw_output_error = True
                else:
                    if final_agent_message != parsed:
                        result["event_validation_result"] = "ISOLATION_VIOLATION"
                        result["validation_result"] = "ISOLATION_VIOLATION"
                        saw_isolation_error = True
                    else:
                        result["parsed_object_sha256"] = canonical_sha256(parsed)
                        result["validation_result"] = "VALID"
        role_results.append(result)

    thread_ids = [
        row.get("thread_id")
        for row in role_results
        if row.get("validation_result") == "VALID"
    ]
    if len(thread_ids) == len(ROLE_ORDER) and len(set(thread_ids)) != len(ROLE_ORDER):
        saw_isolation_error = True

    try:
        validate_private_evidence(private_root, role_results=role_results)
    except (OSError, ValueError):
        saw_evidence_error = True

    if saw_evidence_error:
        state = "PREFLIGHT_EVIDENCE_BLOCKED"
        failure_stage = "PRIVATE_EVIDENCE_VALIDATE"
        failure_reason = "PRIVATE_EVIDENCE_VALIDATION_FAILED"
    elif saw_host_authority_error:
        state = "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED"
        failure_stage = "ROLE_HOST_AUTHORITY"
        failure_reason = "CODEX_HOST_AUTHORITY_DRIFT_DURING_BATCH"
    elif saw_timeout:
        state = "PREFLIGHT_TIMEOUT_BLOCKED"
        failure_stage = "ROLE_BATCH"
        failure_reason = "ROLE_TIMEOUT"
    elif saw_process_error:
        state = "PREFLIGHT_PROCESS_BLOCKED"
        failure_stage = "ROLE_BATCH"
        failure_reason = "ROLE_PROCESS_FAILED"
    elif saw_isolation_error:
        state = "PREFLIGHT_ISOLATION_BLOCKED"
        failure_stage = "ROLE_EVENT_VALIDATE"
        failure_reason = "ROLE_ISOLATION_VIOLATION"
    elif saw_output_error:
        state = "PREFLIGHT_OUTPUT_BLOCKED"
        failure_stage = "ROLE_OUTPUT_VALIDATE"
        failure_reason = "ROLE_OUTPUT_INVALID"
    else:
        state = "PREFLIGHT_READY"
        failure_stage = None
        failure_reason = None
    return _receipt(
        state=state,
        failure_stage=failure_stage,
        failure_reason=failure_reason,
        executable_sha256=cast(str, executable_sha256),
        cli_version=cast(str, cli_version),
        role_results=role_results,
        process_count=sum(cast(int, row["process_count"]) for row in role_results),
    )


def run_successor_preflight() -> dict[str, Any]:
    _assert_no_symlink_path(FROZEN_REPOSITORY_ROOT)
    if FROZEN_REPOSITORY_ROOT.resolve(strict=True) != FROZEN_REPOSITORY_ROOT:
        raise ValueError("frozen repository root authority mismatch")
    _assert_no_symlink_path(PRIVATE_EVIDENCE_ROOT.parent, require_leaf=False)
    _validate_public_receipt_target_at(FROZEN_REPOSITORY_ROOT)
    receipt = _run_successor_preflight(
        private_root=PRIVATE_EVIDENCE_ROOT,
        repository_root=FROZEN_REPOSITORY_ROOT,
        host_probe=_default_host_probe,
        launcher=_default_launcher,
    )
    write_public_receipt(receipt)
    return receipt
