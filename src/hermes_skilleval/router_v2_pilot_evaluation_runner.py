from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from hermes_skilleval.router_v2_pilot_evaluation import (
    ARMS,
    SEEDS,
    build_aggregate_results,
    build_evaluation_plan_contract,
    build_evaluation_summary,
    build_failure_slices,
    build_paired_results,
    build_per_seed_result,
    build_route_row,
    contract_sha256,
    quantize8,
)
from hermes_skilleval.router_v2_internal_package import HELDOUT_ROW_FIELDS
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_run_pack import (
    RUN_PACK_RELATIVE_PATH,
    validate_run_pack_documents,
)
from hermes_skilleval.router_v2_pilot_runtime import (
    AUTHORIZED_OUTPUT_ROOT,
    TRUTH_FIELDS,
    _atomic_publish_noreplace_dirfd,
    canonical_json_line,
    resolve_authorized_output_root,
    snapshot_model_files,
    validate_frozen_config,
    validate_model_manifest_contract,
    validate_run_summary,
)
from hermes_skilleval.router_v2_reviewed_source import CANDIDATE_FIELDS
from hermes_skilleval.router_v2_reviewed_source import (
    CANONICAL_CANDIDATES,
    CANONICAL_MANIFEST,
    CANONICAL_SKILL_INDEX,
)
from hermes_skilleval.skill_index import SKILL_FIELDS


class EvaluationEncoder(Protocol):
    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]: ...


class _LocalSentenceTransformerEncoder:
    def __init__(self, model_path: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real evaluation"
            ) from exc
        self._model = SentenceTransformer(
            model_path,
            device="cpu",
            local_files_only=True,
        )

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        value = self._model.encode(texts, normalize_embeddings=normalize_embeddings)
        if hasattr(value, "tolist"):
            value = value.tolist()
        _require(type(value) is list, "encoder output cannot be converted to list")
        return cast(list[list[float]], value)


ModelFactory = Callable[
    [str, int, dict[str, Any], list[dict[str, str]]], EvaluationEncoder
]
ReadBytes = Callable[[Path], bytes]
GitProbe = Callable[[Path], tuple[str, bool]]


@dataclass(frozen=True)
class PilotAuthority:
    test_only: bool = False
    source_candidates_sha256: str = (
        "5fa7e7feb1a5fedc2cf8bcc8adf17afe3356f9d4614b2848b0d74f88718e3d2a"
    )
    source_manifest_sha256: str = (
        "330f13d58833450293374f91e253dadf452b5a7d5233a4aa025984e09b0ed511"
    )
    skill_index_sha256: str = (
        "c67a786a6dcdc6f71716894f22f8ba409c38ec0954a07143b09a0372159ccaf5"
    )
    heldout_labels_sha256: str = (
        "b7c43c8fa829f0584d9bdfc2804e5d38044b4bfa72fe0cf44ca68370018e6219"
    )
    run_pack_manifest_sha256: str = (
        "6a7b48d1d6a27e15dfd2a1d1a01790706629227313787899bee9d2ab159a88f3"
    )
    run_pack_manifest_file_sha256: str = (
        "efa8edcc0349726575d2adc35dd5e9febb1b64dfc860fae26a89807add91deb8"
    )
    training_code_git_commit: str = "2542397cb1341ee5f0a05e91ea82c4530e49a44b"
    evaluation_code_git_commit: str | None = None
    execution_id: str = "execution-2542397cb134"
    source_candidates_path: str = CANONICAL_CANDIDATES
    source_manifest_path: str = CANONICAL_MANIFEST
    skill_index_path: str = CANONICAL_SKILL_INDEX
    heldout_labels_path: str = (
        "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-001/package/"
        "router-v2-v4-internal-training-package-001/heldout-labels.jsonl"
    )


@dataclass(frozen=True)
class EvaluationTestOverrides:
    authority: PilotAuthority
    model_factory: ModelFactory | None = None
    read_bytes: ReadBytes = Path.read_bytes
    clock_ns: Callable[[], int] = time.perf_counter_ns
    git_probe: GitProbe | None = None
    resolve_output_root: Callable[[Path | str], Path] | None = None
    prevalidated_context: ValidatedAuthorityContext | None = None


@dataclass
class ValidatedAuthorityContext:
    authority: PilotAuthority
    repository_root: Path
    execution_root: Path
    base_model_path: Path
    request: dict[str, Any]
    run_pack_documents: dict[str, bytes]
    training_artifacts: list[dict[str, Any]]


PRODUCTION_AUTHORITY = PilotAuthority()

_FORBIDDEN_PATH_MARKERS = (
    "calibration",
    "blind-v2",
    "blind_v2",
    "old-blind",
    "old_blind",
    "phase16",
    "phase-16",
    "phase_16",
)
_INPUT_HASH_FIELDS = {
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "heldout_labels_sha256",
    "run_pack_manifest_sha256",
}
_ARTIFACT_KINDS = (
    "config",
    "run_summary",
    "model_manifest",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return canonical_json_line(value).encode("utf-8")


def _default_git_probe(repository_root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return commit, status == ""


def _default_model_factory(
    arm: str,
    seed: int,
    artifact: dict[str, Any],
    skills: list[dict[str, str]],
) -> EvaluationEncoder:
    del arm, seed, skills
    return _LocalSentenceTransformerEncoder(artifact["model_path"])


def _validated_request(request: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "repository_root",
        "source_candidates_path",
        "source_manifest_path",
        "skill_index_path",
        "heldout_labels_path",
        "run_pack_manifest_path",
        "run_pack_root",
        "run_pack_internal_sha256",
        "expected_hashes",
        "expected_task_bindings_sha256",
        "training_artifacts",
        "training_code_git_commit",
        "evaluation_code_git_commit",
        "attempt_token_sha256",
    }
    _require(
        type(request) is dict and set(request) == fields,
        "runner request schema mismatch",
    )
    for field in fields - {
        "expected_hashes",
        "expected_task_bindings_sha256",
        "training_artifacts",
    }:
        _require(
            type(request[field]) is str and bool(request[field]),
            f"runner {field} mismatch",
        )
    _require(
        request["expected_task_bindings_sha256"] is None
        or (
            type(request["expected_task_bindings_sha256"]) is str
            and len(request["expected_task_bindings_sha256"]) == 64
        ),
        "runner task binding authority mismatch",
    )
    expected_hashes = request["expected_hashes"]
    _require(
        type(expected_hashes) is dict and set(expected_hashes) == _INPUT_HASH_FIELDS,
        "runner input hash schema mismatch",
    )
    _require(
        all(
            type(value) is str and len(value) == 64
            for value in expected_hashes.values()
        ),
        "runner input hash mismatch",
    )
    _require(
        type(request["training_artifacts"]) is list
        and len(request["training_artifacts"]) == 9,
        "runner training artifact count mismatch",
    )
    artifact_fields = {"arm", "seed", "model_path"} | {
        f"{kind}_{suffix}"
        for kind in _ARTIFACT_KINDS
        for suffix in ("path", "file_sha256")
    }
    seen = set()
    for row in request["training_artifacts"]:
        _require(
            type(row) is dict and set(row) == artifact_fields,
            "runner training artifact schema mismatch",
        )
        _require(
            type(row["arm"]) is str and row["arm"] in ARMS,
            "runner training arm mismatch",
        )
        _require(
            type(row["seed"]) is int and row["seed"] in SEEDS,
            "runner training seed mismatch",
        )
        _require(
            (row["arm"], row["seed"]) not in seen, "runner duplicate training artifact"
        )
        seen.add((row["arm"], row["seed"]))
        for field in artifact_fields - {"arm", "seed"}:
            if field.endswith("_file_sha256"):
                _require(
                    row[field] is None
                    or (type(row[field]) is str and len(row[field]) == 64),
                    f"runner training {field} mismatch",
                )
            else:
                _require(
                    type(row[field]) is str and bool(row[field]),
                    f"runner training {field} mismatch",
                )
    _require(
        seen == {(arm, seed) for arm in ARMS for seed in SEEDS},
        "runner training artifact grid mismatch",
    )
    for field in (
        "source_candidates_path",
        "source_manifest_path",
        "skill_index_path",
        "heldout_labels_path",
        "run_pack_manifest_path",
    ):
        lowered = request[field].lower()
        _require(
            not any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS),
            f"forbidden evaluation input path: {field}",
        )
    return request


def _reject_forbidden_request_paths(request: dict[str, Any]) -> None:
    for field in (
        "source_candidates_path",
        "source_manifest_path",
        "skill_index_path",
        "heldout_labels_path",
        "run_pack_manifest_path",
    ):
        lowered = str(request.get(field, "")).lower()
        _require(
            not any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS),
            f"forbidden evaluation input path: {field}",
        )


def _evaluation_root(execution_root: Path) -> Path:
    root = execution_root.resolve(strict=True)
    metadata = root.stat()
    _require(
        stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o700,
        "execution root must be a 0700 directory",
    )
    target = root / "evaluation"
    created = False
    try:
        target.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        _require(
            target.is_dir() and not target.is_symlink(),
            "evaluation root is not a directory",
        )
        _require(
            stat.S_IMODE(target.stat().st_mode) == 0o700,
            "evaluation root must be mode 0700",
        )
    if created:
        _fsync_directory(root)
    return target


def _write_noreplace(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            _require(written > 0, "atomic write made no progress")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _start_attempt(evaluation_root: Path, request: dict[str, Any]) -> Path:
    started = evaluation_root / "attempt-1.started.json"
    terminal = evaluation_root / "attempt-1.terminal.json"
    artifacts = evaluation_root / "artifacts"
    staging = evaluation_root / ".attempt-1.staging"
    _require(
        not any(
            path.exists() or path.is_symlink()
            for path in (started, terminal, artifacts, staging)
        ),
        "evaluation attempt already exists",
    )
    marker = {
        "schema_version": "router-v2-evaluation-attempt-started-v1",
        "attempt_number": 1,
        "attempt_token_sha256": request["attempt_token_sha256"],
        "status": "STARTED",
        **TRUTH_FIELDS,
    }
    marker_written = False
    try:
        _write_noreplace(started, _canonical_bytes(marker))
        marker_written = True
        _fsync_directory(evaluation_root)
    except FileExistsError as exc:
        raise ValueError("evaluation attempt already exists") from exc
    except BaseException as exc:
        if marker_written:
            try:
                _write_terminal(
                    evaluation_root,
                    request,
                    status="FAILED",
                    error=exc,
                )
            except BaseException:
                pass
        raise
    return staging


def _write_terminal(
    evaluation_root: Path,
    request: dict[str, Any],
    *,
    status: str,
    summary: dict[str, Any] | None = None,
    error: BaseException | None = None,
    plan_sha256: str | None = None,
    artifacts_manifest_sha256: str | None = None,
) -> None:
    terminal = {
        "schema_version": "router-v2-evaluation-attempt-terminal-v1",
        "attempt_number": 1,
        "attempt_token_sha256": request["attempt_token_sha256"],
        "status": status,
        "pilot_evaluation_conclusion": (
            summary["pilot_evaluation_conclusion"]
            if summary is not None
            else "KEEP_BASELINE"
        ),
        "error_type": type(error).__name__ if error is not None else None,
        "plan_sha256": plan_sha256,
        "summary_sha256": summary.get("summary_sha256") if summary else None,
        "artifacts_manifest_sha256": artifacts_manifest_sha256,
        **TRUTH_FIELDS,
    }
    _write_noreplace(
        evaluation_root / "attempt-1.terminal.json", _canonical_bytes(terminal)
    )
    _fsync_directory(evaluation_root)


def _write_recovery_required(
    evaluation_root: Path,
    *,
    plan_sha256: str | None,
    summary_sha256: str | None,
    artifacts_manifest_sha256: str | None,
    error: BaseException,
) -> None:
    recovery = {
        "schema_version": "router-v2-evaluation-recovery-required-v1",
        "status": "ARTIFACTS_PUBLISHED_RECOVERY_REQUIRED",
        "plan_sha256": plan_sha256,
        "summary_sha256": summary_sha256,
        "artifacts_manifest_sha256": artifacts_manifest_sha256,
        "error_type": type(error).__name__,
        **TRUTH_FIELDS,
    }
    _write_noreplace(
        evaluation_root / "attempt-1.recovery-required.json",
        _canonical_bytes(recovery),
    )
    _fsync_directory(evaluation_root)


def _read_verified(
    path: str, expected_sha256: str | None, read_bytes: ReadBytes, label: str
) -> bytes:
    payload = read_bytes(Path(path))
    if expected_sha256 is not None:
        _require(_sha(payload) == expected_sha256, f"{label} SHA-256 mismatch")
    return payload


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    _require(type(value) is dict, f"{label} must be an object")
    return value


def _jsonl_with_bytes(payload: bytes, label: str) -> list[tuple[dict[str, Any], bytes]]:
    _require(payload.endswith(b"\n"), f"{label} must end with LF")
    output = []
    for line in payload.splitlines(keepends=True):
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} contains invalid JSONL") from exc
        _require(
            type(value) is dict and line == _canonical_bytes(value),
            f"{label} must be canonical JSONL",
        )
        output.append((value, line))
    return output


def _derive_inputs(
    request: dict[str, Any], read_bytes: ReadBytes
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    hashes = request["expected_hashes"]
    source_payload = _read_verified(
        request["source_candidates_path"],
        hashes["source_candidates_sha256"],
        read_bytes,
        "source candidates",
    )
    source_manifest_payload = _read_verified(
        request["source_manifest_path"],
        hashes["source_manifest_sha256"],
        read_bytes,
        "source manifest",
    )
    skills_payload = _read_verified(
        request["skill_index_path"],
        hashes["skill_index_sha256"],
        read_bytes,
        "skill index",
    )
    labels_payload = _read_verified(
        request["heldout_labels_path"],
        hashes["heldout_labels_sha256"],
        read_bytes,
        "held-out labels",
    )
    source_manifest = _json_object(source_manifest_payload, "source manifest")
    manifest_records = source_manifest.get("records")
    _require(type(manifest_records) is list, "source manifest records must be a list")
    manifest_records = cast(list[Any], manifest_records)
    source_pairs = _jsonl_with_bytes(source_payload, "source candidates")
    _require(
        len(manifest_records) == len(source_pairs),
        "source manifest record count mismatch",
    )
    restored_rows = []
    for index, ((row, exact_bytes), record) in enumerate(
        zip(source_pairs, manifest_records, strict=True), start=1
    ):
        _require(set(row) == CANDIDATE_FIELDS, "reviewed source exact schema mismatch")
        _require(type(record) is dict, "source manifest record mismatch")
        exact_hash = _sha(exact_bytes)
        _require(
            record.get("source_record_exact_bytes_sha256") == exact_hash,
            f"source manifest record {index} exact hash mismatch",
        )
        for field in (
            "source_record_id",
            "source_role",
            "split",
            "positive_skill_id",
            "skill_id",
            "prompt_text_sha256",
        ):
            _require(
                record.get(field) == row.get(field),
                f"source manifest record {index} {field} mismatch",
            )
        query = row.get("query_text")
        _require(
            type(query) is str
            and _sha(query.encode("utf-8")) == row.get("prompt_text_sha256"),
            "reviewed source prompt hash mismatch",
        )
        restored_rows.append({**row, "source_record_exact_bytes_sha256": exact_hash})
    source_rows = [
        row
        for row in restored_rows
        if row["split"] == "non_blind_test" and row["source_role"] == "POSITIVE"
    ]
    source_rows.sort(key=lambda row: row["task_id"])
    _require(len(source_rows) == 16, "non-blind positive task count must be 16")
    source_by_task = {row["task_id"]: row for row in source_rows}
    _require(len(source_by_task) == 16, "duplicate non-blind task")

    try:
        skill_records = json.loads(skills_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("skill index is invalid JSON") from exc
    _require(
        type(skill_records) is list and len(skill_records) == 16,
        "skill index count must be 16",
    )
    skill_by_id = {}
    for skill in skill_records:
        _require(
            type(skill) is dict and set(skill) == SKILL_FIELDS,
            "skill row exact schema mismatch",
        )
        _require(
            all(
                type(skill[field]) is str
                for field in ("id", "name", "path", "description", "body")
            )
            and type(skill["category"]) is str
            and type(skill["trigger_terms"]) is list
            and all(type(term) is str for term in skill["trigger_terms"])
            and type(skill["token_count_estimate"]) is int,
            "skill row field mismatch",
        )
        _require(skill["id"] not in skill_by_id, "duplicate skill id")
        skill_by_id[skill["id"]] = skill
    skill_ids = set(skill_by_id)
    _require(
        {row["positive_skill_id"] for row in source_rows} == skill_ids,
        "source gold skills do not match skill index",
    )
    skills = [
        {"skill_id": skill_id, "skill_text": _skill_text(skill_by_id[skill_id])}
        for skill_id in sorted(skill_ids)
    ]

    labels = []
    labels_by_task = {}
    for row, _ in _jsonl_with_bytes(labels_payload, "held-out labels"):
        _require(set(row) == HELDOUT_ROW_FIELDS, "held-out label exact schema mismatch")
        unhashed = {key: value for key, value in row.items() if key != "row_sha256"}
        _require(
            row["row_sha256"] == contract_sha256(unhashed),
            "held-out label row hash mismatch",
        )
        _require(
            row["task_id"] in source_by_task and row["task_id"] not in labels_by_task,
            "held-out task alignment mismatch",
        )
        _require(
            row["usage"] == "HELD_OUT_EVAL_ONLY"
            and row["training_eligible"] is False
            and row["mining_eligible"] is False,
            "held-out eligibility boundary mismatch",
        )
        source = source_by_task[row["task_id"]]
        candidate = skill_by_id.get(row["candidate_skill_id"])
        gold = skill_by_id.get(source["positive_skill_id"])
        _require(
            candidate is not None and gold is not None and candidate is not gold,
            "held-out candidate mismatch",
        )
        candidate = cast(dict[str, Any], candidate)
        gold = cast(dict[str, Any], gold)
        exact = {
            "query_text": source["query_text"],
            "query_sha256": source["prompt_text_sha256"],
            "positive_source_record_id": source["source_record_id"],
            "positive_source_record_exact_bytes_sha256": source[
                "source_record_exact_bytes_sha256"
            ],
            "gold_skill_id": source["positive_skill_id"],
            "gold_skill_record_sha256": contract_sha256(gold),
            "candidate_skill_text": _skill_text(candidate),
            "candidate_skill_text_sha256": contract_sha256(_skill_text(candidate)),
            "candidate_skill_record_sha256": contract_sha256(candidate),
            "source_snapshot_id": source_manifest.get("snapshot_id"),
            "source_candidates_sha256": hashes["source_candidates_sha256"],
            "source_manifest_sha256": hashes["source_manifest_sha256"],
            "skill_index_sha256": hashes["skill_index_sha256"],
        }
        _require(
            all(row.get(field) == value for field, value in exact.items()),
            "held-out source or skill binding mismatch",
        )
        labels.append(row)
        labels_by_task[row["task_id"]] = row
    _require(len(labels) == 9, "supported held-out label count must be 9")

    bindings = []
    for source in source_rows:
        label = labels_by_task.get(source["task_id"])
        bindings.append(
            {
                "task_id": source["task_id"],
                "source_record_id": source["source_record_id"],
                "source_record_exact_bytes_sha256": source[
                    "source_record_exact_bytes_sha256"
                ],
                "query_sha256": source["prompt_text_sha256"],
                "gold_skill_id": source["positive_skill_id"],
                "category": skill_by_id[source["positive_skill_id"]]["category"],
                "supported_negative_skill_id": label["candidate_skill_id"]
                if label is not None
                else None,
                "heldout_label_row_sha256": label["row_sha256"]
                if label is not None
                else None,
                "heldout_usage": label["usage"] if label is not None else None,
            }
        )
    if request["expected_task_bindings_sha256"] is not None:
        _require(
            contract_sha256(bindings) == request["expected_task_bindings_sha256"],
            "external task binding commitment mismatch",
        )
    return bindings, source_by_task, skills, labels


def _load_run_pack(
    request: dict[str, Any], read_bytes: ReadBytes
) -> tuple[dict[str, bytes], dict[str, Any]]:
    root = Path(request["run_pack_root"]).resolve(strict=True)
    _require(root.is_dir() and not root.is_symlink(), "run-pack root must be real")
    documents = {}
    for path in root.iterdir():
        _require(path.is_file() and not path.is_symlink(), "run-pack contains non-file")
        documents[path.name] = read_bytes(path)
    manifest_payload = documents.get("run-pack-manifest.json")
    _require(type(manifest_payload) is bytes, "run-pack manifest is missing")
    manifest_payload = cast(bytes, manifest_payload)
    _require(
        _sha(manifest_payload)
        == request["expected_hashes"]["run_pack_manifest_sha256"],
        "run-pack manifest file SHA-256 mismatch",
    )
    manifest = validate_run_pack_documents(documents)
    _require(
        manifest.get("manifest_sha256") == request["run_pack_internal_sha256"],
        "run-pack internal manifest SHA-256 mismatch",
    )
    _require(
        manifest.get("training_code_git_commit") == request["training_code_git_commit"],
        "run-pack training commit mismatch",
    )
    return documents, manifest


def _verify_training_artifacts(
    request: dict[str, Any],
    read_bytes: ReadBytes,
    run_pack_documents: dict[str, bytes],
) -> list[dict[str, Any]]:
    output = []
    for row in sorted(
        request["training_artifacts"],
        key=lambda item: (ARMS.index(item["arm"]), item["seed"]),
    ):
        config = _json_object(
            run_pack_documents[f"config-arm-{row['arm']}-seed-{row['seed']}.json"],
            "config",
        )
        summary = _json_object(
            _read_verified(
                row["run_summary_path"],
                row["run_summary_file_sha256"],
                read_bytes,
                f"{row['arm']}-{row['seed']} run summary",
            ),
            "run summary",
        )
        manifest = _json_object(
            _read_verified(
                row["model_manifest_path"],
                row["model_manifest_file_sha256"],
                read_bytes,
                f"{row['arm']}-{row['seed']} model manifest",
            ),
            "model manifest",
        )
        handoff = _json_object(run_pack_documents["sealed-handoff.json"], "handoff")
        plan = _json_object(
            run_pack_documents[f"sampler-plan-seed-{row['seed']}.json"],
            "sampler plan",
        )
        validate_frozen_config(config, handoff, plan)
        validate_run_summary(summary, config, handoff, plan)
        validate_model_manifest_contract(manifest, config, summary, handoff, plan)
        row["_validated_model_file_manifest"] = _validate_model_snapshot(
            artifact=row, config=config, manifest=manifest
        )
        output.append(
            {
                "arm": row["arm"],
                "seed": row["seed"],
                "config_sha256": config["config_sha256"],
                "run_summary_sha256": summary["summary_sha256"],
                "model_manifest_sha256": manifest["model_manifest_sha256"],
                "model_file_manifest_sha256": manifest["model_file_manifest_sha256"],
            }
        )
    return output


def _validate_model_snapshot(
    artifact: dict[str, Any],
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    model_path = Path(artifact["model_path"]).resolve(strict=True)
    if artifact["arm"] == "A":
        snapshot = snapshot_model_files(model_path)
        expected_snapshot_sha = config["base_model_file_manifest_sha256"]
    else:
        allowed = {
            "train-run-summary.json",
            "model-manifest.json",
            *(row["path"] for row in manifest["model_file_manifest"]),
        }
        actual = {
            path.relative_to(model_path).as_posix()
            for path in model_path.rglob("*")
            if path.is_file()
        }
        _require(actual == allowed, "trained model directory contains extra files")
        snapshot = []
        for expected in manifest["model_file_manifest"]:
            path = model_path / expected["path"]
            _require(
                path.is_file() and not path.is_symlink(),
                "trained model snapshot path mismatch",
            )
            payload = path.read_bytes()
            snapshot.append(
                {
                    "path": expected["path"],
                    "sha256": _sha(payload),
                    "size": len(payload),
                }
            )
        _require(
            manifest["model_file_manifest"] == snapshot,
            "trained model snapshot file list mismatch",
        )
        expected_snapshot_sha = manifest["model_file_manifest_sha256"]
    _require(
        contract_sha256(snapshot) == expected_snapshot_sha,
        "model snapshot SHA-256 mismatch",
    )
    return snapshot


def _rank(
    encoder: EvaluationEncoder,
    skills: list[dict[str, str]],
    skill_embeddings: list[list[float]],
    query_text: str,
    clock_ns: Callable[[], int],
) -> tuple[list[str], list[str], int]:
    encoder.encode([query_text], normalize_embeddings=True)
    started = clock_ns()
    query_vectors = encoder.encode([query_text], normalize_embeddings=True)
    _require(
        type(query_vectors) is list and len(query_vectors) == 1,
        "query embedding shape mismatch",
    )
    query = query_vectors[0]
    _require(
        type(query) is list
        and len(query) > 0
        and all(
            type(value) in {int, float} and math.isfinite(value) for value in query
        ),
        "query embedding must be finite",
    )
    _require(
        len(skill_embeddings) == 16
        and all(len(vector) == len(query) for vector in skill_embeddings),
        "skill embedding shape mismatch",
    )
    scored = []
    for skill, vector in zip(skills, skill_embeddings, strict=True):
        _require(
            all(
                type(value) in {int, float} and math.isfinite(value) for value in vector
            ),
            "skill embedding must be finite",
        )
        score = sum(
            float(left) * float(right)
            for left, right in zip(query, vector, strict=True)
        )
        scored.append((skill["skill_id"], quantize8(score)))
    scored.sort(key=lambda item: (-Decimal(item[1]), item[0]))
    finished = clock_ns()
    _require(
        type(started) is int and type(finished) is int and finished >= started,
        "evaluation clock mismatch",
    )
    raw_latency_ns = finished - started
    return (
        [item[0] for item in scored],
        [item[1] for item in scored],
        raw_latency_ns,
    )


def _copy_model_inputs(
    staging: Path,
    request: dict[str, Any],
) -> dict[tuple[str, int], dict[str, Any]]:
    copied = {}
    by_key = {(row["arm"], row["seed"]): row for row in request["training_artifacts"]}
    for arm in ARMS:
        for seed in SEEDS:
            artifact = by_key[(arm, seed)]
            source = Path(artifact["model_path"]).resolve(strict=True)
            manifest_rows = artifact["_validated_model_file_manifest"]
            target = staging / "model-inputs" / f"arm-{arm}-seed-{seed}"
            target.mkdir(parents=True, mode=0o700)
            for row in manifest_rows:
                source_file = source / row["path"]
                _require(
                    source_file.is_file() and not source_file.is_symlink(),
                    "model copy source mismatch",
                )
                target_file = target / row["path"]
                target_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(source_file, target_file)
            _require(
                snapshot_model_files(target) == manifest_rows,
                "private model copy verification mismatch",
            )
            copied[(arm, seed)] = {**artifact, "model_path": str(target)}
    return copied


def _write_artifact(path: Path, payload: bytes) -> None:
    _write_noreplace(path, payload)


def _run_request_once(
    *,
    execution_root: Path | str,
    request: dict[str, Any],
    model_factory: ModelFactory | None = None,
    read_bytes: ReadBytes = Path.read_bytes,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
    git_probe: GitProbe = _default_git_probe,
    prevalidated_context: ValidatedAuthorityContext | None = None,
) -> dict[str, Any]:
    if prevalidated_context is None:
        request = _validated_request(request)
    repository_root = Path(request["repository_root"]).resolve(strict=True)
    commit, clean = git_probe(repository_root)
    _require(
        clean and commit == request["evaluation_code_git_commit"],
        "evaluation code must be a clean exact commit",
    )
    evaluation_root = _evaluation_root(Path(execution_root))
    staging = _start_attempt(evaluation_root, request)
    factory = model_factory or _default_model_factory
    summary: dict[str, Any] | None = None
    plan_sha256: str | None = None
    artifacts_manifest_sha256: str | None = None
    published = False
    try:
        staging.mkdir(mode=0o700)
        bindings, source_by_task, skills, _ = _derive_inputs(request, read_bytes)
        if prevalidated_context is None:
            run_pack_documents, _ = _load_run_pack(request, read_bytes)
            training_artifacts = _verify_training_artifacts(
                request, read_bytes, run_pack_documents
            )
        else:
            run_pack_documents = prevalidated_context.run_pack_documents
            training_artifacts = prevalidated_context.training_artifacts
        hashes = request["expected_hashes"]
        plan = build_evaluation_plan_contract(
            run_pack_manifest_sha256=request["run_pack_internal_sha256"],
            heldout_labels_sha256=hashes["heldout_labels_sha256"],
            training_artifacts=training_artifacts,
            training_code_git_commit=request["training_code_git_commit"],
            evaluation_code_git_commit=request["evaluation_code_git_commit"],
            expected_task_bindings=bindings,
            attempt_token_sha256=request["attempt_token_sha256"],
            source_candidates_sha256=hashes["source_candidates_sha256"],
            source_manifest_sha256=hashes["source_manifest_sha256"],
            skill_index_sha256=hashes["skill_index_sha256"],
        )
        plan_sha256 = plan["plan_sha256"]
        _write_artifact(staging / "final-evaluation-plan.json", _canonical_bytes(plan))

        artifact_grid = _copy_model_inputs(staging, request)
        route_rows = []
        for arm in ARMS:
            for seed in SEEDS:
                artifact = artifact_grid[(arm, seed)]
                encoder = factory(arm, seed, artifact, skills)
                skill_texts = [skill["skill_text"] for skill in skills]
                skill_embeddings = encoder.encode(
                    skill_texts, normalize_embeddings=True
                )
                _require(
                    type(skill_embeddings) is list and len(skill_embeddings) == 16,
                    "skill embedding count mismatch",
                )
                for binding in bindings:
                    source = source_by_task[binding["task_id"]]
                    ranked_ids, ranked_scores, raw_latency_ns = _rank(
                        encoder,
                        skills,
                        skill_embeddings,
                        source["query_text"],
                        clock_ns,
                    )
                    route_rows.append(
                        build_route_row(
                            plan=plan,
                            arm=arm,
                            seed=seed,
                            task_id=binding["task_id"],
                            ranked_skill_ids=ranked_ids,
                            ranked_scores=ranked_scores,
                            latency_ms=Decimal(raw_latency_ns) / Decimal(1_000_000),
                            raw_latency_ns=raw_latency_ns,
                        )
                    )
        _require(len(route_rows) == 144, "route output count must be 144")
        shutil.rmtree(staging / "model-inputs")
        per_seed = [
            build_per_seed_result(
                plan=plan,
                arm=arm,
                seed=seed,
                route_rows=[
                    row
                    for row in route_rows
                    if row["arm"] == arm and row["seed"] == seed
                ],
            )
            for arm in ARMS
            for seed in SEEDS
        ]
        aggregate = build_aggregate_results(
            plan=plan, per_seed_results=per_seed, route_rows=route_rows
        )
        paired = build_paired_results(plan=plan, route_rows=route_rows)
        failures = build_failure_slices(plan=plan, route_rows=route_rows)
        summary = build_evaluation_summary(
            plan=plan,
            route_rows=route_rows,
            per_seed_results=per_seed,
            aggregate_results=aggregate,
            paired_results=paired,
            failure_slices=failures,
        )
        outputs = {
            "route-results.jsonl": b"".join(
                _canonical_bytes(row) for row in route_rows
            ),
            "per-seed.json": _canonical_bytes(per_seed),
            "aggregate.json": _canonical_bytes(aggregate),
            "paired.json": _canonical_bytes(paired),
            "failure-slices.json": _canonical_bytes(failures),
            "evaluation-summary.json": _canonical_bytes(summary),
        }
        for name, payload in outputs.items():
            _write_artifact(staging / name, payload)
        artifacts_manifest_sha256 = contract_sha256(snapshot_model_files(staging))
        _fsync_directory(staging)
        directory_fd = os.open(evaluation_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
            _atomic_publish_noreplace_dirfd(directory_fd, staging.name, "artifacts")
            published = True
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        try:
            _write_terminal(
                evaluation_root,
                request,
                status="COMPLETED",
                summary=summary,
                plan_sha256=plan_sha256,
                artifacts_manifest_sha256=artifacts_manifest_sha256,
            )
        except BaseException as terminal_error:
            _write_recovery_required(
                evaluation_root,
                plan_sha256=plan_sha256,
                summary_sha256=summary["summary_sha256"],
                artifacts_manifest_sha256=artifacts_manifest_sha256,
                error=terminal_error,
            )
            raise
        return summary
    except BaseException as exc:
        published = published or (evaluation_root / "artifacts").is_dir()
        if published:
            try:
                _write_recovery_required(
                    evaluation_root,
                    plan_sha256=plan_sha256,
                    summary_sha256=summary.get("summary_sha256") if summary else None,
                    artifacts_manifest_sha256=artifacts_manifest_sha256,
                    error=exc,
                )
            except FileExistsError:
                pass
        else:
            if staging.exists():
                try:
                    shutil.rmtree(staging)
                except OSError:
                    pass
            try:
                _write_terminal(
                    evaluation_root,
                    request,
                    status="FAILED",
                    error=exc,
                    plan_sha256=plan_sha256,
                    artifacts_manifest_sha256=artifacts_manifest_sha256,
                )
            except FileExistsError:
                pass
        raise


def _attempt_token(authority: PilotAuthority, evaluation_code_git_commit: str) -> str:
    return contract_sha256(
        {
            "schema_version": "router-v2-evaluation-authority-v1",
            "source_candidates_sha256": authority.source_candidates_sha256,
            "source_manifest_sha256": authority.source_manifest_sha256,
            "skill_index_sha256": authority.skill_index_sha256,
            "heldout_labels_sha256": authority.heldout_labels_sha256,
            "run_pack_manifest_sha256": authority.run_pack_manifest_sha256,
            "run_pack_manifest_file_sha256": authority.run_pack_manifest_file_sha256,
            "training_code_git_commit": authority.training_code_git_commit,
            "evaluation_code_git_commit": evaluation_code_git_commit,
            "execution_id": authority.execution_id,
        }
    )


def _authority_and_root(
    execution_root: Path | str,
    test_overrides: EvaluationTestOverrides | None,
) -> tuple[PilotAuthority, Path]:
    authority = (
        test_overrides.authority if test_overrides is not None else PRODUCTION_AUTHORITY
    )
    if test_overrides is not None:
        _require(authority.test_only is True, "test authority must be marked test-only")
    else:
        _require(authority == PRODUCTION_AUTHORITY, "production authority drift")
    resolver = (
        test_overrides.resolve_output_root
        if test_overrides is not None and test_overrides.resolve_output_root is not None
        else resolve_authorized_output_root
    )
    resolved = resolver(execution_root)
    _require(
        resolved.name == authority.execution_id,
        "execution root does not match frozen execution id",
    )
    if test_overrides is None:
        _require(
            resolved.parent == Path(AUTHORIZED_OUTPUT_ROOT).resolve(strict=True),
            "execution root must be the fixed child of authorized output root",
        )
    return authority, resolved


def _authority_request(
    authority: PilotAuthority,
    repository_root: Path,
    execution_root: Path,
    base_model_path: Path,
    evaluation_code_git_commit: str,
) -> dict[str, Any]:
    run_pack_root = execution_root / RUN_PACK_RELATIVE_PATH
    artifact_rows = []
    for arm in ARMS:
        for seed in SEEDS:
            output = execution_root / f"arm-{arm}/seed-{seed}"
            artifact_rows.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "model_path": str(base_model_path if arm == "A" else output),
                    "config_path": str(
                        run_pack_root / f"config-arm-{arm}-seed-{seed}.json"
                    ),
                    "config_file_sha256": None,
                    "run_summary_path": str(output / "train-run-summary.json"),
                    "run_summary_file_sha256": None,
                    "model_manifest_path": str(output / "model-manifest.json"),
                    "model_manifest_file_sha256": None,
                }
            )
    return {
        "repository_root": str(repository_root),
        "source_candidates_path": str(
            repository_root / authority.source_candidates_path
        ),
        "source_manifest_path": str(repository_root / authority.source_manifest_path),
        "skill_index_path": str(repository_root / authority.skill_index_path),
        "heldout_labels_path": str(repository_root / authority.heldout_labels_path),
        "run_pack_manifest_path": str(run_pack_root / "run-pack-manifest.json"),
        "run_pack_root": str(run_pack_root),
        "run_pack_internal_sha256": authority.run_pack_manifest_sha256,
        "expected_hashes": {
            "source_candidates_sha256": authority.source_candidates_sha256,
            "source_manifest_sha256": authority.source_manifest_sha256,
            "skill_index_sha256": authority.skill_index_sha256,
            "heldout_labels_sha256": authority.heldout_labels_sha256,
            "run_pack_manifest_sha256": authority.run_pack_manifest_file_sha256,
        },
        "expected_task_bindings_sha256": None,
        "training_artifacts": artifact_rows,
        "training_code_git_commit": authority.training_code_git_commit,
        "evaluation_code_git_commit": evaluation_code_git_commit,
        "attempt_token_sha256": _attempt_token(authority, evaluation_code_git_commit),
    }


def preflight_evaluation_authority(
    repository_root: Path | str,
    execution_root: Path | str,
    base_model_path: Path | str,
    *,
    test_overrides: EvaluationTestOverrides | None = None,
) -> ValidatedAuthorityContext:
    authority, resolved_execution_root = _authority_and_root(
        execution_root, test_overrides
    )
    root = Path(repository_root).resolve(strict=True)
    base = Path(base_model_path).resolve(strict=True)
    git_probe = (
        test_overrides.git_probe
        if test_overrides and test_overrides.git_probe is not None
        else _default_git_probe
    )
    commit, clean = git_probe(root)
    _require(
        clean
        and len(commit) == 40
        and (
            authority.evaluation_code_git_commit is None
            or commit == authority.evaluation_code_git_commit
        ),
        "evaluation code must be a clean exact commit",
    )
    request = _validated_request(
        _authority_request(
            authority,
            root,
            resolved_execution_root,
            base,
            commit,
        )
    )
    read_bytes = test_overrides.read_bytes if test_overrides else Path.read_bytes
    run_pack_documents, _ = _load_run_pack(request, read_bytes)
    artifacts = _verify_training_artifacts(request, read_bytes, run_pack_documents)
    return ValidatedAuthorityContext(
        authority=authority,
        repository_root=root,
        execution_root=resolved_execution_root,
        base_model_path=base,
        request=request,
        run_pack_documents=run_pack_documents,
        training_artifacts=artifacts,
    )


def run_evaluation_once(
    repository_root: Path | str,
    execution_root: Path | str,
    base_model_path: Path | str,
    *,
    test_overrides: EvaluationTestOverrides | None = None,
) -> dict[str, Any]:
    context = (
        test_overrides.prevalidated_context
        if test_overrides is not None
        and test_overrides.prevalidated_context is not None
        else preflight_evaluation_authority(
            repository_root,
            execution_root,
            base_model_path,
            test_overrides=test_overrides,
        )
    )
    _require(
        context.authority.test_only is (test_overrides is not None),
        "prevalidated authority mode mismatch",
    )
    _require(
        Path(repository_root).resolve(strict=True) == context.repository_root
        and Path(execution_root).resolve(strict=True) == context.execution_root
        and Path(base_model_path).resolve(strict=True) == context.base_model_path,
        "prevalidated authority path mismatch",
    )
    _reject_forbidden_request_paths(context.request)
    return _run_request_once(
        execution_root=context.execution_root,
        request=context.request,
        model_factory=test_overrides.model_factory if test_overrides else None,
        read_bytes=test_overrides.read_bytes if test_overrides else Path.read_bytes,
        clock_ns=test_overrides.clock_ns if test_overrides else time.perf_counter_ns,
        git_probe=(
            test_overrides.git_probe
            if test_overrides and test_overrides.git_probe is not None
            else _default_git_probe
        ),
        prevalidated_context=context,
    )
