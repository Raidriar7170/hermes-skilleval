from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
import types
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from hermes_skilleval.router_v2_internal_package import HELDOUT_ROW_FIELDS
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_evaluation import contract_sha256
import hermes_skilleval.router_v2_pilot_evaluation as evaluation
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


def _training_artifact(
    inputs: Path,
    arm: str,
    seed: int,
    frozen_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    prefix = inputs / "training" / f"{arm}-{seed}"
    model_path = prefix / "model"
    model_path.mkdir(parents=True)
    model_payload = f"model-{arm}-{seed}".encode()
    model_sha = _write(model_path / "weights.bin", model_payload)
    snapshot = [
        {"path": "weights.bin", "sha256": model_sha, "size": len(model_payload)}
    ]
    hashes = frozen_hashes or {
        "data_manifest_sha256": "1" * 64,
        "accepted_pairs_sha256": "2" * 64,
        "mining_rows_sha256": "3" * 64,
        "mining_manifest_sha256": "4" * 64,
    }
    lineage = {
        **hashes,
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
    frozen_payloads = {
        "data_manifest_sha256": (runner.DATA_MANIFEST_PATH, b"synthetic-data"),
        "accepted_pairs_sha256": (
            runner.ACCEPTED_PAIRS_PATH,
            b"synthetic-accepted",
        ),
        "mining_rows_sha256": (runner.MINING_ROWS_PATH, b"synthetic-mining-rows"),
        "mining_manifest_sha256": (
            runner.MINING_MANIFEST_PATH,
            b"synthetic-mining-manifest",
        ),
    }
    frozen_hashes = {}
    for field, (relative, payload) in frozen_payloads.items():
        frozen_hashes[field] = _write(tmp_path / relative, payload)
    training_artifacts = [
        _training_artifact(inputs, arm, seed, frozen_hashes)
        for arm in ARMS
        for seed in SEEDS
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
        heldout_labels_path=request["heldout_labels_path"],
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
        row["_validated_model_topology"] = _capture_test_model_topology(
            Path(row["model_path"]), row["_validated_model_file_manifest"]
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
        run_pack_documents={
            f"config-arm-{row['arm']}-seed-{row['seed']}.json": Path(
                row["config_path"]
            ).read_bytes()
            for row in request["training_artifacts"]
        },
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


def _capture_test_model_topology(
    model_path: Path, manifest_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    def identity(metadata: os.stat_result) -> tuple[int, int, int]:
        return metadata.st_dev, metadata.st_ino, metadata.st_mode

    root = model_path.resolve(strict=True)
    rows = {}
    for row in manifest_rows:
        relative = Path(row["path"])
        current = root
        parents = []
        for part in relative.parts[:-1]:
            current /= part
            parents.append((part, identity(current.lstat())))
        final = current / relative.parts[-1]
        is_link = final.is_symlink()
        resolved = final.resolve(strict=True) if is_link else None
        rows[row["path"]] = {
            "parents": tuple(parents),
            "final": identity(final.lstat()),
            "link_text": os.readlink(final) if is_link else None,
            "model_root": (
                identity(resolved.parent.parent.lstat())
                if resolved is not None
                else None
            ),
            "blob_dir": (
                identity(resolved.parent.lstat()) if resolved is not None else None
            ),
            "blob": identity(resolved.lstat()) if resolved is not None else None,
        }
    return {"root": identity(root.lstat()), "rows": rows}


def _arm_artifact(
    request: dict[str, Any], arm: str, seed: int = 7170
) -> dict[str, Any]:
    return next(
        row
        for row in request["training_artifacts"]
        if row["arm"] == arm and row["seed"] == seed
    )


def _replace_base_model_with_hf_snapshot(
    request: dict[str, Any],
    cache_parent: Path,
    *,
    snapshot_relative_path: str = "weights.bin",
    blob_relative_path: str = "opaque-blob-name",
    target_outside_cache: bool = False,
) -> tuple[Path, Path]:
    artifact = _arm_artifact(request, "A")
    payload = (Path(artifact["model_path"]) / "weights.bin").read_bytes()
    model_root = cache_parent / "models--sentence-transformers--all-MiniLM-L6-v2"
    blob = (
        cache_parent / "outside-blob"
        if target_outside_cache
        else model_root / "blobs" / blob_relative_path
    )
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    snapshot = model_root / "snapshots" / "exact-revision"
    snapshot.mkdir(parents=True)
    link = snapshot / snapshot_relative_path
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(os.path.relpath(blob, start=link.parent))
    artifact["model_path"] = str(snapshot)
    return snapshot, blob


def _copy_then_mark_factory_called(
    staging: Path,
    request: dict[str, Any],
    factory_calls: list[str],
) -> dict[tuple[str, int], dict[str, Any]]:
    copied = runner._copy_model_inputs(staging, request)
    factory_calls.append("called")
    return copied


def _copy_target(staging: Path, arm: str = "A", seed: int = 7170) -> Path:
    return staging / "model-inputs" / f"arm-{arm}-seed-{seed}"


def test_copy_model_inputs_materializes_valid_hf_blob_symlink(tmp_path: Path) -> None:
    request = _fixture(tmp_path / "fixture")
    snapshot, blob = _replace_base_model_with_hf_snapshot(
        request, tmp_path / "hf-cache"
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )

    copied = runner._copy_model_inputs(tmp_path / "staging", request)

    target = Path(copied[("A", 7170)]["model_path"]) / "weights.bin"
    assert snapshot.joinpath("weights.bin").is_symlink()
    assert target.read_bytes() == blob.read_bytes()
    assert target.is_file() and not target.is_symlink()
    assert factory_calls == []


def test_copy_model_inputs_materializes_valid_nested_hf_blob_symlink(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _, blob = _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        snapshot_relative_path="1_Pooling/config.json",
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )

    copied = runner._copy_model_inputs(tmp_path / "staging", request)

    target = Path(copied[("A", 7170)]["model_path"]) / "1_Pooling" / "config.json"
    assert target.read_bytes() == blob.read_bytes()
    assert target.is_file() and not target.is_symlink()
    assert factory_calls == []


def test_copy_model_inputs_rejects_nested_blob_target_without_residue(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        blob_relative_path="nested/opaque-blob-name",
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="base model snapshot symlink target"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


@pytest.mark.parametrize("target_kind", ["directory", "fifo"])
def test_copy_model_inputs_rejects_non_regular_blob_target_without_residue(
    tmp_path: Path,
    target_kind: str,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _, blob = _replace_base_model_with_hf_snapshot(request, tmp_path / "hf-cache")
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    blob.unlink()
    if target_kind == "directory":
        blob.mkdir()
    else:
        os.mkfifo(blob)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="base model snapshot symlink target"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


@pytest.mark.parametrize("replacement", ["parent", "link", "blob"])
def test_copy_model_inputs_rejects_post_validation_replacement(
    tmp_path: Path,
    replacement: str,
) -> None:
    request = _fixture(tmp_path / "fixture")
    snapshot, blob = _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        snapshot_relative_path="1_Pooling/config.json",
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    link = snapshot / "1_Pooling" / "config.json"
    if replacement == "parent":
        parent = link.parent
        moved = tmp_path / "moved-pooling"
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
    elif replacement == "link":
        link.unlink()
        link.symlink_to(os.path.relpath(blob, start=link.parent))
    else:
        new_blob = blob.with_name("replacement-blob")
        new_blob.write_bytes(blob.read_bytes())
        os.replace(new_blob, blob)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="replaced|parent|topology"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


def test_copy_model_inputs_rejects_trained_nested_parent_symlink(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    artifact = _arm_artifact(request, "B")
    model_root = Path(artifact["model_path"])
    payload = (model_root / "weights.bin").read_bytes()
    (model_root / "weights.bin").unlink()
    nested = model_root / "nested"
    nested.mkdir()
    (nested / "weights.bin").write_bytes(payload)
    manifest_path = Path(artifact["model_manifest_path"])
    manifest = json.loads(manifest_path.read_text())
    manifest["model_file_manifest"] = [
        {"path": "nested/weights.bin", "sha256": _sha(payload), "size": len(payload)}
    ]
    manifest_path.write_bytes(_json_bytes(manifest))
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    moved = tmp_path / "moved-trained-parent"
    nested.rename(moved)
    nested.symlink_to(moved, target_is_directory=True)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="parent|symlink|topology"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging, arm="B").exists()


def test_copy_model_inputs_rejects_post_validation_trained_root_symlink(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    artifact = _arm_artifact(request, "B")
    model_root = Path(artifact["model_path"])
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    moved = tmp_path / "moved-trained-model-root"
    model_root.rename(moved)
    model_root.symlink_to(moved, target_is_directory=True)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="root|symlink|topology|replaced"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging, arm="B").exists()


@pytest.mark.parametrize("replaced_entry", ["model_root", "blobs"])
def test_copy_model_inputs_rejects_post_validation_hf_cache_root_replacement(
    tmp_path: Path,
    replaced_entry: str,
) -> None:
    request = _fixture(tmp_path / "fixture")
    snapshot, _ = _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        snapshot_relative_path="1_Pooling/config.json",
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    model_root = snapshot.parent.parent
    if replaced_entry == "model_root":
        moved = tmp_path / "models--sentence-transformers--all-MiniLM-L6-v2-moved"
        model_root.rename(moved)
        model_root.symlink_to(moved, target_is_directory=True)
    else:
        blobs = model_root / "blobs"
        moved = model_root / "moved-blobs"
        blobs.rename(moved)
        blobs.symlink_to(moved.name, target_is_directory=True)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="root|blobs|topology|replaced"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


@pytest.mark.parametrize("injected_operation", ["open", "fstat", "stat", "readlink"])
def test_copy_model_inputs_closes_all_fds_after_injected_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    injected_operation: str,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        snapshot_relative_path="1_Pooling/config.json",
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    real_stat = os.stat
    real_readlink = os.readlink
    opened: set[int] = set()
    closed: set[int] = set()
    injected = False

    def tracked_open(*args: Any, **kwargs: Any) -> int:
        nonlocal injected
        if injected_operation == "open" and opened and not injected:
            injected = True
            raise OSError("injected open failure")
        descriptor = real_open(*args, **kwargs)
        opened.add(descriptor)
        return descriptor

    def tracked_close(descriptor: int) -> None:
        closed.add(descriptor)
        real_close(descriptor)

    def injected_fstat(*args: Any, **kwargs: Any) -> os.stat_result:
        nonlocal injected
        if injected_operation == "fstat" and opened and not injected:
            injected = True
            raise OSError("injected fstat failure")
        return real_fstat(*args, **kwargs)

    def injected_stat(*args: Any, **kwargs: Any) -> os.stat_result:
        nonlocal injected
        if injected_operation == "stat" and opened and not injected:
            injected = True
            raise OSError("injected stat failure")
        return real_stat(*args, **kwargs)

    def injected_readlink(*args: Any, **kwargs: Any) -> str:
        nonlocal injected
        if injected_operation == "readlink" and opened and not injected:
            injected = True
            raise OSError("injected readlink failure")
        return real_readlink(*args, **kwargs)

    monkeypatch.setattr(runner.os, "open", tracked_open)
    monkeypatch.setattr(runner.os, "close", tracked_close)
    monkeypatch.setattr(runner.os, "fstat", injected_fstat)
    monkeypatch.setattr(runner.os, "stat", injected_stat)
    monkeypatch.setattr(runner.os, "readlink", injected_readlink)
    staging = tmp_path / "staging"

    with pytest.raises((OSError, ValueError), match="injected"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert injected is True
    assert opened == closed
    assert factory_calls == []
    assert not _copy_target(staging).exists()


def test_copy_model_inputs_rejects_hf_symlink_escape_before_factory(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _replace_base_model_with_hf_snapshot(
        request,
        tmp_path / "hf-cache",
        target_outside_cache=True,
    )
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="base model snapshot symlink target"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


@pytest.mark.parametrize("replacement", [b"MODEL-A-7170", b"different-size"])
def test_copy_model_inputs_rejects_hf_blob_hash_or_size_change_before_factory(
    tmp_path: Path,
    replacement: bytes,
) -> None:
    request = _fixture(tmp_path / "fixture")
    _, blob = _replace_base_model_with_hf_snapshot(request, tmp_path / "hf-cache")
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    blob.write_bytes(replacement)
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="model copy content mismatch"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging).exists()


def test_copy_model_inputs_rejects_trained_arm_symlink_before_factory(
    tmp_path: Path,
) -> None:
    request = _fixture(tmp_path / "fixture")
    artifact = _arm_artifact(request, "B")
    weights = Path(artifact["model_path"]) / "weights.bin"
    external = tmp_path / "trained-model-blob"
    external.write_bytes(weights.read_bytes())
    weights.unlink()
    weights.symlink_to(external)
    factory_calls: list[str] = []
    _test_overrides(
        request,
        tmp_path / "execution",
        model_factory=lambda *_: factory_calls.append("called"),
    )
    staging = tmp_path / "staging"

    with pytest.raises(ValueError, match="trained model snapshot symlink"):
        _copy_then_mark_factory_called(staging, request, factory_calls)

    assert factory_calls == []
    assert not _copy_target(staging, arm="B").exists()


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
    assert {path.name for path in output.iterdir()} == {
        "final-evaluation-plan.json",
        "route-results.jsonl",
        "per-seed.json",
        "aggregate.json",
        "paired.json",
        "failure-slices.json",
        "evaluation-summary.json",
    }
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
    calls: dict[str, Any] = {}

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


def _model_load_smoke_fixture(tmp_path: Path) -> dict[str, Any]:
    execution_root = tmp_path / "execution-2542397cb134"
    execution_root.mkdir(mode=0o700)
    cache_root = (
        tmp_path / "hf-cache" / "models--sentence-transformers--all-MiniLM-L6-v2"
    )
    blob = cache_root / "blobs" / "opaque-model-blob"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"synthetic-base-model")
    base_model_path = (
        cache_root / "snapshots" / "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    base_model_path.mkdir(parents=True)
    (base_model_path / "weights.bin").symlink_to(
        os.path.relpath(blob, start=base_model_path)
    )
    base_rows = snapshot_model_files(base_model_path)
    base_manifest_sha256 = contract_sha256(base_rows)
    manifest_hashes: dict[tuple[str, int], str] = {}
    for arm, seeds in (("A", (7170,)), ("B", SEEDS), ("C", SEEDS)):
        for seed in seeds:
            output = execution_root / f"arm-{arm}" / f"seed-{seed}"
            output.mkdir(parents=True)
            if arm == "A":
                model_rows: list[dict[str, Any]] = []
            else:
                payload = f"synthetic-{arm}-{seed}".encode()
                model_sha256 = _write(output / "weights.bin", payload)
                model_rows = [
                    {
                        "path": "weights.bin",
                        "sha256": model_sha256,
                        "size": len(payload),
                    }
                ]
            (output / "train-run-summary.json").write_text("{}\n")
            manifest = _seal(
                {
                    "schema_version": "router-v2-pilot-model-manifest-v1",
                    "arm": arm,
                    "seed": seed,
                    "base_model_revision": ("1110a243fdf4706b3f48f1d95db1a4f5529b4d41"),
                    "base_model_file_manifest_sha256": base_manifest_sha256,
                    "model_file_manifest": model_rows,
                    "model_file_manifest_sha256": contract_sha256(model_rows),
                    "output_dir": f"arm-{arm}/seed-{seed}",
                },
                "model_manifest_sha256",
            )
            manifest_path = output / "model-manifest.json"
            manifest_hashes[(arm, seed)] = _write(manifest_path, _json_bytes(manifest))
    temporary_parent = tmp_path / "temporary-parent"
    temporary_parent.mkdir()
    return {
        "execution_root": execution_root,
        "base_model_path": base_model_path,
        "manifest_hashes": manifest_hashes,
        "temporary_parent": temporary_parent,
    }


class _SmokeEncoder:
    def __init__(
        self,
        *,
        arm: str,
        seed: int,
        model_path: Path,
        calls: list[dict[str, Any]],
        invalid: str | None = None,
    ) -> None:
        self.arm = arm
        self.seed = seed
        self.model_path = model_path
        self.calls = calls
        self.invalid = invalid

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        self.calls.append(
            {
                "arm": self.arm,
                "seed": self.seed,
                "model_path": self.model_path,
                "texts": texts,
                "normalize_embeddings": normalize_embeddings,
            }
        )
        dimension = 383 if self.invalid == "dimension" else 384
        rows = [[0.0] * dimension for _ in range(2)]
        if self.invalid == "finite":
            rows[0][0] = float("nan")
        return rows


def test_model_load_smoke_is_nonheldout_seven_model_canonical_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _model_load_smoke_fixture(tmp_path)
    execution_root = fixture["execution_root"]
    before = sorted(
        path.relative_to(execution_root).as_posix()
        for path in execution_root.rglob("*")
    )
    read_paths: list[Path] = []
    calls: list[dict[str, Any]] = []

    def forbidden(*_: Any, **__: Any) -> None:
        pytest.fail("evaluation authority/attempt/input derivation must not run")

    def read_bytes(path: Path) -> bytes:
        read_paths.append(path)
        return path.read_bytes()

    def factory(
        arm: str,
        seed: int,
        artifact: dict[str, Any],
        skills: list[dict[str, str]],
    ) -> _SmokeEncoder:
        assert skills == []
        model_path = Path(artifact["model_path"])
        if arm == "A":
            temporary_root = model_path.parent
            assert temporary_root.parent == fixture["temporary_parent"]
            assert os.stat(temporary_root).st_mode & 0o777 == 0o700
            assert model_path.name == "arm-A"
            assert all(not path.is_symlink() for path in model_path.rglob("*"))
        else:
            assert model_path == execution_root / f"arm-{arm}" / f"seed-{seed}"
        return _SmokeEncoder(
            arm=arm,
            seed=seed,
            model_path=model_path,
            calls=calls,
        )

    monkeypatch.setattr(runner, "run_evaluation_once", forbidden)
    monkeypatch.setattr(runner, "_start_attempt", forbidden)
    monkeypatch.setattr(runner, "_derive_inputs", forbidden)

    result = runner._run_model_load_smoke(
        execution_root=execution_root,
        base_model_path=fixture["base_model_path"],
        manifest_file_sha256=fixture["manifest_hashes"],
        model_factory=factory,
        read_bytes=read_bytes,
        temporary_parent=fixture["temporary_parent"],
    )

    assert result == {
        "schema_version": "router-v2-pilot-model-load-smoke-v1",
        "smoke_status": "PASS",
    }
    assert [(call["arm"], call["seed"]) for call in calls] == [
        ("A", 7170),
        ("B", 7170),
        ("B", 7171),
        ("B", 7172),
        ("C", 7170),
        ("C", 7171),
        ("C", 7172),
    ]
    assert all(
        call["texts"]
        == [
            "synthetic router query for non-heldout model-load smoke",
            "synthetic skill text for non-heldout model-load smoke",
        ]
        and call["normalize_embeddings"] is True
        for call in calls
    )
    assert len(read_paths) == 7
    assert all(path.name == "model-manifest.json" for path in read_paths)
    assert sorted(fixture["temporary_parent"].iterdir()) == []
    assert not (execution_root / "evaluation").exists()
    assert before == sorted(
        path.relative_to(execution_root).as_posix()
        for path in execution_root.rglob("*")
    )


def test_model_load_smoke_rejects_manifest_file_hash_before_loading(
    tmp_path: Path,
) -> None:
    fixture = _model_load_smoke_fixture(tmp_path)
    manifest = fixture["execution_root"] / "arm-B/seed-7171/model-manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")

    with pytest.raises(ValueError, match="model manifest file SHA-256 mismatch"):
        runner._run_model_load_smoke(
            execution_root=fixture["execution_root"],
            base_model_path=fixture["base_model_path"],
            manifest_file_sha256=fixture["manifest_hashes"],
            model_factory=lambda *_: pytest.fail("model must not load"),
            temporary_parent=fixture["temporary_parent"],
        )

    assert sorted(fixture["temporary_parent"].iterdir()) == []
    assert not (fixture["execution_root"] / "evaluation").exists()


@pytest.mark.parametrize("invalid", ["dimension", "finite"])
def test_model_load_smoke_rejects_invalid_embedding_and_cleans_temp(
    tmp_path: Path,
    invalid: str,
) -> None:
    fixture = _model_load_smoke_fixture(tmp_path)
    calls: list[dict[str, Any]] = []

    def factory(
        arm: str,
        seed: int,
        artifact: dict[str, Any],
        skills: list[dict[str, str]],
    ) -> _SmokeEncoder:
        del skills
        return _SmokeEncoder(
            arm=arm,
            seed=seed,
            model_path=Path(artifact["model_path"]),
            calls=calls,
            invalid=invalid if arm == "A" else None,
        )

    with pytest.raises(ValueError, match="dimension|finite"):
        runner._run_model_load_smoke(
            execution_root=fixture["execution_root"],
            base_model_path=fixture["base_model_path"],
            manifest_file_sha256=fixture["manifest_hashes"],
            model_factory=factory,
            temporary_parent=fixture["temporary_parent"],
        )

    assert len(calls) == 1
    assert sorted(fixture["temporary_parent"].iterdir()) == []
    assert not (fixture["execution_root"] / "evaluation").exists()


def test_model_load_smoke_cli_is_dedicated_and_has_no_evaluation_entrypoints() -> None:
    script = Path(__file__).parents[1] / "scripts/smoke_router_v2_pilot_models.py"
    source = script.read_text()
    assert "run_model_load_smoke" in source
    for forbidden in (
        "run_evaluation_once",
        "_start_attempt",
        "_derive_inputs",
        "heldout",
        "non-blind-test",
    ):
        assert forbidden not in source
    result = subprocess.run(
        [sys.executable, str(script), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--execution-root" in result.stdout
    assert "--base-model-path" in result.stdout


def _replay_fixture(tmp_path: Path) -> dict[str, Any]:
    request = _fixture(tmp_path / "repository")
    training_root = tmp_path / "training-execution-test"
    training_root.mkdir(mode=0o700)
    evaluation_root = tmp_path / "evaluation-execution-test"
    evaluation_root.mkdir(mode=0o700)
    overrides = _test_overrides(
        request,
        training_root,
        model_factory=lambda *_: pytest.fail("model must not load"),
    )
    context = overrides.prevalidated_context
    assert context is not None
    return {
        "request": request,
        "context": context,
        "training_root": training_root,
        "evaluation_root": evaluation_root,
        "base_model_path": context.base_model_path,
        "overrides": runner.ReplayTestOverrides(
            context=context,
            git_probe=lambda _: ("d" * 40, True),
            resolve_output_root=lambda value: Path(value).resolve(strict=True),
        ),
    }


def _tree_snapshot(root: Path) -> str:
    rows = []
    for path in (root, *sorted(root.rglob("*"))):
        metadata = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if path.is_symlink():
            kind = "symlink"
            content = os.readlink(path)
        elif path.is_file():
            kind = "file"
            content = _sha(path.read_bytes())
        else:
            kind = "directory"
            content = None
        rows.append(
            {
                "path": relative,
                "kind": kind,
                "mode": metadata.st_mode & 0o7777,
                "content": content,
            }
        )
    return contract_sha256(rows)


def test_replay_manifest_is_exact_canonical_and_pre_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _replay_fixture(tmp_path)

    def forbidden(*_: Any, **__: Any) -> None:
        pytest.fail("evaluation/training input path must not run")

    monkeypatch.setattr(runner, "run_evaluation_once", forbidden)
    monkeypatch.setattr(runner, "_start_attempt", forbidden)
    monkeypatch.setattr(runner, "_derive_inputs", forbidden)
    manifest = runner.prepare_replay_manifest(
        fixture["context"].repository_root,
        fixture["training_root"],
        fixture["evaluation_root"],
        fixture["base_model_path"],
        test_overrides=fixture["overrides"],
    )

    assert manifest["pilot_id"] == (
        "router-v2-v4-confusion-mined-pilot-002-eval-replay"
    )
    assert manifest["replacement_reason"] == ("INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE")
    assert manifest["replacement_fields"] == [
        "pilot_id",
        "attempt_token_sha256",
        "evaluation_code_git_commit",
        "evaluation_output_namespace",
        "replacement_reason",
    ]
    assert manifest["training_execution_id"] == "training-execution-test"
    assert manifest["training_execution_root"] == str(fixture["training_root"])
    assert manifest["evaluation_execution_id"] == "evaluation-execution-test"
    assert manifest["evaluation_output_namespace"] == str(fixture["evaluation_root"])
    assert (
        manifest["training_execution_root"] != manifest["evaluation_output_namespace"]
    )
    assert manifest["attempt_token_sha256"] != "e" * 64
    assert manifest["evaluation_code_git_commit"] == "d" * 40
    assert manifest["seeds"] == [7170, 7171, 7172]
    contract = manifest["evaluation_contract"]
    assert contract["arm_order"] == ["A", "B", "C"]
    assert contract["seed_order"] == [7170, 7171, 7172]
    assert contract["task_order"] == "ascending_task_id"
    assert contract["gate"]["comparison_scope"] == "A_VS_C_ONLY"
    for field, expected in {
        "reuses_frozen_training_artifacts_from_pilot_001": True,
        "pilot_001_metrics_observed": False,
        "review_mode": "MODEL_ONLY_PILOT",
        "human_reviewer_count": 0,
        "blind_v2_run": False,
        "production_ready": False,
        "release_eligible": False,
        "router_decision": "KEEP_BASELINE",
    }.items():
        assert manifest[field] == expected
    assert len(manifest["training_artifacts"]) == 9
    manifest_path = fixture["evaluation_root"] / "pilot-manifest.json"
    assert manifest_path.read_bytes() == _json_bytes(manifest)
    assert {path.name for path in fixture["evaluation_root"].iterdir()} == {
        "pilot-manifest.json"
    }
    assert (
        runner.prepare_replay_manifest(
            fixture["context"].repository_root,
            fixture["training_root"],
            fixture["evaluation_root"],
            fixture["base_model_path"],
            test_overrides=fixture["overrides"],
        )
        == manifest
    )


@pytest.mark.parametrize("drift", ["run-pack", "model-manifest", "model-file"])
def test_replay_drift_fails_before_manifest_or_attempt(
    tmp_path: Path,
    drift: str,
) -> None:
    fixture = _replay_fixture(tmp_path)
    request = fixture["request"]
    if drift == "run-pack":
        path = Path(request["run_pack_manifest_path"])
    elif drift == "model-manifest":
        path = Path(_arm_artifact(request, "B")["model_manifest_path"])
    else:
        path = Path(_arm_artifact(request, "C")["model_path"]) / "weights.bin"
    path.write_bytes(path.read_bytes() + b"drift")

    with pytest.raises(ValueError, match="SHA-256|snapshot|manifest"):
        runner.prepare_replay_manifest(
            fixture["context"].repository_root,
            fixture["training_root"],
            fixture["evaluation_root"],
            fixture["base_model_path"],
            test_overrides=fixture["overrides"],
        )

    assert sorted(fixture["evaluation_root"].iterdir()) == []
    assert not (fixture["evaluation_root"] / "attempt-1.started.json").exists()


def test_replay_preexisting_manifest_mismatch_fails_closed(tmp_path: Path) -> None:
    fixture = _replay_fixture(tmp_path)
    (fixture["evaluation_root"] / "pilot-manifest.json").write_text("{}\n")

    with pytest.raises(ValueError, match="pilot manifest mismatch"):
        runner.prepare_replay_manifest(
            fixture["context"].repository_root,
            fixture["training_root"],
            fixture["evaluation_root"],
            fixture["base_model_path"],
            test_overrides=fixture["overrides"],
        )

    assert not (fixture["evaluation_root"] / "attempt-1.started.json").exists()


def test_replay_manifest_uses_exact_shared_preregistered_contract(
    tmp_path: Path,
) -> None:
    fixture = _replay_fixture(tmp_path)
    manifest = runner.prepare_replay_manifest(
        fixture["context"].repository_root,
        fixture["training_root"],
        fixture["evaluation_root"],
        fixture["base_model_path"],
        test_overrides=fixture["overrides"],
    )

    contract = evaluation.preregistered_evaluation_contract()
    assert manifest["evaluation_contract"] == contract
    assert contract["metric_fields"] == [
        "recall_at_1",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "negative_hit_rate_at_1",
        "negative_hit_rate_at_5",
        "first_negative_rank_mean",
        "latency_p50_ms",
        "latency_p95_ms",
    ]
    assert contract["ranking"]["rounding"] == "ROUND_HALF_EVEN"
    assert contract["ranking"]["tie_break"] == "skill_id"
    assert contract["latency_percentiles"]["method"] == "nearest_rank"
    assert contract["metrics"]["aggregate_mean"] == "arithmetic"
    assert contract["metrics"]["aggregate_std"] == "sample_n_minus_1"
    assert contract["failure_slices"] == ["ALL", "category", "gold_skill_id", "flag"]


def test_replay_token_binds_models_base_and_evaluation_contract(tmp_path: Path) -> None:
    fixture = _replay_fixture(tmp_path)
    manifest = runner.prepare_replay_manifest(
        fixture["context"].repository_root,
        fixture["training_root"],
        fixture["evaluation_root"],
        fixture["base_model_path"],
        test_overrides=fixture["overrides"],
    )
    config = json.loads(
        Path(fixture["request"]["training_artifacts"][0]["config_path"]).read_text()
    )
    mutated_artifacts = deepcopy(manifest["training_artifacts"])
    mutated_artifacts[0]["model_file_manifest"][0]["sha256"] = "f" * 64
    mutated = runner._replay_manifest(
        context=fixture["context"],
        evaluation_root=fixture["evaluation_root"],
        evaluation_code_git_commit="d" * 40,
        training_artifacts=mutated_artifacts,
        lineage_config=config,
    )
    assert mutated["attempt_token_sha256"] != manifest["attempt_token_sha256"]


def test_replay_requires_test_only_authority(tmp_path: Path) -> None:
    fixture = _replay_fixture(tmp_path)
    production_context = replace(
        fixture["context"],
        authority=replace(fixture["context"].authority, test_only=False),
    )
    overrides = replace(fixture["overrides"], context=production_context)

    with pytest.raises(ValueError, match="test authority"):
        runner.prepare_replay_manifest(
            production_context.repository_root,
            fixture["training_root"],
            fixture["evaluation_root"],
            fixture["base_model_path"],
            test_overrides=overrides,
        )


def test_replay_rejects_output_descendant_of_training_root(tmp_path: Path) -> None:
    fixture = _replay_fixture(tmp_path)
    nested = fixture["training_root"] / "pilot-002-output"
    nested.mkdir(mode=0o700)
    overrides = replace(
        fixture["overrides"],
        resolve_output_root=lambda value: Path(value).resolve(strict=True),
    )

    with pytest.raises(ValueError, match="sibling|ancestor|descendant"):
        runner.prepare_replay_manifest(
            fixture["context"].repository_root,
            fixture["training_root"],
            nested,
            fixture["base_model_path"],
            test_overrides=overrides,
        )


def test_replay_rejects_output_root_swap_before_manifest_write(tmp_path: Path) -> None:
    fixture = _replay_fixture(tmp_path)
    output = fixture["evaluation_root"]
    moved = tmp_path / "moved-output"
    outside = tmp_path / "outside-output"
    outside.mkdir(mode=0o700)
    swapped = False

    def swapping_read(path: Path) -> bytes:
        nonlocal swapped
        if not swapped:
            output.rename(moved)
            output.symlink_to(outside, target_is_directory=True)
            swapped = True
        return path.read_bytes()

    overrides = replace(fixture["overrides"], read_bytes=swapping_read)
    with pytest.raises(ValueError, match="replaced|identity|symlink"):
        runner.prepare_replay_manifest(
            fixture["context"].repository_root,
            fixture["training_root"],
            output,
            fixture["base_model_path"],
            test_overrides=overrides,
        )
    assert not (outside / "pilot-manifest.json").exists()


def test_replay_freshly_hashes_all_frozen_source_files(tmp_path: Path) -> None:
    _replay_fixture(tmp_path)
    bindings = {}
    for name in (
        "accepted_pairs",
        "data_manifest",
        "mining_rows",
        "mining_manifest",
        "heldout_labels",
    ):
        path = tmp_path / f"{name}.bin"
        payload = name.encode()
        path.write_bytes(payload)
        bindings[name] = {"path": str(path), "sha256": _sha(payload)}

    assert runner._validate_replay_frozen_files(bindings, Path.read_bytes) == bindings
    Path(bindings["heldout_labels"]["path"]).write_bytes(b"drift")
    with pytest.raises(ValueError, match="heldout_labels SHA-256"):
        runner._validate_replay_frozen_files(bindings, Path.read_bytes)


def test_replay_refresh_reloads_run_pack_and_training_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _replay_fixture(tmp_path)
    calls: list[str] = []

    def load(
        request: dict[str, Any], read_bytes: Any
    ) -> tuple[dict[str, bytes], dict[str, Any]]:
        del request, read_bytes
        calls.append("run-pack")
        return {"fresh": b"current"}, {}

    def verify(
        request: dict[str, Any],
        read_bytes: Any,
        documents: dict[str, bytes],
    ) -> list[dict[str, Any]]:
        del request, read_bytes
        assert documents == {"fresh": b"current"}
        calls.append("artifacts")
        return [{"fresh": True}]

    monkeypatch.setattr(runner, "_load_run_pack", load)
    monkeypatch.setattr(runner, "_verify_training_artifacts", verify)
    refreshed = runner._refresh_replay_context(fixture["context"], Path.read_bytes)
    assert calls == ["run-pack", "artifacts"]
    assert refreshed.run_pack_documents == {"fresh": b"current"}
    assert refreshed.training_artifacts == [{"fresh": True}]


def test_replay_revalidation_uses_fresh_run_pack_config_bytes_without_second_read(
    tmp_path: Path,
) -> None:
    fixture = _replay_fixture(tmp_path)
    context = fixture["context"]
    artifact = _arm_artifact(context.request, "A")
    config_path = Path(artifact["config_path"])
    config_payload = config_path.read_bytes()
    artifact["config_file_sha256"] = None
    context.run_pack_documents[
        f"config-arm-{artifact['arm']}-seed-{artifact['seed']}.json"
    ] = config_payload
    config_reads = 0

    def drifting_read(path: Path) -> bytes:
        nonlocal config_reads
        if path == config_path:
            config_reads += 1
            return config_payload + b" "
        return path.read_bytes()

    verified, config, _ = runner._revalidate_replay_artifacts(context, drifting_read)

    assert config_reads == 0
    assert config["config_sha256"] == json.loads(config_payload)["config_sha256"]
    assert verified[0]["config_file_sha256"] == _sha(config_payload)


def test_replay_root_swap_in_exact_pre_start_gap_cannot_target_training_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _replay_fixture(tmp_path)
    output = fixture["evaluation_root"]
    moved = tmp_path / "moved-evaluation-output"
    training_evaluation = fixture["training_root"] / "evaluation"
    training_evaluation.mkdir(mode=0o700)
    original = runner._replay_attempt_context

    def swap_after_final_revalidation(**kwargs: Any) -> Any:
        context = original(**kwargs)
        output.rename(moved)
        output.symlink_to(fixture["training_root"], target_is_directory=True)
        return context

    monkeypatch.setattr(
        runner, "_replay_attempt_context", swap_after_final_revalidation
    )
    monkeypatch.setattr(
        runner,
        "_derive_inputs",
        lambda *_: (_ for _ in ()).throw(RuntimeError("stop after marker")),
    )
    overrides = replace(
        fixture["overrides"],
        model_factory=lambda _arm, _seed, _artifact, skills: FakeEncoder(skills),
    )

    with pytest.raises(ValueError, match="replaced|identity|symlink"):
        runner.run_replay_evaluation_once(
            fixture["context"].repository_root,
            fixture["training_root"],
            output,
            fixture["base_model_path"],
            test_overrides=overrides,
        )

    assert not (training_evaluation / "attempt-1.started.json").exists()
    assert not (training_evaluation / "attempt-1.terminal.json").exists()


def test_synthetic_replay_runner_uses_pilot002_token_and_preserves_training_root(
    tmp_path: Path,
) -> None:
    fixture = _replay_fixture(tmp_path)
    frozen = fixture["training_root"] / "frozen-evidence"
    frozen.mkdir(mode=0o700)
    (frozen / "pilot-001-evidence.json").write_bytes(b"frozen-pilot-001")
    before = _tree_snapshot(fixture["training_root"])
    ticks = iter(range(0, 10_000_000_000, 1_000_000))
    overrides = replace(
        fixture["overrides"],
        model_factory=lambda _arm, _seed, _artifact, skills: FakeEncoder(skills),
        clock_ns=lambda: next(ticks),
    )
    summary = runner.run_replay_evaluation_once(
        fixture["context"].repository_root,
        fixture["training_root"],
        fixture["evaluation_root"],
        fixture["base_model_path"],
        test_overrides=overrides,
    )
    manifest = json.loads(
        (fixture["evaluation_root"] / "pilot-manifest.json").read_text()
    )
    started = json.loads(
        (fixture["evaluation_root"] / "evaluation/attempt-1.started.json").read_text()
    )
    assert started["attempt_token_sha256"] == manifest["attempt_token_sha256"]
    assert summary["router_decision"] == "KEEP_BASELINE"
    assert _tree_snapshot(fixture["training_root"]) == before


def test_replay_cli_is_dedicated() -> None:
    script = (
        Path(__file__).parents[1] / "scripts/run_router_v2_pilot_evaluation_replay.py"
    )
    source = script.read_text()
    assert "run_replay_evaluation_once" in source
    result = subprocess.run(
        [sys.executable, str(script), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--training-execution-root" in result.stdout
    assert "--evaluation-output-root" in result.stdout
