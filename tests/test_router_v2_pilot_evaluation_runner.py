from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from hermes_skilleval.router_v2_internal_package import HELDOUT_ROW_FIELDS
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_evaluation import contract_sha256
from hermes_skilleval.router_v2_pilot_evaluation_runner import (
    EvaluationTestOverrides,
    PilotAuthority,
    ValidatedAuthorityContext,
    run_evaluation_once,
)
from hermes_skilleval.router_v2_pilot_runtime import (
    CONFIG_FIELDS,
    LINEAGE_FIELDS,
    TRUTH_FIELDS,
    canonical_json_line,
    snapshot_model_files,
)
from hermes_skilleval.router_v2_reviewed_source import CANDIDATE_FIELDS
import hermes_skilleval.router_v2_pilot_evaluation_runner as runner


ARMS = ("A", "B", "C")
SEEDS = (7170, 7171, 7172)


def test_production_api_has_no_request_or_hash_authority_parameters() -> None:
    parameters = inspect.signature(run_evaluation_once).parameters
    assert tuple(parameters)[:3] == (
        "repository_root",
        "execution_root",
        "base_model_path",
    )
    assert "request" not in parameters
    assert "expected_hashes" not in parameters
    assert PilotAuthority.__dataclass_fields__["test_only"].default is False
    assert (
        PilotAuthority.__dataclass_fields__["evaluation_code_git_commit"].default
        is None
    )
    assert EvaluationTestOverrides.__dataclass_fields__["authority"]


def test_self_validated_training_documents_do_not_require_request_file_hash(
    tmp_path: Path,
) -> None:
    path = tmp_path / "self-validating.json"
    payload = _json_bytes({"schema_version": "self-validating-v1"})
    path.write_bytes(payload)
    assert (
        runner._read_verified(str(path), None, Path.read_bytes, "self-validating")
        == payload
    )


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return _sha(payload)


def _json_bytes(value: Any) -> bytes:
    return canonical_json_line(value).encode()


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {**value, field: contract_sha256(value)}


def _skills() -> list[dict[str, Any]]:
    return [
        {
            "id": f"skill-{index:02d}",
            "name": f"Skill {index:02d}",
            "path": f"skills/skill-{index:02d}/SKILL.md",
            "category": "cat-a" if index < 8 else "cat-b",
            "description": f"Description {index:02d}",
            "body": f"Body {index:02d}",
            "trigger_terms": [f"term-{index:02d}"],
            "token_count_estimate": 10,
        }
        for index in range(16)
    ]


def _training_artifact(inputs: Path, arm: str, seed: int) -> dict[str, Any]:
    prefix = inputs / "training" / f"{arm}-{seed}"
    model_path = prefix / "model"
    model_path.mkdir(parents=True)
    model_payload = f"model-{arm}-{seed}".encode()
    model_sha = _write(model_path / "weights.bin", model_payload)
    snapshot = [
        {"path": "weights.bin", "sha256": model_sha, "size": len(model_payload)}
    ]
    lineage = {
        "data_manifest_sha256": "1" * 64,
        "accepted_pairs_sha256": "2" * 64,
        "mining_rows_sha256": "3" * 64,
        "mining_manifest_sha256": "4" * 64,
        "package_code_git_commit": "5" * 40,
        "training_code_git_commit": "c" * 40,
        "base_model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "base_model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        "base_model_file_manifest_sha256": contract_sha256(snapshot),
        "sampler_version": "skill-unique-v1",
        "sampler_plan_sha256": "6" * 64,
        "dependency_versions": {
            "numpy": "1",
            "python": "3.12",
            "scikit-learn": "1",
            "sentence-transformers": "1",
            "torch": "1",
            "transformers": "1",
        },
    }
    modes = {
        "A": ("EVALUATION_ONLY", "NONE"),
        "B": ("POSITIVE_ONLY", "MultipleNegativesRankingLoss"),
        "C": (
            "POSITIVE_AND_HARD_NEGATIVE",
            "MultipleNegativesRankingLoss+ContrastiveLoss",
        ),
    }
    config = _seal(
        {
            "schema_version": "router-v2-pilot-frozen-config-v1",
            "arm": arm,
            "seed": seed,
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": "0.00002000",
            "hard_negative_margin": "1.50000000",
            "training_mode": modes[arm][0],
            "loss_contract": modes[arm][1],
            **lineage,
            "handoff_fingerprint": "7" * 64,
            "output_dir": f"arm-{arm}/seed-{seed}",
            **TRUTH_FIELDS,
        },
        "config_sha256",
    )
    assert set(config) == CONFIG_FIELDS
    trained_snapshot = [] if arm == "A" else snapshot
    summary = _seal(
        {
            "schema_version": "router-v2-pilot-run-summary-v1",
            "arm": arm,
            "seed": seed,
            "training_mode": modes[arm][0],
            "training_executed": arm != "A",
            "runtime_status": (
                "EVALUATION_METADATA_WRITTEN" if arm == "A" else "TRAINING_COMPLETED"
            ),
            "device": "evaluation-only" if arm == "A" else "cpu",
            "optimizer_step_count": 0 if arm == "A" else (24 if arm == "C" else 12),
            "hard_negative_optimizer_step_count": 12 if arm == "C" else 0,
            "trained_example_count": 0 if arm == "A" else (116 if arm == "C" else 64),
            "loss_values": [] if arm == "A" else [0.1] * (24 if arm == "C" else 12),
            "model_file_manifest": trained_snapshot,
            "model_file_manifest_sha256": contract_sha256(trained_snapshot),
            "output_dir": config["output_dir"],
            "config_sha256": config["config_sha256"],
            "handoff_fingerprint": config["handoff_fingerprint"],
            "positive_count": 64,
            "hard_negative_count": 48,
            **{field: config[field] for field in LINEAGE_FIELDS},
            **TRUTH_FIELDS,
        },
        "summary_sha256",
    )
    manifest = _seal(
        {
            "schema_version": "router-v2-pilot-model-manifest-v1",
            "arm": arm,
            "seed": seed,
            "training_executed": summary["training_executed"],
            "run_summary_sha256": summary["summary_sha256"],
            "config_sha256": config["config_sha256"],
            "handoff_fingerprint": summary["handoff_fingerprint"],
            "output_dir": config["output_dir"],
            "model_file_manifest": trained_snapshot,
            "model_file_manifest_sha256": contract_sha256(trained_snapshot),
            **{field: config[field] for field in LINEAGE_FIELDS},
            **TRUTH_FIELDS,
        },
        "model_manifest_sha256",
    )
    paths = {}
    for name, value in (
        ("config", config),
        ("run_summary", summary),
        ("model_manifest", manifest),
    ):
        path = prefix / f"{name}.json"
        paths[f"{name}_path"] = str(path)
        paths[f"{name}_file_sha256"] = _write(path, _json_bytes(value))
    return {"arm": arm, "seed": seed, "model_path": str(model_path), **paths}


def _fixture(tmp_path: Path) -> dict[str, Any]:
    inputs = tmp_path / "inputs"
    skills = _skills()
    skill_payload = json.dumps(skills, ensure_ascii=False, sort_keys=True).encode()
    skill_hash = _write(inputs / "skills.json", skill_payload)
    source_rows = []
    source_lines = []
    bindings = []
    for index, skill in enumerate(skills):
        query = f"query-{index:02d}"
        row = {
            "schema_version": "router-v2-reviewed-source-record-v1",
            "artifact_version": "router-v2-v4",
            "policy_id": "router-v2-reviewed-source-policy-v1",
            "source_record_id": f"source-{index:02d}",
            "draft_id": f"draft-{index:02d}",
            "task_id": f"task-{index:02d}",
            "prompt_family_id": f"family-{index:02d}",
            "split": "non_blind_test",
            "source_role": "POSITIVE",
            "positive_skill_id": skill["id"],
            "skill_id": skill["id"],
            "query_text": query,
            "query_text_policy": "PROMPT_ONLY",
            "prompt_text_sha256": _sha(query.encode()),
            "skill_record_sha256": contract_sha256(skill),
            "source_kind": "SYNTHETIC_TEST_FIXTURE",
            "source_artifact_path": "synthetic/source.jsonl",
            "source_draft_line_sha256": f"{index + 301:064x}",
            "status": "REVIEWED",
            "decision": "ACCEPT",
            "reviewer": "synthetic-test",
            "reason": "synthetic fixture",
        }
        assert set(row) == CANDIDATE_FIELDS
        line = _json_bytes(row)
        source_rows.append(row)
        source_lines.append(line)
        bindings.append(
            {
                "task_id": row["task_id"],
                "source_record_id": row["source_record_id"],
                "source_record_exact_bytes_sha256": _sha(line),
                "query_sha256": row["prompt_text_sha256"],
                "gold_skill_id": row["positive_skill_id"],
                "category": skill["category"],
                "supported_negative_skill_id": (
                    skills[(index + 1) % 16]["id"] if index < 9 else None
                ),
                "heldout_label_row_sha256": None,
                "heldout_usage": None,
            }
        )
    source_payload = b"".join(source_lines)
    source_hash = _write(inputs / "source-candidates.jsonl", source_payload)
    manifest_records = [
        {
            "source_record_id": row["source_record_id"],
            "source_record_exact_bytes_sha256": bindings[index][
                "source_record_exact_bytes_sha256"
            ],
            **{
                field: row[field]
                for field in (
                    "source_role",
                    "split",
                    "positive_skill_id",
                    "skill_id",
                    "prompt_text_sha256",
                )
            },
        }
        for index, row in enumerate(source_rows)
    ]
    source_manifest = {
        "schema_version": "router-v2-source-snapshot-manifest-v1",
        "snapshot_id": "synthetic-snapshot",
        "records": manifest_records,
    }
    source_manifest_hash = _write(
        inputs / "source-manifest.json", _json_bytes(source_manifest)
    )
    label_lines = []
    for index in range(9):
        source = source_rows[index]
        candidate = skills[(index + 1) % 16]
        row = _seal(
            {
                "schema_version": "router-v2-internal-heldout-label-v1",
                "candidate_id": f"candidate-{index:02d}",
                "candidate_sha256": f"{index + 401:064x}",
                "task_id": source["task_id"],
                "query_text": source["query_text"],
                "query_sha256": source["prompt_text_sha256"],
                "positive_source_record_id": source["source_record_id"],
                "positive_source_record_exact_bytes_sha256": bindings[index][
                    "source_record_exact_bytes_sha256"
                ],
                "gold_skill_id": source["positive_skill_id"],
                "gold_skill_record_sha256": contract_sha256(skills[index]),
                "candidate_skill_id": candidate["id"],
                "candidate_skill_text": _skill_text(candidate),
                "candidate_skill_text_sha256": contract_sha256(_skill_text(candidate)),
                "candidate_skill_record_sha256": contract_sha256(candidate),
                "usage": "HELD_OUT_EVAL_ONLY",
                "training_eligible": False,
                "mining_eligible": False,
                "adjudication_row_sha256": f"{index + 501:064x}",
                "pass_1_row_sha256": f"{index + 601:064x}",
                "pass_2_row_sha256": f"{index + 701:064x}",
                "source_snapshot_id": "synthetic-snapshot",
                "source_candidates_sha256": source_hash,
                "source_manifest_sha256": source_manifest_hash,
                "skill_index_sha256": skill_hash,
            },
            "row_sha256",
        )
        assert set(row) == HELDOUT_ROW_FIELDS
        label_lines.append(_json_bytes(row))
        bindings[index]["heldout_label_row_sha256"] = row["row_sha256"]
        bindings[index]["heldout_usage"] = "HELD_OUT_EVAL_ONLY"
    labels_hash = _write(inputs / "heldout-labels.jsonl", b"".join(label_lines))
    run_pack_payload = _json_bytes({"schema_version": "synthetic-run-pack-v1"})
    run_pack_hash = _write(inputs / "run-pack-manifest.json", run_pack_payload)
    training_artifacts = [
        _training_artifact(inputs, arm, seed) for arm in ARMS for seed in SEEDS
    ]
    return {
        "repository_root": str(tmp_path),
        "source_candidates_path": str(inputs / "source-candidates.jsonl"),
        "source_manifest_path": str(inputs / "source-manifest.json"),
        "skill_index_path": str(inputs / "skills.json"),
        "heldout_labels_path": str(inputs / "heldout-labels.jsonl"),
        "run_pack_manifest_path": str(inputs / "run-pack-manifest.json"),
        "expected_hashes": {
            "source_candidates_sha256": source_hash,
            "source_manifest_sha256": source_manifest_hash,
            "skill_index_sha256": skill_hash,
            "heldout_labels_sha256": labels_hash,
            "run_pack_manifest_sha256": run_pack_hash,
        },
        "expected_task_bindings_sha256": contract_sha256(bindings),
        "training_artifacts": training_artifacts,
        "training_code_git_commit": "c" * 40,
        "evaluation_code_git_commit": "d" * 40,
        "attempt_token_sha256": "e" * 64,
    }


class FakeEncoder:
    def __init__(self, skills: list[dict[str, str]]) -> None:
        self.skill_index = {
            row["skill_text"]: index for index, row in enumerate(skills)
        }
        self.query_index = {f"query-{index:02d}": index for index in range(16)}
        self.skill_calls = 0

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        assert normalize_embeddings is True
        if len(texts) == 16:
            self.skill_calls += 1
            return [
                [1.0 if item == self.skill_index[text] else 0.0 for item in range(16)]
                for text in texts
            ]
        index = self.query_index[texts[0]]
        return [[1.0 if item == index else 0.0 for item in range(16)]]


def _test_overrides(
    request: dict[str, Any],
    execution_root: Path,
    *,
    model_factory: Any,
    read_bytes: Any = Path.read_bytes,
    clock_ns: Any = None,
) -> EvaluationTestOverrides:
    authority = PilotAuthority(
        test_only=True,
        source_candidates_sha256=request["expected_hashes"]["source_candidates_sha256"],
        source_manifest_sha256=request["expected_hashes"]["source_manifest_sha256"],
        skill_index_sha256=request["expected_hashes"]["skill_index_sha256"],
        heldout_labels_sha256=request["expected_hashes"]["heldout_labels_sha256"],
        run_pack_manifest_sha256="a" * 64,
        run_pack_manifest_file_sha256=request["expected_hashes"][
            "run_pack_manifest_sha256"
        ],
        training_code_git_commit="c" * 40,
        evaluation_code_git_commit="d" * 40,
        execution_id=execution_root.name,
    )
    artifacts = []
    for row in request["training_artifacts"]:
        config = json.loads(Path(row["config_path"]).read_text())
        summary = json.loads(Path(row["run_summary_path"]).read_text())
        manifest = json.loads(Path(row["model_manifest_path"]).read_text())
        row["_validated_model_file_manifest"] = (
            snapshot_model_files(Path(row["model_path"]))
            if row["arm"] == "A"
            else manifest["model_file_manifest"]
        )
        artifacts.append(
            {
                "arm": row["arm"],
                "seed": row["seed"],
                "config_sha256": config["config_sha256"],
                "run_summary_sha256": summary["summary_sha256"],
                "model_manifest_sha256": manifest["model_manifest_sha256"],
                "model_file_manifest_sha256": manifest["model_file_manifest_sha256"],
            }
        )
    request["run_pack_root"] = str(execution_root / "synthetic-run-pack")
    request["run_pack_internal_sha256"] = "a" * 64
    context = ValidatedAuthorityContext(
        authority=authority,
        repository_root=Path(request["repository_root"]),
        execution_root=execution_root,
        base_model_path=Path(request["training_artifacts"][0]["model_path"]),
        request=request,
        run_pack_documents={},
        training_artifacts=artifacts,
    )
    return EvaluationTestOverrides(
        authority=authority,
        model_factory=model_factory,
        read_bytes=read_bytes,
        clock_ns=clock_ns or (lambda: 0),
        git_probe=lambda _: ("d" * 40, True),
        resolve_output_root=lambda value: Path(value),
        prevalidated_context=context,
    )


def test_runner_accepts_real_shapes_marks_before_32_reads_and_publishes(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path)
    execution_root = tmp_path / "execution"
    execution_root.mkdir(mode=0o700)
    encoders: list[FakeEncoder] = []
    read_paths: list[Path] = []

    def read_bytes(path: Path) -> bytes:
        assert (execution_root / "evaluation/attempt-1.started.json").exists()
        read_paths.append(path)
        return path.read_bytes()

    def factory(
        arm: str, seed: int, artifact: dict[str, Any], skills: list[dict[str, str]]
    ) -> FakeEncoder:
        assert Path(artifact["model_path"]).is_dir()
        encoder = FakeEncoder(skills)
        encoders.append(encoder)
        return encoder

    ticks = iter(range(0, 10_000_000_000, 1_000_000))
    overrides = _test_overrides(
        request,
        execution_root,
        model_factory=factory,
        read_bytes=read_bytes,
        clock_ns=lambda: next(ticks),
    )
    summary = run_evaluation_once(
        request["repository_root"],
        execution_root,
        request["training_artifacts"][0]["model_path"],
        test_overrides=overrides,
    )
    output = execution_root / "evaluation/artifacts"
    assert summary["router_decision"] == "KEEP_BASELINE"
    assert (
        "COMPLETED"
        in (execution_root / "evaluation/attempt-1.terminal.json").read_text()
    )
    assert len((output / "route-results.jsonl").read_text().splitlines()) == 144
    assert len(read_paths) == 4
    assert len(encoders) == 9 and all(encoder.skill_calls == 1 for encoder in encoders)
    with pytest.raises(ValueError, match="already"):
        run_evaluation_once(
            request["repository_root"],
            execution_root,
            request["training_artifacts"][0]["model_path"],
            test_overrides=overrides,
        )


def test_runner_failed_attempt_is_terminal_and_cannot_retry(tmp_path: Path) -> None:
    request = _fixture(tmp_path)
    execution_root = tmp_path / "execution"
    execution_root.mkdir(mode=0o700)

    def fail_factory(*_: Any) -> FakeEncoder:
        raise RuntimeError("synthetic model failure")

    overrides = _test_overrides(request, execution_root, model_factory=fail_factory)
    with pytest.raises(RuntimeError, match="synthetic model failure"):
        run_evaluation_once(
            request["repository_root"],
            execution_root,
            request["training_artifacts"][0]["model_path"],
            test_overrides=overrides,
        )
    assert (
        json.loads((execution_root / "evaluation/attempt-1.terminal.json").read_text())[
            "status"
        ]
        == "FAILED"
    )
    with pytest.raises(ValueError, match="already"):
        run_evaluation_once(
            request["repository_root"],
            execution_root,
            request["training_artifacts"][0]["model_path"],
            test_overrides=overrides,
        )


def test_runner_rejects_binding_drift_model_snapshot_and_forbidden_path(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path)
    execution_root = tmp_path / "execution"
    execution_root.mkdir(mode=0o700)
    request["expected_task_bindings_sha256"] = "f" * 64
    overrides = _test_overrides(
        request,
        execution_root,
        model_factory=lambda *_: pytest.fail("model must not load"),
    )
    with pytest.raises(ValueError, match="binding commitment"):
        run_evaluation_once(
            request["repository_root"],
            execution_root,
            request["training_artifacts"][0]["model_path"],
            test_overrides=overrides,
        )

    snapshot_root = tmp_path / "snapshot-execution"
    snapshot_root.mkdir(mode=0o700)
    snapshot_request = _fixture(tmp_path / "snapshot")
    first_model = Path(snapshot_request["training_artifacts"][0]["model_path"])
    snapshot_overrides = _test_overrides(
        snapshot_request,
        snapshot_root,
        model_factory=lambda *_: pytest.fail("model must not load"),
    )
    (first_model / "weights.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="copy verification"):
        run_evaluation_once(
            snapshot_request["repository_root"],
            snapshot_root,
            first_model,
            test_overrides=snapshot_overrides,
        )

    other_root = tmp_path / "other-execution"
    other_root.mkdir(mode=0o700)
    forbidden = _fixture(tmp_path / "forbidden")
    forbidden["source_candidates_path"] = str(tmp_path / "calibration.jsonl")
    forbidden_overrides = _test_overrides(
        forbidden,
        other_root,
        model_factory=lambda *_: pytest.fail("model must not load"),
    )
    with pytest.raises(ValueError, match="forbidden"):
        run_evaluation_once(
            forbidden["repository_root"],
            other_root,
            forbidden["training_artifacts"][0]["model_path"],
            test_overrides=forbidden_overrides,
        )
    assert not (other_root / "evaluation/attempt-1.started.json").exists()


def test_offline_wrapper_coerces_array_and_cli_direct_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {}

    class FakeArray:
        def tolist(self) -> list[list[float]]:
            return [[1.0, 0.0]]

    class FakeSentenceTransformer:
        def __init__(self, path: str, **kwargs: Any) -> None:
            calls["init"] = (path, kwargs)

        def encode(self, texts: list[str], **kwargs: Any) -> FakeArray:
            calls["encode"] = (texts, kwargs)
            return FakeArray()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    encoder = runner._LocalSentenceTransformerEncoder("/verified/private/model")
    assert encoder.encode(["query"], normalize_embeddings=True) == [[1.0, 0.0]]
    assert calls["init"] == (
        "/verified/private/model",
        {"device": "cpu", "local_files_only": True},
    )

    script = Path(__file__).parents[1] / "scripts/run_router_v2_pilot_evaluation.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--execution-root" in result.stdout
