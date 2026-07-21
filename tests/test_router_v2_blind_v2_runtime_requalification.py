from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner


REPOSITORY = Path(__file__).resolve().parents[1]
TERMINAL_PATH = (
    REPOSITORY / "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/"
    "agent-config-smoke-terminal.json"
)
PREREGISTRATION_PATH = REPOSITORY / "artifacts/router-v2-blind-v2/preregistration.json"
TERMINAL_SHA256 = "b83aea9ea8fb1bb6bfd3baa58ac23347765bc9bda48a08c20185088d45fe193e"
SCIENTIFIC_CONTRACT_SHA256 = (
    "5865263ab3e63aad375a16259d5ff4391d48b011e104b8a0fb3c96b476262cc5"
)


def _eligibility() -> dict[str, Any]:
    return runner.validate_stage0_requalification_eligibility(
        TERMINAL_PATH,
        repository_root=REPOSITORY,
    )


def _canary(role: str) -> dict[str, str]:
    return {
        "protocol": runner.STAGE0_PROTOCOL,
        "role": role,
        "nonce": runner.STAGE0_ROLE_NONCES[role],
        "status": "READY",
    }


def _invocation(role: str, *, serial: int) -> dict[str, Any]:
    config = runner.AGENT_CONFIGS[role]
    response_text = json.dumps(
        {
            "status": "READY",
            "nonce": runner.STAGE0_ROLE_NONCES[role],
            "role": role,
            "protocol": runner.STAGE0_PROTOCOL,
        },
        indent=2,
    )
    return {
        "role": role,
        "agent_id": f"stage0-agent-{serial}",
        "fork_context": False,
        "history_message_count": 0,
        "imported_memory_count": 0,
        "requested_model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "provider_returned_model": None,
        "provider_returned_model_status": "INTERFACE_UNAVAILABLE",
        "timestamp_utc": f"2026-07-19T09:00:0{serial}+00:00",
        "transport_retry_count": 0,
        "outcome": "RESPONSE",
        "fallback_model_used": False,
        "lineage_observed": True,
        "tool_call_count": 0,
        "descendant_agent_count": 0,
        "response_count": 1,
        "response_text": response_text,
        "response_base64": base64.b64encode(response_text.encode()).decode("ascii"),
        "response_sha256": hashlib.sha256(response_text.encode()).hexdigest(),
    }


def _ledger() -> dict[str, Any]:
    roles = tuple(runner.AGENT_CONFIGS)
    return {
        "schema_version": runner.STAGE0_LEDGER_SCHEMA_VERSION,
        "prior_commit_a": runner.PRIOR_AGENT_COMMIT_A,
        "prior_terminal_sha256": TERMINAL_SHA256,
        "contract_sha256": runner.STAGE0_CONTRACT_SHA256,
        "top_level_invocation_count": 3,
        "total_observed_agent_invocation_count": 3,
        "invocations": [
            _invocation(role, serial=index) for index, role in enumerate(roles, start=1)
        ],
    }


def _cli_module() -> ModuleType:
    path = REPOSITORY / "scripts/run_router_v2_blind_v2_final.py"
    spec = importlib.util.spec_from_file_location("stage0_router_v2_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage0_terminal_and_scientific_contract_are_frozen() -> None:
    assert hashlib.sha256(TERMINAL_PATH.read_bytes()).hexdigest() == TERMINAL_SHA256
    terminal = json.loads(TERMINAL_PATH.read_text(encoding="utf-8"))
    assert terminal["failure_stage"] == "agent_config_smoke"
    assert terminal["commit_a"] == runner.PRIOR_AGENT_COMMIT_A
    assert terminal["candidate_count"] == 0
    assert terminal["commit_b_created"] is False
    assert terminal["arm_a_or_c_model_loaded"] is False
    assert terminal["model_scores_observed"] is False
    assert terminal["formal_evaluation_started"] is False
    assert terminal["attempt_marker_created"] is False

    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    assert (
        runner.stage0_scientific_contract_sha256(preregistration)
        == SCIENTIFIC_CONTRACT_SHA256
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
    assert runner.STAGE0_CONTRACT["host_ledger_fields"] == list(
        runner.STAGE0_LEDGER_FIELDS_IN_ORDER
    )
    assert runner.STAGE0_CONTRACT["invocation_fields"] == list(
        runner.STAGE0_INVOCATION_FIELDS_IN_ORDER
    )
    assert runner.STAGE0_CONTRACT["raw_response_encoding"] == "base64"
    stage0_roles = cast(dict[str, dict[str, Any]], runner.STAGE0_CONTRACT["roles"])
    for role in runner.AGENT_CONFIGS:
        authority = stage0_roles[role]
        assert authority["canary"] == _canary(role)
        assert authority["canary_prompt"] == runner.STAGE0_CANARY_PROMPTS[role]
        assert (
            authority["canary_prompt_sha256"]
            == hashlib.sha256(
                runner.STAGE0_CANARY_PROMPTS[role].encode("utf-8")
            ).hexdigest()
        )
    assert runner.SELECTION_AUTHORITY["round_1_candidate_count"] == 256
    assert runner.POSITIVE_TASK_COUNT == 128
    assert runner.TEMPTING_NEGATIVE_COUNT == 96
    assert runner.TOKEN_5GRAM_JACCARD_MAX == runner.Decimal("0.80")
    assert runner.CHARACTER_5GRAM_JACCARD_MAX == runner.Decimal("0.85")
    assert runner.SEMANTIC_COSINE_MAX == runner.Decimal("0.90")
    assert runner.SELECTION_SEED == 7170
    assert runner.SEEDS == (7170, 7171, 7172)
    assert runner.FINAL_NAMESPACE_RELATIVE.as_posix().endswith("attempt-1")


def test_runtime_preregistration_binds_the_qualified_stage0_receipt() -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    runtime = runner.validate_runtime_requalification_authority(
        preregistration["runtime_requalification"],
        preregistration=preregistration,
        repository_root=REPOSITORY,
    )

    assert preregistration["schema_version"] == (
        runner.RUNTIME_PREREGISTRATION_SCHEMA_VERSION
    )
    assert runtime["status"] == "STAGE0_QUALIFIED_COMMIT_A2_PENDING"
    assert runtime["stage0_receipt_sha256"] == (
        "9009d03fe349efcf60e4f58b0a0b63a9fcaf2a78a04b7d4d838486212bbb9118"
    )
    assert runtime["stage0_top_level_invocations_observed"] == 3
    assert runtime["commit_a2_preparation_authorized"] is True
    assert runtime["commit_a2_creation_authorized"] is True
    assert runtime["candidate_generation_authorized"] is False
    assert runtime["model_loading_authorized"] is False
    assert runtime["model_scoring_authorized"] is False
    assert runtime["formal_evaluation_authorized"] is False


def test_runtime_preregistration_binds_formal_agent_invocation_contract() -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    runtime = runner.validate_runtime_requalification_authority(
        preregistration["runtime_requalification"],
        preregistration=preregistration,
        repository_root=REPOSITORY,
    )

    assert runtime["formal_agent_invocation_contract"] == (
        runner.FORMAL_AGENT_INVOCATION_CONTRACT
    )
    assert runtime["formal_agent_invocation_contract_sha256"] == (
        runner.FORMAL_AGENT_INVOCATION_CONTRACT_SHA256
    )
    assert runner.FORMAL_AGENT_INVOCATION_CONTRACT["required_host_lineage"] == {
        "lineage_observed": True,
        "tool_call_count": 0,
        "descendant_agent_count": 0,
    }
    assert runner.FORMAL_AGENT_INVOCATION_CONTRACT[
        "legal_provider_metadata_combinations"
    ] == [
        {
            "returned_model": None,
            "provider_returned_model_status": "INTERFACE_UNAVAILABLE",
        },
        {
            "returned_model": "EXACT_REQUESTED_ALIAS",
            "provider_returned_model_status": "AVAILABLE",
        },
    ]


def test_scientific_contract_rejects_mutation_but_ignores_runtime_template() -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    changed_runtime = deepcopy(preregistration)
    changed_runtime["runtime_requalification"]["status"] = "TEST_ONLY"
    assert (
        runner.stage0_scientific_contract_sha256(changed_runtime)
        == SCIENTIFIC_CONTRACT_SHA256
    )

    changed_science = deepcopy(preregistration)
    changed_science["blind_v2_expected_task_count"] = 129
    with pytest.raises(ValueError, match="scientific-contract authority drift"):
        runner.stage0_scientific_contract_sha256(changed_science)


def test_all_44_scientific_fields_equal_the_exact_head_baseline() -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(
        subprocess.run(
            [
                "git",
                "show",
                f"{runner.COMMIT_A2_PARENT}:{runner.PREREGISTRATION_RELATIVE.as_posix()}",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )

    assert len(runner.STAGE0_SCIENTIFIC_CONTRACT_FIELDS) == 44
    assert {
        field: preregistration[field]
        for field in runner.STAGE0_SCIENTIFIC_CONTRACT_FIELDS
    } == {field: baseline[field] for field in runner.STAGE0_SCIENTIFIC_CONTRACT_FIELDS}


@pytest.mark.parametrize(
    "protected_path",
    (
        "README.md",
        "README_EN.md",
        "docs/resume.md",
        "docs/interview-project-overview.html",
        "data/router-v2-blind-v2/blind-v2-tasks.jsonl",
        "artifacts/router-v2-v4/internal-training-pilot/pilot-001.json",
        "models/router-v2/checkpoint.safetensors",
    ),
)
def test_stage0_changed_surface_guard_rejects_protected_paths(
    protected_path: str,
) -> None:
    with pytest.raises(ValueError, match="requalification changed-file boundary"):
        runner.validate_requalification_changed_paths([protected_path])


def test_stage0_eligibility_accepts_only_the_exact_zero_exposure_terminal() -> None:
    eligibility = _eligibility()

    assert eligibility == {
        "eligible": True,
        "status": "AGENT_RUNTIME_STAGE0_ELIGIBLE",
        "prior_commit_a": runner.PRIOR_AGENT_COMMIT_A,
        "prior_terminal_commit": runner.PRIOR_AGENT_TERMINAL_COMMIT,
        "prior_terminal_path": runner.PRIOR_AGENT_SMOKE_TERMINAL_RELATIVE.as_posix(),
        "prior_terminal_sha256": TERMINAL_SHA256,
    }


def test_stage0_eligibility_requires_both_terminal_commits_to_be_ancestors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(repository: Path, *arguments: str) -> str:
        assert repository == REPOSITORY
        calls.append(arguments)
        return ""

    monkeypatch.setattr(runner, "_git", fake_git)

    assert _eligibility()["eligible"] is True
    assert (
        "merge-base",
        "--is-ancestor",
        runner.PRIOR_AGENT_TERMINAL_ARTIFACT_COMMIT,
        "HEAD",
    ) in calls


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("failure_stage", "later"),
        ("candidate_count", 1),
        ("commit_b_created", True),
        ("arm_a_or_c_model_loaded", True),
        ("model_scores_observed", True),
        ("formal_evaluation_started", True),
        ("attempt_marker_created", True),
        ("commit_a", "f" * 40),
    ),
)
def test_stage0_eligibility_returns_authority_drift_before_invocation(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    terminal = json.loads(TERMINAL_PATH.read_text(encoding="utf-8"))
    terminal[field] = value
    candidate = tmp_path / "terminal.json"
    candidate.write_text(json.dumps(terminal), encoding="utf-8")

    eligibility = runner.validate_stage0_requalification_eligibility(
        candidate,
        repository_root=REPOSITORY,
        canonical_path_required=False,
    )

    assert eligibility["eligible"] is False
    assert eligibility["status"] == "AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT"
    assert eligibility["router_decision"] == "KEEP_BASELINE"
    assert eligibility["candidate_generation_authorized"] is False


def test_stage0_host_envelope_qualifies_without_provider_returned_metadata() -> None:
    receipt = runner.build_stage0_qualification_receipt(
        _ledger(),
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_QUALIFIED"
    assert receipt["model_identity_evidence"] == "HOST_REQUEST_ENVELOPE"
    assert receipt["backend_alias_resolution_independently_proven"] is False
    assert receipt["commit_a2_preparation_authorized"] is True
    assert receipt["commit_a2_creation_authorized"] is False
    assert receipt["candidate_generation_authorized"] is False
    assert all(
        row["provider_returned_model_status"] == "INTERFACE_UNAVAILABLE"
        for row in receipt["invocations"]
    )


def test_stage0_matching_provider_metadata_is_accepted() -> None:
    ledger = _ledger()
    row = ledger["invocations"][0]
    row["provider_returned_model"] = row["requested_model"]
    row["provider_returned_model_status"] = "AVAILABLE"

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_QUALIFIED"
    assert receipt["backend_alias_resolution_independently_proven"] is False


def test_stage0_conflicting_provider_metadata_is_terminal() -> None:
    ledger = _ledger()
    ledger["invocations"][1]["provider_returned_model"] = "wrong-model"
    ledger["invocations"][1]["provider_returned_model_status"] = "AVAILABLE"

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE"
    assert receipt["commit_a2_preparation_authorized"] is False


@pytest.mark.parametrize(
    "response_text",
    (
        '{"protocol":"wrong","role":"generator","nonce":"x","status":"READY"}',
        '{"protocol":"x","role":"generator","nonce":"x","status":"READY","model":"gpt-5.6-sol"}',
        'prefix {"protocol":"x"}',
        '{"protocol":"x","protocol":"x","role":"generator","nonce":"x","status":"READY"}',
    ),
)
def test_stage0_canary_mismatch_is_terminal(response_text: str) -> None:
    ledger = _ledger()
    ledger["invocations"][0]["response_text"] = response_text
    ledger["invocations"][0]["response_sha256"] = hashlib.sha256(
        response_text.encode()
    ).hexdigest()

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_CANARY_MISMATCH"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("lineage_observed", False, "AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE"),
        ("tool_call_count", 1, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        ("descendant_agent_count", 1, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        ("history_message_count", 1, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        ("imported_memory_count", 1, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        ("response_count", 2, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        ("fork_context", True, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
    ),
)
def test_stage0_lineage_is_fail_closed(
    field: str,
    value: object,
    expected: str,
) -> None:
    ledger = _ledger()
    ledger["invocations"][2][field] = value
    if field == "descendant_agent_count":
        ledger["total_observed_agent_invocation_count"] = 4

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == expected
    assert receipt["commit_a2_preparation_authorized"] is False


def test_stage0_transport_failure_has_no_retry_or_fallback() -> None:
    ledger = _ledger()
    failed = ledger["invocations"][0]
    failed["outcome"] = "TRANSPORT_FAILURE"
    failed["agent_id"] = None
    failed["lineage_observed"] = False
    failed["tool_call_count"] = None
    failed["descendant_agent_count"] = None
    failed["response_count"] = 0
    failed["response_text"] = None
    failed["response_base64"] = None
    failed["response_sha256"] = None

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_TRANSPORT_FAILURE"
    assert receipt["top_level_invocation_count"] == 3
    assert all(row["transport_retry_count"] == 0 for row in receipt["invocations"])
    assert all(row["fallback_model_used"] is False for row in receipt["invocations"])


def test_stage0_retry_is_an_isolation_violation() -> None:
    ledger = _ledger()
    ledger["invocations"][0]["transport_retry_count"] = 1

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"


def test_stage0_unknown_fields_are_rejected_without_a_receipt() -> None:
    ledger = _ledger()
    ledger["invocations"][0]["self_reported_model"] = "gpt-5.6-sol"

    with pytest.raises(ValueError, match="Stage 0 invocation fields mismatch"):
        runner.build_stage0_qualification_receipt(
            ledger,
            eligibility=_eligibility(),
        )


def test_stage0_duplicate_ledger_keys_are_rejected() -> None:
    source = b'{"schema_version":"x","schema_version":"y"}'

    with pytest.raises(ValueError, match="duplicate key: schema_version"):
        runner.parse_stage0_host_envelope_ledger(source)


@pytest.mark.parametrize(
    "payload",
    (
        b"\xff",
        b'{"protocol":"x","role":"generator","nonce":"x"}',
    ),
)
def test_stage0_canary_rejects_invalid_utf8_and_missing_fields(
    payload: bytes,
) -> None:
    with pytest.raises(ValueError):
        runner.validate_stage0_canary_response(payload, role="generator")


def test_stage0_invalid_utf8_response_is_a_canary_terminal() -> None:
    ledger = _ledger()
    row = ledger["invocations"][0]
    raw = b"\xff"
    row["response_text"] = None
    row["response_base64"] = base64.b64encode(raw).decode("ascii")
    row["response_sha256"] = hashlib.sha256(raw).hexdigest()

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_CANARY_MISMATCH"


def test_stage0_timeout_is_part_of_the_host_configuration_envelope() -> None:
    ledger = _ledger()
    ledger["invocations"][0]["timeout_seconds"] = 1799

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE"


def test_stage0_timestamp_must_be_an_observed_utc_instant() -> None:
    ledger = _ledger()
    ledger["invocations"][0]["timestamp_utc"] = "not-a-timestamp"

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("top_level_invocation_count", 4, "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"),
        (
            "total_observed_agent_invocation_count",
            4,
            "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION",
        ),
    ),
)
def test_stage0_rejects_extra_top_level_or_nested_invocations(
    field: str,
    value: int,
    expected: str,
) -> None:
    ledger = _ledger()
    ledger[field] = value

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == expected


def test_stage0_rejects_duplicate_agent_identity() -> None:
    ledger = _ledger()
    ledger["invocations"][1]["agent_id"] = ledger["invocations"][0]["agent_id"]

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] == "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("fallback_model_used", True),
        ("reasoning_effort", "high"),
        ("requested_model", "fallback-model"),
    ),
)
def test_stage0_never_accepts_fallback_or_lowered_configuration(
    field: str,
    value: object,
) -> None:
    ledger = _ledger()
    ledger["invocations"][0][field] = value

    receipt = runner.build_stage0_qualification_receipt(
        ledger,
        eligibility=_eligibility(),
    )

    assert receipt["status"] in {
        "AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE",
        "AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION",
    }
    assert receipt["commit_a2_preparation_authorized"] is False


def test_stage0_receipt_write_is_exclusive_hash_bound_and_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = runner.build_stage0_qualification_receipt(
        _ledger(),
        eligibility=_eligibility(),
    )
    private_root = tmp_path / "private-receipts"
    monkeypatch.setattr(runner, "STAGE0_RECEIPT_ROOT", private_root)
    path = private_root / f"{receipt['receipt_sha256']}.json"

    with pytest.raises(ValueError, match="hash-bound private path"):
        runner.write_stage0_qualification_receipt(
            receipt,
            path=tmp_path / "arbitrary-receipt.json",
        )

    assert runner.write_stage0_qualification_receipt(receipt) == path
    assert path.stat().st_mode & 0o777 == 0o600
    assert runner.validate_stage0_qualification_receipt(path) == receipt

    path.chmod(0o644)
    with pytest.raises(ValueError, match="mode 0600"):
        runner.validate_stage0_qualification_receipt(path)
    path.chmod(0o600)

    private_root.chmod(0o755)
    with pytest.raises(ValueError, match="parent mode 0700"):
        runner.validate_stage0_qualification_receipt(path)
    private_root.chmod(0o700)

    linked = tmp_path / "linked-receipt.json"
    linked.symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        runner.validate_stage0_qualification_receipt(linked)

    not_regular = tmp_path / "not-a-regular-receipt"
    not_regular.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="regular file"):
        runner.validate_stage0_qualification_receipt(not_regular)

    with pytest.raises(FileExistsError):
        runner.write_stage0_qualification_receipt(receipt)


def test_stage0_receipt_rederives_status_instead_of_trusting_self_hash(
    tmp_path: Path,
) -> None:
    receipt = runner.build_stage0_qualification_receipt(
        _ledger(),
        eligibility=_eligibility(),
    )
    receipt["invocations"][0]["timeout_seconds"] = 1799
    document = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = runner.canonical_sha256(document)
    path = tmp_path / "forged.json"
    path.write_bytes(runner._canonical_json_bytes(receipt))
    path.chmod(0o600)

    with pytest.raises(ValueError, match="derived status mismatch"):
        runner.validate_stage0_qualification_receipt(path)


def test_stage0_receipt_terminal_posture_is_invariant() -> None:
    for state in runner.STAGE0_TERMINAL_STATES:
        posture = runner.stage0_terminal_posture(state)
        assert posture["status"] == state
        assert posture["router_decision"] == "KEEP_BASELINE"
        assert posture["production_ready"] is False
        assert posture["release_authorized"] is False
        assert posture["default_router_unchanged"] is True
        assert posture["candidate_generation_authorized"] is False
        assert posture["commit_a2_creation_authorized"] is False


def test_stage0_cli_has_no_runtime_authority_arguments() -> None:
    cli = _cli_module()
    parser = cli._parser()
    subparsers = next(
        action for action in parser._actions if getattr(action, "choices", None)
    )
    command = subparsers.choices["runtime-qualification-status"]
    options = {
        option for action in command._actions for option in action.option_strings
    }

    assert options == {"-h", "--help"}


def test_stage0_cli_reads_private_fixed_ledger_and_writes_qualified_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _cli_module()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    ledger_path = private / "ledger.json"
    ledger_path.write_bytes(runner._canonical_json_bytes(_ledger()))
    ledger_path.chmod(0o600)
    receipt_root = tmp_path / "receipts"
    monkeypatch.setattr(cli.workflow, "STAGE0_HOST_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(cli.workflow, "STAGE0_RECEIPT_ROOT", receipt_root)

    result = cli._runtime_qualification_status(SimpleNamespace())
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output["status"] == "AGENT_RUNTIME_STAGE0_QUALIFIED"
    assert Path(output["receipt_path"]).is_file()
    assert not (REPOSITORY / runner.FINAL_NAMESPACE_RELATIVE).exists()


def test_stage0_cli_malformed_ledger_has_no_receipt_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _cli_module()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    ledger_path = private / "ledger.json"
    ledger_path.write_bytes(b'{"schema_version":"x","schema_version":"y"}')
    ledger_path.chmod(0o600)
    writes: list[object] = []
    monkeypatch.setattr(cli.workflow, "STAGE0_HOST_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(
        cli.workflow,
        "write_stage0_qualification_receipt",
        lambda receipt: writes.append(receipt),
    )

    with pytest.raises(ValueError, match="duplicate key: schema_version"):
        cli._runtime_qualification_status(SimpleNamespace())

    assert writes == []


def test_stage0_cli_checks_authority_before_reading_ledger(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _cli_module()
    monkeypatch.setattr(
        cli.workflow,
        "validate_stage0_requalification_eligibility",
        lambda *args, **kwargs: {
            "eligible": False,
            **runner.stage0_terminal_posture("AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT"),
        },
    )
    monkeypatch.setattr(
        cli,
        "_stage0_host_ledger",
        lambda: pytest.fail("ledger must not be read after authority drift"),
    )

    assert cli._runtime_qualification_status(SimpleNamespace()) == 2
    assert (
        json.loads(capsys.readouterr().out)["status"]
        == "AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT"
    )


def test_stage0_cli_rejects_non_private_or_symlink_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _cli_module()
    private = tmp_path / "private"
    private.mkdir(mode=0o755)
    ledger_path = private / "ledger.json"
    ledger_path.write_bytes(runner._canonical_json_bytes(_ledger()))
    ledger_path.chmod(0o600)
    monkeypatch.setattr(cli.workflow, "STAGE0_HOST_LEDGER_PATH", ledger_path)

    with pytest.raises(ValueError, match="directory must use mode 0700"):
        cli._stage0_host_ledger()

    private.chmod(0o700)
    link = tmp_path / "ledger-link.json"
    link.symlink_to(ledger_path)
    monkeypatch.setattr(cli.workflow, "STAGE0_HOST_LEDGER_PATH", link)
    with pytest.raises(ValueError, match="symlink"):
        cli._stage0_host_ledger()


def test_stage0_cli_allows_only_the_trusted_temp_root_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _cli_module()
    physical_temp = tmp_path / "physical-temp"
    physical_temp.mkdir(mode=0o1777)
    physical_temp.chmod(0o1777)
    trusted_temp = tmp_path / "trusted-temp"
    trusted_temp.symlink_to(physical_temp, target_is_directory=True)
    private = physical_temp / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    ledger_path = trusted_temp / "private" / "ledger.json"
    ledger_path.write_bytes(runner._canonical_json_bytes(_ledger()))
    ledger_path.chmod(0o600)
    monkeypatch.setattr(
        cli.workflow,
        "STAGE0_TRUSTED_TEMP_ROOT",
        trusted_temp,
        raising=False,
    )
    monkeypatch.setattr(cli.workflow, "STAGE0_HOST_LEDGER_PATH", ledger_path)

    assert cli._stage0_host_ledger() == _ledger()

    linked_private = physical_temp / "linked-private"
    linked_private.symlink_to(private, target_is_directory=True)
    monkeypatch.setattr(
        cli.workflow,
        "STAGE0_HOST_LEDGER_PATH",
        trusted_temp / "linked-private" / "ledger.json",
    )
    with pytest.raises(ValueError, match="symlink"):
        cli._stage0_host_ledger()


def test_pending_commit_a2_blocks_before_agent_inputs_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _cli_module()
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    runtime = preregistration["runtime_requalification"]
    runtime["status"] = "PENDING_STAGE0"
    runtime["stage0_top_level_invocations_observed"] = 0
    runtime["stage0_receipt_sha256"] = None
    runtime["commit_a2_preparation_authorized"] = False
    runtime["commit_a2_creation_authorized"] = False
    monkeypatch.setattr(
        cli.workflow,
        "validate_preregistration_authority",
        lambda *args, **kwargs: {"status": "VALID"},
    )
    monkeypatch.setattr(cli, "_json", lambda _path: preregistration)
    monkeypatch.setattr(
        cli,
        "_load_preregistered_agent_inputs",
        lambda *args, **kwargs: pytest.fail(
            "Agent inputs must not be read before Commit A2 authority"
        ),
    )

    with pytest.raises(ValueError, match="blocked pending qualified Stage 0"):
        cli._commit_a_context(require_config_smoke=True)


@pytest.mark.parametrize("entrypoint", ("_model_smoke", "_commit_b_context"))
def test_model_and_post_freeze_entrypoints_gate_on_commit_a2_first(
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
) -> None:
    cli = _cli_module()

    def blocked(*args: object, **kwargs: object) -> None:
        raise ValueError("Commit A2 gate reached first")

    monkeypatch.setattr(cli, "_commit_a_context", blocked)
    monkeypatch.setattr(
        cli.workflow,
        "run_model_load_smoke",
        lambda *args, **kwargs: pytest.fail("model must not load before Commit A2"),
    )
    monkeypatch.setattr(
        cli.workflow,
        "read_frozen_dataset_documents",
        lambda *args, **kwargs: pytest.fail(
            "frozen data must not read before Commit A2"
        ),
    )

    with pytest.raises(ValueError, match="Commit A2 gate reached first"):
        if entrypoint == "_model_smoke":
            cli._model_smoke(SimpleNamespace())
        else:
            cli._commit_b_context(require_model_smoke=False)


def test_commit_a2_is_blocked_while_stage0_is_pending() -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    runtime = preregistration["runtime_requalification"]
    runtime["status"] = "PENDING_STAGE0"
    runtime["stage0_top_level_invocations_observed"] = 0
    runtime["stage0_receipt_sha256"] = None
    runtime["commit_a2_preparation_authorized"] = False
    runtime["commit_a2_creation_authorized"] = False

    with pytest.raises(ValueError, match="blocked pending qualified Stage 0"):
        runner.validate_commit_a2_repository(REPOSITORY, preregistration)


def test_commit_a2_authority_requires_receipt_clean_exact_commit_and_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    preregistration = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    receipt = runner.build_stage0_qualification_receipt(
        _ledger(), eligibility=_eligibility()
    )
    receipt_root = tmp_path / "receipts"
    monkeypatch.setattr(runner, "STAGE0_RECEIPT_ROOT", receipt_root)
    runner.write_stage0_qualification_receipt(receipt)
    runtime = preregistration["runtime_requalification"]
    runtime["status"] = "STAGE0_QUALIFIED_COMMIT_A2_PENDING"
    runtime["stage0_top_level_invocations_observed"] = 3
    runtime["stage0_receipt_sha256"] = receipt["receipt_sha256"]
    runtime["commit_a2_preparation_authorized"] = True
    runtime["commit_a2_creation_authorized"] = True
    head = "a" * 40

    def fake_git(_repository: Path, *arguments: str) -> str:
        if arguments[:2] == ("status", "--porcelain"):
            return ""
        if arguments == ("rev-parse", "HEAD"):
            return head
        if arguments[:4] == ("rev-list", "--parents", "-n", "1"):
            return f"{head} {runner.COMMIT_A2_PARENT}"
        if arguments[:3] == ("diff", "--name-only", "--no-renames"):
            return "\n".join(sorted(runner.STAGE0_REQUALIFICATION_CHANGED_FILES))
        if arguments[:2] == ("merge-base", "--is-ancestor"):
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(runner, "_git", fake_git)

    authority = runner.validate_commit_a2_repository(REPOSITORY, preregistration)

    assert authority["commit_a2"] == head
    assert authority["parent"] == runner.COMMIT_A2_PARENT
    assert authority["stage0_receipt_sha256"] == receipt["receipt_sha256"]
