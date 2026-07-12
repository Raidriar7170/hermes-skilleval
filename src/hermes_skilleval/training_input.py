from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NoReturn


_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_version",
        "policy_id",
        "package_id",
        "accepted_pairs",
        "qualification_report",
    }
)
_ACCEPTED_PAIRS_FIELDS = frozenset({"path", "sha256", "row_count"})
_QUALIFICATION_REPORT_FIELDS = frozenset({"path", "sha256"})
_ACCEPTED_ROW_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_version",
        "policy_id",
        "accepted_record_id",
        "pair_id",
        "source_record_id",
        "source_schema_version",
        "source_kind",
        "source_dataset_id",
        "source_artifact_path",
        "source_split",
        "candidate_type",
        "task_id",
        "skill_id",
        "query_text",
        "query_text_policy",
        "prompt_text_sha256",
        "skill_text",
        "accepted_for_training",
        "training_split",
        "supervision_label",
        "review_status",
        "reviewer",
        "review_reason",
        "source_hash",
        "acceptance_hash",
    }
)
_SOURCE_HASH_FIELDS = (
    "source_record_id",
    "pair_id",
    "source_schema_version",
    "source_kind",
    "source_dataset_id",
    "source_artifact_path",
    "source_split",
    "candidate_type",
    "task_id",
    "skill_id",
    "query_text",
    "query_text_policy",
    "prompt_text_sha256",
    "skill_text",
)
_ACCEPTANCE_HASH_FIELDS = (
    "source_hash",
    "policy_id",
    "accepted_record_id",
    "pair_id",
    "supervision_label",
    "accepted_for_training",
    "training_split",
    "review_status",
    "reviewer",
    "review_reason",
)

_MANIFEST_SCHEMA = "router-training-data-v2-training-input-manifest-v3"
_ACCEPTED_ROW_SCHEMA = "router-training-data-v2-accepted-pair-v3"
_ADMISSION_POLICY = "router-training-data-v2-training-admission-v3"
_REPORT_SCHEMA = "router-training-data-v2-qualification-report-v3"
_QUALIFICATION_POLICY = "router-training-data-v2-qualification-v3"
_SOURCE_SCHEMA = "router-training-data-v2-candidate-v3"
_SOURCE_KIND = "ROUTER_TRAINING_DATA_V2_CANDIDATE"
_SOURCE_DATASET = "router-training-data-v2-qualification-pack"
_SOURCE_ARTIFACT = (
    "docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

TrainingSupervision = Literal["POSITIVE", "HARD_NEGATIVE"]
_ValidatedExampleValues = tuple[str, str, str, TrainingSupervision]


class TrainingInputError(ValueError):
    """Raised when a training-input package fails the exact v3 admission gate."""


def _load_training_input_values(
    manifest_path: str | Path,
) -> tuple[str, tuple[_ValidatedExampleValues, ...]]:
    """Validate one exact v3 package before any sealed object is constructed."""

    manifest_file = Path(manifest_path)
    manifest = _read_json_object(manifest_file, "manifest")
    _require_exact_fields(manifest, _MANIFEST_FIELDS, "manifest")
    _require_equal(manifest, "schema_version", _MANIFEST_SCHEMA, "manifest")
    _require_int_equal(manifest, "artifact_version", 3, "manifest")
    _require_equal(manifest, "policy_id", _ADMISSION_POLICY, "manifest")
    package_id = _require_nonblank_string(manifest, "package_id", "manifest")

    accepted_binding = _require_object(manifest, "accepted_pairs", "manifest")
    report_binding = _require_object(manifest, "qualification_report", "manifest")
    _require_exact_fields(accepted_binding, _ACCEPTED_PAIRS_FIELDS, "accepted_pairs")
    _require_exact_fields(
        report_binding, _QUALIFICATION_REPORT_FIELDS, "qualification_report"
    )
    accepted_hash = _require_sha256(accepted_binding, "sha256", "accepted_pairs")
    report_hash = _require_sha256(report_binding, "sha256", "qualification_report")
    row_count = _require_positive_int(accepted_binding, "row_count", "accepted_pairs")

    try:
        package_root = manifest_file.parent.resolve(strict=True)
    except OSError as exc:
        _fail(str(manifest_file), f"package root is unavailable: {exc}")
    accepted_file = _resolve_bound_file(
        package_root,
        accepted_binding.get("path"),
        "accepted_pairs.path",
    )
    report_file = _resolve_bound_file(
        package_root,
        report_binding.get("path"),
        "qualification_report.path",
    )
    try:
        if os.path.samefile(accepted_file, report_file):
            _fail("manifest", "bound inputs must resolve to distinct files")
    except OSError as exc:
        _fail("manifest", f"could not compare bound inputs: {exc}")

    accepted_bytes = _read_bound_bytes(accepted_file, "accepted_pairs.path")
    report_bytes = _read_bound_bytes(report_file, "qualification_report.path")
    _verify_bound_hash(accepted_bytes, accepted_hash, "accepted_pairs.sha256")
    _verify_bound_hash(report_bytes, report_hash, "qualification_report.sha256")
    physical_rows = accepted_bytes.splitlines()
    if len(physical_rows) != row_count:
        _fail(
            "accepted_pairs.row_count",
            f"declares {row_count}, but bound file has {len(physical_rows)} rows",
        )

    report = _parse_json_object_bytes(report_bytes, report_file, "qualification report")
    _validate_report(report, row_count)
    rows = _parse_accepted_rows(physical_rows, accepted_file)
    examples = _validate_rows(rows, accepted_file)
    if len(examples) != row_count:
        _fail(
            "accepted_pairs.row_count",
            f"declares {row_count}, but parsed file has {len(examples)} rows",
        )
    return package_id, tuple(examples)


def _resolve_bound_file(root: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        _fail(label, "must be a non-empty canonical POSIX-relative string")
    if "\\" in raw_path:
        _fail(label, "must not contain a backslash")
    pure = PurePosixPath(raw_path)
    parts = raw_path.split("/")
    if pure.is_absolute() or raw_path == ".":
        _fail(label, "must be a canonical POSIX-relative path")
    if any(part in {"", ".", ".."} for part in parts):
        _fail(label, "contains an empty, dot, or dot-dot segment")
    if pure.as_posix() != raw_path:
        _fail(label, "is not already in canonical POSIX form")

    current = root
    for part in parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            _fail(label, f"bound path does not exist: {exc}")
        if stat.S_ISLNK(mode):
            _fail(label, "must not traverse a symlink component or target")
    if not stat.S_ISREG(mode):
        _fail(label, "must resolve to an existing regular file")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        _fail(label, f"must remain inside the package root: {exc}")
    return current


def _validate_report(report: dict[str, Any], row_count: int) -> None:
    label = "qualification report"
    _require_equal(report, "schema_version", _REPORT_SCHEMA, label)
    _require_int_equal(report, "artifact_version", 3, label)
    _require_equal(report, "policy_id", _QUALIFICATION_POLICY, label)
    if report.get("can_start_training") is not True:
        _fail(label, "can_start_training must be true")
    if report.get("blocker_codes") != []:
        _fail(label, "blocker_codes must be an empty list")
    counts = _require_object(report, "counts", label)
    accepted_count = counts.get("accepted_train_pair_count")
    if (
        not isinstance(accepted_count, int)
        or isinstance(accepted_count, bool)
        or accepted_count != row_count
    ):
        _fail(
            label,
            "counts.accepted_train_pair_count must equal the accepted row count",
        )


def _parse_accepted_rows(lines: list[bytes], path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line_label = f"{path}:{line_number}"
        if not raw_line.strip():
            _fail(line_label, "accepted row must not be blank")
        try:
            parsed = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _fail(line_label, f"accepted row is not valid UTF-8 JSON: {exc}")
        if not isinstance(parsed, dict):
            _fail(line_label, "accepted row must be a JSON object")
        rows.append(parsed)
    return rows


def _validate_rows(
    rows: list[dict[str, Any]], path: Path
) -> list[_ValidatedExampleValues]:
    examples: list[_ValidatedExampleValues] = []
    seen_ids: dict[str, set[str]] = {
        "accepted_record_id": set(),
        "pair_id": set(),
        "source_record_id": set(),
    }
    seen_sources: set[tuple[str, str, str, str]] = set()
    for line_number, row in enumerate(rows, start=1):
        label = f"accepted row {path}:{line_number}"
        _require_exact_fields(row, _ACCEPTED_ROW_FIELDS, label)
        _require_equal(row, "schema_version", _ACCEPTED_ROW_SCHEMA, label)
        _require_int_equal(row, "artifact_version", 3, label)
        _require_equal(row, "policy_id", _ADMISSION_POLICY, label)
        _require_equal(row, "source_schema_version", _SOURCE_SCHEMA, label)
        _require_equal(row, "query_text_policy", "prompt_only", label)
        if row.get("accepted_for_training") is not True:
            _fail(label, "accepted_for_training must be true")
        _require_equal(row, "training_split", "train", label)

        for field in (
            "accepted_record_id",
            "pair_id",
            "source_record_id",
            "task_id",
            "skill_id",
            "query_text",
            "skill_text",
            "reviewer",
            "review_reason",
        ):
            _require_nonblank_string(row, field, label)
        prompt_hash = _require_sha256(row, "prompt_text_sha256", label)
        source_hash = _require_sha256(row, "source_hash", label)
        acceptance_hash = _require_sha256(row, "acceptance_hash", label)
        expected_prompt_hash = _sha256(row["query_text"].encode("utf-8"))
        if prompt_hash != expected_prompt_hash:
            _fail(label, "prompt_text_sha256 does not bind query_text")

        _require_equal(row, "source_kind", _SOURCE_KIND, f"{label} source")
        _require_equal(row, "source_dataset_id", _SOURCE_DATASET, f"{label} source")
        _require_equal(row, "source_artifact_path", _SOURCE_ARTIFACT, f"{label} source")
        _require_equal(row, "source_split", "dev", f"{label} source")
        role = (
            row.get("candidate_type"),
            row.get("supervision_label"),
            row.get("review_status"),
        )
        allowed_roles = {
            ("positive", "POSITIVE", "ACCEPTED_POSITIVE"),
            (
                "same_category_negative_candidate",
                "HARD_NEGATIVE",
                "ACCEPTED_HARD_NEGATIVE",
            ),
        }
        if role not in allowed_roles:
            _fail(label, "role mapping is not admitted")

        for field, values in seen_ids.items():
            value = row[field]
            if value in values:
                _fail(label, f"duplicate {field}: {value}")
            values.add(value)
        source_identity = (
            row["source_kind"],
            row["source_dataset_id"],
            row["source_artifact_path"],
            row["source_record_id"],
        )
        if source_identity in seen_sources:
            _fail(label, "duplicate source identity tuple")
        seen_sources.add(source_identity)

        expected_source_hash = _canonical_hash(
            {field: row[field] for field in _SOURCE_HASH_FIELDS}
        )
        if source_hash != expected_source_hash:
            _fail(label, "source_hash does not match its canonical projection")
        expected_acceptance_hash = _canonical_hash(
            {field: row[field] for field in _ACCEPTANCE_HASH_FIELDS}
        )
        if acceptance_hash != expected_acceptance_hash:
            _fail(label, "acceptance_hash does not match its canonical projection")

        supervision_label: TrainingSupervision = row["supervision_label"]
        examples.append(
            (
                row["accepted_record_id"],
                row["query_text"],
                row["skill_text"],
                supervision_label,
            )
        )
    return examples


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        _fail(str(path), f"could not read {label}: {exc}")
    return _parse_json_object_bytes(data, path, label)


def _parse_json_object_bytes(data: bytes, path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(str(path), f"{label} is not valid UTF-8 JSON: {exc}")
    if not isinstance(parsed, dict):
        _fail(str(path), f"{label} must be a JSON object")
    return parsed


def _read_bound_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        _fail(label, f"could not read bound file: {exc}")


def _verify_bound_hash(data: bytes, expected: str, label: str) -> None:
    if _sha256(data) != expected:
        _fail(label, "does not match the bound file bytes")


def _require_exact_fields(
    payload: dict[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        _fail(label, f"fields are not exact; missing={missing}, unknown={unknown}")


def _require_object(payload: dict[str, Any], field: str, label: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        _fail(label, f"{field} must be an object")
    return value


def _require_equal(
    payload: dict[str, Any], field: str, expected: Any, label: str
) -> None:
    if payload.get(field) != expected:
        _fail(label, f"{field} must equal {expected!r}")


def _require_int_equal(
    payload: dict[str, Any], field: str, expected: int, label: str
) -> None:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value != expected:
        _fail(label, f"{field} must be integer {expected}")


def _require_positive_int(payload: dict[str, Any], field: str, label: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _fail(label, f"{field} must be a positive integer")
    return value


def _require_nonblank_string(payload: dict[str, Any], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        _fail(label, f"{field} must be a non-blank string")
    return value


def _require_sha256(payload: dict[str, Any], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail(label, f"{field} must be a lowercase SHA-256")
    return value


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(encoded)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(label: str, detail: str) -> NoReturn:
    raise TrainingInputError(f"TRAINING_INPUT_INVALID: {label}: {detail}")


def _create_sealed_training_input_api():
    validation_seal = object()
    fingerprint_secret = os.urandom(32)

    def content_fingerprint(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(fingerprint_secret, encoded, hashlib.sha256).hexdigest()

    def example_payload(example: Any) -> dict[str, Any]:
        return {
            "accepted_record_id": example.accepted_record_id,
            "query_text": example.query_text,
            "skill_text": example.skill_text,
            "supervision_label": example.supervision_label,
        }

    def handoff_payload(package_id: str, examples: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "package_id": package_id,
            "examples": [example_payload(example) for example in examples],
        }

    @dataclass(frozen=True, slots=True, init=False)
    class _ValidatedTrainingExample:
        accepted_record_id: str
        query_text: str
        skill_text: str
        supervision_label: TrainingSupervision
        _validation_seal: object = dataclass_field(repr=False, compare=False)
        _content_fingerprint: str = dataclass_field(repr=False, compare=False)

        def __init__(
            self,
            *,
            accepted_record_id: str,
            query_text: str,
            skill_text: str,
            supervision_label: TrainingSupervision,
            _validation_seal: object,
            _content_fingerprint: str,
        ) -> None:
            if _validation_seal is not validation_seal:
                _fail("training example", "invalid validation seal")
            expected_fingerprint = content_fingerprint(
                {
                    "accepted_record_id": accepted_record_id,
                    "query_text": query_text,
                    "skill_text": skill_text,
                    "supervision_label": supervision_label,
                }
            )
            if not hmac.compare_digest(_content_fingerprint, expected_fingerprint):
                _fail("training example", "invalid content fingerprint")
            object.__setattr__(self, "accepted_record_id", accepted_record_id)
            object.__setattr__(self, "query_text", query_text)
            object.__setattr__(self, "skill_text", skill_text)
            object.__setattr__(self, "supervision_label", supervision_label)
            object.__setattr__(self, "_validation_seal", _validation_seal)
            object.__setattr__(self, "_content_fingerprint", _content_fingerprint)

    @dataclass(frozen=True, slots=True, init=False)
    class _TrainingInputHandoff:
        package_id: str
        examples: tuple[Any, ...]
        _validation_seal: object = dataclass_field(repr=False, compare=False)
        _content_fingerprint: str = dataclass_field(repr=False, compare=False)

        def __init__(
            self,
            *,
            package_id: str,
            examples: tuple[Any, ...],
            _validation_seal: object,
            _content_fingerprint: str,
        ) -> None:
            if _validation_seal is not validation_seal:
                _fail("training handoff", "invalid validation seal")
            expected_fingerprint = content_fingerprint(
                handoff_payload(package_id, examples)
            )
            if not hmac.compare_digest(_content_fingerprint, expected_fingerprint):
                _fail("training handoff", "invalid content fingerprint")
            object.__setattr__(self, "package_id", package_id)
            object.__setattr__(self, "examples", examples)
            object.__setattr__(self, "_validation_seal", _validation_seal)
            object.__setattr__(self, "_content_fingerprint", _content_fingerprint)

    _ValidatedTrainingExample.__name__ = "ValidatedTrainingExample"
    _ValidatedTrainingExample.__qualname__ = "ValidatedTrainingExample"
    _TrainingInputHandoff.__name__ = "TrainingInputHandoff"
    _TrainingInputHandoff.__qualname__ = "TrainingInputHandoff"

    def load_training_input(manifest_path: str | Path) -> Any:
        """Validate one exact v3 package and construct its sealed handoff."""

        package_id, values = _load_training_input_values(manifest_path)
        examples_list = []
        for accepted_record_id, query_text, skill_text, supervision_label in values:
            payload = {
                "accepted_record_id": accepted_record_id,
                "query_text": query_text,
                "skill_text": skill_text,
                "supervision_label": supervision_label,
            }
            examples_list.append(
                _ValidatedTrainingExample(
                    accepted_record_id=accepted_record_id,
                    query_text=query_text,
                    skill_text=skill_text,
                    supervision_label=supervision_label,
                    _validation_seal=validation_seal,
                    _content_fingerprint=content_fingerprint(payload),
                )
            )
        examples = tuple(examples_list)
        fingerprint = content_fingerprint(handoff_payload(package_id, examples))
        return _TrainingInputHandoff(
            package_id=package_id,
            examples=examples,
            _validation_seal=validation_seal,
            _content_fingerprint=fingerprint,
        )

    def verify_training_handoff(handoff: Any) -> None:
        if type(handoff) is not _TrainingInputHandoff:
            _fail("training handoff", "type or validation seal is invalid")
        if getattr(handoff, "_validation_seal", None) is not validation_seal:
            _fail("training handoff", "invalid validation seal")
        if not isinstance(handoff.package_id, str) or not handoff.package_id.strip():
            _fail("training handoff", "package_id must be non-blank")
        if type(handoff.examples) is not tuple:
            _fail("training handoff", "examples must be an immutable tuple")
        for example in handoff.examples:
            if type(example) is not _ValidatedTrainingExample:
                _fail("training example", "type or validation seal is invalid")
            if getattr(example, "_validation_seal", None) is not validation_seal:
                _fail("training example", "invalid validation seal")
            stored_fingerprint = getattr(example, "_content_fingerprint", None)
            expected_fingerprint = content_fingerprint(example_payload(example))
            if not isinstance(stored_fingerprint, str) or not hmac.compare_digest(
                stored_fingerprint, expected_fingerprint
            ):
                _fail("training example", "invalid content fingerprint")
            for field_name in (
                "accepted_record_id",
                "query_text",
                "skill_text",
            ):
                value = getattr(example, field_name, None)
                if not isinstance(value, str) or not value.strip():
                    _fail("training example", f"{field_name} is invalid")
            if example.supervision_label not in {"POSITIVE", "HARD_NEGATIVE"}:
                _fail("training example", "supervision_label is invalid")
        stored_handoff_fingerprint = getattr(handoff, "_content_fingerprint", None)
        expected_handoff_fingerprint = content_fingerprint(
            handoff_payload(handoff.package_id, handoff.examples)
        )
        if not isinstance(stored_handoff_fingerprint, str) or not hmac.compare_digest(
            stored_handoff_fingerprint, expected_handoff_fingerprint
        ):
            _fail("training handoff", "invalid content fingerprint")

    return (
        _ValidatedTrainingExample,
        _TrainingInputHandoff,
        load_training_input,
        verify_training_handoff,
    )


(
    ValidatedTrainingExample,
    TrainingInputHandoff,
    load_training_input,
    _verify_training_handoff,
) = _create_sealed_training_input_api()
del _create_sealed_training_input_api


__all__ = ["load_training_input"]
