from __future__ import annotations

import importlib
import importlib.util
import hashlib
import inspect
import json
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as historical


ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "hermes_skilleval.router_v2_blind_v2_output_schema_preflight"
HISTORICAL_TERMINAL = (
    ROOT
    / "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001"
    / "candidate-generation-terminal.json"
)


def _module() -> ModuleType:
    assert importlib.util.find_spec(MODULE_NAME) is not None, (
        "successor-only output-schema preflight module is missing"
    )
    return importlib.import_module(MODULE_NAME)


@pytest.fixture(autouse=True)
def _bind_frozen_repository_root_to_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the frozen checkout authority portable across macOS and Linux CI."""

    module = _module()
    assert module.canonical_sha256(module._authority_document()) == (
        module.FROZEN_SUCCESSOR_AUTHORITY_SHA256
    )
    monkeypatch.setattr(module, "FROZEN_REPOSITORY_ROOT", ROOT)
    test_root_authority_sha256 = module.canonical_sha256(module._authority_document())
    monkeypatch.setattr(
        module,
        "FROZEN_SUCCESSOR_AUTHORITY_SHA256",
        test_root_authority_sha256,
    )


def _findings(schema: Any) -> tuple[str, ...]:
    return _module().schema_compatibility_findings(schema)


def test_historical_schema_constants_and_terminal_truth_are_pinned() -> None:
    assert historical.canonical_sha256(historical.GENERATOR_RESPONSE_SCHEMA) == (
        "24e63da6d922bc7dd9af8e8eed0b64f44850fcbda70898b7784d5e89260f304e"
    )
    assert historical.canonical_sha256(historical.REVIEWER_RESPONSE_SCHEMA) == (
        "14bc1d39858bf735bfd75f3055cf0761c919aaeb7b079f97e8419a05232f80cb"
    )
    terminal = json.loads(HISTORICAL_TERMINAL.read_text(encoding="utf-8"))
    assert terminal["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert terminal["router_decision"] == "KEEP_BASELINE"
    assert terminal["terminal_sha256"] == (
        "0226edfb3ac0136e73638d38e95b71f0a82336b09c11845f081b64739cfc8fdd"
    )


@pytest.mark.parametrize(
    "external_inputs",
    [
        {"old_candidates": ["candidate-00"]},
        {"blind_prompts": ["old prompt"]},
        {"private_responses": [{"response": "old"}]},
        {"router_scores": {"arm_a": 1.0}},
        {"evaluation_inputs": ["attempt-1"]},
    ],
)
def test_successor_boundary_rejects_old_experiment_inputs(
    external_inputs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="successor canaries accept no external"):
        _module().validate_no_external_experiment_inputs(external_inputs)


def test_successor_authority_constants_are_frozen() -> None:
    module = _module()
    assert module.HISTORICAL_TERMINAL_COMMIT == (
        "aff4e569e90fa30f5a96b212970ad1331d5c7c6e"
    )
    assert module.HISTORICAL_PROTOCOL_STATE == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert module.CODEX_EXECUTABLE == Path("/Users/raidriar/.local/bin/codex")
    assert module.CODEX_EXECUTABLE_RESOLVED == Path(
        "/Users/raidriar/.codex/packages/standalone/releases/"
        "0.144.5-aarch64-apple-darwin/bin/codex"
    )
    assert module.CODEX_EXECUTABLE_SHA256 == (
        "5e29ab10ca1171be158f7335dd6bd8ce1aaf9af1556939db36a5ee338be6f5f2"
    )
    assert module.CODEX_CLI_VERSION == "codex-cli 0.144.5"
    assert module.FROZEN_REPOSITORY_ROOT == ROOT
    assert module.ROLE_CONFIGS == {
        "generator": {"model": "gpt-5.6-sol", "reasoning_effort": "max"},
        "reviewer_a": {"model": "gpt-5.6-sol", "reasoning_effort": "ultra"},
        "reviewer_b": {"model": "gpt-5.6-luna", "reasoning_effort": "max"},
    }
    assert module.PRIVATE_EVIDENCE_ROOT.is_absolute()
    assert module.PUBLIC_RECEIPT_PATH == Path(
        "artifacts/router-v2-blind-v2-successor-preflight/preflight-receipt.json"
    )
    assert module.AUTHORIZATION_DENIALS and all(
        value is False for value in module.AUTHORIZATION_DENIALS.values()
    )
    assert module.HISTORICAL_TERMINAL_PATH == Path(
        "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/"
        "candidate-generation-terminal.json"
    )
    assert module.HISTORICAL_TERMINAL_BYTES_SHA256 == (
        "4af1eed1651eba9757b7edaa64824c315c4abdaf9919ba8e0a68ff79fea64dbf"
    )
    assert module._PINNED_ARGV_TEMPLATE_SHA256 == {
        "generator": "12a1c448631eed3925bbc6268a2e2ab9c428e4b3e1eda2f3796c683acdc5a700",
        "reviewer_a": "b2feb6f67d8896b766166fb130da9d9b3aae940f70e254425220879e2ba81dac",
        "reviewer_b": "59e5ad63b57a7a6d0f519368faf3db6564e786a7320f91e71c08904af6699b8b",
    }
    assert module.historical_authority_findings() == ()


def test_portability_fixture_checks_production_oracle_before_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "FIXED_EXEC_FLAGS",
        (*module.FIXED_EXEC_FLAGS, "--protected-field-drift"),
    )

    class RecordingMonkeyPatch:
        def __init__(self) -> None:
            self.calls: list[tuple[object, str, object]] = []

        def setattr(self, target: object, name: str, value: object) -> None:
            self.calls.append((target, name, value))

    recording = RecordingMonkeyPatch()
    fixture_implementation = inspect.unwrap(_bind_frozen_repository_root_to_checkout)

    with pytest.raises(AssertionError):
        fixture_implementation(recording)

    assert recording.calls == []


def test_recursive_validator_reports_nested_untyped_const_path() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["language"],
                    "properties": {"language": {"const": "en"}},
                },
            }
        },
    }
    assert _findings(schema) == (
        "$.properties.items.items.properties.language.const: CONST_TYPE_REQUIRED",
    )


def test_recursive_validator_reports_mismatched_const_type() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["enabled"],
        "properties": {"enabled": {"type": "string", "const": True}},
    }
    assert _findings(schema) == ("$.properties.enabled.const: CONST_TYPE_MISMATCH",)


@pytest.mark.parametrize(
    ("enum_schema", "expected"),
    [
        (
            {"enum": ["LOW", "HIGH"]},
            "$.properties.confidence.enum: ENUM_TYPE_REQUIRED",
        ),
        (
            {"type": "string", "enum": ["LOW", 1]},
            "$.properties.confidence.enum[1]: ENUM_TYPE_MISMATCH",
        ),
    ],
)
def test_recursive_validator_reports_untyped_or_incompatible_enum(
    enum_schema: dict[str, Any], expected: str
) -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["confidence"],
        "properties": {"confidence": enum_schema},
    }
    assert _findings(schema) == (expected,)


def test_recursive_validator_walks_supported_anyof_branches_by_index() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["payload"],
        "properties": {
            "payload": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["language"],
                        "properties": {"language": {"const": "en"}},
                    },
                    {"type": "string", "enum": ["ok", 1]},
                ]
            }
        },
    }
    assert _findings(schema) == (
        "$.properties.payload.anyOf[0].properties.language.const: CONST_TYPE_REQUIRED",
        "$.properties.payload.anyOf[1].enum[1]: ENUM_TYPE_MISMATCH",
    )


def test_recursive_validator_rejects_defs_instead_of_skipping_schema_nodes() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [],
        "properties": {},
        "$defs": {"hidden": {"const": "unchecked"}},
    }
    assert _findings(schema) == ("$['$defs']: UNSUPPORTED_KEYWORD",)


@pytest.mark.parametrize(
    ("leaf", "expected"),
    [
        ({"description": "missing type"}, "TYPE_REQUIRED"),
        ({"type": "mystery"}, "TYPE_INVALID"),
        ({"type": "string", "examples": ["x"]}, "UNSUPPORTED_KEYWORD"),
    ],
)
def test_recursive_validator_fails_closed_on_missing_type_or_unknown_keyword(
    leaf: dict[str, Any], expected: str
) -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": leaf},
    }
    finding = _findings(schema)
    assert len(finding) == 1
    assert finding[0].startswith("$.properties.value")
    assert finding[0].endswith(expected)


@pytest.mark.parametrize(
    ("leaf", "expected"),
    [
        ({"type": "string", "enum": []}, "ENUM_MUST_BE_NONEMPTY_ARRAY"),
        ({"type": ["string", "integer"]}, "TYPE_UNION_MUST_BE_NULLABLE"),
        ({"type": ["string", "null", "boolean"]}, "TYPE_UNION_MUST_BE_NULLABLE"),
        ({"type": "string", "description": 1}, "DESCRIPTION_MUST_BE_STRING"),
        ({"type": "string", "pattern": 1}, "PATTERN_MUST_BE_STRING"),
        ({"type": "string", "format": 1}, "FORMAT_MUST_BE_STRING"),
        ({"type": "number", "minimum": True}, "MINIMUM_MUST_BE_NUMBER"),
        (
            {"type": "array", "items": {"type": "string"}, "minItems": 1.5},
            "MINITEMS_MUST_BE_NONNEGATIVE_INTEGER",
        ),
    ],
)
def test_recursive_validator_rejects_malformed_supported_keyword_values(
    leaf: dict[str, Any], expected: str
) -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": leaf},
    }
    findings = _findings(schema)
    assert any(finding.endswith(expected) for finding in findings)


@pytest.mark.parametrize(
    "keyword",
    [
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
    ],
)
def test_recursive_validator_rejects_unsupported_keyword_at_stable_path(
    keyword: str,
) -> None:
    if keyword in {"minLength", "maxLength"}:
        nested: dict[str, Any] = {keyword: 1}
    else:
        nested = {keyword: [] if keyword.endswith("Of") else {}}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {},
                **nested,
            }
        },
    }
    assert _findings(schema) == (
        f"$.properties.payload.{keyword}: UNSUPPORTED_KEYWORD",
    )


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        (
            {
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
            "$.additionalProperties: OBJECT_MUST_BE_CLOSED",
        ),
        (
            {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {"value": {"type": "string"}},
            },
            "$.required: OBJECT_REQUIRED_PROPERTIES_MISMATCH",
        ),
        (
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["values"],
                "properties": {"values": {"type": "array"}},
            },
            "$.properties.values.items: ARRAY_ITEMS_REQUIRED",
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            "$: ROOT_OBJECT_REQUIRED",
        ),
    ],
)
def test_recursive_validator_rejects_structural_strictness_violations(
    schema: dict[str, Any], expected: str
) -> None:
    assert _findings(schema) == (expected,)


def _walk_schema(value: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if type(value) is dict:
        node = value
        nodes.append(node)
        for child in node.values():
            nodes.extend(_walk_schema(child))
    elif type(value) is list:
        for child in value:
            nodes.extend(_walk_schema(child))
    return nodes


def test_successor_schemas_have_zero_compatibility_findings() -> None:
    module = _module()
    assert (
        module.schema_compatibility_findings(module.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA)
        == ()
    )
    assert (
        module.schema_compatibility_findings(module.SUCCESSOR_REVIEWER_RESPONSE_SCHEMA)
        == ()
    )
    assert historical.canonical_sha256(historical.GENERATOR_RESPONSE_SCHEMA) == (
        "24e63da6d922bc7dd9af8e8eed0b64f44850fcbda70898b7784d5e89260f304e"
    )
    assert historical.canonical_sha256(historical.REVIEWER_RESPONSE_SCHEMA) == (
        "14bc1d39858bf735bfd75f3055cf0761c919aaeb7b079f97e8419a05232f80cb"
    )


def test_successor_generator_schema_types_const_and_keeps_supported_patterns() -> None:
    module = _module()
    schema = module.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA
    candidate = schema["properties"]["candidates"]["items"]
    properties = candidate["properties"]
    assert properties["language"] == {"type": "string", "const": "en"}
    for field in (
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "rationale",
    ):
        assert properties[field]["pattern"] == r"\S"
    for node in _walk_schema(schema):
        assert "minLength" not in node
        assert "maxLength" not in node


def test_successor_reviewer_schema_is_flat_typed_and_fully_closed() -> None:
    module = _module()
    schema = module.SUCCESSOR_REVIEWER_RESPONSE_SCHEMA
    properties = schema["properties"]
    assert properties["decision"] == {
        "type": "string",
        "enum": [
            "ACCEPT",
            "REJECT_AMBIGUOUS",
            "REJECT_NOT_CONFUSABLE",
            "REJECT_UNNATURAL",
            "REJECT_LABEL_LEAKAGE",
        ],
    }
    assert properties["confidence"] == {
        "type": "string",
        "enum": ["LOW", "MEDIUM", "HIGH"],
    }
    assert set(schema["required"]) == set(properties)
    assert schema["additionalProperties"] is False
    forbidden = {
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
    }
    assert all(forbidden.isdisjoint(node) for node in _walk_schema(schema))


def _valid_review(*, negative: str | None = "schema-canary-negative") -> dict[str, Any]:
    return {
        "decision": "ACCEPT",
        "reviewed_gold_skill_id": "schema-canary-primary",
        "reviewed_negative_skill_id": negative,
        "natural": True,
        "single_primary_skill": True,
        "no_label_leakage": True,
        "negative_confusable": True if negative is not None else None,
        "confidence": "HIGH",
        "reason": "Synthetic response is internally consistent.",
    }


@pytest.mark.parametrize("negative", ["schema-canary-negative", None])
def test_successor_review_semantics_accept_valid_negative_and_null_cases(
    negative: str | None,
) -> None:
    response = _valid_review(negative=negative)
    assert _module().validate_successor_reviewer_response(response) == response


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"negative_confusable": None}, "negative confusability"),
        (
            {
                "reviewed_negative_skill_id": None,
                "negative_confusable": True,
            },
            "negative confusability",
        ),
        ({"natural": False}, "decision/rubric"),
        ({"single_primary_skill": False}, "decision/rubric"),
        ({"no_label_leakage": False}, "decision/rubric"),
        ({"decision": "UNKNOWN"}, "decision"),
        ({"confidence": "CERTAIN"}, "confidence"),
    ],
)
def test_successor_review_semantics_reject_typed_contradictions(
    mutation: dict[str, Any], message: str
) -> None:
    response = {**_valid_review(), **mutation}
    with pytest.raises(ValueError, match=message):
        _module().validate_successor_reviewer_response(response)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class _FakeHost:
    def __init__(
        self,
        *,
        version: str = "codex-cli 0.144.5",
        executable_sha256: str | None = None,
        failure_role: str | None = None,
        failure_kind: str | None = None,
    ) -> None:
        self.version = version
        self.executable_sha256 = executable_sha256
        self.failure_role = failure_role
        self.failure_kind = failure_kind
        self.probes: list[Path] = []
        self.calls: list[dict[str, Any]] = []

    def probe(self, executable: Path) -> dict[str, str]:
        self.probes.append(executable)
        return {
            "version": self.version,
            "executable_sha256": (
                self.executable_sha256 or _module().CODEX_EXECUTABLE_SHA256
            ),
        }

    def launch(
        self,
        *,
        role: str,
        argv: tuple[str, ...],
        stdin: bytes,
        cwd: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        call = {
            "role": role,
            "argv": argv,
            "stdin": stdin,
            "cwd": cwd,
            "timeout_seconds": timeout_seconds,
        }
        self.calls.append(call)
        if role == self.failure_role and self.failure_kind == "raise":
            raise RuntimeError("synthetic host failure with private details")
        response = _module().CANARY_EXPECTED_RESPONSES[role]
        response_text = json.dumps(
            response, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        thread_id = (
            "thread-generator"
            if role == self.failure_role and self.failure_kind == "duplicate_thread"
            else f"thread-{role}"
        )
        if role == self.failure_role and self.failure_kind == "event_mismatch":
            response_text_for_event = "{}"
        else:
            response_text_for_event = response_text
        events = [
            {"type": "thread.started", "thread_id": thread_id},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"id": "item-0", "type": "reasoning", "text": ""},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "item-1",
                    "type": "agent_message",
                    "text": response_text_for_event,
                },
            },
            {"type": "turn.completed", "usage": {}},
        ]
        if role == self.failure_role and self.failure_kind in {
            "tool_call",
            "timeout_tool_call",
        }:
            events.insert(
                -1,
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-tool",
                        "type": "command_execution",
                        "command": "pwd",
                    },
                },
            )
        if role == self.failure_role and self.failure_kind == "reordered_events":
            events[0], events[1] = events[1], events[0]
        if role == self.failure_role and self.failure_kind == "post_completion_event":
            events.append(
                {
                    "type": "item.completed",
                    "item": {"id": "item-late", "type": "reasoning", "text": ""},
                }
            )
        if role == self.failure_role and self.failure_kind == "duplicate_message":
            events.insert(
                -1,
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-message-2",
                        "type": "agent_message",
                        "text": response_text,
                    },
                },
            )
        event_bytes = (
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events)
        ).encode("utf-8")
        response_bytes: bytes | None = response_text.encode("utf-8")
        if role == self.failure_role:
            if self.failure_kind in {"timeout", "timeout_tool_call"}:
                return {
                    "returncode": None,
                    "event_bytes": event_bytes,
                    "response_bytes": None,
                    "response_read_error": False,
                    "timed_out": True,
                    "process_started": True,
                    "host_authority_valid": True,
                }
            if self.failure_kind == "nonzero":
                return {
                    "returncode": 1,
                    "event_bytes": event_bytes,
                    "response_bytes": None,
                    "response_read_error": False,
                    "timed_out": False,
                    "process_started": True,
                    "host_authority_valid": True,
                }
            if self.failure_kind == "missing":
                response_bytes = None
            elif self.failure_kind == "invalid_json":
                response_bytes = b"not-json"
            elif self.failure_kind == "wrong_object":
                wrong: dict[str, Any] = (
                    {"candidates": [{"unexpected": True}]}
                    if role == "generator"
                    else {**response, "natural": False}
                )
                response_bytes = json.dumps(
                    wrong, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
        return {
            "returncode": 0,
            "event_bytes": event_bytes,
            "response_bytes": response_bytes,
            "response_read_error": False,
            "timed_out": False,
            "process_started": True,
            "host_authority_valid": not (
                role == self.failure_role and self.failure_kind == "host_drift"
            ),
        }


def _run_mocked_preflight(
    tmp_path: Path,
    fake: _FakeHost,
    *,
    external_inputs: object = None,
) -> tuple[dict[str, Any], Path]:
    private_root = tmp_path / "successor-private"
    receipt = _module()._run_successor_preflight(
        private_root=private_root,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        external_inputs=external_inputs,
    )
    return receipt, private_root


def test_preflight_rejects_external_inputs_before_host_or_private_write(
    tmp_path: Path,
) -> None:
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(
        tmp_path, fake, external_inputs={"old_candidates": ["old"]}
    )
    assert receipt["preflight_state"] == "PREFLIGHT_INPUT_BLOCKED"
    assert fake.probes == []
    assert fake.calls == []
    assert not private_root.exists()


def test_public_entrypoints_expose_no_path_or_host_injection() -> None:
    module = _module()
    assert inspect.signature(module.run_successor_preflight).parameters == {}
    assert tuple(inspect.signature(module.write_public_receipt).parameters) == (
        "receipt",
    )


def test_public_orchestration_checks_target_then_runs_and_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    calls: list[tuple[str, Any]] = []
    receipt = {"preflight_state": "PREFLIGHT_READY"}
    private_root = tmp_path.resolve() / "successor-private"

    def run_successor(**kwargs: Any) -> dict[str, str]:
        calls.append(("run", kwargs))
        return receipt

    monkeypatch.setattr(
        module,
        "_validate_public_receipt_target_at",
        lambda root: calls.append(("target", root)),
    )
    monkeypatch.setattr(
        module,
        "_run_successor_preflight",
        run_successor,
    )
    monkeypatch.setattr(
        module,
        "write_public_receipt",
        lambda value: calls.append(("write", value)),
    )
    monkeypatch.setattr(module, "PRIVATE_EVIDENCE_ROOT", private_root)

    assert module.run_successor_preflight() == receipt
    assert calls[0] == ("target", module.FROZEN_REPOSITORY_ROOT)
    assert calls[1][0] == "run"
    assert calls[1][1]["private_root"] == private_root
    assert calls[1][1]["repository_root"] == module.FROZEN_REPOSITORY_ROOT
    assert calls[2] == ("write", receipt)


def test_preflight_rejects_schema_before_host_or_private_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    drifted = {
        "type": "object",
        "additionalProperties": False,
        "required": ["language"],
        "properties": {"language": {"const": "en"}},
    }
    monkeypatch.setattr(module, "SUCCESSOR_GENERATOR_RESPONSE_SCHEMA", drifted)
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_SCHEMA_BLOCKED"
    assert fake.probes == []
    assert fake.calls == []
    assert not private_root.exists()


def test_preflight_rejects_host_version_drift_before_any_launch(
    tmp_path: Path,
) -> None:
    fake = _FakeHost(version="codex-cli 0.145.0")
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_HOST_AUTHORITY_BLOCKED"
    assert fake.probes == [Path("/Users/raidriar/.local/bin/codex")]
    assert fake.calls == []
    assert not private_root.exists()


def test_default_host_probe_accepts_and_binds_pinned_codex_symlink() -> None:
    module = _module()
    if not module.CODEX_EXECUTABLE.exists():
        pytest.skip("pinned macOS Codex executable is unavailable on this host")
    assert module.CODEX_EXECUTABLE.is_symlink()
    probe = module._default_host_probe(module.CODEX_EXECUTABLE)
    assert probe == {
        "version": "codex-cli 0.144.5",
        "executable_sha256": module.CODEX_EXECUTABLE_SHA256,
        "resolved_executable": str(module.CODEX_EXECUTABLE_RESOLVED),
    }


def test_default_launcher_revalidates_binary_after_each_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    role_root = tmp_path / "generator"
    role_root.mkdir()
    argv = module._role_argv("generator", role_root)
    observed_hashes = iter([module.CODEX_EXECUTABLE_SHA256, "0" * 64])
    monkeypatch.setattr(
        module, "_pinned_executable_sha256", lambda: next(observed_hashes)
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=b"", stderr=b""
        ),
    )

    launched = module._default_launcher(
        role="generator",
        argv=argv,
        stdin=b"{}",
        cwd=role_root,
        timeout_seconds=1,
    )
    assert launched["process_started"] is True
    assert launched["host_authority_valid"] is False


@pytest.mark.parametrize("timed_out", [False, True])
def test_default_launcher_preserves_started_process_when_post_hash_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timed_out: bool
) -> None:
    module = _module()
    role_root = tmp_path / "generator"
    role_root.mkdir()
    argv = module._role_argv("generator", role_root)
    observed: list[object] = [module.CODEX_EXECUTABLE_SHA256, OSError("post hash")]

    def hash_probe() -> str:
        value = observed.pop(0)
        if isinstance(value, BaseException):
            raise value
        return str(value)

    def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if timed_out:
            raise subprocess.TimeoutExpired(args[0], 1, output=b"partial-events")
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=b"events", stderr=b""
        )

    monkeypatch.setattr(module, "_pinned_executable_sha256", hash_probe)
    monkeypatch.setattr(module.subprocess, "run", run)
    launched = module._default_launcher(
        role="generator",
        argv=argv,
        stdin=b"{}",
        cwd=role_root,
        timeout_seconds=1,
    )
    assert launched["process_started"] is True
    assert launched["host_authority_valid"] is False
    assert launched["timed_out"] is timed_out


def test_default_launcher_converts_prelaunch_hash_exception_to_zero_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    role_root = tmp_path / "generator"
    role_root.mkdir()
    argv = module._role_argv("generator", role_root)

    def fail_hash() -> str:
        raise OSError("prelaunch hash")

    monkeypatch.setattr(module, "_pinned_executable_sha256", fail_hash)
    launched = module._default_launcher(
        role="generator",
        argv=argv,
        stdin=b"{}",
        cwd=role_root,
        timeout_seconds=1,
    )
    assert launched["process_started"] is False
    assert launched["host_authority_valid"] is False


def test_preflight_rejects_executable_hash_drift_before_any_launch(
    tmp_path: Path,
) -> None:
    fake = _FakeHost(executable_sha256="0" * 64)
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_HOST_AUTHORITY_BLOCKED"
    assert fake.probes == [Path("/Users/raidriar/.local/bin/codex")]
    assert fake.calls == []
    assert not private_root.exists()


@pytest.mark.parametrize("drift", ["argv", "role_argv", "schema"])
def test_preflight_rejects_frozen_authority_drift_before_host_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    module = _module()
    if drift == "argv":
        monkeypatch.setattr(
            module,
            "FIXED_EXEC_FLAGS",
            (*module.FIXED_EXEC_FLAGS, "--drifted-flag"),
        )
    elif drift == "role_argv":
        original = module._role_argv

        def drifted_role_argv(role: str, root: Path) -> tuple[str, ...]:
            return tuple(
                value for value in original(role, root) if value != "read-only"
            )

        monkeypatch.setattr(module, "_role_argv", drifted_role_argv)
    else:
        drifted = json.loads(json.dumps(module.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA))
        drifted["properties"]["candidates"]["items"]["properties"]["candidate_index"][
            "minimum"
        ] = 1
        assert module.schema_compatibility_findings(drifted) == ()
        monkeypatch.setattr(module, "SUCCESSOR_GENERATOR_RESPONSE_SCHEMA", drifted)
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_HOST_AUTHORITY_BLOCKED"
    assert fake.probes == []
    assert fake.calls == []
    assert not private_root.exists()


def test_unexpected_host_probe_failure_is_sanitized_and_fail_closed(
    tmp_path: Path,
) -> None:
    fake = _FakeHost()

    def broken_probe(executable: Path) -> dict[str, str]:
        del executable
        raise RuntimeError("private probe detail")

    private_root = tmp_path / "successor-private"
    receipt = _module()._run_successor_preflight(
        private_root=private_root,
        repository_root=ROOT,
        host_probe=broken_probe,
        launcher=fake.launch,
    )
    assert receipt["preflight_state"] == "PREFLIGHT_HOST_AUTHORITY_BLOCKED"
    assert "private probe detail" not in json.dumps(receipt)
    assert fake.calls == []
    assert not private_root.exists()


def test_runtime_rejects_historical_schema_drift_before_host_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drifted = json.loads(json.dumps(historical.GENERATOR_RESPONSE_SCHEMA))
    drifted["properties"]["candidates"]["type"] = "object"
    monkeypatch.setattr(historical, "GENERATOR_RESPONSE_SCHEMA", drifted)
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_HOST_AUTHORITY_BLOCKED"
    assert receipt["failure_reason"] == "HISTORICAL_AUTHORITY_DRIFT"
    assert fake.probes == []
    assert fake.calls == []
    assert not private_root.exists()


def test_exact_three_role_argv_configs_and_synthetic_stdin(tmp_path: Path) -> None:
    module = _module()
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == "PREFLIGHT_READY"
    assert [call["role"] for call in fake.calls] == [
        "generator",
        "reviewer_a",
        "reviewer_b",
    ]
    assert len({call["cwd"] for call in fake.calls}) == 3
    for call in fake.calls:
        role = call["role"]
        config = module.ROLE_CONFIGS[role]
        role_root = private_root / role.replace("_", "-")
        expected = (
            "/Users/raidriar/.codex/packages/standalone/releases/"
            "0.144.5-aarch64-apple-darwin/bin/codex",
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "-C",
            str(role_root),
            "-m",
            config["model"],
            "-c",
            f"model_reasoning_effort={config['reasoning_effort']}",
            "-s",
            "read-only",
            "--disable",
            "multi_agent",
            "--disable",
            "memories",
            "--disable",
            "apps",
            "--disable",
            "browser_use",
            "--disable",
            "computer_use",
            "--disable",
            "chronicle",
            "--disable",
            "image_generation",
            "--disable",
            "in_app_browser",
            "--disable",
            "skill_mcp_dependency_install",
            "--output-schema",
            str(role_root / "response-schema.json"),
            "-o",
            str(role_root / "response.json"),
            "-",
        )
        assert call["argv"] == expected
        assert call["stdin"] == module.CANARY_PROMPTS[role].encode("utf-8")
        assert call["timeout_seconds"] == 1800
        assert "resume" not in call["argv"]
        assert "fork" not in call["argv"]
    assert receipt["process_count"] == 3
    assert receipt["launch_attempt_count"] == 3
    assert receipt["retry_count"] == 0
    assert receipt["fallback_used"] is False
    assert receipt["fork_context"] is False


@pytest.mark.parametrize(
    ("kind", "expected_state"),
    [
        ("timeout", "PREFLIGHT_TIMEOUT_BLOCKED"),
        ("nonzero", "PREFLIGHT_PROCESS_BLOCKED"),
        ("missing", "PREFLIGHT_OUTPUT_BLOCKED"),
        ("invalid_json", "PREFLIGHT_OUTPUT_BLOCKED"),
        ("wrong_object", "PREFLIGHT_OUTPUT_BLOCKED"),
        ("tool_call", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("event_mismatch", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("duplicate_thread", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("reordered_events", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("post_completion_event", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("duplicate_message", "PREFLIGHT_ISOLATION_BLOCKED"),
        ("host_drift", "PREFLIGHT_ROLE_HOST_AUTHORITY_BLOCKED"),
        ("raise", "PREFLIGHT_PROCESS_BLOCKED"),
    ],
)
def test_role_failure_still_completes_all_three_once_without_retry(
    tmp_path: Path, kind: str, expected_state: str
) -> None:
    fake = _FakeHost(failure_role="reviewer_a", failure_kind=kind)
    receipt, _ = _run_mocked_preflight(tmp_path, fake)
    assert receipt["preflight_state"] == expected_state
    assert [call["role"] for call in fake.calls] == [
        "generator",
        "reviewer_a",
        "reviewer_b",
    ]
    assert receipt["process_count"] == (2 if kind == "raise" else 3)
    assert receipt["launch_attempt_count"] == 3
    assert receipt["retry_count"] == 0
    assert all(result["retry_count"] == 0 for result in receipt["role_results"])
    assert all(
        result["launch_attempt_count"] == 1 for result in receipt["role_results"]
    )


def test_private_evidence_modes_hashes_and_sanitized_receipt(tmp_path: Path) -> None:
    module = _module()
    frozen_public_path = ROOT / module.PUBLIC_RECEIPT_PATH
    frozen_public_before = (
        frozen_public_path.read_bytes() if frozen_public_path.exists() else None
    )
    fake = _FakeHost()
    receipt, private_root = _run_mocked_preflight(tmp_path, fake)
    assert stat.S_IMODE(private_root.stat().st_mode) == 0o700
    for role in module.ROLE_ORDER:
        role_root = private_root / role.replace("_", "-")
        assert stat.S_IMODE(role_root.stat().st_mode) == 0o700
        for filename in (
            "response-schema.json",
            "prompt.txt",
            "events.jsonl",
            "response.json",
        ):
            path = role_root / filename
            assert path.is_file() and not path.is_symlink()
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
    serialized = json.dumps(receipt, sort_keys=True)
    assert str(private_root) not in serialized
    assert "Return exactly" not in serialized
    assert "raw_response" not in serialized
    assert receipt["receipt_sha256"] == _canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    assert receipt["router_decision"] == "KEEP_BASELINE"
    assert receipt["production_ready"] is False
    assert receipt["default_router_unchanged"] is True
    assert receipt["old_protocol_state"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
    assert all(receipt[key] is False for key in module.AUTHORIZATION_DENIALS)
    for result, call in zip(receipt["role_results"], fake.calls, strict=True):
        role = result["role"]
        assert result["schema_sha256"] == _canonical_sha256(
            module.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA
            if role == "generator"
            else module.SUCCESSOR_REVIEWER_RESPONSE_SCHEMA
        )
        assert result["stdin_sha256"] == hashlib.sha256(call["stdin"]).hexdigest()
        assert len(result["events_sha256"]) == 64
        assert len(result["response_sha256"]) == 64
        assert len(result["parsed_object_sha256"]) == 64
        assert result["validation_result"] == "VALID"
        assert result["event_validation_result"] == "COMPLETE"
        assert result["thread_id"] == f"thread-{role}"
        assert result["tool_call_count"] == 0
        assert result["final_agent_message_sha256"] == result["parsed_object_sha256"]
    frozen_public_after = (
        frozen_public_path.read_bytes() if frozen_public_path.exists() else None
    )
    assert frozen_public_after == frozen_public_before
    assert module.validate_receipt(receipt) == receipt


def test_failed_role_event_stream_never_fabricates_zero_tool_usage(
    tmp_path: Path,
) -> None:
    receipt, _ = _run_mocked_preflight(
        tmp_path,
        _FakeHost(failure_role="reviewer_a", failure_kind="timeout_tool_call"),
    )
    assert receipt["preflight_state"] == "PREFLIGHT_TIMEOUT_BLOCKED"
    row = receipt["role_results"][1]
    assert row["validation_result"] == "TIMEOUT"
    assert row["event_validation_result"] == "ISOLATION_VIOLATION"
    assert row["thread_id"] == "thread-reviewer_a"
    assert row["tool_call_count"] == 1


def test_public_receipt_is_written_canonically_once_without_private_payloads(
    tmp_path: Path,
) -> None:
    module = _module()
    receipt, private_root = _run_mocked_preflight(tmp_path / "run", _FakeHost())
    repository_root = tmp_path / "repository"
    repository_root.mkdir()

    public_path = module._write_public_receipt_at(
        receipt, repository_root=repository_root
    )

    assert public_path == repository_root / module.PUBLIC_RECEIPT_PATH
    assert public_path.is_file() and not public_path.is_symlink()
    assert stat.S_IMODE(public_path.stat().st_mode) == 0o644
    assert json.loads(public_path.read_text(encoding="utf-8")) == receipt
    public_bytes = public_path.read_bytes()
    assert public_bytes == module._canonical_json_bytes(receipt) + b"\n"
    assert str(private_root) not in public_bytes.decode("utf-8")
    assert "Return exactly" not in public_bytes.decode("utf-8")
    with pytest.raises(FileExistsError):
        module._write_public_receipt_at(receipt, repository_root=repository_root)


def test_public_target_gate_rejects_existing_file_or_symlink(tmp_path: Path) -> None:
    module = _module()
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    target = repository_root / module.PUBLIC_RECEIPT_PATH
    target.parent.mkdir(parents=True)
    target.write_text("occupied", encoding="utf-8")
    with pytest.raises(FileExistsError):
        module._validate_public_receipt_target_at(repository_root)
    target.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("outside", encoding="utf-8")
    target.symlink_to(outside)
    with pytest.raises((FileExistsError, ValueError)):
        module._validate_public_receipt_target_at(repository_root)


def test_successor_cli_materializes_the_sanitized_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script_path = ROOT / "scripts/run_router_v2_blind_v2_output_schema_preflight.py"
    spec = importlib.util.spec_from_file_location(
        "successor_preflight_cli", script_path
    )
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    receipt, _ = _run_mocked_preflight(tmp_path / "run", _FakeHost())
    monkeypatch.setattr(
        cli.preflight,
        "run_successor_preflight",
        lambda **_kwargs: receipt,
    )

    assert cli.main([]) == 0
    assert json.loads(capsys.readouterr().out) == receipt


def test_private_root_and_postrun_evidence_symlinks_are_rejected(
    tmp_path: Path,
) -> None:
    module = _module()
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    linked_root = tmp_path / "successor-private"
    linked_root.symlink_to(outside, target_is_directory=True)
    fake = _FakeHost()
    receipt = module._run_successor_preflight(
        private_root=linked_root,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
    )
    assert receipt["preflight_state"] == "PREFLIGHT_EVIDENCE_BLOCKED"
    assert fake.calls == []

    clean_fake = _FakeHost()
    clean_root = tmp_path / "clean-private"
    clean_receipt = module._run_successor_preflight(
        private_root=clean_root,
        repository_root=ROOT,
        host_probe=clean_fake.probe,
        launcher=clean_fake.launch,
    )
    assert clean_receipt["preflight_state"] == "PREFLIGHT_READY"
    response = clean_root / "generator/response.json"
    payload = response.read_bytes()
    response.unlink()
    target = tmp_path / "outside-response.json"
    target.write_bytes(payload)
    target.chmod(0o600)
    response.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        module.validate_private_evidence(clean_root)


def test_private_evidence_hash_drift_is_rejected(tmp_path: Path) -> None:
    module = _module()
    receipt, private_root = _run_mocked_preflight(tmp_path, _FakeHost())
    events = private_root / "reviewer-a/events.jsonl"
    events.write_bytes(b'{"type":"tampered"}\n')
    events.chmod(0o600)
    with pytest.raises(ValueError, match="hash"):
        module.validate_private_evidence(
            private_root, role_results=receipt["role_results"]
        )


def test_receipt_self_hash_and_terminal_truth_reject_mutation(tmp_path: Path) -> None:
    module = _module()
    receipt, _ = _run_mocked_preflight(tmp_path, _FakeHost())
    drifted = {**receipt, "router_decision": "PROMOTE"}
    with pytest.raises(ValueError, match="receipt hash|terminal truth"):
        module.validate_receipt(drifted)
    forged = {**receipt, "production_ready": True}
    forged["receipt_sha256"] = _canonical_sha256(
        {key: value for key, value in forged.items() if key != "receipt_sha256"}
    )
    with pytest.raises(ValueError, match="terminal truth"):
        module.validate_receipt(forged)
    role_drifted = json.loads(json.dumps(receipt))
    role_drifted["role_results"][0]["schema_sha256"] = "0" * 64
    role_drifted["receipt_sha256"] = _canonical_sha256(
        {key: value for key, value in role_drifted.items() if key != "receipt_sha256"}
    )
    with pytest.raises(ValueError, match="role authority"):
        module.validate_receipt(role_drifted)
    blocked, _ = _run_mocked_preflight(
        tmp_path / "blocked",
        _FakeHost(failure_role="generator", failure_kind="nonzero"),
    )
    assert blocked["preflight_state"] == "PREFLIGHT_PROCESS_BLOCKED"
    assert blocked["router_decision"] == "KEEP_BASELINE"
    assert blocked["production_ready"] is False
    assert blocked["process_count"] == 3
    assert all(blocked[key] is False for key in module.AUTHORIZATION_DENIALS)


def test_prelaunch_receipt_rejects_impossible_nonzero_process_count() -> None:
    module = _module()
    with pytest.raises(ValueError, match="unlaunched process"):
        module._receipt(
            state="PREFLIGHT_INPUT_BLOCKED",
            failure_stage="INPUT_BOUNDARY",
            failure_reason="EXTERNAL_EXPERIMENT_INPUT_REJECTED",
            executable_sha256=None,
            cli_version=None,
            role_results=[],
            process_count=3,
        )


def test_successor_cli_help_exposes_only_safe_preflight_paths() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_router_v2_blind_v2_output_schema_preflight.py"),
            "--help",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--private-root" not in completed.stdout
    assert "--repository-root" not in completed.stdout
    assert "--request-round-1" not in completed.stdout
    assert "--public-receipt" not in completed.stdout
