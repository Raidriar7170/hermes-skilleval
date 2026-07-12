from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "router-training-data-v2-training-input-manifest-v3"
ACCEPTED_ROW_SCHEMA = "router-training-data-v2-accepted-pair-v3"
ADMISSION_POLICY = "router-training-data-v2-training-admission-v3"
REPORT_SCHEMA = "router-training-data-v2-qualification-report-v3"
QUALIFICATION_POLICY = "router-training-data-v2-qualification-v3"
SOURCE_SCHEMA = "router-training-data-v2-candidate-v3"

SOURCE_HASH_FIELDS = (
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
ACCEPTANCE_HASH_FIELDS = (
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def rehash_row(row: dict[str, Any]) -> dict[str, Any]:
    row["prompt_text_sha256"] = sha256_bytes(row["query_text"].encode("utf-8"))
    row["source_hash"] = canonical_hash(
        {field: row[field] for field in SOURCE_HASH_FIELDS}
    )
    row["acceptance_hash"] = canonical_hash(
        {field: row[field] for field in ACCEPTANCE_HASH_FIELDS}
    )
    return row


def make_accepted_row(
    index: int = 1,
    *,
    supervision_label: str = "POSITIVE",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    negative = supervision_label == "HARD_NEGATIVE"
    row: dict[str, Any] = {
        "schema_version": ACCEPTED_ROW_SCHEMA,
        "artifact_version": 3,
        "policy_id": ADMISSION_POLICY,
        "accepted_record_id": f"synthetic-accepted-{index}",
        "pair_id": f"synthetic-pair-{index}",
        "source_record_id": f"synthetic-source-{index}",
        "source_schema_version": SOURCE_SCHEMA,
        "source_kind": "ROUTER_TRAINING_DATA_V2_CANDIDATE",
        "source_dataset_id": "router-training-data-v2-qualification-pack",
        "source_artifact_path": (
            "docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl"
        ),
        "source_split": "dev",
        "candidate_type": (
            "same_category_negative_candidate" if negative else "positive"
        ),
        "task_id": f"synthetic-task-{index}",
        "skill_id": f"synthetic-skill-{index}",
        "query_text": f"Synthetic prompt {index} — only for tests.",
        "query_text_policy": "prompt_only",
        "prompt_text_sha256": "",
        "skill_text": f"Synthetic skill {index}",
        "accepted_for_training": True,
        "training_split": "train",
        "supervision_label": supervision_label,
        "review_status": (
            "ACCEPTED_HARD_NEGATIVE" if negative else "ACCEPTED_POSITIVE"
        ),
        "reviewer": "synthetic-test-reviewer",
        "review_reason": "Synthetic acceptance evidence for unit tests only.",
        "source_hash": "",
        "acceptance_hash": "",
    }
    if overrides:
        row.update(overrides)
    return rehash_row(row)


def write_synthetic_training_package(
    root: Path,
    *,
    rows: list[dict[str, Any]] | None = None,
    manifest_overrides: dict[str, Any] | None = None,
    accepted_pairs_overrides: dict[str, Any] | None = None,
    qualification_report_overrides: dict[str, Any] | None = None,
    report_overrides: dict[str, Any] | None = None,
    accepted_path: str = "accepted-pairs.jsonl",
    report_path: str = "qualification-report.json",
    raw_pairs: bytes | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    package_rows = rows if rows is not None else [make_accepted_row()]
    pairs_bytes = raw_pairs
    if pairs_bytes is None:
        pairs_bytes = b"".join(
            (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            for row in package_rows
        )
    pairs_file = root / accepted_path
    pairs_file.parent.mkdir(parents=True, exist_ok=True)
    pairs_file.write_bytes(pairs_bytes)

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "artifact_version": 3,
        "policy_id": QUALIFICATION_POLICY,
        "can_start_training": True,
        "blocker_codes": [],
        "counts": {"accepted_train_pair_count": len(package_rows)},
        "synthetic_fixture": True,
    }
    if report_overrides:
        report.update(report_overrides)
    report_bytes = (
        json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    report_file = root / report_path
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_bytes(report_bytes)

    accepted_pairs = {
        "path": accepted_path,
        "sha256": sha256_bytes(pairs_bytes),
        "row_count": len(package_rows),
    }
    if accepted_pairs_overrides:
        accepted_pairs.update(accepted_pairs_overrides)
    qualification_report = {
        "path": report_path,
        "sha256": sha256_bytes(report_bytes),
    }
    if qualification_report_overrides:
        qualification_report.update(qualification_report_overrides)
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "artifact_version": 3,
        "policy_id": ADMISSION_POLICY,
        "package_id": "synthetic-training-input-test-only",
        "accepted_pairs": accepted_pairs,
        "qualification_report": qualification_report,
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    manifest_path = root / "training-input-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path
