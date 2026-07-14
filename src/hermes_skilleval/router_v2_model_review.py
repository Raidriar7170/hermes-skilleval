from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SOURCE_SNAPSHOT_ID = "router-v2-v4-source-38afe7d5b2500d4a"
SOURCE_COMMIT = "751bb678bf9fb63a357ff3667e3508a0f5ed83a2"
SOURCE_CANDIDATES_SHA256 = (
    "5fa7e7feb1a5fedc2cf8bcc8adf17afe3356f9d4614b2848b0d74f88718e3d2a"
)
SOURCE_MANIFEST_SHA256 = (
    "330f13d58833450293374f91e253dadf452b5a7d5233a4aa025984e09b0ed511"
)
SOURCE_ROW_COUNT = 192
PILOT_PATH_PREFIX = Path("artifacts/router-v2-v4/model-only-pilot")
REVIEW_DECISIONS_PATH = Path("data/router-v2-v4/review-decisions.csv")
RUBRIC_PATH = "docs/router-v2-model-only-review-rubric-v1.md"
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PILOT_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")

TRUTH_FIELDS: dict[str, object] = {
    "review_mode": "MODEL_ONLY_PILOT",
    "human_reviewer_count": 0,
    "model_review_pass_count": 2,
    "model_adjudication_enabled": True,
    "independent_human_review": False,
    "model_correlation_risk": True,
    "release_eligible": False,
    "router_decision": "KEEP_BASELINE",
    "human_review_status": "REVIEW_REQUIRED",
    "admission_effect": "NONE",
    "can_start_preflight": False,
    "can_start_training": False,
}

OPINIONS_BY_ROLE = {
    "POSITIVE": {
        "POSITIVE_ROLE_SUPPORTED",
        "POSITIVE_ROLE_DISPUTED",
        "MODEL_UNCERTAIN",
    },
    "HARD_NEGATIVE_CANDIDATE": {
        "HARD_NEGATIVE_ROLE_SUPPORTED",
        "HARD_NEGATIVE_ROLE_DISPUTED",
        "MODEL_UNCERTAIN",
    },
    "NO_SKILL_CANDIDATE": {
        "NO_SKILL_ROLE_SUPPORTED",
        "NO_SKILL_ROLE_DISPUTED",
        "MODEL_UNCERTAIN",
    },
}

FORBIDDEN_FIELDS = {
    "reviewer",
    "reviewed_by",
    "decision",
    "accepted",
    "acceptance",
    "is_accepted",
    "human_reviewer",
    "human_decision",
    "training_label",
    "qualification_status",
    "admission_decision",
}
FORBIDDEN_CLAIMS = (
    "human-reviewed",
    "human-accepted",
    "人工审核完成",
    "reviewer is the project owner",
    "independent human review",
    "production-ready data",
    "production release",
    "生产发布",
    "router promotion",
    "release claim",
    "blind-v2 final conclusion",
    "blind-v2 最终结论",
    "human-annotated data",
    "人工标注数据",
    "resume human-review claim",
    "résumé human-review claim",
    "简历中的人工审核 claim",
    "project-owner reviewer",
    "reviewer 是项目所有者本人",
    "blind-v2 conclusion",
    "human annotation promotion",
)
NON_ACTIONS = [
    "accepted_pairs",
    "blind_v2",
    "human_review",
    "model_training",
    "preflight",
    "qualification",
    "release",
    "review_decisions",
    "router_promotion",
    "training_input",
]

PASS_ROW_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "pilot_id",
    "pass_id",
    "pass_run_id",
    "pass_isolation",
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "source_role",
    "model_opinion",
    "rationale",
    "model_provider",
    "model_id",
    "model_snapshot",
    "prompt_id",
    "prompt_sha256",
    "rubric_sha256",
    "row_sha256",
}
ADJUDICATION_ROW_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "pilot_id",
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "source_role",
    "pass_1_row_sha256",
    "pass_2_row_sha256",
    "pass_1_model_opinion",
    "pass_2_model_opinion",
    "opinions_agree",
    "adjudicated_model_opinion",
    "rationale",
    "adjudicator_model_provider",
    "adjudicator_model_id",
    "adjudicator_model_snapshot",
    "adjudication_prompt_id",
    "adjudication_prompt_sha256",
    "rubric_sha256",
    "row_sha256",
}
MANIFEST_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "pilot_id",
    "source_snapshot_id",
    "source_commit",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "source_row_count",
    "rubric_path",
    "rubric_sha256",
    "pass_1",
    "pass_2",
    "adjudication",
    "non_actions",
}
SUMMARY_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "pilot_id",
    "source_row_count",
    "pass_1_row_count",
    "pass_2_row_count",
    "adjudication_row_count",
    "agreement_count",
    "disagreement_count",
    "model_uncertain_count",
    "result",
}
FILE_RECORD_FIELDS = {"path", "sha256", "row_count"}
PASS_FILE_RECORD_FIELDS = FILE_RECORD_FIELDS | {"pass_id", "pass_run_id"}


def validate_router_v2_model_review_pilot(
    *, repository_root: Path | str, pilot_dir: Path | str
) -> dict[str, Any]:
    """Validate a complete non-admissible Router V2 model-review pilot."""

    root = Path(repository_root).resolve(strict=True)
    target = Path(pilot_dir).resolve(strict=True)
    _validate_target(root, target)

    source_dir = root / "data/router-v2-v4"
    candidates_path = source_dir / "source-candidates.jsonl"
    source_manifest_path = source_dir / "source-manifest.json"
    if _sha256(candidates_path.read_bytes()) != SOURCE_CANDIDATES_SHA256:
        raise ValueError("frozen source candidates SHA-256 drift")
    source_manifest_bytes = source_manifest_path.read_bytes()
    if _sha256(source_manifest_bytes) != SOURCE_MANIFEST_SHA256:
        raise ValueError("frozen source manifest SHA-256 drift")
    source_manifest = _load_json_document(source_manifest_path, "source manifest")
    if source_manifest.get("snapshot_id") != SOURCE_SNAPSHOT_ID:
        raise ValueError("frozen source snapshot id drift")
    source_records = source_manifest.get("records")
    if not isinstance(source_records, list) or len(source_records) != SOURCE_ROW_COUNT:
        raise ValueError("frozen source manifest must contain exactly 192 records")

    expected_files = {
        "adjudication.model-opinions.jsonl",
        "pass-1.model-opinions.jsonl",
        "pass-2.model-opinions.jsonl",
        "pilot-manifest.json",
        "summary.json",
    }
    actual_files = {path.name for path in target.iterdir() if path.is_file()}
    if actual_files != expected_files or any(
        path.is_dir() for path in target.iterdir()
    ):
        raise ValueError("pilot directory must contain only the five contract files")

    manifest = _load_json_document(target / "pilot-manifest.json", "pilot manifest")
    _validate_manifest(manifest, root, target)
    pilot_id = manifest["pilot_id"]
    if manifest["pass_1"]["pass_run_id"] == manifest["pass_2"]["pass_run_id"]:
        raise ValueError("model passes require distinct pass run identities")

    pass_1 = _validate_pass(
        target / "pass-1.model-opinions.jsonl",
        source_records,
        manifest,
        expected_pass_id="MODEL_PASS_1",
        expected_file_record=manifest["pass_1"],
    )
    pass_2 = _validate_pass(
        target / "pass-2.model-opinions.jsonl",
        source_records,
        manifest,
        expected_pass_id="MODEL_PASS_2",
        expected_file_record=manifest["pass_2"],
    )
    adjudication = _validate_adjudication(
        target / "adjudication.model-opinions.jsonl",
        source_records,
        pass_1,
        pass_2,
        manifest,
    )
    summary = _load_json_document(target / "summary.json", "pilot summary")
    agreement_count = sum(row["opinions_agree"] for row in adjudication)
    uncertain_count = sum(
        row["adjudicated_model_opinion"] == "MODEL_UNCERTAIN" for row in adjudication
    )
    _validate_summary(summary, pilot_id, agreement_count, uncertain_count)

    return {
        **TRUTH_FIELDS,
        "pilot_id": pilot_id,
        "source_row_count": SOURCE_ROW_COUNT,
        "agreement_count": agreement_count,
        "disagreement_count": SOURCE_ROW_COUNT - agreement_count,
        "model_uncertain_count": uncertain_count,
        "validation_status": "PASS",
    }


def _validate_target(root: Path, target: Path) -> None:
    if (root / REVIEW_DECISIONS_PATH).exists():
        raise ValueError("review-decisions.csv is forbidden for model-only validation")
    expected_parent = (root / PILOT_PATH_PREFIX).resolve(strict=True)
    if target.parent != expected_parent or not PILOT_ID.fullmatch(target.name):
        raise ValueError("model-only pilot path must use the canonical artifact tree")
    if target.is_symlink() or not target.is_dir():
        raise ValueError("model-only pilot path must be a regular directory")


def _validate_manifest(manifest: dict[str, Any], root: Path, target: Path) -> None:
    _validate_exact_fields(manifest, MANIFEST_FIELDS, "pilot manifest")
    _validate_truth(manifest, "pilot manifest")
    expected = {
        "schema_version": "router-v2-model-review-pilot-manifest-v1",
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_commit": SOURCE_COMMIT,
        "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "source_row_count": SOURCE_ROW_COUNT,
        "rubric_path": RUBRIC_PATH,
        "non_actions": NON_ACTIONS,
    }
    for key, value in expected.items():
        if manifest[key] != value:
            raise ValueError(f"pilot manifest field {key} does not match contract")
    pilot_id = manifest["pilot_id"]
    if not isinstance(pilot_id, str) or not PILOT_ID.fullmatch(pilot_id):
        raise ValueError("pilot_id must be a stable kebab-case identifier")
    if target.name != pilot_id:
        raise ValueError("pilot directory name must equal pilot_id")
    rubric_path = root / RUBRIC_PATH
    if not rubric_path.is_file() or rubric_path.is_symlink():
        raise ValueError("stable rubric must be a regular file")
    if manifest["rubric_sha256"] != _sha256(rubric_path.read_bytes()):
        raise ValueError("stable rubric SHA-256 drift")
    for key, fields in (
        ("pass_1", PASS_FILE_RECORD_FIELDS),
        ("pass_2", PASS_FILE_RECORD_FIELDS),
        ("adjudication", FILE_RECORD_FIELDS),
    ):
        record = manifest[key]
        if not isinstance(record, dict):
            raise ValueError(f"manifest {key} must be an object")
        _validate_exact_fields(record, fields, f"manifest {key}")


def _validate_pass(
    path: Path,
    source_records: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    expected_pass_id: str,
    expected_file_record: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _load_jsonl(path, expected_pass_id)
    if len(rows) != SOURCE_ROW_COUNT:
        raise ValueError(f"{expected_pass_id} must contain exactly 192 rows")
    if expected_file_record["path"] != path.name:
        raise ValueError(f"{expected_pass_id} manifest path mismatch")
    if expected_file_record["row_count"] != SOURCE_ROW_COUNT:
        raise ValueError(f"{expected_pass_id} manifest row count mismatch")
    if expected_file_record["pass_id"] != expected_pass_id:
        raise ValueError(f"{expected_pass_id} manifest pass identity mismatch")
    expected_run_id = expected_file_record["pass_run_id"]
    _validate_explicit(expected_run_id, f"{expected_pass_id} pass_run_id")

    for index, (row, source) in enumerate(zip(rows, source_records, strict=True)):
        label = f"{expected_pass_id} row {index + 1}"
        _validate_exact_fields(row, PASS_ROW_FIELDS, label)
        _validate_truth(row, label)
        _validate_no_claims(row, label)
        if row["schema_version"] != "router-v2-model-opinion-row-v1":
            raise ValueError(f"{label} schema version mismatch")
        if row["pilot_id"] != manifest["pilot_id"]:
            raise ValueError(f"{label} pilot id mismatch")
        if row["pass_id"] != expected_pass_id:
            raise ValueError(f"{label} pass identity mismatch")
        if row["pass_run_id"] != expected_run_id:
            raise ValueError(f"{label} pass run identity mismatch")
        if row["pass_isolation"] != "OTHER_PASS_OUTPUT_NOT_PROVIDED":
            raise ValueError(f"{label} pass isolation metadata mismatch")
        _validate_source_identity(row, source, label)
        _validate_opinion(row["source_role"], row["model_opinion"])
        for key in (
            "rationale",
            "model_provider",
            "model_id",
            "model_snapshot",
            "prompt_id",
        ):
            _validate_explicit(row[key], key)
        _validate_prompt_sha256(row["prompt_sha256"], "prompt_sha256")
        if row["rubric_sha256"] != manifest["rubric_sha256"]:
            raise ValueError(f"{label} rubric SHA-256 mismatch")
        _validate_row_hash(row, label)

    if expected_file_record["sha256"] != _sha256(path.read_bytes()):
        raise ValueError(f"{expected_pass_id} file SHA-256 mismatch")
    return rows


def _validate_adjudication(
    path: Path,
    source_records: list[dict[str, Any]],
    pass_1: list[dict[str, Any]],
    pass_2: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _load_jsonl(path, "model adjudication")
    if len(rows) != SOURCE_ROW_COUNT:
        raise ValueError("model adjudication must contain exactly 192 rows")
    file_record = manifest["adjudication"]
    if file_record["path"] != path.name or file_record["row_count"] != SOURCE_ROW_COUNT:
        raise ValueError("model adjudication manifest record mismatch")

    for index, (row, source, first, second) in enumerate(
        zip(rows, source_records, pass_1, pass_2, strict=True)
    ):
        label = f"adjudication row {index + 1}"
        _validate_exact_fields(row, ADJUDICATION_ROW_FIELDS, label)
        _validate_truth(row, label)
        _validate_no_claims(row, label)
        if row["schema_version"] != "router-v2-model-adjudication-row-v1":
            raise ValueError(f"{label} schema version mismatch")
        if row["pilot_id"] != manifest["pilot_id"]:
            raise ValueError(f"{label} pilot id mismatch")
        _validate_source_identity(row, source, label)
        if row["pass_1_row_sha256"] != first["row_sha256"]:
            raise ValueError(f"{label} adjudication pass-1 row hash mismatch")
        if row["pass_2_row_sha256"] != second["row_sha256"]:
            raise ValueError(f"{label} adjudication pass-2 row hash mismatch")
        if row["pass_1_model_opinion"] != first["model_opinion"]:
            raise ValueError(f"{label} pass-1 opinion mismatch")
        if row["pass_2_model_opinion"] != second["model_opinion"]:
            raise ValueError(f"{label} pass-2 opinion mismatch")
        expected_agreement = first["model_opinion"] == second["model_opinion"]
        if row["opinions_agree"] is not expected_agreement:
            raise ValueError(f"{label} agreement flag mismatch")
        _validate_opinion(row["source_role"], row["adjudicated_model_opinion"])
        for key in (
            "rationale",
            "adjudicator_model_provider",
            "adjudicator_model_id",
            "adjudicator_model_snapshot",
            "adjudication_prompt_id",
        ):
            _validate_explicit(row[key], key)
        _validate_prompt_sha256(
            row["adjudication_prompt_sha256"], "adjudication_prompt_sha256"
        )
        if row["rubric_sha256"] != manifest["rubric_sha256"]:
            raise ValueError(f"{label} rubric SHA-256 mismatch")
        _validate_row_hash(row, label)

    if file_record["sha256"] != _sha256(path.read_bytes()):
        raise ValueError("model adjudication file SHA-256 mismatch")
    return rows


def _validate_summary(
    summary: dict[str, Any], pilot_id: str, agreement_count: int, uncertain_count: int
) -> None:
    _validate_exact_fields(summary, SUMMARY_FIELDS, "pilot summary")
    _validate_truth(summary, "pilot summary")
    _validate_no_claims(summary, "pilot summary")
    expected = {
        "schema_version": "router-v2-model-review-pilot-summary-v1",
        "pilot_id": pilot_id,
        "source_row_count": SOURCE_ROW_COUNT,
        "pass_1_row_count": SOURCE_ROW_COUNT,
        "pass_2_row_count": SOURCE_ROW_COUNT,
        "adjudication_row_count": SOURCE_ROW_COUNT,
        "agreement_count": agreement_count,
        "disagreement_count": SOURCE_ROW_COUNT - agreement_count,
        "model_uncertain_count": uncertain_count,
        "result": "MODEL_AUDIT_RECORDED_NO_ADMISSION_EFFECT",
    }
    for key, value in expected.items():
        if summary[key] != value:
            raise ValueError(f"pilot summary field {key} mismatch")


def _validate_truth(row: dict[str, Any], label: str) -> None:
    for key, value in TRUTH_FIELDS.items():
        if row.get(key) != value or type(row.get(key)) is not type(value):
            raise ValueError(f"{label} truth field {key} must equal {value!r}")


def _validate_source_identity(
    row: dict[str, Any], source: dict[str, Any], label: str
) -> None:
    expected = (
        source["source_record_id"],
        source["source_record_exact_bytes_sha256"],
        source["source_role"],
    )
    actual = (
        row["source_record_id"],
        row["source_record_exact_bytes_sha256"],
        row["source_role"],
    )
    if actual != expected:
        raise ValueError(f"{label} source row identity or order mismatch")


def _validate_opinion(role: object, opinion: object) -> None:
    if not isinstance(role, str) or not isinstance(opinion, str):
        raise ValueError("source role and model opinion must be strings")
    if role not in OPINIONS_BY_ROLE or opinion not in OPINIONS_BY_ROLE[role]:
        raise ValueError(
            f"model opinion {opinion!r} is not valid for source role {role}"
        )


def _validate_row_hash(row: dict[str, Any], label: str) -> None:
    declared = row["row_sha256"]
    unhashed = dict(row)
    del unhashed["row_sha256"]
    if not isinstance(declared, str) or declared != _sha256(_canonical(unhashed)):
        raise ValueError(f"{label} row SHA-256 mismatch")


def _validate_explicit(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be explicit or UNAVAILABLE")


def _validate_prompt_sha256(value: object, label: str) -> None:
    if value != "UNAVAILABLE" and (
        not isinstance(value, str) or not HEX_SHA256.fullmatch(value)
    ):
        raise ValueError(f"{label} must be UNAVAILABLE or lowercase 64-hex")


def _validate_no_claims(row: dict[str, Any], label: str) -> None:
    for key in row:
        if key in FORBIDDEN_FIELDS:
            raise ValueError(f"{label} contains forbidden field {key}")
    for value in row.values():
        if isinstance(value, str):
            lowered = value.casefold()
            if any(claim.casefold() in lowered for claim in FORBIDDEN_CLAIMS):
                raise ValueError(f"{label} contains a forbidden human or release claim")


def _validate_exact_fields(row: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(row)
    forbidden = sorted(actual & FORBIDDEN_FIELDS)
    if forbidden:
        raise ValueError(f"{label} contains forbidden field {forbidden[0]}")
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} fields mismatch: missing={missing}, extra={extra}")


def _load_json_document(path: Path, label: str) -> dict[str, Any]:
    payload = path.read_bytes()
    row = _parse_json_object(payload, label)
    if payload != _canonical(row):
        raise ValueError(f"{label} must use canonical JSON")
    return row


def _load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} canonical JSONL requires one LF per row")
    lines = payload.splitlines(keepends=True)
    rows = []
    for index, line in enumerate(lines, start=1):
        row = _parse_json_object(line, f"{label} row {index}")
        if line != _canonical(row):
            raise ValueError(f"{label} must use canonical JSONL")
        rows.append(row)
    return rows


def _parse_json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must use UTF-8") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key {key}")
            result[key] = value
        return result

    try:
        parsed = json.loads(text, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _canonical(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--pilot-dir", type=Path, required=True)
    args = parser.parse_args()
    result = validate_router_v2_model_review_pilot(
        repository_root=args.repository_root,
        pilot_dir=args.pilot_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
