from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from hermes_skilleval import router_v2_blind_v2_run002 as run002
from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner
from hermes_skilleval import router_v2_blind_v2_output_schema_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]
RUN001_TERMINAL = (
    ROOT
    / "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001"
    / "candidate-generation-terminal.json"
)
RUN001_TERMINAL_SHA256 = (
    "74b8e9fb01e008ee40c1f38c65c73a9fde371c615e4689f847ab88887cefa6ea"
)
SCRIPT_PATH = ROOT / "scripts/run_router_v2_blind_v2_final.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "router_v2_run002_cli", SCRIPT_PATH
)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
run002_cli = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(run002_cli)


def _canonical_skill_ids() -> set[str]:
    return {f"test-skill-{index:02d}" for index in range(16)}


def _skills() -> list[dict[str, Any]]:
    return [
        {
            "id": f"test-skill-{index:02d}",
            "name": f"Skill {index:02d}",
            "category": "test",
            "description": f"Description {index:02d}",
            "trigger_terms": [f"trigger-{index:02d}"],
            "body": f"Body {index:02d}",
        }
        for index in range(16)
    ]


def _response() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "prompt_text": f"Natural synthetic Run002 request {index}",
                "semantic_family_id": f"run002-family-{index:02d}",
                "proposed_gold_skill_id": "test-skill-00",
                "proposed_negative_skill_id": ("test-skill-01" if index < 12 else None),
                "language": "en",
                "rationale": f"Synthetic Run002 rationale {index}",
            }
            for index in range(16)
        ]
    }


def _synthetic_freeze_documents(commit_a: str) -> dict[str, bytes]:
    tasks: list[dict[str, Any]] = []
    outcomes: dict[str, str] = {}
    for skill_index in range(16):
        gold = f"test-skill-{skill_index:02d}"
        negative = f"test-skill-{(skill_index + 1) % 16:02d}"
        for index in range(8):
            task_id = hashlib.sha256(f"{gold}:{index}".encode()).hexdigest()[:24]
            prompt = f"Synthetic Run002 evaluation prompt {gold} {index}"
            tasks.append(
                {
                    "candidate_id": task_id,
                    "candidate_index": index,
                    "generation_round": 1,
                    "prompt_text": prompt,
                    "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "semantic_family_id": f"eval-family-{skill_index:02d}-{index}",
                    "proposed_gold_skill_id": gold,
                    "proposed_negative_skill_id": negative if index < 6 else None,
                    "language": "en",
                    "rationale": "Synthetic evaluation binding rationale.",
                }
            )
            outcomes[task_id] = "SELECTED"
    validation = {
        "status": "VALID",
        "run_id": run002.RUN_ID,
        "tasks": tasks,
        "review_request_count": 256,
        "reviewer_valid_count": 256,
        "reviewer_unanimous_agreement_count": 128,
        "candidate_outcomes": outcomes,
        "source_file_sha256": {
            filename: hashlib.sha256(filename.encode()).hexdigest()
            for filename in (
                "agent-run-metadata.json",
                "blind-v2-contamination.jsonl",
                "blind-v2-generation.jsonl",
                "blind-v2-review-a.jsonl",
                "blind-v2-review-b.jsonl",
            )
        },
        "candidate_generation_count": 256,
        "candidate_import_rejection_count": 0,
        "accepted_candidate_count": 256,
        "rejected_candidate_count": 0,
        "supplement_request_count": 0,
        "duplicate_and_contamination_checks_passed": True,
        "contamination_checked_candidate_count": 256,
        "agent_configs": deepcopy(run002.AGENT_CONFIGS),
        "source_skill_index_sha256": run002.canonical_sha256(_skills()),
        "authority_manifest_sha256": "a" * 64,
        "retry_records": [],
        "agent_run_evidence": [
            {
                "role": "generator",
                "run_id": run002.RUN_ID,
                "commit_a": commit_a,
            }
        ],
        "deterministic_selection_authority": {
            "selection_authority": dict(runner.SELECTION_AUTHORITY),
            "selected_candidate_ids": [row["candidate_id"] for row in tasks],
            "selected_candidate_ids_sha256": run002.canonical_sha256(
                [row["candidate_id"] for row in tasks]
            ),
        },
    }
    return run002.build_dataset_freeze_documents(validation, commit_a=commit_a)


def _model_bindings() -> list[dict[str, Any]]:
    files = [{"path": "model.bin", "size": 1, "sha256": "a" * 64}]
    manifest_sha256 = runner._manifest_rows_hash(files)
    return [
        {
            "arm": arm,
            "seed": seed,
            "model_path": f"/models/{arm}/{seed}",
            "model_manifest_path": f"/models/{arm}/{seed}/manifest.json",
            "model_manifest_file_sha256": "b" * 64,
            "model_manifest_sha256": "c" * 64,
            "model_file_manifest_sha256": manifest_sha256,
            "model_files": deepcopy(files),
        }
        for seed in runner.SEEDS
        for arm in runner.ARMS
    ]


def _import(response: dict[str, Any]) -> dict[str, Any]:
    return run002.import_generator_response(
        response,
        run_id=run002.RUN_ID,
        request_id="a" * 64,
        expected_gold_skill_id="test-skill-00",
        expected_negative_quota=12,
        expected_positive_only_quota=4,
        canonical_skill_ids=_canonical_skill_ids(),
    )


def test_run002_generator_schema_has_only_semantic_candidate_fields() -> None:
    schema = run002.GENERATOR_RESPONSE_SCHEMA
    candidate_array = schema["properties"]["candidates"]
    candidate_schema = candidate_array["items"]

    assert schema["additionalProperties"] is False
    assert candidate_array["minItems"] == 16
    assert candidate_array["maxItems"] == 16
    assert set(candidate_schema["required"]) == {
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    assert set(candidate_schema["properties"]) == set(candidate_schema["required"])
    assert candidate_schema["additionalProperties"] is False
    assert "candidate_index" not in candidate_schema["properties"]
    assert "candidate_id" not in candidate_schema["properties"]


def test_host_imports_index_free_response_and_assigns_strict_positions() -> None:
    imported = _import(_response())

    assert imported["request_outcome"] == "ACCEPTED"
    assert [row["candidate_index"] for row in imported["accepted_candidates"]] == list(
        range(16)
    )
    assert [row["position"] for row in imported["candidate_outcomes"]] == list(
        range(16)
    )
    assert all(row["outcome"] == "ACCEPTED" for row in imported["candidate_outcomes"])


def test_host_candidate_ids_are_stable_and_prompt_sensitive() -> None:
    response = _response()
    first = _import(response)
    second = _import(deepcopy(response))
    changed_response = deepcopy(response)
    changed_response["candidates"][7]["prompt_text"] += " changed"
    changed = _import(changed_response)

    first_ids = [row["candidate_id"] for row in first["accepted_candidates"]]
    second_ids = [row["candidate_id"] for row in second["accepted_candidates"]]
    changed_ids = [row["candidate_id"] for row in changed["accepted_candidates"]]
    assert first_ids == second_ids
    assert first_ids[:7] == changed_ids[:7]
    assert first_ids[7] != changed_ids[7]
    assert first_ids[8:] == changed_ids[8:]


def test_candidate_id_binds_run_request_position_and_prompt() -> None:
    request_id = "b" * 64
    prompt_text = "Synthetic identity request"
    baseline = run002.host_candidate_id(
        run_id=run002.RUN_ID,
        request_id=request_id,
        position=3,
        prompt_text=prompt_text,
    )

    assert baseline == run002.host_candidate_id(
        run_id=run002.RUN_ID,
        request_id=request_id,
        position=3,
        prompt_text=prompt_text,
    )
    assert baseline != run002.host_candidate_id(
        run_id="other-run",
        request_id=request_id,
        position=3,
        prompt_text=prompt_text,
    )
    assert baseline != run002.host_candidate_id(
        run_id=run002.RUN_ID,
        request_id="c" * 64,
        position=3,
        prompt_text=prompt_text,
    )
    assert baseline != run002.host_candidate_id(
        run_id=run002.RUN_ID,
        request_id=request_id,
        position=4,
        prompt_text=prompt_text,
    )
    assert baseline != run002.host_candidate_id(
        run_id=run002.RUN_ID,
        request_id=request_id,
        position=3,
        prompt_text="Different request",
    )


def test_wrong_candidate_count_rejects_only_the_request() -> None:
    for count in (15, 17):
        response = _response()
        if count == 15:
            response["candidates"].pop()
        else:
            response["candidates"].append(deepcopy(response["candidates"][-1]))

        imported = _import(response)

        assert imported["request_outcome"] == "REJECTED_CANDIDATE_COUNT"
        assert imported["observed_candidate_count"] == count
        assert imported["accepted_candidates"] == []
        assert imported["candidate_outcomes"] == []
        assert imported["retry_allowed"] is False


def test_single_semantically_invalid_candidate_is_rejected_without_aborting() -> None:
    response = _response()
    response["candidates"][5]["proposed_gold_skill_id"] = "test-skill-09"

    imported = _import(response)

    assert imported["request_outcome"] == "ACCEPTED_WITH_CANDIDATE_REJECTIONS"
    assert len(imported["accepted_candidates"]) == 15
    assert [row["candidate_index"] for row in imported["accepted_candidates"]] == [
        *range(5),
        *range(6, 16),
    ]
    rejected = [
        row for row in imported["candidate_outcomes"] if row["outcome"] != "ACCEPTED"
    ]
    assert rejected == [
        {
            "position": 5,
            "candidate_index": 5,
            "candidate_id": run002.host_candidate_id(
                run_id=run002.RUN_ID,
                request_id="a" * 64,
                position=5,
                prompt_text="Natural synthetic Run002 request 5",
            ),
            "outcome": "REJECTED_SEMANTIC",
            "reasons": ["PROPOSED_GOLD_MISMATCH"],
        }
    ]
    assert imported["retry_allowed"] is False


def test_formal_generator_prompt_and_import_freeze_quality_and_quota_rules() -> None:
    commit_a = "d" * 40
    request = run002.build_formal_generator_request(
        _skills(),
        commit_a=commit_a,
        gold_skill_id="test-skill-00",
        negative_quota=12,
        positive_only_quota=4,
        round_number=1,
    )

    prompt = request["system_prompt"].lower()
    assert "natural" in prompt
    assert "single primary" in prompt
    assert "label leakage" in prompt
    assert "plausible" in prompt and "confusable" in prompt
    assert request["input"]["rules"] == run002.GENERATOR_RULES
    assert request["authority"]["commit_a"] == commit_a
    assert "authority" not in request["input"]

    wrong_strata = _response()
    wrong_strata["candidates"][11]["proposed_negative_skill_id"] = None
    imported = run002.import_generator_response(
        wrong_strata,
        run_id=run002.RUN_ID,
        request_id=request["request_sha256"],
        expected_gold_skill_id="test-skill-00",
        expected_negative_quota=12,
        expected_positive_only_quota=4,
        canonical_skill_ids=_canonical_skill_ids(),
    )
    assert imported["request_outcome"] == "REJECTED_QUOTA_STRATA"
    assert imported["accepted_candidates"] == []


def test_run001_public_terminal_bytes_remain_unchanged() -> None:
    assert hashlib.sha256(RUN001_TERMINAL.read_bytes()).hexdigest() == (
        RUN001_TERMINAL_SHA256
    )


def test_generator_canary_is_synthetic_deterministic_and_side_effect_free(
    tmp_path: Path,
) -> None:
    before = list(tmp_path.iterdir())
    first = run002.run_generator_canary()
    second = run002.run_generator_canary()

    assert first == second
    assert first["status"] == "RUN002_GENERATOR_CANARY_PASSED"
    assert first["run_id"] == run002.RUN_ID
    assert first["candidate_count"] == 16
    assert first["candidate_indexes"] == list(range(16))
    assert len(first["candidate_ids"]) == len(set(first["candidate_ids"])) == 16
    assert first["formal_data_written"] is False
    assert first["router_loaded"] is False
    assert list(tmp_path.iterdir()) == before


def test_generator_canary_controller_invokes_one_real_host_boundary(
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []
    authority_root = tmp_path / ("d" * 40)
    authority_root.mkdir(mode=0o700)
    manifest = run002.build_authority_manifest(
        commit_a=authority_root.name,
        current_git_commit=authority_root.name,
        private_evidence_root=authority_root,
    )

    def invoke(**kwargs: Any) -> dict[str, Any]:
        assert (authority_root / run002.AUTHORITY_MANIFEST_FILENAME).is_file()
        calls.append(kwargs)
        response = run002.synthetic_canary_response()
        return {
            "status": "VALID",
            "invocation": {"synthetic": True},
            "response": response,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }

    result = run002_cli.run_run002_generator_canary(
        invocation_runner=invoke,
        authority_root=authority_root,
        authority_manifest=manifest,
        private_root=authority_root / "generator-canary",
    )

    assert result["status"] == "RUN002_GENERATOR_CANARY_PASSED"
    assert len(calls) == 1
    request = calls[0]["request"]
    assert request["model"] == "gpt-5.6-sol"
    assert request["reasoning_effort"] == "max"
    assert request["response_schema"] == run002.GENERATOR_RESPONSE_SCHEMA
    assert request["input"]["synthetic_canary"] is True
    assert request["input"]["formal_data"] is False
    assert calls[0]["private_root"] == authority_root / "generator-canary"
    assert result["formal_data_written"] is False
    assert result["router_loaded"] is False


def test_existing_formal_host_accepts_run002_canary_request_and_schema(
    tmp_path: Path,
) -> None:
    request = run002.build_generator_canary_request()
    response = run002.synthetic_canary_response()
    response_bytes = json.dumps(
        response,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    events = [
        {"type": "thread.started", "thread_id": "run002-canary-thread"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "message-1",
                "type": "agent_message",
                "text": response_bytes.decode(),
            },
        },
        {"type": "turn.completed"},
    ]
    event_bytes = b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for event in events
    )

    def probe(_executable: Path) -> dict[str, str]:
        return {
            "version": preflight.CODEX_CLI_VERSION,
            "executable_sha256": preflight.CODEX_EXECUTABLE_SHA256,
            "resolved_executable": str(preflight.CODEX_EXECUTABLE_RESOLVED),
        }

    def launch(**_kwargs: Any) -> dict[str, object]:
        return {
            "returncode": 0,
            "event_bytes": event_bytes,
            "response_bytes": response_bytes,
            "response_read_error": False,
            "timed_out": False,
            "process_started": True,
            "host_authority_valid": True,
        }

    result = preflight.run_formal_agent_invocation(
        request=request,
        private_root=tmp_path / "formal-run002-canary",
        repository_root=ROOT,
        host_probe=cast(preflight.HostProbe, probe),
        launcher=launch,
    )

    assert runner.validate_agent_request(request) == request
    assert result["status"] == "VALID"
    assert result["response"] == response


def test_formal_host_classifies_invalid_json_as_the_only_output_retry_case(
    tmp_path: Path,
) -> None:
    request = run002.build_generator_canary_request()
    response_bytes = b"{not-json"
    events = [
        {"type": "thread.started", "thread_id": "run002-invalid-json-thread"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "message-1",
                "type": "agent_message",
                "text": response_bytes.decode(),
            },
        },
        {"type": "turn.completed"},
    ]
    event_bytes = b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for event in events
    )

    def probe(_executable: Path) -> dict[str, str]:
        return {
            "version": preflight.CODEX_CLI_VERSION,
            "executable_sha256": preflight.CODEX_EXECUTABLE_SHA256,
            "resolved_executable": str(preflight.CODEX_EXECUTABLE_RESOLVED),
        }

    def launch(**_kwargs: Any) -> dict[str, object]:
        return {
            "returncode": 0,
            "event_bytes": event_bytes,
            "response_bytes": response_bytes,
            "response_read_error": False,
            "timed_out": False,
            "process_started": True,
            "host_authority_valid": True,
        }

    result = preflight.run_formal_agent_invocation(
        request=request,
        private_root=tmp_path / "formal-run002-invalid-json",
        repository_root=ROOT,
        host_probe=cast(preflight.HostProbe, probe),
        launcher=launch,
    )

    assert result["status"] == "FORMAL_OUTPUT_BLOCKED"
    assert result["failure_kind"] == "INVALID_JSON"


def test_retry_policy_allows_only_recorded_no_response_transport_or_invalid_json() -> (
    None
):
    assert run002.retry_allowed(
        "TRANSPORT_FAILURE",
        retry_count=0,
        transport_failure_no_response=True,
        syntactically_valid_response=False,
    )
    assert run002.retry_allowed(
        "INVALID_JSON",
        retry_count=0,
        transport_failure_no_response=False,
        syntactically_valid_response=False,
    )
    assert not run002.retry_allowed(
        "TRANSPORT_FAILURE",
        retry_count=0,
        transport_failure_no_response=False,
        syntactically_valid_response=False,
    )
    assert not run002.retry_allowed(
        "TRANSPORT_FAILURE",
        retry_count=0,
        transport_failure_no_response=True,
        syntactically_valid_response=True,
    )
    for failure_kind in ("TRANSPORT_FAILURE", "INVALID_JSON"):
        assert not run002.retry_allowed(
            failure_kind,
            retry_count=1,
            transport_failure_no_response=True,
            syntactically_valid_response=False,
        )
    for failure_kind in (
        "UNCLASSIFIED_EXCEPTION",
        "PROCESS_EXIT",
        "SEMANTIC_INVALID",
        "CANDIDATE_COUNT_MISMATCH",
        "SCHEMA_INVALID",
        "REVIEW_DISAGREEMENT",
    ):
        assert not run002.retry_allowed(
            failure_kind,
            retry_count=0,
            transport_failure_no_response=False,
            syntactically_valid_response=False,
        )


def test_formal_schedule_does_not_retry_arbitrary_exception(tmp_path: Path) -> None:
    request = run002.build_generator_canary_request()
    calls = 0

    def invoke(**_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("not a classified transport failure")

    outcomes, failure = run002_cli._invoke_formal_schedule(
        [{"request": request}],
        repository=ROOT,
        invocation_root=tmp_path / "invocations",
        invocation_runner=invoke,
        seen_thread_ids=set(),
        ordinal_state={"next": 1},
        max_workers=1,
        on_batch=lambda _batch: None,
        run002_retry=True,
        continue_on_failure=True,
    )

    assert calls == 1
    assert failure is outcomes[0]
    assert outcomes[0]["retry_count"] == 0
    assert outcomes[0]["attempt_records"] == [
        {
            "attempt_ordinal": 1,
            "status": "FORMAL_PROCESS_BLOCKED",
            "failure_kind": "UNCLASSIFIED_EXCEPTION",
            "request_sha256": request["request_sha256"],
            "transport_failure_no_response": False,
            "syntactically_valid_response": False,
            "retry_authorized": False,
        }
    ]


def test_formal_schedule_does_not_retry_nonzero_process_exit(tmp_path: Path) -> None:
    request = run002.build_generator_canary_request()
    calls = 0

    def invoke(**_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "status": "FORMAL_PROCESS_BLOCKED",
            "failure_kind": "PROCESS_EXIT",
            "transport_failure_no_response": False,
            "invocation": None,
            "response": None,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }

    outcomes, failure = run002_cli._invoke_formal_schedule(
        [{"request": request}],
        repository=ROOT,
        invocation_root=tmp_path / "invocations",
        invocation_runner=invoke,
        seen_thread_ids=set(),
        ordinal_state={"next": 1},
        max_workers=1,
        on_batch=lambda _batch: None,
        run002_retry=True,
        continue_on_failure=True,
    )

    assert calls == 1
    assert failure is outcomes[0]
    assert outcomes[0]["retry_count"] == 0
    assert outcomes[0]["attempt_records"][0]["failure_kind"] == "PROCESS_EXIT"
    assert outcomes[0]["attempt_records"][0]["retry_authorized"] is False


def test_formal_schedule_retries_one_identical_request_once_on_transport(
    tmp_path: Path,
) -> None:
    request = run002.build_generator_canary_request()
    response = run002.synthetic_canary_response()
    calls: list[dict[str, Any]] = []

    def invoke(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "status": "FORMAL_PROCESS_BLOCKED",
                "failure_kind": "TRANSPORT_FAILURE",
                "transport_failure_no_response": True,
                "invocation": None,
                "response": None,
                "retry_count": 0,
                "fallback_used": False,
                "fork_context": False,
            }
        return {
            "status": "VALID",
            "invocation": {
                "transport_failure": False,
                "response_bytes_present": True,
                "envelope": {
                    "role": "generator",
                    "thread_id": "run002-retry-thread",
                    "fork_context": False,
                    "history_message_count": 0,
                    "imported_memory_count": 0,
                    "requested_model": "gpt-5.6-sol",
                    "returned_model": None,
                    "provider_returned_model_status": "INTERFACE_UNAVAILABLE",
                    "reasoning_effort": "max",
                    "timeout_seconds": 1800,
                    "lineage_observed": True,
                    "tool_call_count": 0,
                    "descendant_agent_count": 0,
                    "transport_retry_count": 0,
                    "request_sha256": request["request_sha256"],
                    "response": response,
                },
            },
            "response": response,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }

    outcomes, failure = run002_cli._invoke_formal_schedule(
        [{"request": request}],
        repository=ROOT,
        invocation_root=tmp_path / "invocations",
        invocation_runner=invoke,
        seen_thread_ids=set(),
        ordinal_state={"next": 1},
        max_workers=1,
        on_batch=lambda _batch: None,
        run002_retry=True,
        continue_on_failure=True,
    )

    assert failure is None
    assert len(calls) == 2
    assert calls[0]["request"] == calls[1]["request"] == request
    assert outcomes[0]["valid"] is True
    assert outcomes[0]["retry_count"] == 1
    assert outcomes[0]["attempt_statuses"] == [
        "FORMAL_PROCESS_BLOCKED",
        "VALID",
    ]


def test_round_one_and_deficit_only_supplement_keep_every_response_at_16() -> None:
    skill_ids = sorted(_canonical_skill_ids())
    round_one = run002.round_one_quota_plan(skill_ids)
    assert len(round_one) == 16
    assert all(
        row["negative_quota"] == 12
        and row["positive_only_quota"] == 4
        and row["response_candidate_count"] == 16
        for row in round_one
    )
    assert run002.FORMAL_GENERATOR_MAX_CONCURRENCY == 4

    supplement = run002.supplement_quota_plan(
        {
            "test-skill-00": {"negative": 2, "positive_only": 0},
            "test-skill-01": {"negative": 1, "positive_only": 1},
            "test-skill-02": {"negative": 0, "positive_only": 0},
        },
        canonical_skill_ids=set(skill_ids),
    )
    assert supplement == [
        {
            "gold_skill_id": "test-skill-00",
            "negative_quota": 16,
            "positive_only_quota": 0,
            "response_candidate_count": 16,
            "round_number": 2,
        },
        {
            "gold_skill_id": "test-skill-01",
            "negative_quota": 8,
            "positive_only_quota": 8,
            "response_candidate_count": 16,
            "round_number": 2,
        },
    ]


def test_run002_root_namespace_and_manifest_are_independent_from_run001() -> None:
    commit_a = "d" * 40
    root = run002.private_evidence_root(commit_a)
    manifest = run002.build_authority_manifest(
        commit_a=commit_a,
        current_git_commit="e" * 40,
    )

    assert root.is_absolute()
    assert run002.RUN_ID in root.parts
    assert run002.RUN001_COMMIT_A not in root.parts
    assert root != run002.RUN001_PRIVATE_EVIDENCE_ROOT
    assert run002.OUTPUT_NAMESPACE == Path(
        "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-002"
    )
    assert manifest["run_id"] == run002.RUN_ID
    assert manifest["predecessor_run_id"] == ("router-v2-v4-successor-blind-v2-001")
    assert manifest["predecessor_terminal_sha256"] == RUN001_TERMINAL_SHA256
    assert manifest["replacement_reason"] == "HOST_ASSIGNED_CANDIDATE_IDENTITY"
    assert manifest["run001_model_scores_observed"] is False
    assert manifest["run001_candidates_reused"] is False
    assert manifest["router_decision"] == "KEEP_BASELINE"
    assert manifest["current_git_commit"] == "e" * 40
    assert manifest["generator_schema_sha256"] == run002.canonical_sha256(
        run002.GENERATOR_RESPONSE_SCHEMA
    )
    assert run002.validate_authority_manifest(manifest) == manifest


class _Run002ConstructionHost:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.labels_by_prompt: dict[str, tuple[str, str | None, int, int]] = {}
        self.attempts: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def __call__(
        self,
        *,
        request: dict[str, Any],
        private_root: Path,
        repository_root: Path,
        seen_thread_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        del repository_root, seen_thread_ids
        response: dict[str, Any]
        role = str(request["role"])
        key = (role, str(request["request_sha256"]))
        with self._lock:
            ordinal = len(self.calls) + 1
            self.calls.append(
                {"request": deepcopy(request), "private_root": private_root}
            )
            attempt = self.attempts.get(key, 0) + 1
            self.attempts[key] = attempt
        private_root.mkdir(mode=0o700)

        if role == "generator":
            assert request["response_schema"] == run002.GENERATOR_RESPONSE_SCHEMA
            quota = request["input"]["quota"]
            gold = str(quota["gold_skill_id"])
            round_number = int(quota["round_number"])
            if gold == "test-skill-11" and round_number == 1 and attempt == 1:
                return self._failure("TRANSPORT_FAILURE")
            if gold == "test-skill-15" and round_number == 1:
                return self._failure("SCHEMA_INVALID")
            skill_ids = [str(row["id"]) for row in request["input"]["canonical_skills"]]
            negative = next(skill_id for skill_id in skill_ids if skill_id != gold)
            candidates: list[dict[str, Any]] = []
            for index in range(16):
                is_negative = index < int(quota["negative_quota"])
                prompt = f"run002:{round_number}:{gold}:{index}:natural request"
                candidate_gold = (
                    "test-skill-13"
                    if gold == "test-skill-14" and round_number == 1 and index == 0
                    else gold
                )
                candidate = {
                    "prompt_text": prompt,
                    "semantic_family_id": f"family-{round_number}-{gold}-{index}",
                    "proposed_gold_skill_id": candidate_gold,
                    "proposed_negative_skill_id": negative if is_negative else None,
                    "language": "en",
                    "rationale": f"Synthetic rationale {round_number}-{index}",
                }
                candidates.append(candidate)
                with self._lock:
                    self.labels_by_prompt[prompt] = (
                        gold,
                        negative if is_negative else None,
                        round_number,
                        index,
                    )
            response = {"candidates": candidates}
        else:
            prompt = str(request["input"]["prompt_text"])
            gold, reviewed_negative, round_number, candidate_index = (
                self.labels_by_prompt[prompt]
            )
            if role == "reviewer_a" and (
                gold,
                round_number,
                candidate_index,
            ) == ("test-skill-13", 1, 0):
                return self._failure("TRANSPORT_FAILURE")
            if role == "reviewer_b" and (
                gold,
                round_number,
                candidate_index,
            ) == ("test-skill-12", 1, 0):
                return self._failure("SCHEMA_INVALID")
            reject = role == "reviewer_a" and (
                gold == "test-skill-00" and round_number == 1 and candidate_index < 7
            )
            response = {
                "decision": "REJECT_UNNATURAL" if reject else "ACCEPT",
                "reviewed_gold_skill_id": gold,
                "reviewed_negative_skill_id": reviewed_negative,
                "natural": not reject,
                "single_primary_skill": True,
                "no_label_leakage": True,
                "negative_confusable": (
                    True if reviewed_negative is not None else None
                ),
                "confidence": "HIGH",
                "reason": "Synthetic blind review decision.",
            }

        envelope = {
            "role": role,
            "thread_id": f"run002-construction-{ordinal:04d}",
            "fork_context": False,
            "history_message_count": 0,
            "imported_memory_count": 0,
            "requested_model": request["model"],
            "returned_model": None,
            "provider_returned_model_status": "INTERFACE_UNAVAILABLE",
            "reasoning_effort": request["reasoning_effort"],
            "timeout_seconds": request["timeout_seconds"],
            "lineage_observed": True,
            "tool_call_count": 0,
            "descendant_agent_count": 0,
            "transport_retry_count": 0,
            "request_sha256": request["request_sha256"],
            "response": response,
        }
        runner.validate_agent_invocation_envelope(envelope, request=request)
        return {
            "status": "VALID",
            "invocation": {
                "transport_failure": False,
                "response_bytes_present": True,
                "envelope": envelope,
            },
            "response": response,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }

    @staticmethod
    def _failure(kind: str) -> dict[str, Any]:
        return {
            "status": "FORMAL_PROCESS_BLOCKED",
            "failure_kind": kind,
            "transport_failure_no_response": kind == "TRANSPORT_FAILURE",
            "invocation": None,
            "response": None,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }


def test_run002_construction_uses_host_ids_and_isolates_candidate_request_and_review_failures(
    tmp_path: Path,
) -> None:
    staging_root = tmp_path / ("d" * 40)
    host = _Run002ConstructionHost()
    authority_manifest = run002.build_authority_manifest(
        commit_a=staging_root.name,
        current_git_commit=staging_root.name,
        private_evidence_root=staging_root,
    )
    context = {
        "repository": ROOT,
        "commit_a": staging_root.name,
        "staging_root": staging_root,
        "canonical_skills": _skills(),
        "preregistration": {},
        "train_prompts": [],
        "pilot_prompts": [],
        "phase16_prompts": [],
        "prior_candidate_prompts": [],
        "train_family_ids": set(),
        "pilot_family_ids": set(),
        "phase16_family_ids": set(),
        "prior_candidate_family_ids": set(),
        "run002_authority": True,
        "authority_manifest": authority_manifest,
    }

    def scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        clean: list[str] = []
        for candidate in candidates:
            quarantined = candidate["prompt_text"] == (
                "run002:1:test-skill-00:0:natural request"
            )
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "scanner_decision": "REJECT" if quarantined else "PASS",
                    "rejection_codes": ["TEST_QUARANTINE"] if quarantined else [],
                    "evidence_sha256": run002.canonical_sha256(
                        {
                            "candidate_id": candidate["candidate_id"],
                            "quarantined": quarantined,
                        }
                    ),
                }
            )
            if not quarantined:
                clean.append(candidate["candidate_id"])
        return {
            "rows": rows,
            "clean_candidate_ids": clean,
            "scanner_config": {"test": "frozen"},
        }

    def invoke_after_manifest(**kwargs: Any) -> dict[str, Any]:
        manifest_path = staging_root / run002.AUTHORITY_MANIFEST_FILENAME
        assert manifest_path.is_file()
        assert (
            run002.validate_authority_manifest(
                json.loads(manifest_path.read_bytes()),
                expected_root=staging_root,
            )
            == authority_manifest
        )
        return host(**kwargs)

    result = run002_cli.run_successor_agent_construction(
        context,
        invocation_runner=invoke_after_manifest,
        contamination_scanner=scan,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
        run002_mode=True,
    )

    assert result["status"] == "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE", result
    assert result["router_decision"] == "KEEP_BASELINE"
    assert result["production_ready"] is False
    assert result["release_authorized"] is False
    assert result["default_router_unchanged"] is True
    generation_rows = run002_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    round_one = [row for row in generation_rows if row["generation_round"] == 1]
    round_two = [row for row in generation_rows if row["generation_round"] == 2]
    assert len(round_one) == 16
    assert {row["gold_skill_id"] for row in round_two} == {
        "test-skill-00",
        "test-skill-15",
    }
    assert all(
        row["request"]["input"]["quota"]["response_candidate_count"] == 16
        and row["request"]["input"]["quota"]["negative_quota"]
        + row["request"]["input"]["quota"]["positive_only_quota"]
        == 16
        for row in generation_rows
    )
    rejected = [
        outcome
        for row in generation_rows
        for outcome in row.get("candidate_outcomes", [])
        if outcome["outcome"] != "ACCEPTED"
    ]
    assert any("PROPOSED_GOLD_MISMATCH" in row["reasons"] for row in rejected)
    assert result["round_1_candidate_count"] == 239
    assert result["round_2_candidate_count"] == 32
    assert result["retry_count"] == 2
    reviewer_rows = {
        role: run002_cli._jsonl(staging_root / filename)
        for role, filename in (
            ("reviewer_a", "blind-v2-review-a.jsonl"),
            ("reviewer_b", "blind-v2-review-b.jsonl"),
        )
    }
    assert any(row.get("valid") is False for row in reviewer_rows["reviewer_a"])
    assert any(row.get("valid") is False for row in reviewer_rows["reviewer_b"])
    quarantined_prompt = "run002:1:test-skill-00:0:natural request"
    assert all(
        call["request"]["input"].get("prompt_text") != quarantined_prompt
        for call in host.calls
        if call["request"]["role"].startswith("reviewer_")
    )
    assert all(
        set(candidate) == run002.GENERATOR_CANDIDATE_FIELDS
        for call in host.calls
        if call["request"]["role"] == "generator"
        for candidate in (
            call["request"]["response_schema"]["properties"]["candidates"]["items"][
                "properties"
            ],
        )
    )

    validation = run002.validate_agent_pack(
        staging_root,
        canonical_skills=_skills(),
        contamination_replayer=scan,
        expected_commit_a=staging_root.name,
    )
    assert validation["task_count"] == 128
    assert validation["negative_labeled_task_count"] == 96
    assert validation["family_count"] == 128
    assert set(validation["gold_distribution"].values()) == {8}
    assert set(validation["negative_per_gold"].values()) == {6}
    assert set(validation["positive_only_per_gold"].values()) == {2}
    documents = run002.build_dataset_freeze_documents(
        validation,
        commit_a=staging_root.name,
    )
    output_dir = tmp_path / run002.DATASET_FREEZE_RELATIVE
    run002.write_dataset_freeze(
        documents,
        output_dir,
        repository_root=tmp_path,
    )
    assert {path.name for path in output_dir.iterdir()} == set(
        run002.DATASET_FREEZE_FILENAMES
    )
    manifest = json.loads((output_dir / "blind-v2-manifest.json").read_bytes())
    assert manifest["task_count"] == 128
    assert manifest["negative_labeled_task_count"] == 96
    assert manifest["skill_count"] == 16
    assert manifest["tasks_per_skill"] == 8
    assert manifest["negative_per_skill"] == 6
    assert manifest["positive_only_per_skill"] == 2
    assert manifest["semantic_family_count"] == 128
    assert manifest["source_type"] == "AGENT_GENERATED"
    assert manifest["review_mode"] == "DUAL_AGENT_UNANIMOUS_REVIEWED"
    assert manifest["human_reviewer_count"] == 0
    assert manifest["human_author_count"] == 0
    assert manifest["evaluation_started"] is False
    assert manifest["release_authorized"] is False
    assert manifest["retry_records"] == validation["retry_records"]
    assert manifest["agent_run_evidence"] == validation["agent_run_evidence"]
    assert all(
        evidence["run_id"] == run002.RUN_ID
        and evidence["commit_a"] == staging_root.name
        and len(evidence["request_sha256"]) == 64
        and len(evidence["system_prompt_sha256"]) == 64
        and len(evidence["response_schema_sha256"]) == 64
        and len(evidence["agent_config_sha256"]) == 64
        for evidence in manifest["agent_run_evidence"]
    )
    assert (
        manifest["deterministic_selection_authority"]
        == validation["deterministic_selection_authority"]
    )
    assert manifest["model_scores_observed"] is False
    assert manifest["training_after_data_access"] is False
    assert manifest["router_decision"] == "KEEP_BASELINE"

    private_files = {
        path.name: path.read_bytes()
        for path in staging_root.iterdir()
        if path.is_file()
    }

    def restore_private_pack() -> None:
        for filename, payload in private_files.items():
            (staging_root / filename).write_bytes(payload)

    def write_jsonl(filename: str, rows: list[dict[str, Any]]) -> None:
        (staging_root / filename).write_bytes(
            b"".join(run002_cli._canonical_bytes(row) for row in rows)
        )

    def validate_tamper(message: str) -> None:
        with pytest.raises(ValueError, match=message):
            run002.validate_agent_pack(
                staging_root,
                canonical_skills=_skills(),
                contamination_replayer=scan,
                expected_commit_a=staging_root.name,
            )

    contamination = run002_cli._jsonl(staging_root / "blind-v2-contamination.jsonl")
    contamination[0]["scanner_decision"] = (
        "REJECT" if contamination[0]["scanner_decision"] == "PASS" else "PASS"
    )
    write_jsonl("blind-v2-contamination.jsonl", contamination)
    validate_tamper("contamination ledger evidence")
    restore_private_pack()

    generation = run002_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    generation[0], generation[1] = generation[1], generation[0]
    write_jsonl("blind-v2-generation.jsonl", generation)
    validate_tamper("generation schedule authority")
    restore_private_pack()

    generation = run002_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    duplicate_supplement = deepcopy(generation[-1])
    duplicate_supplement.update(
        {
            "invocations": [],
            "request_outcome": "FORMAL_OUTPUT_BLOCKED",
            "candidate_outcomes": [],
            "status": "FORMAL_OUTPUT_BLOCKED",
            "valid": False,
            "retry_count": 0,
            "attempt_statuses": ["FORMAL_OUTPUT_BLOCKED"],
            "attempt_records": [
                {
                    "attempt_ordinal": 1,
                    "status": "FORMAL_OUTPUT_BLOCKED",
                    "failure_kind": "SCHEMA_INVALID",
                    "request_sha256": duplicate_supplement["request"]["request_sha256"],
                    "transport_failure_no_response": False,
                    "syntactically_valid_response": False,
                    "retry_authorized": False,
                }
            ],
        }
    )
    generation.append(duplicate_supplement)
    write_jsonl("blind-v2-generation.jsonl", generation)
    validate_tamper("generation schedule authority")
    restore_private_pack()

    generation = run002_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    generation[0]["attempt_records"][0]["request_sha256"] = "f" * 64
    write_jsonl("blind-v2-generation.jsonl", generation)
    validate_tamper("byte-identical retry authority")
    restore_private_pack()

    rejected_id = next(
        row["candidate_id"]
        for row in run002_cli._jsonl(staging_root / "blind-v2-contamination.jsonl")
        if row["scanner_decision"] == "REJECT"
    )
    reviews = run002_cli._jsonl(staging_root / "blind-v2-review-a.jsonl")
    forged_review = deepcopy(reviews[0])
    forged_review["candidate_id"] = rejected_id
    reviews.append(forged_review)
    write_jsonl("blind-v2-review-a.jsonl", reviews)
    validate_tamper("quarantined or duplicate review candidate")
    restore_private_pack()

    generation = run002_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    generator_thread = next(
        invocation["envelope"]["thread_id"]
        for row in generation
        for invocation in row["invocations"]
    )
    reviews = run002_cli._jsonl(staging_root / "blind-v2-review-a.jsonl")
    reviews[0]["invocations"][0]["envelope"]["thread_id"] = generator_thread
    write_jsonl("blind-v2-review-a.jsonl", reviews)
    validate_tamper("session/thread id must be unique")
    restore_private_pack()

    authority = json.loads(
        (staging_root / run002.AUTHORITY_MANIFEST_FILENAME).read_bytes()
    )
    authority["generator_rules_sha256"] = "0" * 64
    (staging_root / run002.AUTHORITY_MANIFEST_FILENAME).write_bytes(
        run002_cli._canonical_bytes(authority)
    )
    validate_tamper("authority manifest mismatch")
    restore_private_pack()

    metadata = json.loads((staging_root / "agent-run-metadata.json").read_bytes())
    metadata["roles"]["generator"]["provider_returned_models"] = ["forged-model"]
    (staging_root / "agent-run-metadata.json").write_bytes(
        run002_cli._canonical_bytes(metadata)
    )
    validate_tamper("role metadata binding")
    restore_private_pack()


def test_run002_cli_exposes_canary_and_explicit_authority_selection() -> None:
    canary = run002_cli._parser().parse_args(["run002-generator-canary"])
    assert canary.authority == "run002"

    construction = run002_cli._parser().parse_args(
        ["run-agent-construction", "--authority", "run002", "--max-workers", "4"]
    )
    assert construction.authority == "run002"
    assert construction.max_workers == 4

    for command in ("pack-status", "freeze", "model-smoke", "evaluate"):
        args = run002_cli._parser().parse_args([command, "--authority", "run002"])
        assert args.authority == "run002"

    legacy = run002_cli._parser().parse_args(["pack-status", "--successor"])
    assert legacy.successor is True


def test_run002_model_smoke_adapter_uses_new_dataset_root() -> None:
    calls: list[dict[str, Any]] = []

    def smoke_runner(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        commit_state = kwargs["commit_b_validator"](
            ROOT,
            commit_a="d" * 40,
        )
        assert commit_state == {"commit_a": "d" * 40, "commit_b": "e" * 40}
        return {"status": "PASS"}

    result = run002_cli.run_run002_model_load_smoke(
        {
            "repository": ROOT,
            "commit_a": "d" * 40,
            "commit_b": "e" * 40,
            "pilot_manifest_path": ROOT / runner.PILOT_MANIFEST_RELATIVE,
        },
        smoke_runner=smoke_runner,
    )

    assert result == {"status": "PASS"}
    assert calls[0]["dataset_freeze_relative"] == run002.DATASET_FREEZE_RELATIVE
    assert calls[0]["dataset_freeze_relative"] != runner.DATASET_FREEZE_RELATIVE


def test_run002_post_commit_b_requires_clean_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def dirty_git(_repository: Path, *args: str) -> str:
        calls.append(args)
        return " M tracked-file\n"

    monkeypatch.setattr(runner, "_git", dirty_git)
    with pytest.raises(ValueError, match="clean worktree"):
        run002_cli._require_run002_clean_worktree(ROOT)
    assert calls == [("status", "--porcelain", "--untracked-files=all")]

    monkeypatch.setattr(runner, "_git", lambda _repository, *_args: "")
    run002_cli._require_run002_clean_worktree(ROOT)


def test_run002_evaluation_bindings_preserve_gate_metrics_and_namespace() -> None:
    commit_a = "d" * 40
    frozen_documents = _synthetic_freeze_documents(commit_a)
    metric_definitions = {
        "raw_count_first": True,
        "positive_denominator": 128,
        "negative_denominator": 96,
    }
    gate = {"recall_at_1_min": "0.90", "router_decision": "KEEP_BASELINE"}
    preregistration: dict[str, Any] = {
        "pilot_002_gate_artifact": deepcopy(gate),
        "metric_definitions": deepcopy(metric_definitions),
        "query_contract": {"version": "prompt-only-v1"},
        "skill_representation_builder": {"version": "frozen-skill-v1"},
        "evaluator": {"version": "unchanged-evaluator-v1"},
    }
    preregistration["preregistration_sha256"] = run002.canonical_sha256(preregistration)
    preregistration_bytes = run002_cli._canonical_bytes(preregistration)

    bindings = run002.build_evaluation_bindings(
        preregistration=preregistration,
        preregistration_bytes=preregistration_bytes,
        canonical_skills=_skills(),
        model_bindings=_model_bindings(),
        frozen_documents=frozen_documents,
        commit_a=commit_a,
    )

    assert bindings["gate"] == gate
    assert bindings["metric_definitions"] == metric_definitions
    assert bindings["output_namespace"] == run002.OUTPUT_NAMESPACE.as_posix()
    assert bindings["evaluation_kernel"] == "UNCHANGED_ROUTER_V2_BLIND_V2"
    assert bindings["run_id"] == run002.RUN_ID
    commit_b = "e" * 40
    attempt_token = "f" * 64
    started = run002_cli._canonical_bytes(
        runner.build_attempt_started_document(
            {
                "commit_a": commit_a,
                "commit_b": commit_b,
                "attempt_token_sha256": attempt_token,
            }
        )
    )
    tasks, skills, models = run002.validate_evaluation_inputs(
        commit_a=commit_a,
        commit_b=commit_b,
        attempt_token_sha256=attempt_token,
        frozen_bindings=bindings,
        input_artifacts={
            "preregistration.json": preregistration_bytes,
            "blind-v2-tasks.jsonl": frozen_documents["blind-v2-tasks.jsonl"],
            "blind-v2-manifest.json": frozen_documents["blind-v2-manifest.json"],
            "review-summary.json": frozen_documents["blind-v2-review-summary.json"],
        },
        attempt_started_artifact=started,
    )
    assert len(tasks) == 128
    assert len(skills) == 16
    assert [(row["arm"], row["seed"]) for row in models] == [
        (arm, seed) for seed in runner.SEEDS for arm in runner.ARMS
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    (("evaluation_started", True), ("release_authorized", True)),
)
def test_run002_evaluation_rejects_mutated_frozen_truth_fields(
    field: str,
    value: bool,
) -> None:
    commit_a = "d" * 40
    frozen_documents = _synthetic_freeze_documents(commit_a)
    manifest = json.loads(frozen_documents["blind-v2-manifest.json"])
    manifest[field] = value
    frozen_documents["blind-v2-manifest.json"] = run002_cli._canonical_bytes(manifest)

    with pytest.raises(ValueError, match="evaluation manifest mismatch"):
        run002._validated_evaluation_tasks(
            frozen_documents,
            commit_a=commit_a,
        )


def test_run002_evaluate_handler_uses_run002_adapter_unchanged_kernel_and_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    commit_a = "d" * 40
    commit_b = "e" * 40
    frozen_documents = _synthetic_freeze_documents(commit_a)
    tasks = json.loads(
        "["
        + ",".join(
            line.decode()
            for line in frozen_documents["blind-v2-tasks.jsonl"].splitlines()
        )
        + "]"
    )
    models = _model_bindings()
    context = {
        "repository": ROOT,
        "commit_a": commit_a,
        "commit_b": commit_b,
        "preregistration_path": ROOT / runner.PREREGISTRATION_RELATIVE,
        "pilot_manifest_path": ROOT / runner.PILOT_MANIFEST_RELATIVE,
        "frozen_documents": frozen_documents,
        "frozen_manifest_file_sha256": hashlib.sha256(
            frozen_documents["blind-v2-manifest.json"]
        ).hexdigest(),
        "canonical_skills": _skills(),
    }
    monkeypatch.setattr(run002_cli, "_run002_commit_b_context", lambda **_kw: context)
    monkeypatch.setattr(
        runner,
        "validate_preregistration_authority",
        lambda *_args, **_kwargs: {"preregistration_sha256": "a" * 64},
    )
    monkeypatch.setattr(runner, "_jsonl_no_duplicate_keys", lambda *_args: tasks)
    monkeypatch.setattr(run002_cli, "_model_bindings", lambda _pilot: models)

    def build_bindings(**_kwargs: Any) -> dict[str, Any]:
        events.append("bindings")
        return {"run_id": run002.RUN_ID}

    def validate_inputs(**_kwargs: Any) -> tuple[list[Any], list[Any], list[Any]]:
        events.append("pre-scoring")
        return tasks, _skills(), models

    def evaluate_routes(*_args: Any, **_kwargs: Any) -> list[Any]:
        events.append("unchanged-kernel")
        return []

    def build_documents(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        events.append("unchanged-metrics-gate")
        return {}

    monkeypatch.setattr(
        run002,
        "build_evaluation_bindings",
        build_bindings,
    )
    monkeypatch.setattr(
        run002,
        "validate_evaluation_inputs",
        validate_inputs,
    )
    monkeypatch.setattr(
        runner,
        "_evaluate_routes_validated",
        evaluate_routes,
    )
    monkeypatch.setattr(
        run002,
        "validate_evaluation_routes",
        lambda *_args, **_kwargs: events.append("route-authority"),
    )
    monkeypatch.setattr(
        runner,
        "_build_evaluation_documents_validated",
        build_documents,
    )

    def single_attempt(
        output_root: Path,
        *,
        output_namespace: Path,
        evaluate: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        assert output_root == ROOT / run002.OUTPUT_NAMESPACE
        assert output_namespace == run002.OUTPUT_NAMESPACE
        events.append("run002-namespace")
        assert evaluate() == {}
        return {"status": "COMPLETED"}

    monkeypatch.setattr(runner, "run_single_attempt", single_attempt)

    assert (
        run002_cli._evaluate(
            run002_cli.argparse.Namespace(authority="run002", successor=False)
        )
        == 0
    )
    assert events == [
        "bindings",
        "pre-scoring",
        "run002-namespace",
        "unchanged-kernel",
        "route-authority",
        "unchanged-metrics-gate",
    ]


def test_run002_handlers_consume_run002_contexts_and_namespace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    construction_context = {
        "run002_authority": True,
        "commit_a": "d" * 40,
        "repository": ROOT,
    }

    def construction_context_factory() -> dict[str, Any]:
        events.append("construction-context")
        return construction_context

    monkeypatch.setattr(
        run002_cli,
        "_run002_commit_a_context",
        construction_context_factory,
    )

    def construct(context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        assert context is construction_context
        assert kwargs["run002_mode"] is True
        events.append("construction-run002")
        return {"status": "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE"}

    monkeypatch.setattr(run002_cli, "run_successor_agent_construction", construct)
    assert (
        run002_cli._run_agent_construction(
            run002_cli.argparse.Namespace(authority="run002", max_workers=4)
        )
        == 0
    )

    validation = {
        "status": "VALID",
        "task_count": 128,
        "negative_labeled_task_count": 96,
        "family_count": 128,
        "model_scores_observed": False,
    }

    def pack_context(*, authority: str) -> tuple[dict[str, Any], dict[str, Any], Any]:
        assert authority == "run002"
        events.append("pack-context")
        return construction_context, validation, lambda _left, _right: 0.0

    monkeypatch.setattr(run002_cli, "_validated_pack_context", pack_context)
    args = run002_cli.argparse.Namespace(authority="run002", successor=False)
    assert run002_cli._pack_status(args) == 0
    monkeypatch.setattr(
        run002,
        "build_dataset_freeze_documents",
        lambda *_args, **_kwargs: {
            name: b"{}\n" for name in run002.DATASET_FREEZE_FILENAMES
        },
    )
    monkeypatch.setattr(
        run002,
        "write_dataset_freeze",
        lambda *_args, **_kwargs: events.append("freeze-run002"),
    )
    assert run002_cli._freeze(args) == 0

    commit_b_context = {"commit_a": "d" * 40, "commit_b": "e" * 40}

    def commit_b_context_factory(**_kwargs: Any) -> dict[str, Any]:
        events.append("commit-b-context")
        return commit_b_context

    monkeypatch.setattr(
        run002_cli,
        "_run002_commit_b_context",
        commit_b_context_factory,
    )
    monkeypatch.setattr(
        run002_cli,
        "run_run002_model_load_smoke",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        runner,
        "write_model_load_smoke_receipt",
        lambda _receipt: tmp_path / "smoke.json",
    )
    assert run002_cli._model_smoke(args) == 0

    class StopAfterRun002Context(RuntimeError):
        pass

    def stop_evaluate(**_kwargs: Any) -> dict[str, Any]:
        assert run002_cli._selected_authority(args) == "run002"
        assert run002.OUTPUT_NAMESPACE.name == run002.RUN_ID
        raise StopAfterRun002Context

    monkeypatch.setattr(run002_cli, "_run002_commit_b_context", stop_evaluate)
    with pytest.raises(StopAfterRun002Context):
        run002_cli._evaluate(args)

    assert events == [
        "construction-context",
        "construction-run002",
        "pack-context",
        "pack-context",
        "freeze-run002",
        "commit-b-context",
    ]
