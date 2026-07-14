from __future__ import annotations

import ctypes
import errno
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import secrets
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from hermes_skilleval.router_query import router_query_text


BASE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001"
)
PACKAGE_DIR = BASE / "package/router-v2-v4-internal-training-package-001"
DATA_MANIFEST_PATH = PACKAGE_DIR / "data-manifest.json"
ACCEPTED_PAIRS_PATH = PACKAGE_DIR / "accepted-pairs.jsonl"
MINING_ROWS_PATH = BASE / "mining/mining.jsonl"
MINING_MANIFEST_PATH = BASE / "mining/mining-manifest.json"

DATA_MANIFEST_SHA256 = (
    "c26b1f367dabf624c580ca1f0e64da6003b670221166a5d21dfee0d123077623"
)
ACCEPTED_PAIRS_SHA256 = (
    "7bfa059ccafabe6b6ccb817e57a2984170f29e35603f3e4a6e78a585258914ff"
)
MINING_ROWS_SHA256 = "29d20c95f1e280de2a24875ea3cfbf4fd5fbae8fb513d749c13da3ab2df21f88"
MINING_MANIFEST_SHA256 = (
    "1eba5a66f5065ae6792f43c2c8b186db2628d33a2a7c2a0d9f0e0787935e6a2d"
)
SAMPLER_VERSION = "skill-unique-v1"
ALLOWED_ARMS = {"A", "B", "C"}
ALLOWED_SEEDS = {7170, 7171, 7172}
DEPENDENCY_KEYS = {
    "numpy",
    "python",
    "scikit-learn",
    "sentence-transformers",
    "torch",
    "transformers",
}
AUTHORIZED_OUTPUT_ROOT = Path("/mnt/data/minghongsun")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TRUTH_FIELDS: dict[str, object] = {
    "review_mode": "MODEL_ONLY_PILOT",
    "human_reviewer_count": 0,
    "model_review_pass_count": 2,
    "model_adjudication_enabled": True,
    "independent_human_review": False,
    "model_correlation_risk": True,
    "can_start_internal_training": True,
    "can_start_production_training": False,
    "release_eligible": False,
    "blind_v2_eligible": False,
    "router_decision": "KEEP_BASELINE",
}

EXAMPLE_FIELDS = {
    "schema_version",
    "example_id",
    "source_row_sha256",
    "query_text",
    "skill_id",
    "skill_text",
    "supervision_label",
    "fingerprint",
}
HANDOFF_FIELDS = {
    "schema_version",
    "data_manifest_sha256",
    "accepted_pairs_sha256",
    "mining_rows_sha256",
    "mining_manifest_sha256",
    "package_code_git_commit",
    "base_model_id",
    "base_model_revision",
    "base_model_file_manifest_sha256",
    "positive_count",
    "hard_negative_count",
    "examples",
    "examples_sha256",
    "handoff_fingerprint",
}
PLAN_FIELDS = {
    "schema_version",
    "sampler_version",
    "seed",
    "epochs",
    "batch_size",
    "positive_count_per_epoch",
    "handoff_fingerprint",
    "batches",
    "plan_sha256",
}
CONFIG_FIELDS = {
    "schema_version",
    "arm",
    "seed",
    "epochs",
    "batch_size",
    "learning_rate",
    "hard_negative_margin",
    "training_mode",
    "loss_contract",
    "data_manifest_sha256",
    "accepted_pairs_sha256",
    "mining_rows_sha256",
    "mining_manifest_sha256",
    "package_code_git_commit",
    "training_code_git_commit",
    "base_model_id",
    "base_model_revision",
    "base_model_file_manifest_sha256",
    "sampler_version",
    "sampler_plan_sha256",
    "handoff_fingerprint",
    "dependency_versions",
    "output_dir",
    "config_sha256",
} | set(TRUTH_FIELDS)
LINEAGE_FIELDS = (
    "data_manifest_sha256",
    "accepted_pairs_sha256",
    "mining_rows_sha256",
    "mining_manifest_sha256",
    "package_code_git_commit",
    "training_code_git_commit",
    "base_model_id",
    "base_model_revision",
    "base_model_file_manifest_sha256",
    "sampler_version",
    "sampler_plan_sha256",
    "dependency_versions",
)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _exact(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def canonical_json_line(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _loads_unique(payload: str, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains duplicate key: {key}")
            value[key] = item
        return value

    return json.loads(payload, object_pairs_hook=reject_duplicates)


def _fixed_file(root: Path, relative: Path) -> Path:
    target = (root / relative).resolve(strict=True)
    if not target.is_file() or not target.is_relative_to(root):
        raise ValueError(f"fixed input is not a repository file: {relative}")
    return target


def _json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = _loads_unique(payload.decode("utf-8", errors="strict"), label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _jsonl(payload: bytes, label: str) -> list[dict[str, Any]]:
    if not payload.endswith(b"\n"):
        raise ValueError(f"{label} must end with LF")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(payload.splitlines(keepends=True), 1):
        try:
            value = _loads_unique(line.decode("utf-8", errors="strict"), label)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} line {index} is invalid") from exc
        if not isinstance(value, dict) or line.decode() != canonical_json_line(value):
            raise ValueError(f"{label} line {index} is not canonical JSONL")
        rows.append(value)
    return rows


def load_json_object_file(path: Path | str, *, label: str) -> dict[str, Any]:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable: {exc}") from exc
    return _json(payload, label)


def _with_fingerprint(value: dict[str, Any], field: str) -> dict[str, Any]:
    unhashed = {key: item for key, item in value.items() if key != field}
    return {**unhashed, field: canonical_sha256(unhashed)}


def load_and_seal_internal_package(repository_root: Path | str) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    paths = {
        "data": _fixed_file(root, DATA_MANIFEST_PATH),
        "accepted": _fixed_file(root, ACCEPTED_PAIRS_PATH),
        "mining_rows": _fixed_file(root, MINING_ROWS_PATH),
        "mining_manifest": _fixed_file(root, MINING_MANIFEST_PATH),
    }
    payloads = {key: path.read_bytes() for key, path in paths.items()}
    expected_hashes = {
        "data": DATA_MANIFEST_SHA256,
        "accepted": ACCEPTED_PAIRS_SHA256,
        "mining_rows": MINING_ROWS_SHA256,
        "mining_manifest": MINING_MANIFEST_SHA256,
    }
    for key, expected in expected_hashes.items():
        if _sha256(payloads[key]) != expected:
            raise ValueError(f"{key} SHA-256 mismatch")

    manifest = _json(payloads["data"], "data manifest")
    mining_manifest = _json(payloads["mining_manifest"], "mining manifest")
    rows = _jsonl(payloads["accepted"], "accepted pairs")
    for field, expected_truth in TRUTH_FIELDS.items():
        if manifest.get(field) != expected_truth or type(
            manifest.get(field)
        ) is not type(expected_truth):
            raise ValueError(f"package truth field {field} mismatch")
    if manifest.get("accepted_pairs_jsonl_sha256") != ACCEPTED_PAIRS_SHA256:
        raise ValueError("accepted pairs manifest binding mismatch")
    inputs = manifest.get("input_artifact_sha256")
    if not isinstance(inputs, dict):
        raise ValueError("package input lineage is missing")
    if (
        inputs.get("mining_rows") != MINING_ROWS_SHA256
        or inputs.get("mining_manifest") != MINING_MANIFEST_SHA256
    ):
        raise ValueError("package mining lineage mismatch")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or (
        counts.get("accepted_pair_count"),
        counts.get("positive_count"),
        counts.get("hard_negative_count"),
    ) != (116, 64, 52):
        raise ValueError("package counts mismatch")
    if len(rows) != 116:
        raise ValueError("accepted pairs must contain exactly 116 rows")

    examples: list[dict[str, Any]] = []
    positive_count = 0
    hard_negative_count = 0
    for row in rows:
        if canonical_sha256(
            {k: v for k, v in row.items() if k != "row_sha256"}
        ) != row.get("row_sha256"):
            raise ValueError("accepted row SHA-256 mismatch")
        label = row.get("label")
        role = row.get("role")
        if (label, role) == (1, "POSITIVE"):
            supervision = "POSITIVE"
            positive_count += 1
        elif (label, role) == (0, "HARD_NEGATIVE"):
            supervision = "HARD_NEGATIVE"
            hard_negative_count += 1
        else:
            raise ValueError("accepted row label or role mismatch")
        for field in ("example_id", "query_text", "skill_id", "skill_text"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"accepted row {field} is invalid")
        examples.append(
            _with_fingerprint(
                {
                    "schema_version": "router-v2-pilot-validated-example-v1",
                    "example_id": row["example_id"],
                    "source_row_sha256": row["row_sha256"],
                    "query_text": router_query_text(row["query_text"]),
                    "skill_id": row["skill_id"],
                    "skill_text": row["skill_text"],
                    "supervision_label": supervision,
                },
                "fingerprint",
            )
        )
    if (positive_count, hard_negative_count) != (64, 52):
        raise ValueError("sealed example counts mismatch")
    handoff = _with_fingerprint(
        {
            "schema_version": "router-v2-pilot-sealed-handoff-v1",
            "data_manifest_sha256": DATA_MANIFEST_SHA256,
            "accepted_pairs_sha256": ACCEPTED_PAIRS_SHA256,
            "mining_rows_sha256": MINING_ROWS_SHA256,
            "mining_manifest_sha256": MINING_MANIFEST_SHA256,
            "package_code_git_commit": manifest["code_git_commit"],
            "base_model_id": mining_manifest["model_id"],
            "base_model_revision": mining_manifest["model_revision"],
            "base_model_file_manifest_sha256": mining_manifest[
                "model_file_manifest_sha256"
            ],
            "positive_count": positive_count,
            "hard_negative_count": hard_negative_count,
            "examples": examples,
            "examples_sha256": canonical_sha256(examples),
        },
        "handoff_fingerprint",
    )
    return validate_sealed_handoff(handoff)


def validate_sealed_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    if set(handoff) != HANDOFF_FIELDS:
        raise ValueError("sealed handoff fields mismatch")
    examples = handoff.get("examples")
    if not isinstance(examples, list) or len(examples) != 116:
        raise ValueError("sealed handoff examples mismatch")
    counts = {"POSITIVE": 0, "HARD_NEGATIVE": 0}
    for example in examples:
        if not isinstance(example, dict) or set(example) != EXAMPLE_FIELDS:
            raise ValueError("sealed example fields mismatch")
        if _with_fingerprint(example, "fingerprint") != example:
            raise ValueError("example fingerprint mismatch")
        skill_id = example.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            raise ValueError("sealed example skill_id mismatch")
        label = example.get("supervision_label")
        if label not in counts:
            raise ValueError("sealed example supervision mismatch")
        counts[label] += 1
    if counts != {"POSITIVE": 64, "HARD_NEGATIVE": 52}:
        raise ValueError("sealed handoff supervision counts mismatch")
    if handoff.get("examples_sha256") != canonical_sha256(examples):
        raise ValueError("sealed examples hash mismatch")
    if _with_fingerprint(handoff, "handoff_fingerprint") != handoff:
        raise ValueError("handoff fingerprint mismatch")
    return handoff


def _rng(seed: int, epoch: int, label: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{epoch}:{label}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _build_skill_unique_plan(
    handoff: dict[str, Any], *, seed: int, epochs: int
) -> dict[str, Any]:
    validate_sealed_handoff(handoff)
    if type(seed) is not int or seed not in ALLOWED_SEEDS or epochs != 3:
        raise ValueError("sampler seed or epoch count is not frozen")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in handoff["examples"]:
        if example["supervision_label"] == "POSITIVE":
            groups[example["skill_id"]].append(example)
    if len(groups) != 16 or any(len(values) != 4 for values in groups.values()):
        raise ValueError("positive skill distribution must be 16 x 4")
    batches: list[dict[str, Any]] = []
    for epoch in range(epochs):
        shuffled: dict[str, list[dict[str, Any]]] = {}
        for skill_id, values in sorted(groups.items()):
            shuffled[skill_id] = list(values)
            _rng(seed, epoch, skill_id).shuffle(shuffled[skill_id])
        for round_index in range(4):
            skill_ids = sorted(shuffled)
            _rng(seed, epoch, f"round-{round_index}").shuffle(skill_ids)
            fingerprints = [
                shuffled[skill_id][round_index]["fingerprint"] for skill_id in skill_ids
            ]
            batches.append(
                {
                    "epoch": epoch,
                    "batch_index": round_index,
                    "example_fingerprints": fingerprints,
                }
            )
    plan = _with_fingerprint(
        {
            "schema_version": "router-v2-pilot-sampler-plan-v1",
            "sampler_version": SAMPLER_VERSION,
            "seed": seed,
            "epochs": epochs,
            "batch_size": 16,
            "positive_count_per_epoch": 64,
            "handoff_fingerprint": handoff["handoff_fingerprint"],
            "batches": batches,
        },
        "plan_sha256",
    )
    return plan


def build_skill_unique_plan(
    handoff: dict[str, Any], *, seed: int, epochs: int
) -> dict[str, Any]:
    plan = _build_skill_unique_plan(handoff, seed=seed, epochs=epochs)
    return validate_skill_unique_plan(plan, handoff)


def validate_skill_unique_plan(
    plan: dict[str, Any], handoff: dict[str, Any]
) -> dict[str, Any]:
    validate_sealed_handoff(handoff)
    if set(plan) != PLAN_FIELDS or _with_fingerprint(plan, "plan_sha256") != plan:
        raise ValueError("sampler plan schema or SHA-256 mismatch")
    if (
        plan.get("sampler_version") != SAMPLER_VERSION
        or type(plan.get("seed")) is not int
        or plan.get("seed") not in ALLOWED_SEEDS
        or plan.get("epochs") != 3
        or plan.get("batch_size") != 16
        or plan.get("positive_count_per_epoch") != 64
        or plan.get("handoff_fingerprint") != handoff["handoff_fingerprint"]
    ):
        raise ValueError("sampler plan frozen fields mismatch")
    positives = {
        row["fingerprint"]: row
        for row in handoff["examples"]
        if row["supervision_label"] == "POSITIVE"
    }
    batches = plan.get("batches")
    if not isinstance(batches, list):
        raise ValueError("sampler batches are invalid")
    for epoch in range(3):
        emitted: list[str] = []
        for batch in [row for row in batches if row.get("epoch") == epoch]:
            items = batch.get("example_fingerprints")
            if not isinstance(items, list) or not 1 <= len(items) <= 16:
                raise ValueError("sampler coverage or skill collision")
            if any(item not in positives for item in items):
                raise ValueError("sampler coverage or skill collision")
            skills = [positives[item]["skill_id"] for item in items]
            if len(set(skills)) != len(skills):
                raise ValueError("sampler coverage or skill collision")
            emitted.extend(items)
        if len(emitted) != 64 or set(emitted) != set(positives):
            raise ValueError("sampler coverage or skill collision")
    expected = _build_skill_unique_plan(
        handoff, seed=plan["seed"], epochs=plan["epochs"]
    )
    if plan["batches"] != expected["batches"]:
        raise ValueError("sampler exact canonical batches mismatch")
    return plan


def _validate_dependency_versions(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != DEPENDENCY_KEYS:
        raise ValueError("dependency versions must use the exact frozen map")
    if any(not isinstance(item, str) or not item for item in value.values()):
        raise ValueError("dependency versions must be exact non-empty strings")
    return value


def _output_dir(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("output directory syntax mismatch")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("output directory syntax mismatch")
    return value


def _resolve_with_missing(path: Path) -> Path:
    missing: list[str] = []
    current = path
    while not current.exists():
        if current.parent == current:
            raise ValueError("could not resolve output path prefix")
        missing.append(current.name)
        current = current.parent
    resolved = current.resolve(strict=True)
    for part in reversed(missing):
        resolved = resolved / part
    return resolved


DirectoryIdentity = tuple[int, int, Path]


def _secure_directory_identity(path: Path, label: str) -> DirectoryIdentity:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label} must be a pre-existing directory") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be a real directory")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError(f"{label} must not be group/other writable")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError(f"{label} must have mode 0700")
    return metadata.st_dev, metadata.st_ino, path.resolve(strict=True)


def _verify_secure_directory_identity(
    path: Path, expected: DirectoryIdentity, label: str
) -> None:
    if _secure_directory_identity(path, label) != expected:
        raise ValueError(f"{label} identity drift")


def _reject_symlink_components(base: Path, target: Path, label: str) -> None:
    try:
        relative = target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"{label} is outside authorized output root") from exc
    if ".." in relative.parts:
        raise ValueError(f"{label} is outside authorized output root")
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} symlink prefix is forbidden")


def resolve_authorized_output_root(output_root: Path | str) -> Path:
    fd, resolved, _ = _open_output_root_fd(output_root)
    os.close(fd)
    return resolved


def resolve_training_output_dir(output_root: Path | str, output_dir: str) -> Path:
    root_fd, root, root_identity = _open_output_root_fd(output_root)
    relative = _output_dir(output_dir)
    target = _resolve_with_missing(root / relative)
    if not target.is_relative_to(root):
        raise ValueError("training output escapes authorized output root")
    if target.exists() or target.is_symlink():
        raise ValueError("training output directory must not already exist")
    return target


def _secure_open_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required):
        raise RuntimeError("secure directory file-descriptor operations unsupported")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _openat_directory(parent_fd: int, name: str, label: str) -> int:
    try:
        return os.open(name, _secure_open_flags(), dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ValueError(
                f"{label} contains a symlink prefix or non-directory"
            ) from exc
        if exc.errno == errno.ENOENT:
            raise ValueError(f"{label} must be pre-existing") from exc
        raise ValueError(f"{label} component is unavailable: {name}") from exc


def _open_absolute_directory_components(path: Path, label: str) -> int:
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    fd = os.open("/", _secure_open_flags())
    try:
        for part in path.parts[1:]:
            next_fd = _openat_directory(fd, part, label)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_output_root_fd(
    output_root: Path | str,
) -> tuple[int, Path, tuple[int, int]]:
    authorized = Path(AUTHORIZED_OUTPUT_ROOT)
    raw = Path(output_root)
    if not raw.is_absolute():
        raise ValueError("output root must be absolute")
    if raw.is_symlink():
        raise ValueError("output root must not be a symlink")
    try:
        relative = raw.relative_to(authorized)
    except ValueError as exc:
        raise ValueError("output root is outside authorized output root") from exc
    if ".." in relative.parts:
        raise ValueError("output root is outside authorized output root")
    fd = _open_absolute_directory_components(authorized, "authorized output root")
    try:
        _fd_identity(fd, "authorized output root")
        for part in relative.parts:
            next_fd = _openat_directory(fd, part, "output root")
            os.close(fd)
            fd = next_fd
        identity = _fd_identity(fd, "output root")
        path_identity = _secure_directory_identity(raw, "output root")
        if path_identity[:2] != identity:
            raise ValueError("output root identity drift")
        return fd, path_identity[2], identity
    except BaseException:
        os.close(fd)
        raise


def _fd_identity(fd: int, label: str) -> tuple[int, int]:
    metadata = os.fstat(fd)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} file descriptor is not a directory")
    mode = stat.S_IMODE(metadata.st_mode)
    if mode & 0o022:
        raise ValueError(f"{label} file descriptor must not be group/other writable")
    if mode != 0o700:
        raise ValueError(f"{label} file descriptor must have mode 0700")
    return metadata.st_dev, metadata.st_ino


def _verify_entry_identity(
    parent_fd: int, name: str, expected: tuple[int, int], label: str
) -> None:
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != expected
    ):
        raise ValueError(f"{label} identity drift")


def _entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _fd_access_path(fd: int, *, darwin_fallback: Path | None = None) -> Path:
    if sys.platform.startswith("linux"):
        return Path(f"/proc/self/fd/{fd}")
    if sys.platform == "darwin" and darwin_fallback is not None:
        return darwin_fallback
    raise RuntimeError(f"secure staging path unsupported on {sys.platform}")


def _remove_tree_at(parent_fd: int, name: str) -> None:
    try:
        child_fd = os.open(name, _secure_open_flags(), dir_fd=parent_fd)
    except FileNotFoundError:
        return
    try:
        for child_name in os.listdir(child_fd):
            metadata = os.stat(child_name, dir_fd=child_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                _remove_tree_at(child_fd, child_name)
            else:
                os.unlink(child_name, dir_fd=child_fd)
    finally:
        os.close(child_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _atomic_publish_noreplace_dirfd(
    parent_fd: int, source_name: str, target_name: str
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError as exc:
            raise RuntimeError(
                "no supported dirfd no-replace primitive: renameat2 unavailable"
            ) from exc
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            parent_fd,
            os.fsencode(source_name),
            parent_fd,
            os.fsencode(target_name),
            1,
        )
    elif sys.platform == "darwin":
        try:
            rename = libc.renameatx_np
        except AttributeError as exc:
            raise RuntimeError(
                "no supported dirfd no-replace primitive: renameatx_np unavailable"
            ) from exc
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            parent_fd,
            os.fsencode(source_name),
            parent_fd,
            os.fsencode(target_name),
            0x00000004,
        )
    else:
        raise RuntimeError(
            f"no supported dirfd no-replace primitive for {sys.platform}"
        )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, os.strerror(error), target_name)
        raise OSError(error, os.strerror(error), target_name)


def _atomic_output_publish(
    output_root: Path | str,
    output_dir: str,
    writer: Callable[[Path], None],
) -> Path:
    root_fd, root, root_identity = _open_output_root_fd(output_root)
    relative = PurePosixPath(_output_dir(output_dir))
    if len(relative.parts) != 2:
        raise ValueError("training output must have one secure arm parent")
    parent_name, target_name = relative.parts
    parent_path = root / parent_name
    parent_created = False
    parent_fd = -1
    staging_fd = -1
    staging_name = f".{target_name}.staging-{secrets.token_hex(8)}"
    published = False
    try:
        try:
            os.mkdir(parent_name, mode=0o700, dir_fd=root_fd)
            parent_created = True
        except FileExistsError:
            pass
        parent_fd = _openat_directory(root_fd, parent_name, "training output parent")
        if parent_created:
            os.fchmod(parent_fd, 0o700)
        parent_identity = _fd_identity(parent_fd, "training output parent")
        _verify_entry_identity(
            root_fd, parent_name, parent_identity, "training output parent"
        )
        parent_path_identity = _secure_directory_identity(
            parent_path, "training output parent"
        )
        if parent_path_identity[:2] != parent_identity:
            raise ValueError("training output parent identity drift")
        if _entry_exists(parent_fd, target_name):
            raise ValueError("training output directory must not already exist")
        os.mkdir(staging_name, mode=0o700, dir_fd=parent_fd)
        staging_fd = _openat_directory(parent_fd, staging_name, "training staging")
        os.fchmod(staging_fd, 0o700)
        staging_identity = _fd_identity(staging_fd, "training staging")
        staging = (
            Path(f"/proc/self/fd/{staging_fd}")
            if sys.platform.startswith("linux")
            else parent_path / staging_name
        )
        writer(staging)
        if _fd_identity(root_fd, "output root") != root_identity:
            raise ValueError("output root identity drift")
        _verify_entry_identity(
            root_fd, parent_name, parent_identity, "training output parent"
        )
        if (
            _secure_directory_identity(parent_path, "training output parent")
            != parent_path_identity
        ):
            raise ValueError("training output parent identity drift")
        if _fd_identity(parent_fd, "training output parent") != parent_identity:
            raise ValueError("training output parent identity drift")
        _verify_entry_identity(
            parent_fd, staging_name, staging_identity, "training staging"
        )
        if _entry_exists(parent_fd, target_name):
            raise ValueError("training output directory appeared during staging")
        _atomic_publish_noreplace_dirfd(parent_fd, staging_name, target_name)
        _verify_entry_identity(
            parent_fd, target_name, staging_identity, "published training output"
        )
        _verify_entry_identity(
            root_fd, parent_name, parent_identity, "training output parent"
        )
        published = True
        return root / parent_name / target_name
    finally:
        if parent_fd >= 0:
            if not published and _entry_exists(parent_fd, staging_name):
                _remove_tree_at(parent_fd, staging_name)
            if staging_fd >= 0:
                os.close(staging_fd)
            os.close(parent_fd)
        if parent_created and not published:
            try:
                _verify_entry_identity(
                    root_fd, parent_name, parent_identity, "training output parent"
                )
                os.rmdir(parent_name, dir_fd=root_fd)
            except (FileNotFoundError, OSError, UnboundLocalError, ValueError):
                pass
        os.close(root_fd)


def build_frozen_config(
    *,
    handoff: dict[str, Any],
    plan: dict[str, Any],
    arm: str,
    seed: int,
    training_code_git_commit: str,
    dependency_versions: dict[str, str],
    output_dir: str,
) -> dict[str, Any]:
    validate_sealed_handoff(handoff)
    validate_skill_unique_plan(plan, handoff)
    modes = {
        "A": ("EVALUATION_ONLY", "NONE"),
        "B": ("POSITIVE_ONLY", "MultipleNegativesRankingLoss"),
        "C": (
            "POSITIVE_AND_HARD_NEGATIVE",
            "MultipleNegativesRankingLoss+ContrastiveLoss",
        ),
    }
    if (
        arm not in modes
        or type(seed) is not int
        or seed not in ALLOWED_SEEDS
        or plan["seed"] != seed
    ):
        raise ValueError("arm or seed is not preregistered")
    if HEX40.fullmatch(training_code_git_commit) is None:
        raise ValueError("training code Git commit is invalid")
    expected_output_dir = f"arm-{arm}/seed-{seed}"
    if output_dir != expected_output_dir:
        raise ValueError("output directory does not match frozen arm/seed mapping")
    dependencies = _validate_dependency_versions(dependency_versions)
    mode, loss = modes[arm]
    config = _with_fingerprint(
        {
            "schema_version": "router-v2-pilot-frozen-config-v1",
            "arm": arm,
            "seed": seed,
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": "0.00002000",
            "hard_negative_margin": "1.50000000",
            "training_mode": mode,
            "loss_contract": loss,
            **{field: handoff[field] for field in LINEAGE_FIELDS[:5]},
            "training_code_git_commit": training_code_git_commit,
            "base_model_id": handoff["base_model_id"],
            "base_model_revision": handoff["base_model_revision"],
            "base_model_file_manifest_sha256": handoff[
                "base_model_file_manifest_sha256"
            ],
            "sampler_version": SAMPLER_VERSION,
            "sampler_plan_sha256": plan["plan_sha256"],
            "handoff_fingerprint": handoff["handoff_fingerprint"],
            "dependency_versions": dict(sorted(dependencies.items())),
            "output_dir": _output_dir(expected_output_dir),
            **TRUTH_FIELDS,
        },
        "config_sha256",
    )
    return validate_frozen_config(config, handoff, plan)


def validate_frozen_config(
    config: dict[str, Any], handoff: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    validate_sealed_handoff(handoff)
    validate_skill_unique_plan(plan, handoff)
    if (
        set(config) != CONFIG_FIELDS
        or _with_fingerprint(config, "config_sha256") != config
    ):
        raise ValueError("frozen config schema or SHA-256 mismatch")
    for field, expected_truth in TRUTH_FIELDS.items():
        if not _exact(config.get(field), expected_truth):
            raise ValueError(f"config truth field {field} mismatch")
    arm = config.get("arm")
    modes = {
        "A": ("EVALUATION_ONLY", "NONE"),
        "B": ("POSITIVE_ONLY", "MultipleNegativesRankingLoss"),
        "C": (
            "POSITIVE_AND_HARD_NEGATIVE",
            "MultipleNegativesRankingLoss+ContrastiveLoss",
        ),
    }
    if (
        arm not in modes
        or config.get("training_mode") != modes[arm][0]
        or config.get("loss_contract") != modes[arm][1]
    ):
        raise ValueError("frozen arm contract mismatch")
    if (
        type(config.get("seed")) is not int
        or config.get("seed") not in ALLOWED_SEEDS
        or not _exact(config.get("seed"), plan["seed"])
        or not _exact(config.get("epochs"), 3)
        or not _exact(config.get("batch_size"), 16)
        or not _exact(config.get("learning_rate"), "0.00002000")
        or not _exact(config.get("hard_negative_margin"), "1.50000000")
    ):
        raise ValueError("frozen hyperparameter mismatch")
    if HEX40.fullmatch(str(config.get("training_code_git_commit"))) is None:
        raise ValueError("training code Git commit mismatch")
    for field in LINEAGE_FIELDS[:5]:
        if config.get(field) != handoff[field]:
            raise ValueError(f"{field} lineage mismatch")
    if (
        config.get("base_model_id") != handoff["base_model_id"]
        or config.get("base_model_revision") != handoff["base_model_revision"]
        or config.get("base_model_file_manifest_sha256")
        != handoff["base_model_file_manifest_sha256"]
        or config.get("sampler_version") != SAMPLER_VERSION
        or config.get("sampler_plan_sha256") != plan["plan_sha256"]
        or config.get("handoff_fingerprint") != handoff["handoff_fingerprint"]
    ):
        raise ValueError("config lineage mismatch")
    _validate_dependency_versions(config.get("dependency_versions"))
    if config.get("output_dir") != f"arm-{arm}/seed-{config['seed']}":
        raise ValueError("output directory does not match frozen arm/seed mapping")
    _output_dir(config.get("output_dir"))
    return config


def _model_manifest(repository_root: Path | str) -> list[dict[str, Any]]:
    root = Path(repository_root).resolve(strict=True)
    payload = _fixed_file(root, MINING_MANIFEST_PATH).read_bytes()
    if _sha256(payload) != MINING_MANIFEST_SHA256:
        raise ValueError("mining manifest SHA-256 mismatch")
    value = _json(payload, "mining manifest").get("model_file_manifest")
    try:
        return _validate_model_file_manifest(value)
    except ValueError as exc:
        raise ValueError("base model snapshot manifest is invalid") from exc


def _validate_model_file_manifest(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("model files must be a list")
    paths: list[str] = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise ValueError("model files use an invalid exact schema")
        path = row.get("path")
        if not isinstance(path, str) or not path or "\\" in path:
            raise ValueError("model files contain an invalid path")
        relative = PurePosixPath(path)
        if relative.is_absolute() or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise ValueError("model files contain an invalid path")
        if HEX64.fullmatch(str(row.get("sha256"))) is None:
            raise ValueError("model files contain an invalid SHA-256")
        if type(row.get("size")) is not int or row["size"] < 0:
            raise ValueError("model files contain an invalid size")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("model files must be unique and canonically sorted")
    return value


def preflight_for_test(
    *,
    repository_root: Path | str,
    config: dict[str, Any],
    base_model_path: Path | str,
    output_root: Path | str,
    training_code_git_commit: str,
    dependency_versions: dict[str, str],
    model_file_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    handoff = load_and_seal_internal_package(repository_root)
    plan = build_skill_unique_plan(handoff, seed=config["seed"], epochs=3)
    validate_frozen_config(config, handoff, plan)
    if config["training_code_git_commit"] != training_code_git_commit:
        raise ValueError("training code Git commit mismatch")
    if config["dependency_versions"] != dependency_versions:
        raise ValueError("dependency versions mismatch")
    expected_model_files = _model_manifest(repository_root)
    if (
        model_file_manifest != expected_model_files
        or canonical_sha256(model_file_manifest)
        != config["base_model_file_manifest_sha256"]
    ):
        raise ValueError("base model snapshot hash mismatch")
    model_path = Path(base_model_path)
    if not model_path.is_absolute():
        raise ValueError("base model path must be absolute")
    resolve_training_output_dir(output_root, config["output_dir"])
    result = {
        "schema_version": "router-v2-pilot-preflight-result-v1",
        "preflight_status": "PASS",
        "arm": config["arm"],
        "seed": config["seed"],
        "config_sha256": config["config_sha256"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "sampler_plan_sha256": plan["plan_sha256"],
        "training_code_git_commit": training_code_git_commit,
        "training_executed": False,
        "files_written": 0,
        **TRUTH_FIELDS,
    }
    return validate_preflight_result(result, config, handoff, plan)


def validate_preflight_result(
    result: dict[str, Any],
    config: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "preflight_status",
        "arm",
        "seed",
        "config_sha256",
        "handoff_fingerprint",
        "sampler_plan_sha256",
        "training_code_git_commit",
        "training_executed",
        "files_written",
        *TRUTH_FIELDS,
    }
    if set(result) != expected_fields:
        raise ValueError("preflight result exact schema mismatch")
    if (
        not _exact(result.get("schema_version"), "router-v2-pilot-preflight-result-v1")
        or not _exact(result.get("preflight_status"), "PASS")
        or not _exact(result.get("arm"), config["arm"])
        or not _exact(result.get("seed"), config["seed"])
        or not _exact(result.get("training_executed"), False)
        or not _exact(result.get("files_written"), 0)
        or not _exact(result.get("config_sha256"), config["config_sha256"])
        or not _exact(result.get("handoff_fingerprint"), handoff["handoff_fingerprint"])
        or not _exact(result.get("sampler_plan_sha256"), plan["plan_sha256"])
        or not _exact(
            result.get("training_code_git_commit"),
            config["training_code_git_commit"],
        )
    ):
        raise ValueError("preflight result status or binding mismatch")
    for field, expected_truth in TRUTH_FIELDS.items():
        if not _exact(result.get(field), expected_truth):
            raise ValueError(f"preflight truth field {field} mismatch")
    return result


def _clean_git_commit(root: Path) -> str:
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    head = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    status = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout
    if HEX40.fullmatch(head) is None or status != "":
        raise ValueError("training code lineage requires a clean 40-hex Git HEAD")
    return head


def dependency_versions() -> dict[str, str]:
    return {
        "numpy": importlib.metadata.version("numpy"),
        "python": platform.python_version(),
        "scikit-learn": importlib.metadata.version("scikit-learn"),
        "sentence-transformers": importlib.metadata.version("sentence-transformers"),
        "torch": importlib.metadata.version("torch"),
        "transformers": importlib.metadata.version("transformers"),
    }


def snapshot_model_files(model_path: Path | str) -> list[dict[str, Any]]:
    root = Path(model_path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("base model path must be a directory")
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(payload),
                "size": len(payload),
            }
        )
    return rows


def preflight(
    *,
    repository_root: Path | str,
    config: dict[str, Any],
    base_model_path: Path | str,
    output_root: Path | str,
) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    return preflight_for_test(
        repository_root=root,
        config=config,
        base_model_path=base_model_path,
        output_root=output_root,
        training_code_git_commit=_clean_git_commit(root),
        dependency_versions=dependency_versions(),
        model_file_manifest=snapshot_model_files(base_model_path),
    )


def _lineage(config: dict[str, Any]) -> dict[str, Any]:
    return {field: config[field] for field in LINEAGE_FIELDS}


def build_run_summary(
    config: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    validate_frozen_config(config, handoff, plan)
    summary = {
        "schema_version": "router-v2-pilot-run-summary-v1",
        "arm": config["arm"],
        "seed": config["seed"],
        "training_mode": config["training_mode"],
        "training_executed": execution.get("training_executed", False),
        "runtime_status": execution.get("status", "READY_NOT_EXECUTED"),
        "device": execution.get("device", "evaluation-only"),
        "optimizer_step_count": execution.get("optimizer_step_count", 0),
        "hard_negative_optimizer_step_count": execution.get(
            "hard_negative_optimizer_step_count", 0
        ),
        "trained_example_count": execution.get("trained_example_count", 0),
        "loss_values": execution.get("loss_values", []),
        "model_file_manifest": execution.get("model_file_manifest", []),
        "model_file_manifest_sha256": canonical_sha256(
            execution.get("model_file_manifest", [])
        ),
        "output_dir": config["output_dir"],
        "config_sha256": config["config_sha256"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "positive_count": handoff["positive_count"],
        "hard_negative_count": handoff["hard_negative_count"],
        **_lineage(config),
        **TRUTH_FIELDS,
    }
    sealed = _with_fingerprint(summary, "summary_sha256")
    return validate_run_summary(sealed, config, handoff, plan)


def validate_run_summary(
    summary: dict[str, Any],
    config: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    validate_frozen_config(config, handoff, plan)
    expected_fields = {
        "schema_version",
        "arm",
        "seed",
        "training_mode",
        "training_executed",
        "runtime_status",
        "device",
        "optimizer_step_count",
        "hard_negative_optimizer_step_count",
        "trained_example_count",
        "loss_values",
        "model_file_manifest",
        "model_file_manifest_sha256",
        "output_dir",
        "config_sha256",
        "handoff_fingerprint",
        "positive_count",
        "hard_negative_count",
        "summary_sha256",
        *LINEAGE_FIELDS,
        *TRUTH_FIELDS,
    }
    losses_value = summary.get("loss_values")
    if not isinstance(losses_value, list) or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in losses_value
    ):
        raise ValueError("run summary losses must be finite JSON numbers")
    if set(summary) != expected_fields:
        raise ValueError("run summary exact schema or SHA-256 mismatch")
    try:
        fingerprint_matches = _with_fingerprint(summary, "summary_sha256") == summary
    except (TypeError, ValueError):
        fingerprint_matches = False
    if not fingerprint_matches:
        raise ValueError("run summary exact schema or SHA-256 mismatch")
    exact_bindings = {
        "schema_version": "router-v2-pilot-run-summary-v1",
        "arm": config["arm"],
        "seed": config["seed"],
        "training_mode": config["training_mode"],
        "positive_count": handoff["positive_count"],
        "hard_negative_count": handoff["hard_negative_count"],
        "config_sha256": config["config_sha256"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "output_dir": config["output_dir"],
    }
    for field, expected in exact_bindings.items():
        if not _exact(summary.get(field), expected):
            raise ValueError(f"run summary {field} binding mismatch")
    for field in LINEAGE_FIELDS:
        if not _exact(summary.get(field), config[field]):
            raise ValueError(f"run summary {field} mismatch")
    for field, expected_truth in TRUTH_FIELDS.items():
        if not _exact(summary.get(field), expected_truth):
            raise ValueError(f"run summary truth field {field} mismatch")
    if config["arm"] == "A":
        expected_execution = {
            "training_executed": False,
            "runtime_status": "EVALUATION_METADATA_WRITTEN",
            "device": "evaluation-only",
            "optimizer_step_count": 0,
            "hard_negative_optimizer_step_count": 0,
            "trained_example_count": 0,
            "loss_values": [],
            "model_file_manifest": [],
        }
    else:
        hard_negative_steps = 12 if config["arm"] == "C" else 0
        optimizer_steps = 12 + hard_negative_steps
        expected_execution = {
            "training_executed": True,
            "runtime_status": "TRAINING_COMPLETED",
            "optimizer_step_count": optimizer_steps,
            "hard_negative_optimizer_step_count": hard_negative_steps,
            "trained_example_count": 116 if config["arm"] == "C" else 64,
        }
        if (
            not isinstance(summary.get("device"), str)
            or not summary["device"]
            or summary["device"] == "evaluation-only"
            or not isinstance(summary.get("loss_values"), list)
            or len(summary["loss_values"]) != optimizer_steps
            or not summary.get("model_file_manifest")
        ):
            raise ValueError("run summary execution contract mismatch")
    if any(
        not _exact(summary.get(field), value)
        for field, value in expected_execution.items()
    ):
        if config["arm"] == "A" and summary.get("training_executed") is not False:
            raise ValueError("Arm A cannot report training executed")
        raise ValueError("run summary execution contract mismatch")
    model_files = summary.get("model_file_manifest")
    try:
        validated_model_files = _validate_model_file_manifest(model_files)
    except ValueError as exc:
        raise ValueError("run summary model files mismatch") from exc
    if summary.get("model_file_manifest_sha256") != canonical_sha256(
        validated_model_files
    ):
        raise ValueError("run summary model files mismatch")
    return summary


def build_model_manifest_contract(
    config: dict[str, Any],
    summary: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    validate_run_summary(summary, config, handoff, plan)
    manifest = {
        "schema_version": "router-v2-pilot-model-manifest-v1",
        "arm": config["arm"],
        "seed": config["seed"],
        "training_executed": summary["training_executed"],
        "run_summary_sha256": summary["summary_sha256"],
        "config_sha256": config["config_sha256"],
        "handoff_fingerprint": summary["handoff_fingerprint"],
        "output_dir": config["output_dir"],
        "model_file_manifest": summary["model_file_manifest"],
        "model_file_manifest_sha256": summary["model_file_manifest_sha256"],
        **_lineage(config),
        **TRUTH_FIELDS,
    }
    sealed = _with_fingerprint(manifest, "model_manifest_sha256")
    return validate_model_manifest_contract(sealed, config, summary, handoff, plan)


def validate_model_manifest_contract(
    manifest: dict[str, Any],
    config: dict[str, Any],
    summary: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    validate_run_summary(summary, config, handoff, plan)
    expected_fields = {
        "schema_version",
        "arm",
        "seed",
        "training_executed",
        "run_summary_sha256",
        "config_sha256",
        "handoff_fingerprint",
        "output_dir",
        "model_file_manifest",
        "model_file_manifest_sha256",
        "model_manifest_sha256",
        *LINEAGE_FIELDS,
        *TRUTH_FIELDS,
    }
    if set(manifest) != expected_fields:
        raise ValueError("model manifest exact schema or SHA-256 mismatch")
    try:
        fingerprint_matches = (
            _with_fingerprint(manifest, "model_manifest_sha256") == manifest
        )
    except (TypeError, ValueError):
        fingerprint_matches = False
    if not fingerprint_matches:
        raise ValueError("model manifest exact schema or SHA-256 mismatch")
    exact_bindings = {
        "schema_version": "router-v2-pilot-model-manifest-v1",
        "arm": config["arm"],
        "seed": config["seed"],
        "training_executed": summary["training_executed"],
        "run_summary_sha256": summary["summary_sha256"],
        "config_sha256": config["config_sha256"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "output_dir": config["output_dir"],
        "model_file_manifest": summary["model_file_manifest"],
        "model_file_manifest_sha256": summary["model_file_manifest_sha256"],
    }
    for field, expected in exact_bindings.items():
        if not _exact(manifest.get(field), expected):
            raise ValueError(
                f"model manifest {field} validated summary binding mismatch"
            )
    for field in LINEAGE_FIELDS:
        if not _exact(manifest.get(field), config[field]):
            raise ValueError(f"model manifest {field} mismatch")
    for field, expected_truth in TRUTH_FIELDS.items():
        if not _exact(manifest.get(field), expected_truth):
            raise ValueError(f"model manifest truth field {field} mismatch")
    return manifest


def _batch_to_device(batch: dict[str, Any], device: Any) -> dict[str, Any]:
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in batch.items()
    }


def _training_features(model: Any, examples: list[dict[str, Any]]) -> list[Any]:
    return [
        _batch_to_device(
            model.tokenize([router_query_text(row["query_text"]) for row in examples]),
            model.device,
        ),
        _batch_to_device(
            model.tokenize([row["skill_text"] for row in examples]), model.device
        ),
    ]


def execute_training_run(
    config: dict[str, Any],
    handoff: dict[str, Any],
    plan: dict[str, Any],
    *,
    repository_root: Path | str,
    preflight_result: dict[str, Any],
    base_model_path: Path | str,
    output_root: Path | str,
) -> dict[str, Any]:
    validate_frozen_config(config, handoff, plan)
    validate_preflight_result(preflight_result, config, handoff, plan)
    root = Path(repository_root).resolve(strict=True)
    clean_commit = _clean_git_commit(root)
    if config["training_code_git_commit"] != clean_commit:
        raise ValueError("training code Git commit mismatch")
    observed_dependencies = dependency_versions()
    if config["dependency_versions"] != observed_dependencies:
        raise ValueError("dependency versions mismatch")
    base_model = Path(base_model_path).resolve(strict=True)
    if not base_model.is_dir():
        raise ValueError("base model path must be a directory")
    observed_model_files = snapshot_model_files(base_model)
    if (
        observed_model_files != _model_manifest(root)
        or canonical_sha256(observed_model_files)
        != config["base_model_file_manifest_sha256"]
    ):
        raise ValueError("base model snapshot hash mismatch")
    resolve_training_output_dir(output_root, config["output_dir"])
    completed_summary: dict[str, Any] | None = None

    def write_and_validate(staging: Path) -> None:
        nonlocal completed_summary
        execution: dict[str, Any] = {
            "training_executed": False,
            "status": "EVALUATION_METADATA_WRITTEN",
            "device": "evaluation-only",
            "optimizer_step_count": 0,
            "hard_negative_optimizer_step_count": 0,
            "trained_example_count": 0,
            "loss_values": [],
            "model_file_manifest": [],
        }
        if config["arm"] != "A":
            model_input = staging / "base-model-input"
            shutil.copytree(base_model, model_input, symlinks=False)
            copied_model_files = snapshot_model_files(model_input)
            if (
                copied_model_files != observed_model_files
                or canonical_sha256(copied_model_files)
                != config["base_model_file_manifest_sha256"]
            ):
                raise ValueError("copied base model snapshot mismatch")
            try:
                import torch
                from sentence_transformers import SentenceTransformer, losses  # type: ignore[attr-defined]
            except (ImportError, ModuleNotFoundError) as exc:
                raise RuntimeError("training frameworks are unavailable") from exc
            seed = config["seed"]
            random.seed(seed)
            torch.manual_seed(seed)
            torch.use_deterministic_algorithms(True)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            if hasattr(torch, "backends") and hasattr(torch.backends, "cudnn"):
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
            model = SentenceTransformer(str(model_input))
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = model.to(device)
            model.train()
            mnrl = losses.MultipleNegativesRankingLoss(model)
            contrastive = (
                losses.ContrastiveLoss(model, margin=1.5)
                if config["arm"] == "C"
                else None
            )
            optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
            by_fingerprint = {row["fingerprint"]: row for row in handoff["examples"]}
            observed_losses: list[float] = []
            optimizer_steps = 0
            hard_negative_steps = 0
            for batch in plan["batches"]:
                examples = [
                    by_fingerprint[item] for item in batch["example_fingerprints"]
                ]
                labels = torch.empty(len(examples), device=model.device)
                optimizer.zero_grad()
                loss = mnrl(_training_features(model, examples), labels)
                loss.backward()
                optimizer.step()
                optimizer_steps += 1
                observed_losses.append(float(loss.detach().cpu()))
            if contrastive is not None:
                hard_negatives = [
                    row
                    for row in handoff["examples"]
                    if row["supervision_label"] == "HARD_NEGATIVE"
                ]
                for epoch in range(3):
                    epoch_rows = list(hard_negatives)
                    _rng(seed, epoch, "hard-negatives").shuffle(epoch_rows)
                    for start in range(0, len(epoch_rows), 16):
                        examples = epoch_rows[start : start + 16]
                        labels = torch.zeros(len(examples), device=model.device)
                        optimizer.zero_grad()
                        loss = contrastive(_training_features(model, examples), labels)
                        loss.backward()
                        optimizer.step()
                        optimizer_steps += 1
                        hard_negative_steps += 1
                        observed_losses.append(float(loss.detach().cpu()))
            shutil.rmtree(model_input)
            model.save(str(staging), create_model_card=False)
            execution = {
                "training_executed": True,
                "status": "TRAINING_COMPLETED",
                "device": str(model.device),
                "optimizer_step_count": optimizer_steps,
                "hard_negative_optimizer_step_count": hard_negative_steps,
                "trained_example_count": 64 if config["arm"] == "B" else 116,
                "loss_values": observed_losses,
                "model_file_manifest": snapshot_model_files(staging),
            }
        summary = build_run_summary(config, handoff, plan, execution)
        manifest = build_model_manifest_contract(config, summary, handoff, plan)
        (staging / "train-run-summary.json").write_text(
            canonical_json_line(summary), encoding="utf-8"
        )
        (staging / "model-manifest.json").write_text(
            canonical_json_line(manifest), encoding="utf-8"
        )
        written_summary = load_json_object_file(
            staging / "train-run-summary.json", label="run summary"
        )
        written_manifest = load_json_object_file(
            staging / "model-manifest.json", label="model manifest"
        )
        validate_run_summary(written_summary, config, handoff, plan)
        validate_model_manifest_contract(
            written_manifest, config, written_summary, handoff, plan
        )
        completed_summary = written_summary

    _atomic_output_publish(output_root, config["output_dir"], write_and_validate)
    if completed_summary is None:
        raise RuntimeError("training output was not validated")
    return completed_summary
