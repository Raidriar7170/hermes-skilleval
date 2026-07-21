from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import threading
from copy import deepcopy
from datetime import UTC, datetime as real_datetime
from pathlib import Path
from typing import Any

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner
from hermes_skilleval import router_v2_blind_v2_output_schema_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RECEIPT = (
    ROOT / "artifacts/router-v2-blind-v2-successor-preflight/preflight-receipt.json"
)
SCRIPT_PATH = ROOT / "scripts/run_router_v2_blind_v2_final.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "router_v2_blind_v2_successor_formal_cli", SCRIPT_PATH
)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
formal_cli = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(formal_cli)


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


def _successor_generator_request() -> dict[str, Any]:
    return runner._build_generator_request_payload(
        _skills(),
        gold_skill_id="test-skill-00",
        negative_quota=2,
        positive_only_quota=1,
        successor_output_schema=True,
    )


def _generator_response() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "candidate_index": index,
                "prompt_text": f"Natural synthetic request {index}",
                "semantic_family_id": f"family-{index}",
                "proposed_gold_skill_id": "test-skill-00",
                "proposed_negative_skill_id": ("test-skill-01" if index < 2 else None),
                "language": "en",
                "rationale": f"Synthetic rationale {index}",
            }
            for index in range(3)
        ]
    }


def _reviewer_response() -> dict[str, Any]:
    return {
        "decision": "ACCEPT",
        "reviewed_gold_skill_id": "test-skill-00",
        "reviewed_negative_skill_id": "test-skill-01",
        "natural": True,
        "single_primary_skill": True,
        "no_label_leakage": True,
        "negative_confusable": True,
        "confidence": "HIGH",
        "reason": "Synthetic review is internally consistent.",
    }


class _FakeFormalHost:
    def __init__(
        self,
        response: dict[str, Any],
        *,
        thread_id: str = "formal-thread-001",
        response_override: bytes | None = None,
    ) -> None:
        self.response = response
        self.thread_id = thread_id
        self.response_override = response_override
        self.probes: list[Path] = []
        self.calls: list[dict[str, Any]] = []

    def probe(self, executable: Path) -> dict[str, str]:
        self.probes.append(executable)
        return {
            "version": preflight.CODEX_CLI_VERSION,
            "executable_sha256": preflight.CODEX_EXECUTABLE_SHA256,
            "resolved_executable": str(preflight.CODEX_EXECUTABLE_RESOLVED),
        }

    def launch(
        self,
        *,
        role: str,
        argv: tuple[str, ...],
        stdin: bytes,
        cwd: Path,
        timeout_seconds: int,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "role": role,
                "argv": argv,
                "stdin": stdin,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
            }
        )
        response_bytes = self.response_override or json.dumps(
            self.response,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        message = response_bytes.decode("utf-8", errors="replace")
        events = [
            {"type": "thread.started", "thread_id": self.thread_id},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {
                    "id": "message-1",
                    "type": "agent_message",
                    "text": message,
                },
            },
            {"type": "turn.completed"},
        ]
        event_bytes = b"".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            for event in events
        )
        return {
            "returncode": 0,
            "event_bytes": event_bytes,
            "response_bytes": response_bytes,
            "response_read_error": False,
            "timed_out": False,
            "process_started": True,
            "host_authority_valid": True,
        }


class _FakeConstructionRunner:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.fail_at = fail_at
        self.calls: list[dict[str, Any]] = []
        self.candidate_labels: dict[str, tuple[str, str | None, int, int]] = {}
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
        with self._lock:
            ordinal = len(self.calls) + 1
            self.calls.append(
                {
                    "request": deepcopy(request),
                    "private_root": private_root,
                }
            )
        private_root.mkdir(mode=0o700)
        if ordinal == self.fail_at:
            return {
                "status": "FORMAL_PROCESS_BLOCKED",
                "invocation": None,
                "response": None,
                "retry_count": 0,
                "fallback_used": False,
                "fork_context": False,
            }

        role = request["role"]
        if role == "generator":
            quota = request["input"]["quota"]
            gold = quota["gold_skill_id"]
            round_number = quota["round_number"]
            skill_ids = [row["id"] for row in request["input"]["canonical_skills"]]
            negative = next(value for value in skill_ids if value != gold)
            candidates = []
            for index in range(quota["negative_quota"] + quota["positive_only_quota"]):
                unique_text = hashlib.sha256(
                    f"{round_number}:{gold}:{index}".encode()
                ).hexdigest()
                candidates.append(
                    {
                        "candidate_index": index,
                        "prompt_text": (
                            f"{unique_text} {unique_text[::-1]} synthetic request "
                            f"for scenario {round_number}-{index}"
                        ),
                        "semantic_family_id": (
                            f"family-round-{round_number}-{gold}-{index}"
                        ),
                        "proposed_gold_skill_id": gold,
                        "proposed_negative_skill_id": (
                            negative if index < quota["negative_quota"] else None
                        ),
                        "language": "en",
                        "rationale": f"Synthetic rationale {round_number}-{index}",
                    }
                )
            response = {"candidates": candidates}
            response_sha256 = runner.canonical_sha256(response)
            with self._lock:
                for candidate in candidates:
                    candidate_id = runner.opaque_candidate_id(
                        round_number,
                        gold,
                        candidate["candidate_index"],
                        response_sha256,
                    )
                    self.candidate_labels[candidate_id] = (
                        gold,
                        candidate["proposed_negative_skill_id"],
                        round_number,
                        candidate["candidate_index"],
                    )
        else:
            candidate_id = request["input"]["task_id"]
            with self._lock:
                gold, negative, round_number, candidate_index = self.candidate_labels[
                    candidate_id
                ]
            reject = (
                role == "reviewer_a"
                and round_number == 1
                and gold == "test-skill-00"
                and candidate_index < 7
            )
            response = {
                "decision": "REJECT_UNNATURAL" if reject else "ACCEPT",
                "reviewed_gold_skill_id": gold,
                "reviewed_negative_skill_id": negative,
                "natural": not reject,
                "single_primary_skill": True,
                "no_label_leakage": True,
                "negative_confusable": True if negative is not None else None,
                "confidence": "HIGH",
                "reason": "Synthetic blind review decision.",
            }

        envelope = {
            "role": role,
            "thread_id": f"successor-thread-{ordinal:04d}",
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
        invocation = {
            "transport_failure": False,
            "response_bytes_present": True,
            "envelope": envelope,
        }
        return {
            "status": "VALID",
            "invocation": invocation,
            "response": response,
            "retry_count": 0,
            "fallback_used": False,
            "fork_context": False,
        }


def _successor_context(staging_root: Path) -> dict[str, Any]:
    return {
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
        "successor_authority": True,
    }


def _all_clean_scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": [
            {"candidate_id": row["candidate_id"], "decision": "ACCEPT"}
            for row in candidates
        ],
        "clean_candidate_ids": [row["candidate_id"] for row in candidates],
    }


def _all_contaminated_scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": [
            {"candidate_id": row["candidate_id"], "decision": "REJECT"}
            for row in candidates
        ],
        "clean_candidate_ids": [],
    }


def _test_generator_builder(
    canonical_skills: list[dict[str, Any]],
    *,
    gold_skill_id: str,
    negative_quota: int,
    positive_only_quota: int,
    repository_root: Path,
    round_number: int,
    successor_output_schema: bool,
) -> dict[str, Any]:
    del repository_root
    return runner._build_generator_request_payload(
        canonical_skills,
        gold_skill_id=gold_skill_id,
        negative_quota=negative_quota,
        positive_only_quota=positive_only_quota,
        round_number=round_number,
        successor_output_schema=successor_output_schema,
    )


def _copy_public_receipt(repository: Path) -> None:
    target = repository / preflight.PUBLIC_RECEIPT_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(PUBLIC_RECEIPT.read_bytes())


def _rewrite_first_review_request_as_historical(
    staging_root: Path,
    *,
    role: str,
    canonical_skills: list[dict[str, Any]],
) -> None:
    filename = {
        "reviewer_a": "blind-v2-review-a.jsonl",
        "reviewer_b": "blind-v2-review-b.jsonl",
    }[role]
    path = staging_root / filename
    rows = formal_cli._jsonl(path)
    original = rows[0]["request"]
    historical_request = runner.build_reviewer_request(
        {
            "candidate_id": original["input"]["task_id"],
            "prompt_text": original["input"]["prompt_text"],
        },
        canonical_skills,
        role=role,
        successor_output_schema=False,
    )
    rows[0]["request"] = historical_request
    for invocation in rows[0]["invocations"]:
        invocation["envelope"]["request_sha256"] = historical_request["request_sha256"]
    path.write_bytes(formal_cli._jsonl_bytes(rows))

    metadata_path = staging_root / "agent-run-metadata.json"
    metadata = formal_cli._json(metadata_path)
    metadata["source_file_sha256"][filename] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    metadata_path.write_bytes(formal_cli._canonical_bytes(metadata))


def _rebind_validation_source_files(
    validation: dict[str, Any], staging_root: Path
) -> None:
    for filename in runner.REQUIRED_AGENT_PACK_FILES:
        payload = (staging_root / filename).read_bytes()
        validation["source_file_bytes"][filename] = payload.hex()
        validation["source_file_sha256"][filename] = hashlib.sha256(payload).hexdigest()


def test_successor_formal_authority_constants_bind_exact_preflight_receipt() -> None:
    assert runner.SUCCESSOR_PREFLIGHT_COMMIT == (
        "6b6f2a5f6502bbc7a761e70cbb95d39ce38c7916"
    )
    assert runner.SUCCESSOR_PREFLIGHT_RECEIPT_SHA256 == (
        "d852c20feea13ee7e0c4fdcd6d75f490c144db4c0dd59386d28640251e5ff291"
    )
    assert runner.SUCCESSOR_PREFLIGHT_RECEIPT_FILE_SHA256 == (
        "2b679afe989f68f43ec72120e7b59a72250b25ad01b2fe31c3a25b20756ea6aa"
    )
    assert runner.SUCCESSOR_NAMESPACE_RELATIVE == Path(
        "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001"
    )
    assert (
        runner.SUCCESSOR_FINAL_NAMESPACE_RELATIVE == runner.SUCCESSOR_NAMESPACE_RELATIVE
    )


def test_successor_public_receipt_validation_accepts_false_flags_as_boundary(
    tmp_path: Path,
) -> None:
    _copy_public_receipt(tmp_path)
    receipt = runner.validate_successor_preflight_authority(tmp_path)
    assert receipt["preflight_state"] == "PREFLIGHT_READY"
    assert receipt["receipt_sha256"] == runner.SUCCESSOR_PREFLIGHT_RECEIPT_SHA256
    assert receipt["formal_candidate_generation_authorized"] is False
    assert receipt["commit_b_authorized"] is False
    assert receipt["formal_evaluation_authorized"] is False
    assert all(row["validation_result"] == "VALID" for row in receipt["role_results"])
    assert all(row["exit_code"] == 0 for row in receipt["role_results"])
    assert receipt["retry_count"] == 0
    assert receipt["fallback_used"] is False


@pytest.mark.parametrize("drift", ["file", "self_hash", "role"])
def test_successor_public_receipt_drift_is_rejected(tmp_path: Path, drift: str) -> None:
    _copy_public_receipt(tmp_path)
    path = tmp_path / preflight.PUBLIC_RECEIPT_PATH
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if drift == "file":
        path.write_bytes(path.read_bytes() + b"\n")
    elif drift == "self_hash":
        receipt["receipt_sha256"] = "0" * 64
        path.write_text(json.dumps(receipt), encoding="utf-8")
    else:
        receipt["role_results"][0]["validation_result"] = "INVALID_OUTPUT"
        document = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        receipt["receipt_sha256"] = preflight.canonical_sha256(document)
        path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt|preflight|role"):
        runner.validate_successor_preflight_authority(tmp_path)


def test_successor_commit_a_requires_direct_child_clean_exact_allowlist_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_public_receipt(tmp_path)
    commit_a = "a" * 40

    def fake_git(_repository: Path, *arguments: str) -> str:
        key = tuple(arguments)
        return {
            ("status", "--porcelain", "--untracked-files=all"): "",
            ("rev-parse", "HEAD"): commit_a,
            ("rev-list", "--parents", "-n", "1", commit_a): (
                f"{commit_a} {runner.SUCCESSOR_PREFLIGHT_COMMIT}"
            ),
            (
                "diff",
                "--name-only",
                "--no-renames",
                f"{runner.SUCCESSOR_PREFLIGHT_COMMIT}..{commit_a}",
            ): "\n".join(runner.SUCCESSOR_COMMIT_A_CHANGED_FILES),
        }[key]

    monkeypatch.setattr(runner, "_git", fake_git)
    state = runner.validate_successor_commit_a_repository(tmp_path)
    assert state["commit_a"] == commit_a
    assert state["parent"] == runner.SUCCESSOR_PREFLIGHT_COMMIT
    assert state["preflight_receipt_sha256"] == (
        runner.SUCCESSOR_PREFLIGHT_RECEIPT_SHA256
    )


@pytest.mark.parametrize("failure", ["old_a2", "dirty", "extra_file"])
def test_successor_commit_a_rejects_old_a2_bypass_or_boundary_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _copy_public_receipt(tmp_path)
    commit_a = "a" * 40
    parent = (
        runner.COMMIT_A2_PARENT
        if failure == "old_a2"
        else runner.SUCCESSOR_PREFLIGHT_COMMIT
    )
    changed = list(runner.SUCCESSOR_COMMIT_A_CHANGED_FILES)
    if failure == "extra_file":
        changed.append("artifacts/router-v2-blind-v2/preregistration.json")

    def fake_git(_repository: Path, *arguments: str) -> str:
        key = tuple(arguments)
        if key == ("status", "--porcelain", "--untracked-files=all"):
            return " M dirty.py" if failure == "dirty" else ""
        if key == ("rev-parse", "HEAD"):
            return commit_a
        if key == ("rev-list", "--parents", "-n", "1", commit_a):
            return f"{commit_a} {parent}"
        return "\n".join(changed)

    monkeypatch.setattr(runner, "_git", fake_git)
    with pytest.raises(ValueError, match="clean|parent|changed-file"):
        runner.validate_successor_commit_a_repository(tmp_path)


def test_successor_commit_b_is_direct_child_with_only_three_frozen_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit_a = "a" * 40
    commit_b = "b" * 40
    expected = sorted(
        (runner.DATASET_FREEZE_RELATIVE / filename).as_posix()
        for filename in runner.DATASET_FREEZE_FILENAMES
    )

    def fake_git(_repository: Path, *arguments: str) -> str:
        key = tuple(arguments)
        return {
            ("status", "--porcelain", "--untracked-files=all"): "",
            ("rev-parse", "HEAD"): commit_b,
            ("rev-list", "--parents", "-n", "1", commit_b): (f"{commit_b} {commit_a}"),
            ("rev-list", "--parents", "-n", "1", commit_a): (
                f"{commit_a} {runner.SUCCESSOR_PREFLIGHT_COMMIT}"
            ),
            (
                "diff",
                "--name-only",
                "--no-renames",
                f"{runner.SUCCESSOR_PREFLIGHT_COMMIT}..{commit_a}",
            ): "\n".join(runner.SUCCESSOR_COMMIT_A_CHANGED_FILES),
            ("rev-list", "--count", f"{commit_a}..{commit_b}"): "1",
            (
                "diff",
                "--name-only",
                "--no-renames",
                f"{commit_a}..{commit_b}",
            ): "\n".join(expected),
        }[key]

    monkeypatch.setattr(runner, "_git", fake_git)
    assert runner.validate_successor_commit_b_repository(
        tmp_path, commit_a=commit_a
    ) == {"commit_a": commit_a, "commit_b": commit_b, "changed_files": expected}


@pytest.mark.parametrize("drift", ["parent", "allowlist", "preflight_as_commit_a"])
def test_successor_commit_b_revalidates_commit_a_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    commit_a = (
        runner.SUCCESSOR_PREFLIGHT_COMMIT
        if drift == "preflight_as_commit_a"
        else "a" * 40
    )
    commit_b = "b" * 40
    data_files = sorted(
        (runner.DATASET_FREEZE_RELATIVE / filename).as_posix()
        for filename in runner.DATASET_FREEZE_FILENAMES
    )
    wrong_parent = "c" * 40
    adapter_files = list(runner.SUCCESSOR_COMMIT_A_CHANGED_FILES)
    if drift == "allowlist":
        adapter_files.append("artifacts/router-v2-blind-v2/preregistration.json")

    def fake_git(_repository: Path, *arguments: str) -> str:
        key = tuple(arguments)
        if key == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if key == ("rev-parse", "HEAD"):
            return commit_b
        if key == ("rev-list", "--parents", "-n", "1", commit_a):
            return (
                f"{commit_a} "
                f"{wrong_parent if drift == 'parent' else runner.SUCCESSOR_PREFLIGHT_COMMIT}"
            )
        if key == (
            "diff",
            "--name-only",
            "--no-renames",
            f"{runner.SUCCESSOR_PREFLIGHT_COMMIT}..{commit_a}",
        ):
            return "\n".join(adapter_files)
        if key == ("rev-list", "--parents", "-n", "1", commit_b):
            return f"{commit_b} {commit_a}"
        if key == ("rev-list", "--count", f"{commit_a}..{commit_b}"):
            return "1"
        return "\n".join(data_files)

    monkeypatch.setattr(runner, "_git", fake_git)
    with pytest.raises(ValueError, match="Commit A|parent|changed-file|preflight"):
        runner.validate_successor_commit_b_repository(tmp_path, commit_a=commit_a)


def test_successor_request_builders_use_exact_preflight_schemas_and_keep_legacy() -> (
    None
):
    legacy = runner._build_generator_request_payload(
        _skills(),
        gold_skill_id="test-skill-00",
        negative_quota=2,
        positive_only_quota=1,
    )
    successor = _successor_generator_request()
    reviewer = runner.build_reviewer_request(
        {
            "candidate_id": "a" * 24,
            "prompt_text": "Natural blind reviewer request",
            "proposed_gold_skill_id": "must-not-leak",
            "proposed_negative_skill_id": "must-not-leak",
            "rationale": "must-not-leak",
        },
        _skills(),
        role="reviewer_a",
        successor_output_schema=True,
    )
    assert legacy["response_schema"] == runner.GENERATOR_RESPONSE_SCHEMA
    assert successor["response_schema"] == preflight.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA
    assert reviewer["response_schema"] == preflight.SUCCESSOR_REVIEWER_RESPONSE_SCHEMA
    assert successor["model"] == preflight.ROLE_CONFIGS["generator"]["model"]
    assert (
        successor["reasoning_effort"]
        == (preflight.ROLE_CONFIGS["generator"]["reasoning_effort"])
    )
    serialized_reviewer_input = json.dumps(reviewer["input"], sort_keys=True)
    assert "proposed_gold_skill_id" not in serialized_reviewer_input
    assert "proposed_negative_skill_id" not in serialized_reviewer_input
    assert "rationale" not in serialized_reviewer_input


def test_successor_request_rejects_schema_drift_even_with_rehashed_request() -> None:
    request = _successor_generator_request()
    request["response_schema"] = deepcopy(preflight.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA)
    request["response_schema"]["properties"]["candidates"]["maxItems"] = 1
    request["request_sha256"] = runner._request_sha256(request)
    with pytest.raises(ValueError, match="response schema"):
        runner.validate_agent_request(request)


def test_reviewer_request_protocol_mode_is_coherent_in_both_directions() -> None:
    candidate = {
        "candidate_id": "a" * 24,
        "prompt_text": "Synthetic protocol-mode boundary request",
    }
    candidates = {candidate["candidate_id"]: candidate}
    for expected_successor_mode in (False, True):
        matching_request = runner.build_reviewer_request(
            candidate,
            _skills(),
            role="reviewer_a",
            successor_output_schema=expected_successor_mode,
        )
        row, candidate_id, request = runner._validated_reviewer_source_row(
            {
                "candidate_id": candidate["candidate_id"],
                "request": matching_request,
                "invocations": [],
            },
            role="reviewer_a",
            candidates=candidates,
            projected_skills=_skills(),
            review_candidate_ids={candidate["candidate_id"]},
            successor_protocol_mode=expected_successor_mode,
            label="coherent reviewer row",
        )
        assert row["request"] == matching_request
        assert candidate_id == candidate["candidate_id"]
        assert request == matching_request

        mixed_request = runner.build_reviewer_request(
            candidate,
            _skills(),
            role="reviewer_a",
            successor_output_schema=not expected_successor_mode,
        )
        with pytest.raises(ValueError, match="protocol mode"):
            runner._validated_reviewer_source_row(
                {
                    "candidate_id": candidate["candidate_id"],
                    "request": mixed_request,
                    "invocations": [],
                },
                role="reviewer_a",
                candidates=candidates,
                projected_skills=_skills(),
                review_candidate_ids={candidate["candidate_id"]},
                successor_protocol_mode=expected_successor_mode,
                label="mixed reviewer row",
            )


def test_formal_invocation_reuses_exact_host_transport_and_private_modes(
    tmp_path: Path,
) -> None:
    request = _successor_generator_request()
    fake = _FakeFormalHost(_generator_response())
    private_root = tmp_path / "formal-invocation"
    result = preflight.run_formal_agent_invocation(
        request=request,
        private_root=private_root,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=set(),
    )
    assert result["status"] == "VALID"
    assert len(fake.probes) == 1
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["role"] == "generator"
    assert call["argv"] == preflight._role_argv("generator", private_root)
    assert (
        call["timeout_seconds"] == runner.AGENT_CONFIGS["generator"]["timeout_seconds"]
    )
    assert "resume" not in call["argv"]
    assert "fork" not in call["argv"]
    assert "fallback" not in call["argv"]
    assert stat.S_IMODE(private_root.stat().st_mode) == 0o700
    for filename in (
        "response-schema.json",
        "prompt.txt",
        "events.jsonl",
        "response.json",
    ):
        path = private_root / filename
        assert path.is_file() and not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    schema = json.loads((private_root / "response-schema.json").read_text("utf-8"))
    assert schema == preflight.SUCCESSOR_GENERATOR_RESPONSE_SCHEMA
    envelope = result["invocation"]["envelope"]
    assert envelope["thread_id"] == "formal-thread-001"
    assert envelope["fork_context"] is False
    assert envelope["history_message_count"] == 0
    assert envelope["imported_memory_count"] == 0
    assert envelope["tool_call_count"] == 0
    assert envelope["descendant_agent_count"] == 0
    assert envelope["transport_retry_count"] == 0
    assert envelope["response"] == _generator_response()


def test_formal_reviewer_stdin_is_blind_and_uses_exact_successor_schema(
    tmp_path: Path,
) -> None:
    request = runner.build_reviewer_request(
        {
            "candidate_id": "a" * 24,
            "prompt_text": "Natural blind reviewer request",
            "proposed_gold_skill_id": "LEAK_GENERATOR_GOLD",
            "proposed_negative_skill_id": "LEAK_GENERATOR_NEGATIVE",
            "rationale": "LEAK_GENERATOR_RATIONALE",
            "generation_quota": "LEAK_QUOTA",
            "round_deficit": "LEAK_DEFICIT",
            "other_reviewer_response": "LEAK_OTHER_REVIEWER",
            "contamination_result": "LEAK_CONTAMINATION",
            "arm_a_result": "LEAK_ARM_A",
            "arm_c_result": "LEAK_ARM_C",
        },
        _skills(),
        role="reviewer_a",
        successor_output_schema=True,
    )
    fake = _FakeFormalHost(_reviewer_response())
    private_root = tmp_path / "formal-review"
    result = preflight.run_formal_agent_invocation(
        request=request,
        private_root=private_root,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=set(),
    )
    assert result["status"] == "VALID"
    stdin = fake.calls[0]["stdin"].decode("utf-8")
    assert runner.REVIEWER_SYSTEM_PROMPT in stdin
    assert runner.REVIEW_RUBRIC["natural"] in stdin
    assert "Natural blind reviewer request" in stdin
    for confidential_value in (
        "LEAK_QUOTA",
        "LEAK_DEFICIT",
        "LEAK_OTHER_REVIEWER",
        "LEAK_CONTAMINATION",
        "LEAK_ARM_A",
        "LEAK_ARM_C",
        "LEAK_GENERATOR_GOLD",
        "LEAK_GENERATOR_NEGATIVE",
        "LEAK_GENERATOR_RATIONALE",
    ):
        assert confidential_value not in stdin
    schema = json.loads((private_root / "response-schema.json").read_text("utf-8"))
    assert schema == preflight.SUCCESSOR_REVIEWER_RESPONSE_SCHEMA


def test_formal_substantive_failure_is_not_retried_or_fallbacked(
    tmp_path: Path,
) -> None:
    request = _successor_generator_request()
    fake = _FakeFormalHost(_generator_response(), response_override=b'{"wrong":true}')
    result = preflight.run_formal_agent_invocation(
        request=request,
        private_root=tmp_path / "invalid-formal",
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=set(),
    )
    assert result["status"] == "FORMAL_OUTPUT_BLOCKED"
    assert result["invocation"] is None
    assert len(fake.calls) == 1


def test_formal_duplicate_thread_and_existing_or_symlink_root_fail_closed(
    tmp_path: Path,
) -> None:
    request = _successor_generator_request()
    seen = {"formal-thread-001"}
    fake = _FakeFormalHost(_generator_response())
    duplicate = preflight.run_formal_agent_invocation(
        request=request,
        private_root=tmp_path / "duplicate-thread",
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=seen,
    )
    assert duplicate["status"] == "FORMAL_ISOLATION_BLOCKED"
    assert seen == {"formal-thread-001"}

    existing = tmp_path / "existing"
    existing.mkdir()
    calls_before = len(fake.calls)
    blocked = preflight.run_formal_agent_invocation(
        request=request,
        private_root=existing,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=set(),
    )
    assert blocked["status"] == "FORMAL_EVIDENCE_BLOCKED"
    assert len(fake.calls) == calls_before

    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    blocked = preflight.run_formal_agent_invocation(
        request=request,
        private_root=linked,
        repository_root=ROOT,
        host_probe=fake.probe,
        launcher=fake.launch,
        seen_thread_ids=set(),
    )
    assert blocked["status"] == "FORMAL_EVIDENCE_BLOCKED"
    assert len(fake.calls) == calls_before


def test_public_receipt_fixture_hash_is_exact() -> None:
    assert hashlib.sha256(PUBLIC_RECEIPT.read_bytes()).hexdigest() == (
        "2b679afe989f68f43ec72120e7b59a72250b25ad01b2fe31c3a25b20756ea6aa"
    )


def test_private_checkpoint_rewrite_is_atomic_durable_and_mode_0600(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    target = root / "blind-v2-generation.jsonl"
    preflight._write_private_file(target, b"old-checkpoint\n")
    original_inode = target.stat().st_ino
    replacements: list[tuple[object, ...]] = []
    real_replace = preflight.os.replace

    def replace(
        source: Any,
        destination: Any,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        replacements.append(
            (source, destination, {"src_dir_fd": src_dir_fd, "dst_dir_fd": dst_dir_fd})
        )
        real_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(preflight.os, "replace", replace)
    preflight._write_private_file(target, b"new-checkpoint\n")
    assert target.read_bytes() == b"new-checkpoint\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.stat().st_ino != original_inode
    assert len(replacements) == 1
    assert list(root.iterdir()) == [target]

    preflight._write_private_file(target, b"new-checkpoint\n")
    assert target.read_bytes() == b"new-checkpoint\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert len(replacements) == 2
    assert list(root.iterdir()) == [target]


def test_private_checkpoint_failed_rewrite_preserves_old_bytes_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    target = root / "blind-v2-review-a.jsonl"
    preflight._write_private_file(target, b"sealed-old-checkpoint\n")
    real_write = preflight.os.write
    write_count = 0

    def fail_after_partial_write(
        descriptor: int, payload: bytes | bytearray | memoryview
    ) -> int:
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            return real_write(descriptor, memoryview(payload)[:4])
        raise OSError("simulated checkpoint write failure")

    monkeypatch.setattr(preflight.os, "write", fail_after_partial_write)
    with pytest.raises(OSError, match="simulated checkpoint write failure"):
        preflight._write_private_file(target, b"replacement-checkpoint\n")
    assert target.read_bytes() == b"sealed-old-checkpoint\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert list(root.iterdir()) == [target]


def test_private_checkpoint_atomic_rewrite_still_rejects_symlink_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(b"outside-sealed\n")
    target = root / "blind-v2-review-b.jsonl"
    target.symlink_to(outside)
    with pytest.raises((OSError, ValueError), match="symlink|follow|loop"):
        preflight._write_private_file(target, b"must-not-replace\n")
    assert target.is_symlink()
    assert outside.read_bytes() == b"outside-sealed\n"

    outside_root = tmp_path / "outside-root"
    outside_parent = outside_root / "nested"
    outside_parent.mkdir(parents=True)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(outside_root, target_is_directory=True)
    escaped_target = linked_root / "nested/blind-v2-contamination.jsonl"
    with pytest.raises(ValueError, match="symlink"):
        preflight._write_private_file(escaped_target, b"must-remain-confined\n")
    assert not (outside_parent / escaped_target.name).exists()


def test_run_agent_construction_is_partial_safe_and_never_retries(
    tmp_path: Path,
) -> None:
    commit_a = "a" * 40
    staging_root = tmp_path / commit_a
    fake = _FakeConstructionRunner(fail_at=3)
    result = formal_cli.run_successor_agent_construction(
        _successor_context(staging_root),
        invocation_runner=fake,
        contamination_scanner=_all_clean_scan,
        generator_request_builder=_test_generator_builder,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=1,
    )
    assert result["status"] == "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"
    assert result["failure_stage"] == "round-1-generation"
    assert len(fake.calls) == 3
    assert all(call["request"]["role"] == "generator" for call in fake.calls)
    generation_rows = formal_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    assert len(generation_rows) == 3
    assert generation_rows[-1]["invocations"] == []
    for filename in runner.REQUIRED_AGENT_PACK_FILES:
        path = staging_root / filename
        assert path.is_file() and not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(staging_root.stat().st_mode) == 0o700


def test_contaminated_candidates_are_still_dual_reviewed_but_never_accepted(
    tmp_path: Path,
) -> None:
    commit_a = "f" * 40
    staging_root = tmp_path / commit_a
    fake = _FakeConstructionRunner()
    result = formal_cli.run_successor_agent_construction(
        _successor_context(staging_root),
        invocation_runner=fake,
        contamination_scanner=_all_contaminated_scan,
        generator_request_builder=_test_generator_builder,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
    )
    assert result["status"] == "AGENT_BLIND_V2_DATASET_INSUFFICIENT"
    assert result["reviewed_candidate_count"] == 512
    assert result["final_deficits"]
    review_candidate_ids = {
        role: [
            row["candidate_id"] for row in formal_cli._jsonl(staging_root / filename)
        ]
        for role, filename in (
            ("reviewer_a", "blind-v2-review-a.jsonl"),
            ("reviewer_b", "blind-v2-review-b.jsonl"),
        )
    }
    assert len(review_candidate_ids["reviewer_a"]) == 512
    assert len(review_candidate_ids["reviewer_b"]) == 512
    assert set(review_candidate_ids["reviewer_a"]) == set(
        review_candidate_ids["reviewer_b"]
    )
    reviewer_calls = [
        call
        for call in fake.calls
        if call["request"]["role"] in {"reviewer_a", "reviewer_b"}
    ]
    assert len(reviewer_calls) == 1024


def test_run_agent_construction_round_two_is_deficit_only_and_never_rereviews(
    tmp_path: Path,
) -> None:
    commit_a = "b" * 40
    staging_root = tmp_path / commit_a
    fake = _FakeConstructionRunner()
    result = formal_cli.run_successor_agent_construction(
        _successor_context(staging_root),
        invocation_runner=fake,
        contamination_scanner=_all_clean_scan,
        generator_request_builder=_test_generator_builder,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
    )
    assert result["status"] == "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE", result
    assert result["round_1_candidate_count"] == 256
    assert result["round_2_candidate_count"] == 2
    assert result["final_deficits"] == {}

    generation_rows = formal_cli._jsonl(staging_root / "blind-v2-generation.jsonl")
    round_two = [row for row in generation_rows if row["generation_round"] == 2]
    assert len(round_two) == 1
    quota = round_two[0]["request"]["input"]["quota"]
    assert quota == {
        "gold_skill_id": "test-skill-00",
        "negative_quota": 2,
        "positive_only_quota": 0,
        "round_number": 2,
    }

    review_rows = {
        role: formal_cli._jsonl(staging_root / filename)
        for role, filename in (
            ("reviewer_a", "blind-v2-review-a.jsonl"),
            ("reviewer_b", "blind-v2-review-b.jsonl"),
        )
    }
    for role, rows in review_rows.items():
        candidate_ids = [row["candidate_id"] for row in rows]
        assert len(candidate_ids) == 258
        assert len(candidate_ids) == len(set(candidate_ids))
        assert candidate_ids == sorted(
            candidate_ids,
            key=lambda value: runner.review_schedule_key(role, value),
        )
    reviewed_requests = [
        call["request"]
        for call in fake.calls
        if call["request"]["role"] in {"reviewer_a", "reviewer_b"}
    ]
    reviewed_task_ids = [request["input"]["task_id"] for request in reviewed_requests]
    assert len(reviewed_task_ids) == 516
    assert all(
        reviewed_task_ids.count(candidate_id) == 2
        for candidate_id in set(reviewed_task_ids)
    )

    metadata = formal_cli._json(staging_root / "agent-run-metadata.json")
    for filename in runner.REQUIRED_AGENT_PACK_FILES[:-1]:
        payload = (staging_root / filename).read_bytes()
        assert (
            metadata["source_file_sha256"][filename]
            == hashlib.sha256(payload).hexdigest()
        )
    assert metadata["review_schedule_sha256"] == {
        role: runner.canonical_sha256(
            [row["candidate_id"] for row in review_rows[role]]
        )
        for role in ("reviewer_a", "reviewer_b")
    }
    all_threads = [
        thread_id
        for role in runner.AGENT_CONFIGS
        for thread_id in metadata["roles"][role]["session_or_thread_ids"]
    ]
    assert len(all_threads) == len(set(all_threads)) == 533
    assert all(
        metadata["roles"][role]["tool_call_count"] == 0
        and metadata["roles"][role]["descendant_agent_count"] == 0
        and metadata["roles"][role]["lineage_observed"] is True
        for role in runner.AGENT_CONFIGS
    )


def test_successor_staging_root_and_namespace_fail_closed(tmp_path: Path) -> None:
    commit_a = "c" * 40
    existing = tmp_path / commit_a
    existing.mkdir()
    with pytest.raises(ValueError, match="new|exist"):
        formal_cli.run_successor_agent_construction(
            _successor_context(existing),
            invocation_runner=_FakeConstructionRunner(),
            contamination_scanner=_all_clean_scan,
            generator_request_builder=_test_generator_builder,
            first_read_timestamp="2026-07-21T00:00:00Z",
        )

    linked_target = tmp_path / "linked-target"
    linked_target.mkdir()
    linked = tmp_path / ("d" * 40)
    linked.symlink_to(linked_target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink|new"):
        formal_cli.run_successor_agent_construction(
            _successor_context(linked),
            invocation_runner=_FakeConstructionRunner(),
            contamination_scanner=_all_clean_scan,
            generator_request_builder=_test_generator_builder,
            first_read_timestamp="2026-07-21T00:00:00Z",
        )

    repository = ROOT.resolve()
    assert (
        runner._assert_output_safe(
            repository / runner.SUCCESSOR_FINAL_NAMESPACE_RELATIVE,
            repository,
            [],
            expected_namespace=runner.SUCCESSOR_FINAL_NAMESPACE_RELATIVE,
        )
        == repository / runner.SUCCESSOR_FINAL_NAMESPACE_RELATIVE
    )
    with pytest.raises(ValueError, match="canonical namespace"):
        runner._assert_output_safe(
            repository / runner.FINAL_NAMESPACE_RELATIVE,
            repository,
            [],
            expected_namespace=runner.SUCCESSOR_FINAL_NAMESPACE_RELATIVE,
        )


def test_cli_exposes_bounded_successor_construction_command() -> None:
    args = formal_cli._parser().parse_args(
        ["run-agent-construction", "--max-workers", "4"]
    )
    assert args.max_workers == 4


def test_first_read_timestamp_is_captured_before_successor_context_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FrozenDateTime:
        @classmethod
        def now(cls, timezone: object) -> real_datetime:
            assert timezone is UTC
            events.append("timestamp")
            return real_datetime(2026, 7, 21, tzinfo=UTC)

    def context() -> dict[str, Any]:
        events.append("context-read")
        return {"commit_a": "a" * 40}

    def construct(
        active_context: dict[str, Any],
        *,
        invocation_runner: object,
        generator_request_builder: object,
        first_read_timestamp: str,
        max_workers: int,
    ) -> dict[str, Any]:
        assert active_context == {"commit_a": "a" * 40}
        assert callable(invocation_runner)
        assert generator_request_builder is formal_cli.workflow.build_generator_request
        assert first_read_timestamp == "2026-07-21T00:00:00Z"
        assert max_workers == 1
        return {"status": "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE"}

    monkeypatch.setattr(formal_cli, "datetime", FrozenDateTime)
    monkeypatch.setattr(formal_cli, "_successor_commit_a_context", context)
    monkeypatch.setattr(formal_cli, "run_successor_agent_construction", construct)
    assert (
        formal_cli._run_agent_construction(formal_cli.argparse.Namespace(max_workers=1))
        == 0
    )
    assert events == ["timestamp", "context-read"]


def test_run_agent_construction_maps_receipt_drift_before_host_to_infrastructure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    host_calls: list[dict[str, Any]] = []

    def drifted_context() -> dict[str, Any]:
        raise ValueError("successor preflight receipt bytes drifted")

    def host(**kwargs: Any) -> dict[str, Any]:
        host_calls.append(kwargs)
        raise AssertionError("host must not be called")

    monkeypatch.setattr(formal_cli, "_successor_commit_a_context", drifted_context)
    monkeypatch.setattr(formal_cli.formal, "run_formal_agent_invocation", host)
    assert (
        formal_cli._run_agent_construction(formal_cli.argparse.Namespace(max_workers=1))
        == 2
    )
    terminal = json.loads(capsys.readouterr().out)
    assert terminal["status"] == "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"
    assert terminal["failure_stage"] == "pre-data-setup"
    assert terminal["invocation_count"] == 0
    assert terminal["retry_count"] == 0
    assert terminal["fallback_used"] is False
    assert host_calls == []


@pytest.mark.parametrize(
    "failure_point",
    ("canonical-skills", "staging-root", "first-generator-request"),
)
def test_run_agent_construction_maps_all_pre_host_setup_failures_to_infrastructure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_point: str,
) -> None:
    staging_root = tmp_path / ("a" * 40)
    context = _successor_context(staging_root)
    if failure_point == "canonical-skills":
        context["canonical_skills"][0].pop("id")
    elif failure_point == "staging-root":
        staging_root.mkdir()

    host_calls: list[dict[str, Any]] = []

    def host(**kwargs: Any) -> dict[str, Any]:
        host_calls.append(kwargs)
        raise AssertionError("host must not be called")

    def request_builder(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        raise ValueError("first generator request validation failed")

    monkeypatch.setattr(formal_cli, "_successor_commit_a_context", lambda: context)
    monkeypatch.setattr(formal_cli.formal, "run_formal_agent_invocation", host)
    if failure_point == "first-generator-request":
        monkeypatch.setattr(
            formal_cli.workflow, "build_generator_request", request_builder
        )

    assert (
        formal_cli._run_agent_construction(formal_cli.argparse.Namespace(max_workers=1))
        == 2
    )
    terminal = json.loads(capsys.readouterr().out)
    assert terminal["status"] == "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"
    assert terminal["failure_stage"] == "pre-data-setup"
    assert terminal["invocation_count"] == 0
    assert terminal["retry_count"] == 0
    assert terminal["fallback_used"] is False
    assert host_calls == []


@pytest.mark.parametrize("signal", (KeyboardInterrupt, SystemExit))
def test_run_agent_construction_does_not_swallow_process_control_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    signal: type[BaseException],
) -> None:
    def interrupted_context() -> dict[str, Any]:
        raise signal()

    monkeypatch.setattr(formal_cli, "_successor_commit_a_context", interrupted_context)
    with pytest.raises(signal):
        formal_cli._run_agent_construction(formal_cli.argparse.Namespace(max_workers=1))


def test_successor_constructed_pack_reuses_existing_validation_pipeline(
    tmp_path: Path,
) -> None:
    commit_a = "e" * 40
    staging_root = tmp_path / commit_a
    preregistration_path = ROOT / runner.PREREGISTRATION_RELATIVE
    inputs = formal_cli._load_preregistered_agent_inputs(
        preregistration_path,
        repository_root=ROOT,
    )
    context = {
        **inputs,
        "repository": ROOT,
        "commit_a": commit_a,
        "staging_root": staging_root,
        "successor_authority": True,
    }
    semantic_files = [{"path": "synthetic/model.bin", "sha256": "f" * 64}]
    semantic_authority = {
        "materialized_model_files": semantic_files,
        "materialized_model_files_sha256": runner.canonical_sha256(semantic_files),
    }

    def scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return runner._scan_contamination(
            candidates,
            protected_prompts={
                "train": inputs["train_prompts"],
                "pilot-002": inputs["pilot_prompts"],
                "phase16": inputs["phase16_prompts"],
                "prior_candidate": inputs["prior_candidate_prompts"],
            },
            protected_family_ids={
                "train": inputs["train_family_ids"],
                "pilot-002": inputs["pilot_family_ids"],
                "phase16": inputs["phase16_family_ids"],
                "prior_candidate": inputs["prior_candidate_family_ids"],
            },
            semantic_similarity=lambda _left, _right: 0.0,
            semantic_model_authority=semantic_authority,
        )

    result = formal_cli.run_successor_agent_construction(
        context,
        invocation_runner=_FakeConstructionRunner(),
        contamination_scanner=scan,
        generator_request_builder=_test_generator_builder,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
    )
    assert result["status"] == "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE", result
    validation = runner.validate_agent_pack(
        staging_root,
        repository_root=ROOT,
        canonical_skills=inputs["canonical_skills"],
        train_prompts=inputs["train_prompts"],
        pilot_prompts=inputs["pilot_prompts"],
        phase16_prompts=inputs["phase16_prompts"],
        train_family_ids=inputs["train_family_ids"],
        pilot_family_ids=inputs["pilot_family_ids"],
        phase16_family_ids=inputs["phase16_family_ids"],
        prior_candidate_prompts=inputs["prior_candidate_prompts"],
        prior_candidate_family_ids=inputs["prior_candidate_family_ids"],
        first_read_timestamp="2026-07-21T00:00:00Z",
        semantic_similarity=lambda _left, _right: 0.0,
        semantic_model_authority=semantic_authority,
        construction_input_bindings=inputs["construction_input_bindings"],
    )
    assert validation["status"] == "VALID"
    assert validation["task_count"] == 128
    assert validation["negative_labeled_task_count"] == 96
    assert validation["model_scores_observed"] is False


def test_successor_pack_rejects_historical_reviewer_schema_in_live_and_frozen_sources(
    tmp_path: Path,
) -> None:
    commit_a = "9" * 40
    staging_root = tmp_path / commit_a
    preregistration_path = ROOT / runner.PREREGISTRATION_RELATIVE
    inputs = formal_cli._load_preregistered_agent_inputs(
        preregistration_path,
        repository_root=ROOT,
    )
    context = {
        **inputs,
        "repository": ROOT,
        "commit_a": commit_a,
        "staging_root": staging_root,
        "successor_authority": True,
    }
    semantic_files = [{"path": "synthetic/model.bin", "sha256": "f" * 64}]
    semantic_authority = {
        "materialized_model_files": semantic_files,
        "materialized_model_files_sha256": runner.canonical_sha256(semantic_files),
    }

    def scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return runner._scan_contamination(
            candidates,
            protected_prompts={
                "train": inputs["train_prompts"],
                "pilot-002": inputs["pilot_prompts"],
                "phase16": inputs["phase16_prompts"],
                "prior_candidate": inputs["prior_candidate_prompts"],
            },
            protected_family_ids={
                "train": inputs["train_family_ids"],
                "pilot-002": inputs["pilot_family_ids"],
                "phase16": inputs["phase16_family_ids"],
                "prior_candidate": inputs["prior_candidate_family_ids"],
            },
            semantic_similarity=lambda _left, _right: 0.0,
            semantic_model_authority=semantic_authority,
        )

    result = formal_cli.run_successor_agent_construction(
        context,
        invocation_runner=_FakeConstructionRunner(),
        contamination_scanner=scan,
        generator_request_builder=_test_generator_builder,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
    )
    assert result["status"] == "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE", result
    validation_kwargs = {
        "repository_root": ROOT,
        "canonical_skills": inputs["canonical_skills"],
        "train_prompts": inputs["train_prompts"],
        "pilot_prompts": inputs["pilot_prompts"],
        "phase16_prompts": inputs["phase16_prompts"],
        "train_family_ids": inputs["train_family_ids"],
        "pilot_family_ids": inputs["pilot_family_ids"],
        "phase16_family_ids": inputs["phase16_family_ids"],
        "prior_candidate_prompts": inputs["prior_candidate_prompts"],
        "prior_candidate_family_ids": inputs["prior_candidate_family_ids"],
        "first_read_timestamp": "2026-07-21T00:00:00Z",
        "semantic_similarity": lambda _left, _right: 0.0,
        "semantic_model_authority": semantic_authority,
        "construction_input_bindings": inputs["construction_input_bindings"],
    }
    valid = runner.validate_agent_pack(staging_root, **validation_kwargs)
    assert valid["status"] == "VALID"
    original_payloads = {
        filename: (staging_root / filename).read_bytes()
        for filename in runner.REQUIRED_AGENT_PACK_FILES
    }

    for role in ("reviewer_a", "reviewer_b"):
        for filename, payload in original_payloads.items():
            preflight._write_private_file(staging_root / filename, payload)
        frozen_validation = deepcopy(valid)
        _rewrite_first_review_request_as_historical(
            staging_root,
            role=role,
            canonical_skills=inputs["canonical_skills"],
        )
        mixed = runner.validate_agent_pack(staging_root, **validation_kwargs)
        assert mixed["status"] == "INVALID"
        assert mixed["research_conclusion"] == "AGENT_BLIND_V2_PROTOCOL_INVALID"
        assert mixed["failure_stage"] == "reviewer_request"
        assert "protocol mode" in mixed["failure_reason"]

        _rebind_validation_source_files(frozen_validation, staging_root)
        with pytest.raises(ValueError) as exc_info:
            runner._validated_agent_source_ledger_evidence(
                frozen_validation,
                semantic_similarity=lambda _left, _right: 0.0,
            )
        assert exc_info.value.__cause__ is not None
        assert "protocol mode" in str(exc_info.value.__cause__)
