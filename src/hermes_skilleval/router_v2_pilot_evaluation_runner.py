from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
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
    preregistered_evaluation_contract,
    quantize8,
)
from hermes_skilleval.router_v2_internal_package import HELDOUT_ROW_FIELDS
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_run_pack import (
    RUN_PACK_RELATIVE_PATH,
    validate_run_pack_documents,
)
from hermes_skilleval.router_v2_pilot_runtime import (
    ACCEPTED_PAIRS_PATH,
    AUTHORIZED_OUTPUT_ROOT,
    DATA_MANIFEST_PATH,
    MINING_MANIFEST_PATH,
    MINING_ROWS_PATH,
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
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
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


@dataclass(frozen=True)
class ReplayTestOverrides:
    context: ValidatedAuthorityContext
    git_probe: GitProbe
    read_bytes: ReadBytes = Path.read_bytes
    resolve_output_root: Callable[[Path | str], Path] | None = None
    context_factory: Callable[[], ValidatedAuthorityContext] | None = None
    model_factory: ModelFactory | None = None
    clock_ns: Callable[[], int] = time.perf_counter_ns


@dataclass
class ValidatedAuthorityContext:
    authority: PilotAuthority
    repository_root: Path
    execution_root: Path
    base_model_path: Path
    request: dict[str, Any]
    run_pack_documents: dict[str, bytes]
    training_artifacts: list[dict[str, Any]]


@dataclass
class ReplayAttemptContext:
    validated: ValidatedAuthorityContext
    output_root: Path
    output_fd: int
    output_identity: tuple[int, ...]
    evaluation_root: Path
    evaluation_fd: int


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
MODEL_LOAD_SMOKE_TEXTS = [
    "synthetic router query for non-heldout model-load smoke",
    "synthetic skill text for non-heldout model-load smoke",
]
_MODEL_LOAD_SMOKE_PASS = {
    "schema_version": "router-v2-pilot-model-load-smoke-v1",
    "smoke_status": "PASS",
}
_FROZEN_BASE_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
_FROZEN_MODEL_LOAD_SMOKE_MANIFEST_FILE_SHA256 = {
    ("A", 7170): "8b4478fc6df70c7fe2f6a8d84a39bb5d358f224a75016784dcf36c1f41665607",
    ("B", 7170): "bdc32447192c635fed8c83c147a1c3886ecb783c5691a5945b8fdbcae0c7d9cf",
    ("B", 7171): "58eebba5e1a5dfbcf80b6e15bdedb17b024b0688ff01dcfb2c05ed1738dc96b2",
    ("B", 7172): "f1f12fb6b2d9598f1df21f0574eff9ed6acba811bd99c4cbba65b344085189a8",
    ("C", 7170): "6d88194eec0d8e90a73ae5ab035a88c19993c13614a65fa33027fc332f55fca9",
    ("C", 7171): "076131899eca87582c3d9db1461d5c6f2ec235f97185bf59894f8fd30db4cb13",
    ("C", 7172): "3da9ae52487dcabdde354d5007df31db9fac43629b78fb710f6d285310706480",
}
REPLAY_PILOT_ID = "router-v2-v4-confusion-mined-pilot-002-eval-replay"
REPLAY_REPLACEMENT_REASON = "INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE"
REPLAY_EVALUATION_EXECUTION_ID = f"evaluation-{REPLAY_PILOT_ID}"
_REPLAY_ARTIFACT_FILE_SHA256 = {
    ("A", 7170): (
        "716ef6a1b338ba199363b2342eddc4c5cad6f217c28b302d202d63967ebe0241",
        "8b4478fc6df70c7fe2f6a8d84a39bb5d358f224a75016784dcf36c1f41665607",
    ),
    ("A", 7171): (
        "b531aee9894027fd7c31d31b072f27690e0cc77ead743293cff9a7da4d18aa45",
        "18b034dc2fd17a6e637b98e5f8cf4ff24e80af9a5dfea7a32303e6583e2034a3",
    ),
    ("A", 7172): (
        "7fc09898498c2f9ad5a2fbfd7cff006d2923dcc271d17d0267b93109278dcfed",
        "36eb45002ebee0a2d4dbebeab94a5478aa28f09f01f7ba13b6ddc46c3a0770e7",
    ),
    ("B", 7170): (
        "1243422379436798f227c5db237114cd93e0b740942e798faf50278d3d1d4a33",
        "bdc32447192c635fed8c83c147a1c3886ecb783c5691a5945b8fdbcae0c7d9cf",
    ),
    ("B", 7171): (
        "e197c29fd273530cdc7aaf48aff521ad2a8871be52b49f88a6f043f0d0fd777e",
        "58eebba5e1a5dfbcf80b6e15bdedb17b024b0688ff01dcfb2c05ed1738dc96b2",
    ),
    ("B", 7172): (
        "a6a4870a1cd866d77c63078a0b64dffee9d3df0323d6a07bffec530341293fda",
        "f1f12fb6b2d9598f1df21f0574eff9ed6acba811bd99c4cbba65b344085189a8",
    ),
    ("C", 7170): (
        "7c52159432674d4a4c2adf3b702288c9ef9535ffd89f3f678ba70a1d3667a35b",
        "6d88194eec0d8e90a73ae5ab035a88c19993c13614a65fa33027fc332f55fca9",
    ),
    ("C", 7171): (
        "f4477e1e0a1ba2ebf453cb07061a3d2336fc21d55f357a0ee414eb0f4cee8c1c",
        "076131899eca87582c3d9db1461d5c6f2ec235f97185bf59894f8fd30db4cb13",
    ),
    ("C", 7172): (
        "c58defd646953054048e5f4500d420e1c1a4e385fcd5e7c0f82d2aaa09bf350d",
        "3da9ae52487dcabdde354d5007df31db9fac43629b78fb710f6d285310706480",
    ),
}


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
        row["_validated_model_topology"] = _capture_model_topology(
            Path(row["model_path"]), row["_validated_model_file_manifest"]
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
            source = _absolute_model_path(Path(artifact["model_path"]))
            manifest_rows = artifact["_validated_model_file_manifest"]
            topology = artifact["_validated_model_topology"]
            target = staging / "model-inputs" / f"arm-{arm}-seed-{seed}"
            target.mkdir(parents=True, mode=0o700)
            try:
                for row in manifest_rows:
                    relative = _model_relative(row["path"])
                    target_file = target.joinpath(*relative.parts)
                    target_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    _materialize_model_file(
                        arm=arm,
                        snapshot_root=source,
                        relative=relative,
                        target_file=target_file,
                        expected=row,
                        expected_root_topology=topology["root"],
                        expected_row_topology=topology["rows"][row["path"]],
                    )
                _require(
                    snapshot_model_files(target) == manifest_rows,
                    "private model copy verification mismatch",
                )
            except Exception:
                shutil.rmtree(target)
                raise
            copied[(arm, seed)] = {**artifact, "model_path": str(target)}
    return copied


def _stable_stat(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _topology_stat(metadata: os.stat_result) -> tuple[int, int, int]:
    return metadata.st_dev, metadata.st_ino, metadata.st_mode


def _model_relative(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    _require(
        not relative.is_absolute()
        and relative.as_posix() == path
        and bool(relative.parts)
        and all(part not in {"", ".", ".."} for part in relative.parts),
        "model copy path mismatch",
    )
    return relative


def _absolute_model_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _capture_model_topology(
    model_path: Path,
    manifest_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    root = _absolute_model_path(model_path)
    root_stat = root.lstat()
    _require(
        stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode),
        "model snapshot root topology mismatch",
    )
    rows = {}
    for row in manifest_rows:
        relative = _model_relative(row["path"])
        current = root
        parents = []
        for part in relative.parts[:-1]:
            current /= part
            parent_stat = current.lstat()
            _require(
                stat.S_ISDIR(parent_stat.st_mode)
                and not stat.S_ISLNK(parent_stat.st_mode),
                "model snapshot parent topology mismatch",
            )
            parents.append((part, _topology_stat(parent_stat)))
        final = current / relative.parts[-1]
        final_stat = final.lstat()
        _require(
            stat.S_ISREG(final_stat.st_mode) or stat.S_ISLNK(final_stat.st_mode),
            "model snapshot final topology mismatch",
        )
        is_link = stat.S_ISLNK(final_stat.st_mode)
        resolved = final.resolve(strict=True) if is_link else None
        rows[row["path"]] = {
            "parents": tuple(parents),
            "final": _topology_stat(final_stat),
            "link_text": os.readlink(final) if is_link else None,
            "model_root": (
                _topology_stat(resolved.parent.parent.lstat())
                if resolved is not None
                else None
            ),
            "blob_dir": (
                _topology_stat(resolved.parent.lstat())
                if resolved is not None
                else None
            ),
            "blob": (
                _topology_stat(resolved.lstat()) if resolved is not None else None
            ),
        }
    return {"root": _topology_stat(root_stat), "rows": rows}


def _directory_flags() -> int:
    _require(
        all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW")),
        "secure directory open is unavailable",
    )
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _file_flags() -> int:
    _require(hasattr(os, "O_NOFOLLOW"), "secure no-follow open is unavailable")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _close_all(descriptors: list[int]) -> None:
    close_error: OSError | None = None
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except OSError as exc:
            if close_error is None:
                close_error = exc
    if close_error is not None:
        raise close_error


def _materialize_model_file(
    *,
    arm: str,
    snapshot_root: Path,
    relative: PurePosixPath,
    target_file: Path,
    expected: dict[str, Any],
    expected_root_topology: tuple[int, int, int],
    expected_row_topology: dict[str, Any],
) -> None:
    descriptors: list[int] = []
    entry_guards: list[tuple[int, str, tuple[int, int, int, int, int, int], str]] = []
    path_guards: list[tuple[Path, tuple[int, int, int, int, int, int], str]] = []
    target_created = False
    try:
        root_before = snapshot_root.lstat()
        _require(
            _topology_stat(root_before) == expected_root_topology
            and stat.S_ISDIR(root_before.st_mode),
            "model snapshot root topology replaced",
        )
        root_fd = os.open(snapshot_root, _directory_flags())
        descriptors.append(root_fd)
        root_opened = os.fstat(root_fd)
        _require(
            _stable_stat(root_opened) == _stable_stat(root_before),
            "model snapshot root replaced",
        )
        path_guards.append(
            (snapshot_root, _stable_stat(root_opened), "model snapshot root replaced")
        )
        current_fd = root_fd
        parent_path = snapshot_root
        expected_parents = expected_row_topology["parents"]
        _require(
            len(expected_parents) == len(relative.parts) - 1,
            "model copy parent topology mismatch",
        )
        for part, (expected_name, expected_topology) in zip(
            relative.parts[:-1], expected_parents, strict=True
        ):
            _require(part == expected_name, "model copy parent topology mismatch")
            parent_before = os.stat(
                part,
                dir_fd=current_fd,
                follow_symlinks=False,
            )
            _require(
                _topology_stat(parent_before) == expected_topology
                and stat.S_ISDIR(parent_before.st_mode),
                "model copy parent topology replaced",
            )
            parent_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            descriptors.append(parent_fd)
            parent_opened = os.fstat(parent_fd)
            _require(
                _stable_stat(parent_opened) == _stable_stat(parent_before),
                "model copy parent replaced",
            )
            entry_guards.append(
                (
                    current_fd,
                    part,
                    _stable_stat(parent_opened),
                    "model copy parent replaced",
                )
            )
            current_fd = parent_fd
            parent_path /= part

        final_name = relative.parts[-1]
        final_before = os.stat(
            final_name,
            dir_fd=current_fd,
            follow_symlinks=False,
        )
        _require(
            _topology_stat(final_before) == expected_row_topology["final"],
            "model copy final topology replaced",
        )
        entry_guards.append(
            (
                current_fd,
                final_name,
                _stable_stat(final_before),
                "model copy final source replaced",
            )
        )
        if stat.S_ISLNK(final_before.st_mode):
            _require(arm == "A", "trained model snapshot symlink is forbidden")
            _require(
                snapshot_root.parent.name == "snapshots"
                and snapshot_root.parent.parent.name.startswith("models--"),
                "base model snapshot cache layout mismatch",
            )
            link_text = os.readlink(final_name, dir_fd=current_fd)
            _require(
                link_text == expected_row_topology["link_text"],
                "base model snapshot symlink source replaced",
            )
            model_root = snapshot_root.parent.parent
            blobs = model_root / "blobs"
            source_parent = parent_path
            target = Path(os.path.abspath(os.path.join(source_parent, link_text)))
            _require(
                target.parent == blobs and target.name not in {"", ".", ".."},
                "base model snapshot symlink target mismatch",
            )
            model_root_before = model_root.lstat()
            _require(
                _topology_stat(model_root_before) == expected_row_topology["model_root"]
                and stat.S_ISDIR(model_root_before.st_mode),
                "base model snapshot model root replaced",
            )
            model_root_fd = os.open(model_root, _directory_flags())
            descriptors.append(model_root_fd)
            model_root_opened = os.fstat(model_root_fd)
            _require(
                _stable_stat(model_root_opened) == _stable_stat(model_root_before),
                "base model snapshot model root replaced",
            )
            path_guards.append(
                (
                    model_root,
                    _stable_stat(model_root_opened),
                    "base model snapshot model root replaced",
                )
            )
            blobs_before = os.stat("blobs", dir_fd=model_root_fd, follow_symlinks=False)
            _require(
                _topology_stat(blobs_before) == expected_row_topology["blob_dir"]
                and stat.S_ISDIR(blobs_before.st_mode),
                "base model snapshot blobs directory replaced",
            )
            blobs_fd = os.open("blobs", _directory_flags(), dir_fd=model_root_fd)
            descriptors.append(blobs_fd)
            blobs_opened = os.fstat(blobs_fd)
            _require(
                _stable_stat(blobs_opened) == _stable_stat(blobs_before),
                "base model snapshot blobs directory replaced",
            )
            entry_guards.append(
                (
                    model_root_fd,
                    "blobs",
                    _stable_stat(blobs_opened),
                    "base model snapshot blobs directory replaced",
                )
            )
            blob_before = os.stat(
                target.name,
                dir_fd=blobs_fd,
                follow_symlinks=False,
            )
            _require(
                _topology_stat(blob_before) == expected_row_topology["blob"]
                and stat.S_ISREG(blob_before.st_mode),
                "base model snapshot symlink target replaced",
            )
            source_fd = os.open(target.name, _file_flags(), dir_fd=blobs_fd)
            descriptors.append(source_fd)
            source_opened = os.fstat(source_fd)
            _require(
                _stable_stat(source_opened) == _stable_stat(blob_before),
                "base model snapshot symlink target replaced",
            )
            entry_guards.append(
                (
                    blobs_fd,
                    target.name,
                    _stable_stat(source_opened),
                    "base model snapshot symlink target replaced",
                )
            )
        else:
            _require(
                stat.S_ISREG(final_before.st_mode),
                "model copy source must be a regular file",
            )
            source_fd = os.open(final_name, _file_flags(), dir_fd=current_fd)
            descriptors.append(source_fd)
            source_opened = os.fstat(source_fd)
            _require(
                _stable_stat(source_opened) == _stable_stat(final_before),
                "model copy source replaced",
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        target_fd = os.open(target_file, flags, 0o600)
        descriptors.append(target_fd)
        target_created = True
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(target_fd, view)
                _require(written > 0, "private model copy write mismatch")
                view = view[written:]
        for path, initial, message in path_guards:
            _require(
                _stable_stat(path.lstat()) == initial,
                message,
            )
        for parent_fd, name, initial, message in entry_guards:
            _require(
                _stable_stat(os.stat(name, dir_fd=parent_fd, follow_symlinks=False))
                == initial,
                message,
            )
        _require(
            size == expected["size"] and digest.hexdigest() == expected["sha256"],
            "model copy content mismatch during private model copy verification",
        )
    except Exception:
        if target_created:
            target_file.unlink(missing_ok=True)
        raise
    finally:
        _close_all(descriptors)


def _smoke_model_keys() -> tuple[tuple[str, int], ...]:
    return (
        ("A", 7170),
        ("B", 7170),
        ("B", 7171),
        ("B", 7172),
        ("C", 7170),
        ("C", 7171),
        ("C", 7172),
    )


def _validate_smoke_manifest(
    *,
    payload: bytes,
    expected_file_sha256: str,
    arm: str,
    seed: int,
) -> dict[str, Any]:
    _require(
        _sha(payload) == expected_file_sha256,
        f"{arm}-{seed} model manifest file SHA-256 mismatch",
    )
    manifest = _json_object(payload, f"{arm}-{seed} model manifest")
    fingerprint = manifest.get("model_manifest_sha256")
    _require(
        type(fingerprint) is str
        and contract_sha256(
            {
                key: value
                for key, value in manifest.items()
                if key != "model_manifest_sha256"
            }
        )
        == fingerprint,
        f"{arm}-{seed} model manifest fingerprint mismatch",
    )
    _require(
        manifest.get("schema_version") == "router-v2-pilot-model-manifest-v1"
        and manifest.get("arm") == arm
        and manifest.get("seed") == seed
        and manifest.get("output_dir") == f"arm-{arm}/seed-{seed}"
        and manifest.get("base_model_revision") == _FROZEN_BASE_MODEL_REVISION
        and type(manifest.get("base_model_file_manifest_sha256")) is str,
        f"{arm}-{seed} model manifest frozen lineage mismatch",
    )
    raw_rows = manifest.get("model_file_manifest")
    _require(type(raw_rows) is list, f"{arm}-{seed} model file manifest mismatch")
    rows = cast(list[dict[str, Any]], raw_rows)
    paths: list[str] = []
    for row in rows:
        _require(
            type(row) is dict
            and set(row) == {"path", "sha256", "size"}
            and type(row["path"]) is str
            and type(row["sha256"]) is str
            and len(row["sha256"]) == 64
            and type(row["size"]) is int
            and row["size"] >= 0,
            f"{arm}-{seed} model file manifest row mismatch",
        )
        _model_relative(row["path"])
        paths.append(row["path"])
    _require(
        paths == sorted(paths)
        and len(paths) == len(set(paths))
        and contract_sha256(rows) == manifest.get("model_file_manifest_sha256"),
        f"{arm}-{seed} model file manifest SHA-256 mismatch",
    )
    _require(
        (arm == "A" and rows == []) or (arm in {"B", "C"} and bool(rows)),
        f"{arm}-{seed} model file manifest arm mismatch",
    )
    return manifest


def _load_smoke_model_artifacts(
    *,
    execution_root: Path,
    base_model_path: Path,
    manifest_file_sha256: dict[tuple[str, int], str],
    read_bytes: ReadBytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    keys = _smoke_model_keys()
    _require(
        set(manifest_file_sha256) == set(keys)
        and all(
            type(value) is str and len(value) == 64
            for value in manifest_file_sha256.values()
        ),
        "model-load smoke manifest authority mismatch",
    )
    manifests: dict[tuple[str, int], dict[str, Any]] = {}
    for arm, seed in keys:
        manifest_path = execution_root / f"arm-{arm}/seed-{seed}/model-manifest.json"
        manifests[(arm, seed)] = _validate_smoke_manifest(
            payload=read_bytes(manifest_path),
            expected_file_sha256=manifest_file_sha256[(arm, seed)],
            arm=arm,
            seed=seed,
        )

    base_manifest_sha256 = manifests[("A", 7170)]["base_model_file_manifest_sha256"]
    _require(
        all(
            manifest["base_model_file_manifest_sha256"] == base_manifest_sha256
            for manifest in manifests.values()
        ),
        "model-load smoke base model manifest lineage mismatch",
    )

    base_rows = snapshot_model_files(base_model_path)
    base_manifest = manifests[("A", 7170)]
    _require(
        contract_sha256(base_rows) == base_manifest["base_model_file_manifest_sha256"],
        "base model snapshot SHA-256 mismatch",
    )
    base_artifact = {
        "arm": "A",
        "seed": 7170,
        "model_path": str(base_model_path),
        "_validated_model_file_manifest": base_rows,
        "_validated_model_topology": _capture_model_topology(
            base_model_path, base_rows
        ),
    }
    trained_artifacts = []
    for arm, seed in keys[1:]:
        model_path = execution_root / f"arm-{arm}/seed-{seed}"
        artifact = {"arm": arm, "seed": seed, "model_path": str(model_path)}
        rows = _validate_model_snapshot(
            artifact=artifact,
            config={},
            manifest=manifests[(arm, seed)],
        )
        trained_artifacts.append(
            {
                **artifact,
                "_validated_model_file_manifest": rows,
                "_validated_model_topology": _capture_model_topology(model_path, rows),
            }
        )
    return trained_artifacts, base_rows, base_artifact


def _materialize_smoke_base_model(
    *, source_artifact: dict[str, Any], target: Path
) -> None:
    source = _absolute_model_path(Path(source_artifact["model_path"]))
    rows = source_artifact["_validated_model_file_manifest"]
    topology = source_artifact["_validated_model_topology"]
    target.mkdir(mode=0o700)
    for row in rows:
        relative = _model_relative(row["path"])
        target_file = target.joinpath(*relative.parts)
        target_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _materialize_model_file(
            arm="A",
            snapshot_root=source,
            relative=relative,
            target_file=target_file,
            expected=row,
            expected_root_topology=topology["root"],
            expected_row_topology=topology["rows"][row["path"]],
        )
    _require(
        snapshot_model_files(target) == rows,
        "private base model copy verification mismatch",
    )


def _validate_smoke_embeddings(value: Any) -> None:
    _require(
        type(value) is list and len(value) == 2,
        "model-load smoke embedding count mismatch",
    )
    _require(
        all(
            type(row) is list
            and len(row) == 384
            and all(type(item) in {int, float} and math.isfinite(item) for item in row)
            for row in value
        ),
        "model-load smoke embedding dimension or finite-value mismatch",
    )


def _run_model_load_smoke(
    *,
    execution_root: Path | str,
    base_model_path: Path | str,
    manifest_file_sha256: dict[tuple[str, int], str],
    model_factory: ModelFactory = _default_model_factory,
    read_bytes: ReadBytes = Path.read_bytes,
    temporary_parent: Path | str | None = None,
) -> dict[str, str]:
    execution = _absolute_model_path(Path(execution_root))
    base = _absolute_model_path(Path(base_model_path))
    _require(
        execution.name == PRODUCTION_AUTHORITY.execution_id
        and execution.is_dir()
        and not execution.is_symlink(),
        "model-load smoke execution root mismatch",
    )
    _require(
        base.name == _FROZEN_BASE_MODEL_REVISION
        and base.parent.name == "snapshots"
        and base.parent.parent.name.startswith("models--")
        and base.is_dir()
        and not base.is_symlink(),
        "model-load smoke base model path mismatch",
    )
    trained, _, base_artifact = _load_smoke_model_artifacts(
        execution_root=execution,
        base_model_path=base,
        manifest_file_sha256=manifest_file_sha256,
        read_bytes=read_bytes,
    )
    parent = Path(temporary_parent) if temporary_parent is not None else None
    temporary = Path(tempfile.mkdtemp(prefix="router-v2-model-load-smoke-", dir=parent))
    try:
        os.chmod(temporary, 0o700)
        _require(
            stat.S_IMODE(temporary.stat().st_mode) == 0o700,
            "model-load smoke temporary root mode mismatch",
        )
        private_base = temporary / "arm-A"
        _materialize_smoke_base_model(
            source_artifact=base_artifact,
            target=private_base,
        )
        models = [
            {**base_artifact, "model_path": str(private_base)},
            *trained,
        ]
        for artifact in models:
            encoder = model_factory(artifact["arm"], artifact["seed"], artifact, [])
            embeddings = encoder.encode(
                list(MODEL_LOAD_SMOKE_TEXTS), normalize_embeddings=True
            )
            if hasattr(embeddings, "tolist"):
                embeddings = embeddings.tolist()
            _validate_smoke_embeddings(embeddings)
            del encoder
        return dict(_MODEL_LOAD_SMOKE_PASS)
    finally:
        shutil.rmtree(temporary)


def run_model_load_smoke(
    execution_root: Path | str,
    base_model_path: Path | str,
) -> dict[str, str]:
    return _run_model_load_smoke(
        execution_root=execution_root,
        base_model_path=base_model_path,
        manifest_file_sha256=_FROZEN_MODEL_LOAD_SMOKE_MANIFEST_FILE_SHA256,
    )


def _production_replay_context(
    repository_root: Path,
    training_execution_root: Path | str,
    base_model_path: Path,
    evaluation_code_git_commit: str,
) -> ValidatedAuthorityContext:
    authority, execution = _authority_and_root(training_execution_root, None)
    request = _authority_request(
        authority,
        repository_root,
        execution,
        base_model_path,
        evaluation_code_git_commit,
    )
    for row in request["training_artifacts"]:
        run_summary_sha, model_manifest_sha = _REPLAY_ARTIFACT_FILE_SHA256[
            (row["arm"], row["seed"])
        ]
        row["run_summary_file_sha256"] = run_summary_sha
        row["model_manifest_file_sha256"] = model_manifest_sha
    request = _validated_request(request)
    documents, _ = _load_run_pack(request, Path.read_bytes)
    artifacts = _verify_training_artifacts(request, Path.read_bytes, documents)
    return ValidatedAuthorityContext(
        authority=authority,
        repository_root=repository_root,
        execution_root=execution,
        base_model_path=base_model_path,
        request=request,
        run_pack_documents=documents,
        training_artifacts=artifacts,
    )


def _refresh_replay_context(
    context: ValidatedAuthorityContext, read_bytes: ReadBytes
) -> ValidatedAuthorityContext:
    documents, _ = _load_run_pack(context.request, read_bytes)
    artifacts = _verify_training_artifacts(context.request, read_bytes, documents)
    return ValidatedAuthorityContext(
        authority=context.authority,
        repository_root=context.repository_root,
        execution_root=context.execution_root,
        base_model_path=context.base_model_path,
        request=context.request,
        run_pack_documents=documents,
        training_artifacts=artifacts,
    )


def _validate_replay_frozen_files(
    bindings: dict[str, dict[str, str]], read_bytes: ReadBytes
) -> dict[str, dict[str, str]]:
    expected = {
        "accepted_pairs",
        "data_manifest",
        "mining_rows",
        "mining_manifest",
        "heldout_labels",
    }
    _require(set(bindings) == expected, "replay frozen file binding mismatch")
    output = {}
    for name in sorted(bindings):
        row = bindings[name]
        _require(
            type(row) is dict
            and set(row) == {"path", "sha256"}
            and type(row["path"]) is str
            and type(row["sha256"]) is str
            and len(row["sha256"]) == 64,
            f"{name} binding mismatch",
        )
        payload = read_bytes(Path(row["path"]))
        _require(_sha(payload) == row["sha256"], f"{name} SHA-256 mismatch")
        output[name] = dict(row)
    return output


def _revalidate_replay_artifacts(
    context: ValidatedAuthorityContext,
    read_bytes: ReadBytes,
) -> tuple[list[dict[str, Any]], dict[str, Any], ValidatedAuthorityContext]:
    if not context.authority.test_only:
        context = _refresh_replay_context(context, read_bytes)
    request = context.request
    _read_verified(
        request["run_pack_manifest_path"],
        request["expected_hashes"]["run_pack_manifest_sha256"],
        read_bytes,
        "replay run-pack manifest",
    )
    verified = []
    first_config: dict[str, Any] | None = None
    for row in sorted(
        request["training_artifacts"],
        key=lambda item: (ARMS.index(item["arm"]), item["seed"]),
    ):
        config_name = f"config-arm-{row['arm']}-seed-{row['seed']}.json"
        config_payload = context.run_pack_documents.get(config_name)
        _require(
            type(config_payload) is bytes,
            f"{row['arm']}-{row['seed']} validated run-pack config missing",
        )
        config_payload = cast(bytes, config_payload)
        if row["config_file_sha256"] is not None:
            _require(
                _sha(config_payload) == row["config_file_sha256"],
                f"{row['arm']}-{row['seed']} config SHA-256 mismatch",
            )
        summary_payload = _read_verified(
            row["run_summary_path"],
            row["run_summary_file_sha256"],
            read_bytes,
            f"{row['arm']}-{row['seed']} run summary",
        )
        manifest_payload = _read_verified(
            row["model_manifest_path"],
            row["model_manifest_file_sha256"],
            read_bytes,
            f"{row['arm']}-{row['seed']} model manifest",
        )
        config = _json_object(config_payload, "replay config")
        manifest = _json_object(manifest_payload, "replay model manifest")
        if first_config is None:
            first_config = config
        if context.authority.test_only and row["arm"] != "A":
            model_files = snapshot_model_files(row["model_path"])
            _require(
                model_files == manifest["model_file_manifest"],
                "trained model snapshot SHA-256 mismatch",
            )
        else:
            model_files = _validate_model_snapshot(
                artifact=row,
                config=config,
                manifest=manifest,
            )
        verified.append(
            {
                "arm": row["arm"],
                "seed": row["seed"],
                "config_path": row["config_path"],
                "config_file_sha256": _sha(config_payload),
                "run_summary_path": row["run_summary_path"],
                "run_summary_file_sha256": _sha(summary_payload),
                "model_path": row["model_path"],
                "model_manifest_path": row["model_manifest_path"],
                "model_manifest_file_sha256": _sha(manifest_payload),
                "model_manifest_sha256": manifest["model_manifest_sha256"],
                "model_file_manifest": model_files,
                "model_file_manifest_sha256": contract_sha256(model_files),
            }
        )
    _require(first_config is not None, "replay training artifact grid is empty")
    return verified, cast(dict[str, Any], first_config), context


def _replay_manifest(
    *,
    context: ValidatedAuthorityContext,
    evaluation_root: Path,
    evaluation_code_git_commit: str,
    training_artifacts: list[dict[str, Any]],
    lineage_config: dict[str, Any],
) -> dict[str, Any]:
    run_pack_inputs = [
        {"path": name, "sha256": _sha(payload), "size": len(payload)}
        for name, payload in sorted(context.run_pack_documents.items())
        if name != "run-pack-manifest.json"
    ]
    frozen_files = {
        "accepted_pairs": {
            "path": str(context.repository_root / ACCEPTED_PAIRS_PATH),
            "sha256": lineage_config["accepted_pairs_sha256"],
        },
        "data_manifest": {
            "path": str(context.repository_root / DATA_MANIFEST_PATH),
            "sha256": lineage_config["data_manifest_sha256"],
        },
        "mining_rows": {
            "path": str(context.repository_root / MINING_ROWS_PATH),
            "sha256": lineage_config["mining_rows_sha256"],
        },
        "mining_manifest": {
            "path": str(context.repository_root / MINING_MANIFEST_PATH),
            "sha256": lineage_config["mining_manifest_sha256"],
        },
        "heldout_labels": {
            "path": str(
                context.repository_root / context.authority.heldout_labels_path
            ),
            "sha256": context.authority.heldout_labels_sha256,
        },
    }
    frozen_inputs = {
        **frozen_files,
        "run_pack": {
            "path": context.request["run_pack_root"],
            "manifest_file_sha256": context.authority.run_pack_manifest_file_sha256,
            "manifest_sha256": context.authority.run_pack_manifest_sha256,
            "inputs": run_pack_inputs,
        },
    }
    evaluation_contract = preregistered_evaluation_contract()
    base_model = {
        "id": lineage_config["base_model_id"],
        "revision": lineage_config["base_model_revision"],
        "path": str(context.base_model_path),
        "file_manifest_sha256": lineage_config["base_model_file_manifest_sha256"],
        "file_manifest_rows": training_artifacts[0]["model_file_manifest"],
    }
    frozen_authority = {
        "training_execution_id": context.authority.execution_id,
        "training_execution_root": str(context.execution_root),
        "training_code_git_commit": context.authority.training_code_git_commit,
        "frozen_inputs": frozen_inputs,
        "training_artifacts": training_artifacts,
        "base_model": base_model,
        "seeds": list(SEEDS),
        "evaluation_contract": evaluation_contract,
    }
    token = contract_sha256(
        {
            "schema_version": "router-v2-evaluation-replay-authority-v1",
            "pilot_id": REPLAY_PILOT_ID,
            "replacement_reason": REPLAY_REPLACEMENT_REASON,
            "evaluation_code_git_commit": evaluation_code_git_commit,
            "evaluation_output_namespace": str(evaluation_root),
            "frozen_authority": frozen_authority,
        }
    )
    manifest = {
        "schema_version": "router-v2-pilot-evaluation-replay-manifest-v1",
        "pilot_id": REPLAY_PILOT_ID,
        "replacement_reason": REPLAY_REPLACEMENT_REASON,
        "replacement_fields": [
            "pilot_id",
            "attempt_token_sha256",
            "evaluation_code_git_commit",
            "evaluation_output_namespace",
            "replacement_reason",
        ],
        **frozen_authority,
        "evaluation_execution_id": evaluation_root.name,
        "evaluation_output_namespace": str(evaluation_root),
        "attempt_number": 1,
        "maximum_attempts": 1,
        "attempt_token_sha256": token,
        "evaluation_code_git_commit": evaluation_code_git_commit,
        "frozen_authority_sha256": contract_sha256(frozen_authority),
        "reuses_frozen_training_artifacts_from_pilot_001": True,
        "pilot_001_metrics_observed": False,
        "review_mode": "MODEL_ONLY_PILOT",
        "human_reviewer_count": 0,
        "blind_v2_run": False,
        "production_ready": False,
        "release_eligible": False,
        "router_decision": "KEEP_BASELINE",
    }
    return {**manifest, "manifest_sha256": contract_sha256(manifest)}


def _open_replay_output_root(output_root: Path) -> tuple[int, tuple[int, ...]]:
    before = output_root.lstat()
    _require(
        stat.S_ISDIR(before.st_mode)
        and not stat.S_ISLNK(before.st_mode)
        and stat.S_IMODE(before.st_mode) == 0o700,
        "replay output root must be a real 0700 directory",
    )
    try:
        descriptor = os.open(output_root, _directory_flags())
    except OSError as exc:
        raise ValueError("replay output root symlink or identity mismatch") from exc
    opened = os.fstat(descriptor)
    try:
        _require(
            _stable_stat(opened) == _stable_stat(before),
            "replay output root identity mismatch",
        )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, _stable_stat(opened)


def _require_replay_output_identity(
    output_root: Path, expected: tuple[int, ...]
) -> None:
    metadata = output_root.lstat()
    _require(
        not stat.S_ISLNK(metadata.st_mode) and _stable_stat(metadata) == expected,
        "replay output root replaced or symlinked",
    )


def _read_file_at(directory_fd: int, name: str) -> bytes:
    descriptor = os.open(name, _file_flags(), dir_fd=directory_fd)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _write_noreplace_at(directory_fd: int, name: str, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            _require(written > 0, "dirfd write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_or_verify_replay_manifest(
    output_fd: int,
    output_root: Path,
    output_identity: tuple[int, ...],
    manifest: dict[str, Any],
) -> None:
    name = "pilot-manifest.json"
    payload = _canonical_bytes(manifest)
    _require_replay_output_identity(output_root, output_identity)
    entries = set(os.listdir(output_fd))
    _require(
        entries <= {name},
        "replay output namespace is not pre-attempt clean",
    )
    if name in entries:
        _require(
            _read_file_at(output_fd, name) == payload,
            "pilot manifest mismatch",
        )
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=output_fd)
    except FileExistsError:
        _require(
            _read_file_at(output_fd, name) == payload,
            "pilot manifest mismatch",
        )
        return
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            _require(written > 0, "pilot manifest write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(output_fd)


def prepare_replay_manifest(
    repository_root: Path | str,
    training_execution_root: Path | str,
    evaluation_output_root: Path | str,
    base_model_path: Path | str,
    *,
    test_overrides: ReplayTestOverrides | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    base = Path(base_model_path).resolve(strict=True)
    git_probe = test_overrides.git_probe if test_overrides else _default_git_probe
    commit, clean = git_probe(root)
    _require(clean and len(commit) == 40, "evaluation code must be a clean commit")
    if test_overrides is not None:
        _require(
            test_overrides.context.authority.test_only is True,
            "replay test authority must be marked test-only",
        )
        context = (
            test_overrides.context_factory()
            if test_overrides.context_factory is not None
            else test_overrides.context
        )
        _require(
            context.authority.test_only is True,
            "replay refreshed test authority must be marked test-only",
        )
    else:
        context = _production_replay_context(
            root, training_execution_root, base, commit
        )
        _require(
            context.authority == PRODUCTION_AUTHORITY,
            "replay production authority drift",
        )
    _require(
        context.repository_root == root
        and context.execution_root == Path(training_execution_root).resolve(strict=True)
        and context.base_model_path == base,
        "replay authority path mismatch",
    )
    resolver = (
        test_overrides.resolve_output_root
        if test_overrides and test_overrides.resolve_output_root is not None
        else resolve_authorized_output_root
    )
    output = resolver(evaluation_output_root)
    training = context.execution_root
    _require(
        output != training
        and output.is_dir()
        and not output.is_symlink()
        and stat.S_IMODE(output.stat().st_mode) == 0o700,
        "replay output root must be a separate 0700 directory",
    )
    _require(
        output.parent == training.parent
        and not output.is_relative_to(training)
        and not training.is_relative_to(output),
        "replay output root must be a sibling, never ancestor or descendant",
    )
    if test_overrides is None:
        _require(
            output.name == REPLAY_EVALUATION_EXECUTION_ID,
            "replay evaluation execution id mismatch",
        )
    read_bytes = test_overrides.read_bytes if test_overrides else Path.read_bytes
    output_fd, output_identity = _open_replay_output_root(output)
    try:
        _require(
            set(os.listdir(output_fd)) <= {"pilot-manifest.json"},
            "replay output namespace is not pre-attempt clean",
        )
        artifacts, config, context = _revalidate_replay_artifacts(context, read_bytes)
        frozen_files = {
            "accepted_pairs": {
                "path": str(root / ACCEPTED_PAIRS_PATH),
                "sha256": config["accepted_pairs_sha256"],
            },
            "data_manifest": {
                "path": str(root / DATA_MANIFEST_PATH),
                "sha256": config["data_manifest_sha256"],
            },
            "mining_rows": {
                "path": str(root / MINING_ROWS_PATH),
                "sha256": config["mining_rows_sha256"],
            },
            "mining_manifest": {
                "path": str(root / MINING_MANIFEST_PATH),
                "sha256": config["mining_manifest_sha256"],
            },
            "heldout_labels": {
                "path": str(root / context.authority.heldout_labels_path),
                "sha256": context.authority.heldout_labels_sha256,
            },
        }
        _validate_replay_frozen_files(frozen_files, read_bytes)
        manifest = _replay_manifest(
            context=context,
            evaluation_root=output,
            evaluation_code_git_commit=commit,
            training_artifacts=artifacts,
            lineage_config=config,
        )
        _write_or_verify_replay_manifest(output_fd, output, output_identity, manifest)
        return manifest
    finally:
        os.close(output_fd)


def _replay_attempt_context(
    *,
    repository_root: Path,
    training_execution_root: Path,
    evaluation_output_root: Path,
    base_model_path: Path,
    manifest: dict[str, Any],
    evaluation_code_git_commit: str,
    test_overrides: ReplayTestOverrides | None,
) -> ReplayAttemptContext:
    read_bytes = test_overrides.read_bytes if test_overrides else Path.read_bytes
    if test_overrides is not None:
        _require(
            test_overrides.context.authority.test_only is True,
            "replay test authority must be marked test-only",
        )
        context = (
            test_overrides.context_factory()
            if test_overrides.context_factory is not None
            else test_overrides.context
        )
        _require(
            context.authority.test_only is True,
            "replay refreshed test authority must be marked test-only",
        )
    else:
        context = _production_replay_context(
            repository_root,
            training_execution_root,
            base_model_path,
            evaluation_code_git_commit,
        )
    artifacts, config, context = _revalidate_replay_artifacts(context, read_bytes)
    frozen_files = {
        "accepted_pairs": {
            "path": str(repository_root / ACCEPTED_PAIRS_PATH),
            "sha256": config["accepted_pairs_sha256"],
        },
        "data_manifest": {
            "path": str(repository_root / DATA_MANIFEST_PATH),
            "sha256": config["data_manifest_sha256"],
        },
        "mining_rows": {
            "path": str(repository_root / MINING_ROWS_PATH),
            "sha256": config["mining_rows_sha256"],
        },
        "mining_manifest": {
            "path": str(repository_root / MINING_MANIFEST_PATH),
            "sha256": config["mining_manifest_sha256"],
        },
        "heldout_labels": {
            "path": str(repository_root / context.authority.heldout_labels_path),
            "sha256": context.authority.heldout_labels_sha256,
        },
    }
    _validate_replay_frozen_files(frozen_files, read_bytes)
    expected = _replay_manifest(
        context=context,
        evaluation_root=evaluation_output_root,
        evaluation_code_git_commit=evaluation_code_git_commit,
        training_artifacts=artifacts,
        lineage_config=config,
    )
    _require(expected == manifest, "pilot manifest changed before attempt")
    request = _replay_request(
        context, evaluation_code_git_commit, manifest["attempt_token_sha256"]
    )
    validated = ValidatedAuthorityContext(
        authority=context.authority,
        repository_root=context.repository_root,
        execution_root=context.execution_root,
        base_model_path=context.base_model_path,
        request=request,
        run_pack_documents=context.run_pack_documents,
        training_artifacts=context.training_artifacts,
    )
    output_fd, output_identity = _open_replay_output_root(evaluation_output_root)
    evaluation_fd: int | None = None
    try:
        _require_replay_output_identity(evaluation_output_root, output_identity)
        _require(
            set(os.listdir(output_fd)) == {"pilot-manifest.json", "evaluation"},
            "replay output namespace changed before attempt",
        )
        _require(
            _read_file_at(output_fd, "pilot-manifest.json")
            == _canonical_bytes(manifest),
            "pilot manifest changed before attempt",
        )
        evaluation_metadata = os.stat(
            "evaluation", dir_fd=output_fd, follow_symlinks=False
        )
        _require(
            stat.S_ISDIR(evaluation_metadata.st_mode)
            and stat.S_IMODE(evaluation_metadata.st_mode) == 0o700,
            "replay evaluation root must be a real 0700 directory",
        )
        evaluation_fd = os.open("evaluation", _directory_flags(), dir_fd=output_fd)
        _require(
            _stable_stat(os.fstat(evaluation_fd)) == _stable_stat(evaluation_metadata),
            "replay evaluation root identity mismatch",
        )
        _require(
            not os.listdir(evaluation_fd),
            "evaluation attempt already exists",
        )
        return ReplayAttemptContext(
            validated=validated,
            output_root=evaluation_output_root,
            output_fd=output_fd,
            output_identity=output_identity,
            evaluation_root=evaluation_output_root / "evaluation",
            evaluation_fd=evaluation_fd,
        )
    except BaseException:
        if evaluation_fd is not None:
            os.close(evaluation_fd)
        os.close(output_fd)
        raise


def _start_replay_attempt(
    replay: ReplayAttemptContext, request: dict[str, Any]
) -> Path:
    _require_replay_output_identity(replay.output_root, replay.output_identity)
    _require(not os.listdir(replay.evaluation_fd), "evaluation attempt already exists")
    marker = {
        "schema_version": "router-v2-evaluation-attempt-started-v1",
        "attempt_number": 1,
        "attempt_token_sha256": request["attempt_token_sha256"],
        "status": "STARTED",
        **TRUTH_FIELDS,
    }
    marker_written = False
    try:
        _write_noreplace_at(
            replay.evaluation_fd,
            "attempt-1.started.json",
            _canonical_bytes(marker),
        )
        marker_written = True
        os.fsync(replay.evaluation_fd)
        os.fsync(replay.output_fd)
    except FileExistsError as exc:
        raise ValueError("evaluation attempt already exists") from exc
    except BaseException as exc:
        if marker_written:
            try:
                _write_terminal(
                    replay.evaluation_root,
                    request,
                    status="FAILED",
                    error=exc,
                )
            except BaseException:
                pass
        raise
    return replay.evaluation_root / ".attempt-1.staging"


def _replay_request(
    context: ValidatedAuthorityContext,
    evaluation_code_git_commit: str,
    attempt_token_sha256: str,
) -> dict[str, Any]:
    rows = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in context.request["training_artifacts"]
    ]
    request = _validated_request(
        {
            **context.request,
            "training_artifacts": rows,
            "evaluation_code_git_commit": evaluation_code_git_commit,
            "attempt_token_sha256": attempt_token_sha256,
        }
    )
    originals = {
        (row["arm"], row["seed"]): row for row in context.request["training_artifacts"]
    }
    for row in request["training_artifacts"]:
        original = originals[(row["arm"], row["seed"])]
        for field in (
            "_validated_model_file_manifest",
            "_validated_model_topology",
        ):
            if field in original:
                row[field] = original[field]
    return request


def run_replay_evaluation_once(
    repository_root: Path | str,
    training_execution_root: Path | str,
    evaluation_output_root: Path | str,
    base_model_path: Path | str,
    *,
    test_overrides: ReplayTestOverrides | None = None,
) -> dict[str, Any]:
    manifest = prepare_replay_manifest(
        repository_root,
        training_execution_root,
        evaluation_output_root,
        base_model_path,
        test_overrides=test_overrides,
    )
    root = Path(repository_root).resolve(strict=True)
    training = Path(training_execution_root).resolve(strict=True)
    output = Path(evaluation_output_root).resolve(strict=True)
    base = Path(base_model_path).resolve(strict=True)
    git_probe = test_overrides.git_probe if test_overrides else _default_git_probe
    commit, clean = git_probe(root)
    _require(
        clean and commit == manifest["evaluation_code_git_commit"],
        "evaluation code must remain a clean exact commit",
    )
    initial_context = (
        test_overrides.context
        if test_overrides is not None
        else _production_replay_context(root, training, base, commit)
    )
    request = _replay_request(initial_context, commit, manifest["attempt_token_sha256"])

    def refresh_before_attempt() -> ReplayAttemptContext:
        return _replay_attempt_context(
            repository_root=root,
            training_execution_root=training,
            evaluation_output_root=output,
            base_model_path=base,
            manifest=manifest,
            evaluation_code_git_commit=commit,
            test_overrides=test_overrides,
        )

    return _run_request_once(
        execution_root=output,
        request=request,
        model_factory=test_overrides.model_factory if test_overrides else None,
        read_bytes=test_overrides.read_bytes if test_overrides else Path.read_bytes,
        clock_ns=test_overrides.clock_ns if test_overrides else time.perf_counter_ns,
        git_probe=git_probe,
        prevalidated_context=initial_context,
        pre_start_replay=refresh_before_attempt,
    )


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
    pre_start_context: Callable[[], ValidatedAuthorityContext] | None = None,
    pre_start_replay: Callable[[], ReplayAttemptContext] | None = None,
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
    _require(
        pre_start_context is None or pre_start_replay is None,
        "only one pre-start authority hook is allowed",
    )
    if pre_start_replay is not None:
        replay = pre_start_replay()
        try:
            prevalidated_context = replay.validated
            request = prevalidated_context.request
            _require(
                request["evaluation_code_git_commit"] == commit,
                "pre-attempt replay commit mismatch",
            )
            staging = _start_replay_attempt(replay, request)
        finally:
            os.close(replay.evaluation_fd)
            os.close(replay.output_fd)
    elif pre_start_context is not None:
        prevalidated_context = pre_start_context()
        request = prevalidated_context.request
        _require(
            request["evaluation_code_git_commit"] == commit,
            "pre-attempt replay commit mismatch",
        )
        staging = _start_attempt(evaluation_root, request)
    else:
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
