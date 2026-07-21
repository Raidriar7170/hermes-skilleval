from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import threading
from argparse import Namespace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation_runner as runner
from hermes_skilleval import router_v2_blind_v2_output_schema_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]
RUN003_MODULE = "hermes_skilleval.router_v2_blind_v2_run003"
CURRENT_COMMIT = "8a34995f85954777b1130c4be8c94a2e5e3e950b"
FUTURE_COMMIT = "b" * 40
RUN001_TERMINAL_SHA256 = (
    "74b8e9fb01e008ee40c1f38c65c73a9fde371c615e4689f847ab88887cefa6ea"
)
RUN002_EVIDENCE_SHA256 = {
    "run002-authority-manifest.json": (
        "936877c62c452370906c693be4d92abad23e99bdb24b4c7cd86397ddc3435a32"
    ),
    "generator-canary/prompt.txt": (
        "5fc04bf46e83e5dc9549879728f31d453d6590d031738b1a39b5ef21ffa276ab"
    ),
    "generator-canary/response-schema.json": (
        "ef75d30acaeec87bbe1b300ff10b59f599a60c40dc3cddb51e3f7129dfc1bf3a"
    ),
    "generator-canary/events.jsonl": (
        "a1d17f4e174ff8082b485d0d97f5e183036114a6feebdd697255296f0d2841e3"
    ),
    "generator-canary/response.json": (
        "65bab0ff3805bcac82d9102bbcb4ebefe1f8f7115c2a2803cdba8d3fd07cfbe6"
    ),
}
RUN002_EVIDENCE_ROOT = Path(
    "/Users/raidriar/.codex/private/hermes-blind-v2-successor-run002/"
    "router-v2-v4-successor-blind-v2-002/"
    "4b1e1221ac548a4a0b465c2fbe47833c16e358b0"
)


def _run003() -> ModuleType:
    assert importlib.util.find_spec(RUN003_MODULE) is not None, (
        "explicit Run003 authority module is missing"
    )
    return importlib.import_module(RUN003_MODULE)


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run003_final_cli", ROOT / "scripts/run_router_v2_blind_v2_final.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index in range(128):
        gold_index = index // 8
        prompt = f"Natural Run003 synthetic freeze task {index:03d}"
        tasks.append(
            {
                "candidate_id": hashlib.sha256(prompt.encode()).hexdigest()[:24],
                "prompt_text": prompt,
                "prompt_text_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "semantic_family_id": f"run003-family-{index:03d}",
                "proposed_gold_skill_id": f"test-skill-{gold_index:02d}",
                "proposed_negative_skill_id": (
                    f"test-skill-{(gold_index + 1) % 16:02d}" if index % 8 < 6 else None
                ),
            }
        )
    return tasks


def _validation() -> dict[str, Any]:
    return {
        "status": "VALID",
        "run_id": "router-v2-v4-successor-blind-v2-003",
        "tasks": _tasks(),
        "candidate_generation_count": 256,
        "candidate_import_rejection_count": 0,
        "accepted_candidate_count": 128,
        "rejected_candidate_count": 128,
        "review_request_count": 512,
        "reviewer_valid_count": 512,
        "reviewer_unanimous_agreement_count": 128,
        "supplement_request_count": 0,
        "duplicate_and_contamination_checks_passed": True,
        "contamination_checked_candidate_count": 256,
        "transport_diagnostic_count": 7,
        "transport_diagnostic_types": [
            "TEMPORARY_TLS_DISCONNECT",
            "TEMPORARY_TRANSPORT_TIMEOUT",
        ],
        "transport_diagnostics_observed": True,
        "event_policy_version": preflight.RUN003_EVENT_POLICY_VERSION,
        "agent_configs": cast(dict[str, Any], _run003().AGENT_CONFIGS),
        "system_prompt_sha256": {
            "generator": "1" * 64,
            "reviewer_a": "2" * 64,
            "reviewer_b": "2" * 64,
        },
        "response_schema_sha256": {
            "generator": "3" * 64,
            "reviewer_a": "4" * 64,
            "reviewer_b": "4" * 64,
        },
        "agent_config_sha256": {
            "generator": "5" * 64,
            "reviewer_a": "6" * 64,
            "reviewer_b": "7" * 64,
        },
        "authority_manifest_sha256": "8" * 64,
        "retry_records": [],
        "agent_run_evidence": [],
        "deterministic_selection_authority": {"selection_seed": 7170},
        "source_skill_index_sha256": "9" * 64,
        "source_file_sha256": {
            "blind-v2-generation.jsonl": "a" * 64,
            "blind-v2-review-a.jsonl": "b" * 64,
            "blind-v2-review-b.jsonl": "c" * 64,
            "blind-v2-contamination.jsonl": "d" * 64,
            "agent-run-metadata.json": "e" * 64,
            "run003-authority-manifest.json": "f" * 64,
        },
        "candidate_outcomes": {"ACCEPTED": 128, "REJECTED": 128},
    }


class _FakeRun003ConstructionRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_ordinal = 1
        self._candidate_labels: dict[str, tuple[str, str | None]] = {}

    def __call__(
        self,
        *,
        request: dict[str, Any],
        private_root: Path,
        repository_root: Path,
        seen_thread_ids: set[str] | None = None,
        event_policy_version: str | None = None,
    ) -> dict[str, Any]:
        del repository_root, seen_thread_ids
        module = _run003()
        assert event_policy_version == module.EVENT_POLICY_VERSION
        with self._lock:
            ordinal = self._next_ordinal
            self._next_ordinal += 1
        private_root.mkdir(mode=0o700)
        role = cast(str, request["role"])
        if role == "generator":
            quota = cast(dict[str, Any], request["input"]["quota"])
            gold = cast(str, quota["gold_skill_id"])
            negative = next(
                cast(str, skill["id"])
                for skill in cast(
                    list[dict[str, Any]], request["input"]["canonical_skills"]
                )
                if skill["id"] != gold
            )
            candidates = []
            for position in range(
                cast(int, quota["negative_quota"])
                + cast(int, quota["positive_only_quota"])
            ):
                prompt = (
                    f"Run003 fake-core prompt {quota['round_number']} {gold} "
                    f"{position:02d} {request['request_sha256'][:16]}"
                )
                candidate = {
                    "prompt_text": prompt,
                    "semantic_family_id": (
                        f"run003-family-{quota['round_number']}-{gold}-{position:02d}"
                    ),
                    "proposed_gold_skill_id": gold,
                    "proposed_negative_skill_id": (
                        negative if position < quota["negative_quota"] else None
                    ),
                    "language": "en",
                    "rationale": "Synthetic fake-only integration evidence.",
                }
                candidates.append(candidate)
                candidate_id = module.run002.host_candidate_id(
                    run_id=module.RUN_ID,
                    request_id=cast(str, request["request_sha256"]),
                    position=position,
                    prompt_text=prompt,
                )
                with self._lock:
                    self._candidate_labels[candidate_id] = (
                        gold,
                        cast(str | None, candidate["proposed_negative_skill_id"]),
                    )
            response: dict[str, Any] = {"candidates": candidates}
        else:
            candidate_id = cast(str, request["input"]["task_id"])
            with self._lock:
                reviewed_gold, reviewed_negative = self._candidate_labels[candidate_id]
            response = {
                "decision": "ACCEPT",
                "reviewed_gold_skill_id": reviewed_gold,
                "reviewed_negative_skill_id": reviewed_negative,
                "natural": True,
                "single_primary_skill": True,
                "no_label_leakage": True,
                "negative_confusable": (
                    True if reviewed_negative is not None else None
                ),
                "confidence": "HIGH",
                "reason": "Synthetic fake-only integration acceptance.",
            }
        diagnostic_types = ["TEMPORARY_TRANSPORT_TIMEOUT"] if ordinal == 1 else []
        envelope = {
            "role": role,
            "thread_id": f"run003-fake-thread-{ordinal:04d}",
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
            "event_policy_version": module.EVENT_POLICY_VERSION,
            "transport_diagnostic_count": len(diagnostic_types),
            "transport_diagnostic_types": diagnostic_types,
            "transport_diagnostics_observed": bool(diagnostic_types),
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


def _all_clean_scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": [
            {"candidate_id": candidate["candidate_id"], "decision": "ACCEPT"}
            for candidate in candidates
        ],
        "clean_candidate_ids": [candidate["candidate_id"] for candidate in candidates],
    }


def test_run003_authority_is_separate_and_binds_real_predecessor_bundle() -> None:
    module = _run003()

    assert module.RUN_ID == "router-v2-v4-successor-blind-v2-003"
    assert module.REPLACEMENT_REASON == (
        "ALLOW_VALIDATED_TRANSIENT_TRANSPORT_DIAGNOSTICS"
    )
    assert module.OUTPUT_NAMESPACE == Path(
        "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-003"
    )
    assert module.DATASET_FREEZE_RELATIVE == Path(
        "data/router-v2-blind-v2-successor-003"
    )
    assert module.EVENT_POLICY_VERSION == preflight.RUN003_EVENT_POLICY_VERSION
    assert module.RUN002_TERMINAL_EVIDENCE_BUNDLE == {
        "schema_version": "router-v2-run002-terminal-evidence-bundle-v1",
        "run_id": "router-v2-v4-successor-blind-v2-002",
        "git_commit": CURRENT_COMMIT,
        "standalone_terminal_json_present": False,
        "authority_manifest_sha256": RUN002_EVIDENCE_SHA256[
            "run002-authority-manifest.json"
        ],
        "generator_canary_prompt_sha256": RUN002_EVIDENCE_SHA256[
            "generator-canary/prompt.txt"
        ],
        "generator_canary_response_schema_sha256": RUN002_EVIDENCE_SHA256[
            "generator-canary/response-schema.json"
        ],
        "generator_canary_events_sha256": RUN002_EVIDENCE_SHA256[
            "generator-canary/events.jsonl"
        ],
        "generator_canary_response_sha256": RUN002_EVIDENCE_SHA256[
            "generator-canary/response.json"
        ],
    }
    assert module.RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256 == (
        "ca1c9c4b6b908d62442dd64f2a9b1b9891182662a29e1824c91c15b7416971b5"
    )
    root = module.private_evidence_root(FUTURE_COMMIT)
    assert "run003" in str(root)
    assert "run002" not in str(root)

    manifest = module.build_authority_manifest(
        commit_a=FUTURE_COMMIT,
        current_git_commit=FUTURE_COMMIT,
        commit_a_parent_git_commits=[CURRENT_COMMIT],
        private_evidence_root=root,
    )
    assert manifest["current_git_commit"] == FUTURE_COMMIT
    assert manifest["commit_a_parent_git_commits"] == [CURRENT_COMMIT]
    assert manifest["run001_terminal_sha256"] == RUN001_TERMINAL_SHA256
    assert manifest["run002_terminal_evidence_bundle_sha256"] == (
        module.RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256
    )
    assert manifest["run001_candidates_reused"] is False
    assert manifest["run002_candidates_reused"] is False
    assert manifest["run001_model_scores_observed"] is False
    assert manifest["run002_model_scores_observed"] is False
    assert manifest["model_scores_observed"] is False
    assert manifest["router_decision"] == "KEEP_BASELINE"


def test_run003_generator_canary_remains_synthetic_and_host_assigns_identity() -> None:
    module = _run003()
    request = module.build_generator_canary_request()

    assert request["schema_version"] == "router-v2-run003-generation-request-v1"
    assert request["input"]["run_id"] == module.RUN_ID
    assert request["input"]["synthetic_canary"] is True
    assert request["input"]["formal_data"] is False
    assert request["response_schema"] == module.GENERATOR_RESPONSE_SCHEMA
    assert set(
        request["response_schema"]["properties"]["candidates"]["items"]["properties"]
    ) == {
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }

    result = module.run_generator_canary(module.synthetic_canary_response())
    assert result["status"] == "RUN003_GENERATOR_CANARY_PASSED"
    assert result["candidate_count"] == 16
    assert result["candidate_indexes"] == list(range(16))
    assert len(result["candidate_ids"]) == len(set(result["candidate_ids"])) == 16
    assert all(len(value) == 24 for value in result["candidate_ids"])
    assert result["formal_data_written"] is False
    assert result["router_loaded"] is False


def test_run003_formal_request_uses_explicit_authority_not_schema_equality() -> None:
    module = _run003()
    request = module.build_formal_generator_request(
        _skills(),
        commit_a=CURRENT_COMMIT,
        gold_skill_id="test-skill-00",
        negative_quota=12,
        positive_only_quota=4,
        round_number=1,
    )

    assert request["schema_version"] == "router-v2-run003-generation-request-v1"
    assert request["authority"]["run_id"] == module.RUN_ID
    assert request["authority"]["event_policy_version"] == module.EVENT_POLICY_VERSION
    assert request["input"]["run_id"] == module.RUN_ID
    assert runner.validate_agent_request(request) == request


def test_run003_freeze_manifest_includes_diagnostic_and_truth_contract() -> None:
    module = _run003()
    documents = module.build_dataset_freeze_documents(
        _validation(), commit_a=CURRENT_COMMIT
    )

    assert set(documents) == set(module.DATASET_FREEZE_FILENAMES)
    manifest = json.loads(documents["blind-v2-manifest.json"])
    review = json.loads(documents["blind-v2-review-summary.json"])
    assert manifest["task_count"] == 128
    assert manifest["negative_labeled_task_count"] == 96
    assert manifest["skill_count"] == 16
    assert manifest["tasks_per_skill"] == 8
    assert manifest["negative_per_skill"] == 6
    assert manifest["positive_only_per_skill"] == 2
    assert manifest["semantic_family_count"] == 128
    assert manifest["transport_diagnostic_count"] == 7
    assert manifest["transport_diagnostic_types"] == [
        "TEMPORARY_TLS_DISCONNECT",
        "TEMPORARY_TRANSPORT_TIMEOUT",
    ]
    assert manifest["transport_diagnostics_observed"] is True
    assert manifest["event_policy_version"] == module.EVENT_POLICY_VERSION
    assert manifest["source_type"] == "AGENT_GENERATED"
    assert manifest["review_mode"] == "DUAL_AGENT_UNANIMOUS_REVIEWED"
    assert manifest["human_author_count"] == 0
    assert manifest["human_reviewer_count"] == 0
    assert manifest["run001_model_scores_observed"] is False
    assert manifest["run002_model_scores_observed"] is False
    assert manifest["model_scores_observed"] is False
    assert manifest["run001_candidates_reused"] is False
    assert manifest["run002_candidates_reused"] is False
    assert manifest["run001_terminal_sha256"] == RUN001_TERMINAL_SHA256
    assert manifest["run002_terminal_evidence_bundle_sha256"] == (
        module.RUN002_TERMINAL_EVIDENCE_BUNDLE_SHA256
    )
    assert manifest["replacement_reason"] == module.REPLACEMENT_REASON
    assert manifest["training_after_data_access"] is False
    assert manifest["router_decision"] == "KEEP_BASELINE"
    assert review["transport_diagnostic_count"] == 7
    assert review["transport_diagnostics_observed"] is True


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("run001_terminal_sha256", "0" * 64),
        ("run002_terminal_evidence_bundle_sha256", "0" * 64),
        ("replacement_reason", "UNAUTHORIZED_REPLACEMENT"),
        ("run001_candidates_reused", True),
        ("run002_candidates_reused", True),
        ("run001_model_scores_observed", True),
        ("run002_model_scores_observed", True),
        ("model_scores_observed", True),
    ],
)
def test_run003_evaluation_replay_rejects_predecessor_or_score_truth_drift(
    field: str, invalid_value: object
) -> None:
    module = _run003()
    documents = module.build_dataset_freeze_documents(
        _validation(), commit_a=FUTURE_COMMIT
    )
    module.run002._validated_evaluation_tasks(
        documents, commit_a=FUTURE_COMMIT, run003_mode=True
    )
    manifest = json.loads(documents["blind-v2-manifest.json"])
    manifest[field] = invalid_value
    mutated = {
        **documents,
        "blind-v2-manifest.json": (
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode(),
    }

    with pytest.raises(ValueError, match="Run003 evaluation"):
        module.run002._validated_evaluation_tasks(
            mutated, commit_a=FUTURE_COMMIT, run003_mode=True
        )


def test_run003_fake_only_construction_pack_replay_and_freeze_preserve_truth(
    tmp_path: Path,
) -> None:
    cli = _cli()
    module = _run003()
    staging_root = tmp_path / "private" / FUTURE_COMMIT
    authority = module.build_authority_manifest(
        commit_a=FUTURE_COMMIT,
        current_git_commit=FUTURE_COMMIT,
        commit_a_parent_git_commits=[CURRENT_COMMIT],
        private_evidence_root=staging_root,
    )
    context = {
        "repository": ROOT,
        "commit_a": FUTURE_COMMIT,
        "staging_root": staging_root,
        "canonical_skills": _skills(),
        "authority_manifest": authority,
        "run003_authority": True,
    }

    construction = cli.run_successor_agent_construction(
        context,
        invocation_runner=_FakeRun003ConstructionRunner(),
        contamination_scanner=_all_clean_scan,
        first_read_timestamp="2026-07-21T00:00:00Z",
        max_workers=4,
        run003_mode=True,
    )
    validation = module.run002.validate_agent_pack(
        staging_root,
        canonical_skills=_skills(),
        contamination_replayer=_all_clean_scan,
        expected_commit_a=FUTURE_COMMIT,
        run003_mode=True,
    )
    documents = module.build_dataset_freeze_documents(
        validation, commit_a=FUTURE_COMMIT
    )
    manifest = json.loads(documents["blind-v2-manifest.json"])

    assert construction["status"] == "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE"
    assert construction["retry_count"] == 0
    assert validation["status"] == "VALID"
    assert validation["transport_diagnostic_count"] == 1
    assert validation["transport_diagnostic_types"] == ["TEMPORARY_TRANSPORT_TIMEOUT"]
    assert manifest["transport_diagnostic_count"] == 1
    assert manifest["run001_candidates_reused"] is False
    assert manifest["run002_candidates_reused"] is False
    assert manifest["run001_model_scores_observed"] is False
    assert manifest["run002_model_scores_observed"] is False
    assert manifest["model_scores_observed"] is False


def test_run003_cli_selectors_are_explicit() -> None:
    cli = _cli()
    parser = cli._parser()

    canary = parser.parse_args(["run003-generator-canary"])
    assert canary.authority == "run003"
    for command in (
        "run-agent-construction",
        "pack-status",
        "freeze",
        "model-smoke",
        "evaluate",
    ):
        arguments = [command, "--authority", "run003"]
        if command == "run-agent-construction":
            arguments.extend(["--max-workers", "4"])
        parsed = parser.parse_args(arguments)
        assert parsed.authority == "run003"


def test_predecessor_bytes_remain_immutable_and_run002_has_no_standalone_terminal() -> (
    None
):
    run001_terminal = (
        ROOT
        / "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001"
        / "candidate-generation-terminal.json"
    )
    assert hashlib.sha256(run001_terminal.read_bytes()).hexdigest() == (
        RUN001_TERMINAL_SHA256
    )
    assert not (
        ROOT
        / "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-002"
        / "candidate-generation-terminal.json"
    ).exists()
    if not RUN002_EVIDENCE_ROOT.is_dir():
        pytest.skip("private Run002 evidence is intentionally host-local")
    for relative, expected_sha256 in RUN002_EVIDENCE_SHA256.items():
        assert (
            hashlib.sha256((RUN002_EVIDENCE_ROOT / relative).read_bytes()).hexdigest()
            == expected_sha256
        )


def _configure_run003_commit_a_git(
    cli: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_git_commit: str = FUTURE_COMMIT,
    parent_git_commits: list[str],
) -> None:
    terminal_source = (
        ROOT
        / "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001"
        / "candidate-generation-terminal.json"
    )
    terminal_target = (
        tmp_path
        / "artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-001"
        / "candidate-generation-terminal.json"
    )
    terminal_target.parent.mkdir(parents=True)
    terminal_target.write_bytes(terminal_source.read_bytes())
    monkeypatch.setattr(
        cli,
        "_successor_frozen_input_context",
        lambda: {"repository": tmp_path},
    )

    def fake_git(_repository: Path, *args: str) -> str:
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args == ("rev-list", "--parents", "-n", "1", "HEAD"):
            return " ".join([current_git_commit, *parent_git_commits])
        raise AssertionError(args)

    monkeypatch.setattr(cli.workflow, "_git", fake_git)


def test_run003_authority_uses_future_clean_head_and_exact_single_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    _configure_run003_commit_a_git(
        cli,
        tmp_path,
        monkeypatch,
        parent_git_commits=[CURRENT_COMMIT],
    )

    context = cli._run003_commit_a_context()

    assert context["commit_a"] == FUTURE_COMMIT
    assert context["authority_manifest"]["current_git_commit"] == FUTURE_COMMIT
    assert context["authority_manifest"]["commit_a_parent_git_commits"] == [
        CURRENT_COMMIT
    ]


def test_run003_authority_rejects_merge_even_when_first_parent_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    _configure_run003_commit_a_git(
        cli,
        tmp_path,
        monkeypatch,
        parent_git_commits=[CURRENT_COMMIT, "d" * 40],
    )

    with pytest.raises(ValueError, match="single parent|direct non-merge child"):
        cli._run003_commit_a_context()


@pytest.mark.parametrize(
    ("current_git_commit", "parent_git_commits"),
    [
        ("c" * 40, [CURRENT_COMMIT]),
        (FUTURE_COMMIT, ["d" * 40]),
        (FUTURE_COMMIT, [CURRENT_COMMIT, "d" * 40]),
    ],
)
def test_run003_authority_rejects_current_or_parent_mismatch(
    tmp_path: Path, current_git_commit: str, parent_git_commits: list[str]
) -> None:
    module = _run003()

    with pytest.raises(ValueError, match="Git authority|parent"):
        module.build_authority_manifest(
            commit_a=FUTURE_COMMIT,
            current_git_commit=current_git_commit,
            commit_a_parent_git_commits=parent_git_commits,
            private_evidence_root=tmp_path,
        )


def test_run003_authority_rejects_zero_parent_commit(tmp_path: Path) -> None:
    module = _run003()

    with pytest.raises(ValueError, match="single parent"):
        module.build_authority_manifest(
            commit_a=FUTURE_COMMIT,
            current_git_commit=FUTURE_COMMIT,
            commit_a_parent_git_commits=[],
            private_evidence_root=tmp_path,
        )


def test_run003_role_metadata_aggregates_validated_transport_diagnostics() -> None:
    cli = _cli()
    rows = [
        {
            "invocations": [
                {
                    "envelope": {
                        "thread_id": "run003-thread-001",
                        "returned_model": None,
                        "provider_returned_model_status": "INTERFACE_UNAVAILABLE",
                        "lineage_observed": True,
                        "tool_call_count": 0,
                        "descendant_agent_count": 0,
                        "event_policy_version": preflight.RUN003_EVENT_POLICY_VERSION,
                        "transport_diagnostic_count": 2,
                        "transport_diagnostic_types": [
                            "TEMPORARY_TLS_DISCONNECT",
                            "TEMPORARY_TRANSPORT_TIMEOUT",
                        ],
                        "transport_diagnostics_observed": True,
                    }
                }
            ]
        }
    ]

    metadata = cli._role_metadata(rows, role="generator", run003_mode=True)

    assert metadata["event_policy_version"] == _run003().EVENT_POLICY_VERSION
    assert metadata["transport_diagnostic_count"] == 2
    assert metadata["transport_diagnostic_types"] == [
        "TEMPORARY_TLS_DISCONNECT",
        "TEMPORARY_TRANSPORT_TIMEOUT",
    ]
    assert metadata["transport_diagnostics_observed"] is True


def test_run003_construction_routes_explicit_mode_and_event_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _cli()
    context = {"run003_authority": True}
    observed: dict[str, Any] = {}

    monkeypatch.setattr(cli, "_run003_commit_a_context", lambda: context)
    monkeypatch.setattr(
        cli, "_write_stdout", lambda payload: observed.update(output=payload)
    )

    def fake_formal(**kwargs: Any) -> dict[str, Any]:
        observed["formal_kwargs"] = kwargs
        return {"status": "NOT_EXECUTED"}

    def fake_construction(
        received_context: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        observed["context"] = received_context
        observed["construction_kwargs"] = kwargs
        kwargs["invocation_runner"](request={"synthetic": True})
        return {"status": "AGENT_BLIND_V2_CONSTRUCTION_COMPLETE"}

    monkeypatch.setattr(cli.formal, "run_formal_agent_invocation", fake_formal)
    monkeypatch.setattr(cli, "run_successor_agent_construction", fake_construction)

    exit_code = cli._run_agent_construction(
        Namespace(authority="run003", max_workers=4)
    )

    assert exit_code == 0
    assert observed["context"] is context
    assert observed["construction_kwargs"]["run003_mode"] is True
    assert observed["formal_kwargs"]["event_policy_version"] == (
        _run003().EVENT_POLICY_VERSION
    )


def test_run003_pack_status_routes_run003_replay_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    metadata_path = tmp_path / "agent-run-metadata.json"
    context = {
        "repository": ROOT,
        "staging_root": tmp_path,
        "commit_a": CURRENT_COMMIT,
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
    }
    observed: dict[str, Any] = {}
    monkeypatch.setattr(cli, "_run003_commit_a_context", lambda: context)
    monkeypatch.setattr(cli, "_agent_pack_file", lambda *_args: metadata_path)
    monkeypatch.setattr(
        cli,
        "_json",
        lambda _path: {"first_read_timestamp": "2026-07-21T00:00:00Z"},
    )
    monkeypatch.setattr(
        cli,
        "_semantic_validation_components",
        lambda _preregistration: (object(), {}),
    )

    def fake_validate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return {"status": "VALID", "run_id": _run003().RUN_ID}

    monkeypatch.setattr(cli.run002, "validate_agent_pack", fake_validate)

    received_context, validation, _similarity = cli._validated_pack_context(
        authority="run003"
    )

    assert received_context is context
    assert validation["run_id"] == _run003().RUN_ID
    assert observed["kwargs"]["run003_mode"] is True


def test_run003_freeze_routes_run003_documents_and_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    module = _run003()
    context = {"repository": tmp_path, "commit_a": CURRENT_COMMIT}
    validation = {
        "status": "VALID",
        "task_count": 128,
        "negative_labeled_task_count": 96,
        "family_count": 128,
    }
    documents = {filename: b"test" for filename in module.DATASET_FREEZE_FILENAMES}
    observed: dict[str, Any] = {}
    monkeypatch.setattr(
        cli,
        "_validated_pack_context",
        lambda **_kwargs: (context, validation, object()),
    )
    monkeypatch.setattr(
        cli.run003,
        "build_dataset_freeze_documents",
        lambda received, *, commit_a: (
            observed.update(validation=received, commit_a=commit_a) or documents
        ),
    )
    monkeypatch.setattr(
        cli.run003,
        "write_dataset_freeze",
        lambda received, output_dir, *, repository_root: observed.update(
            documents=received,
            output_dir=output_dir,
            repository_root=repository_root,
        ),
    )
    monkeypatch.setattr(
        cli, "_write_stdout", lambda payload: observed.update(output=payload)
    )

    assert cli._freeze(Namespace(authority="run003", successor=False)) == 0
    assert observed["output_dir"] == tmp_path / module.DATASET_FREEZE_RELATIVE
    assert observed["documents"] is documents


def test_run003_model_smoke_routes_run003_commit_b_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _cli()
    context = {"repository": ROOT, "commit_a": CURRENT_COMMIT, "commit_b": "b" * 40}
    observed: dict[str, Any] = {}
    monkeypatch.setattr(cli, "_run003_commit_b_context", lambda **_kwargs: context)
    monkeypatch.setattr(
        cli,
        "run_run003_model_load_smoke",
        lambda received: observed.update(context=received) or {"status": "PASSED"},
    )
    monkeypatch.setattr(
        cli.workflow,
        "write_model_load_smoke_receipt",
        lambda _receipt: ROOT / "receipt.json",
    )
    monkeypatch.setattr(
        cli, "_write_stdout", lambda payload: observed.update(output=payload)
    )

    assert cli._model_smoke(Namespace(authority="run003", successor=False)) == 0
    assert observed["context"] is context


def test_run003_evaluate_routes_frozen_bindings_and_output_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = _cli()
    module = _run003()
    preregistration_path = tmp_path / "preregistration.json"
    pilot_manifest_path = tmp_path / "pilot.json"
    preregistration_path.write_text("{}", encoding="utf-8")
    pilot_manifest_path.write_text("{}", encoding="utf-8")
    frozen_documents = {
        "blind-v2-tasks.jsonl": b"",
        "blind-v2-manifest.json": b"{}",
        "blind-v2-review-summary.json": b"{}",
    }
    context = {
        "repository": tmp_path,
        "preregistration_path": preregistration_path,
        "pilot_manifest_path": pilot_manifest_path,
        "frozen_documents": frozen_documents,
        "canonical_skills": _skills(),
        "commit_a": CURRENT_COMMIT,
        "commit_b": "b" * 40,
        "frozen_manifest_file_sha256": "f" * 64,
    }
    observed: dict[str, Any] = {}
    monkeypatch.setattr(cli, "_run003_commit_b_context", lambda **_kwargs: context)
    monkeypatch.setattr(
        cli.workflow,
        "validate_preregistration_authority",
        lambda *_args, **_kwargs: {"preregistration_sha256": "a" * 64},
    )
    monkeypatch.setattr(cli.workflow, "_jsonl_no_duplicate_keys", lambda *_args: [])
    monkeypatch.setattr(
        cli,
        "_json",
        lambda path: (
            {"training_execution_root": str(tmp_path / "training")}
            if path == pilot_manifest_path
            else {}
        ),
    )
    monkeypatch.setattr(cli, "_model_bindings", lambda _pilot: [])
    monkeypatch.setattr(
        cli.run003,
        "build_evaluation_bindings",
        lambda **kwargs: observed.update(binding_kwargs=kwargs) or {"run003": True},
    )
    monkeypatch.setattr(
        cli.workflow,
        "build_attempt_started_document",
        lambda payload: {"started": payload},
    )
    monkeypatch.setattr(
        cli.workflow,
        "build_attempt_terminal_document",
        lambda count: {"terminal": count},
    )
    monkeypatch.setattr(
        cli.run003,
        "validate_evaluation_inputs",
        lambda **kwargs: observed.update(input_kwargs=kwargs) or ([], [], []),
    )
    monkeypatch.setattr(
        cli.workflow,
        "_evaluate_routes_validated",
        lambda *_args: [{"route": True}],
    )
    monkeypatch.setattr(
        cli.run003,
        "validate_evaluation_routes",
        lambda routes, **kwargs: observed.update(routes=routes, route_kwargs=kwargs),
    )
    monkeypatch.setattr(
        cli.workflow,
        "_build_evaluation_documents_validated",
        lambda *_args, **_kwargs: {"evaluation-summary.json": b"{}"},
    )

    def fake_single_attempt(output_root: Path, **kwargs: Any) -> dict[str, Any]:
        observed["output_root"] = output_root
        observed["output_namespace"] = kwargs["output_namespace"]
        kwargs["evaluate"]()
        return {"status": "DONE"}

    monkeypatch.setattr(cli.workflow, "run_single_attempt", fake_single_attempt)
    monkeypatch.setattr(
        cli, "_write_stdout", lambda payload: observed.update(output=payload)
    )

    assert cli._evaluate(Namespace(authority="run003", successor=False)) == 0
    assert observed["binding_kwargs"]["commit_a"] == CURRENT_COMMIT
    assert observed["routes"] == [{"route": True}]
    assert observed["output_namespace"] == module.OUTPUT_NAMESPACE
    assert observed["output_root"] == tmp_path / module.OUTPUT_NAMESPACE
