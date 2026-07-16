from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.router_v2_blind_v2_evaluation import (
    ARMS,
    SEEDS,
    apply_preregistered_gate,
    build_aggregate_results,
    build_failure_slices,
    build_lineage_manifest,
    build_paired_results,
    build_per_seed_result,
    build_statistics,
    canonical_sha256,
    preregistered_evaluation_contract,
    validate_preregistration_truth,
)
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_evaluation import quantize8


MODEL_LOAD_SMOKE_TEXTS = (
    "synthetic blind-v2 model load query",
    "synthetic blind-v2 skill description",
)
QUERY_CONTRACT_VERSION = "router-v2-prompt-only-query-v1"
SKILL_REPRESENTATION_BUILDER_VERSION = (
    "router-v2-id-name-category-description-trigger-terms-body-v1"
)
FINAL_NAMESPACE_RELATIVE = Path(
    "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001"
)
DATASET_FREEZE_RELATIVE = Path("data/router-v2-blind-v2")
PREREGISTRATION_RELATIVE = Path("artifacts/router-v2-blind-v2/preregistration.json")
DATASET_FREEZE_FILENAMES = (
    "blind-v2-tasks.jsonl",
    "blind-v2-review-summary.json",
    "blind-v2-manifest.json",
)
PILOT_MANIFEST_RELATIVE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-002-eval-replay/pilot-manifest.json"
)
EVALUATION_OUTPUT_FILENAMES = (
    "preregistration.json",
    "blind-v2-manifest.json",
    "review-summary.json",
    "per-seed.json",
    "aggregate.json",
    "paired.json",
    "statistics.json",
    "failure-slices.json",
    "evaluation-summary.json",
    "result-report.md",
    "lineage-manifest.json",
)
SMOKE_RECEIPT_ROOT = Path("/tmp/hermes-router-v2-blind-v2-smoke-receipts")
AUTHORING_TEMPLATE_ROOT = Path("/tmp/hermes-blind-v2-authoring-pack")
PREREGISTRATION_PARENT_COMMIT = "8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552"
EVALUATOR_SOURCE_PATHS = (
    "src/hermes_skilleval/router_v2_blind_v2_evaluation.py",
    "src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py",
    "src/hermes_skilleval/router_v2_pilot_evaluation.py",
    "scripts/run_router_v2_blind_v2_final.py",
)
REQUIRED_PACK_FILES = (
    "blind-v2-authored.csv",
    "blind-v2-independent-review.csv",
    "reviewer-metadata.json",
)
AUTHORED_FIELDS = (
    "task_id",
    "prompt_text",
    "semantic_family_id",
    "gold_skill_id",
    "negative_skill_id",
    "author_id",
    "author_reason",
    "language",
    "source_type",
)
REVIEW_FIELDS = (
    "task_id",
    "prompt_text_sha256",
    "reviewer_id",
    "review_decision",
    "reviewed_gold_skill_id",
    "reviewed_negative_skill_id",
    "review_confidence",
    "review_reason",
)
REVIEW_DECISIONS = {
    "ACCEPT",
    "REJECT_AMBIGUOUS",
    "REJECT_WRONG_GOLD",
    "REJECT_WRONG_NEGATIVE",
    "REJECT_NOT_CONFUSABLE",
    "REJECT_NEAR_DUPLICATE",
    "REJECT_UNNATURAL",
    "REJECT_LABEL_LEAKAGE",
}
_LEAKAGE_MARKERS = (
    "gold skill",
    "negative skill",
    "benchmark",
    "router",
)
_PROTECTED_MARKERS = (
    "phase16",
    "phase-16",
    "phase_16",
    "pilot-002",
    "pilot_002",
    "heldout-labels",
)


class EvaluationEncoder(Protocol):
    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]: ...


class RouteScorer(Protocol):
    def rank(self, query: str, skill_ids: list[str]) -> list[str]: ...


EncoderFactory = Callable[[str, int, Path], EvaluationEncoder]
ScorerFactory = Callable[[str, int, Path], RouteScorer]
AuthorityValidator = Callable[..., dict[str, Any]]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _json_no_duplicate_keys(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in values:
            if key in output:
                raise ValueError(f"{label} contains duplicate key: {key}")
            output[key] = value
        return output

    try:
        decoded = payload.decode("utf-8", errors="strict")
        value = json.loads(decoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    _require(type(value) is dict, f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonl_no_duplicate_keys(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(payload.splitlines(), start=1):
        if line.strip():
            rows.append(_json_no_duplicate_keys(line, f"{label} line {index}"))
    return rows


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        result.returncode == 0,
        f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
    )
    return result.stdout.strip()


def validate_commit_a_repository(
    repository_root: Path | str, preregistration: dict[str, Any]
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit A worktree must be clean",
    )
    head = _git(repository, "rev-parse", "HEAD")
    parent = _git(repository, "rev-parse", "HEAD^")
    origin_main = _git(repository, "rev-parse", "origin/main")
    expected_parent = preregistration.get("preregistration_parent_git_commit")
    _require(
        parent == expected_parent and origin_main == expected_parent,
        "Commit A must be based directly on the preregistered origin/main",
    )
    _require(
        _git(repository, "rev-list", "--count", f"{parent}..{head}") == "1",
        "Commit A must be exactly one commit above origin/main",
    )
    return {"commit_a": head, "parent": parent, "origin_main": origin_main}


def validate_commit_b_repository(
    repository_root: Path | str, *, commit_a: str
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit B worktree must be clean",
    )
    head = _git(repository, "rev-parse", "HEAD")
    head_parent = _git(repository, "rev-parse", "HEAD^")
    commit_a_parent = _git(repository, "rev-parse", f"{commit_a}^")
    origin_main = _git(repository, "rev-parse", "origin/main")
    _require(
        commit_a_parent == PREREGISTRATION_PARENT_COMMIT
        and origin_main == PREREGISTRATION_PARENT_COMMIT,
        "Commit B lineage no longer matches preregistered origin/main",
    )
    _require(head != commit_a, "Commit B must differ from Commit A")
    _require(head_parent == commit_a, "Commit B must be a direct child of Commit A")
    _require(
        _git(repository, "rev-list", "--count", f"{commit_a}..{head}") == "1",
        "Commit B must be exactly one commit above Commit A",
    )
    changed = set(
        _git(repository, "diff", "--name-only", f"{commit_a}..{head}").splitlines()
    )
    expected = {
        (DATASET_FREEZE_RELATIVE / filename).as_posix()
        for filename in DATASET_FREEZE_FILENAMES
    }
    _require(changed == expected, "Commit B may contain only frozen blind-v2 data")
    return {
        "commit_a": commit_a,
        "commit_b": head,
        "origin_main": origin_main,
        "changed_files": sorted(changed),
    }


def _read_csv(
    path: Path, required_fields: tuple[str, ...]
) -> tuple[bytes, list[dict[str, str]]]:
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} must be UTF-8") from exc
    reader = csv.DictReader(text.splitlines())
    fields = reader.fieldnames
    if fields is None:
        raise ValueError(f"{path.name} is missing a header")
    _require(len(fields) == len(set(fields)), f"{path.name} contains duplicate keys")
    _require(
        set(required_fields).issubset(fields),
        f"{path.name} schema is missing required fields",
    )
    rows = [dict(row) for row in reader]
    return payload, rows


def _outside_repository(root: Path, repository_root: Path) -> None:
    resolved = root.resolve(strict=True)
    repository = repository_root.resolve(strict=False)
    _require(resolved.is_dir(), "human pack root must be a directory")
    _require(
        not resolved.is_relative_to(repository),
        "human pack root must stay outside the repository",
    )


def validate_human_pack(
    root: Path | str,
    *,
    repository_root: Path | str,
    canonical_skills: list[dict[str, Any]],
    train_prompts: list[str],
    pilot_prompts: list[str],
    train_family_ids: set[str],
    pilot_family_ids: set[str],
    first_read_timestamp: str,
    phase16_prompts: list[str] | None = None,
) -> dict[str, Any]:
    pack_root = Path(root)
    _outside_repository(pack_root, Path(repository_root))
    for filename in REQUIRED_PACK_FILES:
        _require(
            (pack_root / filename).is_file(),
            f"missing required human pack file: {filename}",
        )

    authored_bytes, authored_rows = _read_csv(
        pack_root / REQUIRED_PACK_FILES[0], AUTHORED_FIELDS
    )
    review_bytes, review_rows = _read_csv(
        pack_root / REQUIRED_PACK_FILES[1], REVIEW_FIELDS
    )
    metadata_bytes = (pack_root / REQUIRED_PACK_FILES[2]).read_bytes()
    metadata = _json_no_duplicate_keys(metadata_bytes, REQUIRED_PACK_FILES[2])

    _require(
        len(canonical_skills) == 16, "canonical skill index must contain 16 skills"
    )
    skill_ids = [row.get("id") for row in canonical_skills]
    _require(
        all(type(skill_id) is str and skill_id for skill_id in skill_ids)
        and len(set(skill_ids)) == 16,
        "canonical skill ids must be unique",
    )
    canonical_ids = {cast(str, skill_id) for skill_id in skill_ids}
    normalized_phase16_prompts = {
        _normalize(prompt) for prompt in (phase16_prompts or [])
    }
    leakage_terms = {
        _normalize(cast(str, row[field]))
        for row in canonical_skills
        for field in ("id", "name")
        if type(row.get(field)) is str and row[field]
    }

    authored_by_id: dict[str, dict[str, Any]] = {}
    prompt_bytes_seen: set[bytes] = set()
    normalized_prompts_seen: set[str] = set()
    family_ids_seen: set[str] = set()
    for raw in authored_rows:
        _require(
            all(
                raw.get(field, "").strip()
                for field in AUTHORED_FIELDS
                if field != "negative_skill_id"
            ),
            "authored row contains empty required field",
        )
        task_id = raw["task_id"].strip()
        _require(task_id not in authored_by_id, "task ids must be unique")
        prompt = raw["prompt_text"]
        prompt_bytes = prompt.encode("utf-8")
        normalized = _normalize(prompt)
        family = raw["semantic_family_id"].strip()
        gold = raw["gold_skill_id"].strip()
        negative = raw["negative_skill_id"].strip() or None
        _require(prompt_bytes not in prompt_bytes_seen, "prompt bytes must be unique")
        _require(
            normalized not in normalized_prompts_seen,
            "normalized prompts must be unique",
        )
        _require(
            normalized not in normalized_phase16_prompts,
            "Phase 16 prompt overlap detected",
        )
        _require(family not in family_ids_seen, "semantic families must be unique")
        _require(gold in canonical_ids, "gold skill must be canonical")
        _require(
            negative is None or negative in canonical_ids,
            "negative skill must be canonical",
        )
        _require(negative != gold, "negative skill must differ from gold")
        _require(
            raw["source_type"] == "HUMAN_AUTHORED", "source_type must be HUMAN_AUTHORED"
        )
        normalized_with_spaces = f" {normalized.replace('-', ' ')} "
        _require(
            not any(
                f" {marker} " in normalized_with_spaces for marker in _LEAKAGE_MARKERS
            ),
            "prompt contains label leakage",
        )
        _require(
            not any(marker in normalized for marker in _PROTECTED_MARKERS),
            "prompt contains protected old-data marker",
        )
        for term in leakage_terms:
            expanded = term.replace("-", " ")
            _require(
                f" {expanded} " not in normalized_with_spaces,
                "prompt contains a skill id or name",
            )
        authored_by_id[task_id] = {
            "task_id": task_id,
            "prompt_text": prompt,
            "prompt_text_sha256": _sha256_bytes(prompt_bytes),
            "semantic_family_id": family,
            "gold_skill_id": gold,
            "negative_skill_id": negative,
            "author_id": raw["author_id"].strip(),
            "author_reason": raw["author_reason"].strip(),
            "language": raw["language"].strip(),
            "source_type": raw["source_type"],
        }
        prompt_bytes_seen.add(prompt_bytes)
        normalized_prompts_seen.add(normalized)
        family_ids_seen.add(family)

    review_by_id: dict[str, dict[str, str]] = {}
    for row in review_rows:
        _require(
            all(
                row.get(field, "").strip()
                for field in REVIEW_FIELDS
                if field != "reviewed_negative_skill_id"
            ),
            "review row contains empty required field",
        )
        task_id = row["task_id"].strip()
        _require(task_id not in review_by_id, "review task ids must be unique")
        _require(task_id in authored_by_id, "review references unknown task")
        _require(row["review_decision"] in REVIEW_DECISIONS, "review decision mismatch")
        _require(
            row["prompt_text_sha256"] == authored_by_id[task_id]["prompt_text_sha256"],
            "review prompt hash mismatch",
        )
        _require(
            row["reviewer_id"].strip() != authored_by_id[task_id]["author_id"],
            "author and reviewer must differ",
        )
        review_by_id[task_id] = {key: value.strip() for key, value in row.items()}

    _require(
        set(review_by_id) == set(authored_by_id), "every authored task must be reviewed"
    )
    accepted = []
    excluded = 0
    for task_id, authored in authored_by_id.items():
        review = review_by_id[task_id]
        if review["review_decision"] != "ACCEPT":
            excluded += 1
            continue
        reviewed_negative = review["reviewed_negative_skill_id"] or None
        _require(
            review["reviewed_gold_skill_id"] == authored["gold_skill_id"]
            and reviewed_negative == authored["negative_skill_id"],
            "accepted review must exactly agree with author labels",
        )
        accepted.append(
            {
                **authored,
                "reviewer_id": review["reviewer_id"],
                "review_confidence": review["review_confidence"],
                "review_reason": review["review_reason"],
            }
        )

    _require(len(accepted) == 64, "human agreement must leave exactly 64 tasks")
    negative_rows = [row for row in accepted if row["negative_skill_id"] is not None]
    _require(
        len(negative_rows) == 48,
        "human agreement must leave exactly 48 negative-labeled tasks",
    )
    gold_counts = Counter(row["gold_skill_id"] for row in accepted)
    _require(
        set(gold_counts) == canonical_ids and set(gold_counts.values()) == {4},
        "gold distribution must be 16 skills x 4 tasks",
    )
    negative_by_gold = Counter(row["gold_skill_id"] for row in negative_rows)
    _require(
        set(negative_by_gold) == canonical_ids
        and set(negative_by_gold.values()) == {3},
        "each gold skill must have three negative-labeled tasks",
    )
    target_counts = Counter(row["negative_skill_id"] for row in negative_rows)
    _require(len(target_counts) >= 12, "negative targets must cover at least 12 skills")
    _require(
        max(target_counts.values(), default=0) <= 6,
        "negative target count may not exceed six",
    )
    _require(
        len({row["semantic_family_id"] for row in accepted}) == 64,
        "final pack must contain 64 semantic families",
    )

    train_normalized = {_normalize(prompt) for prompt in train_prompts}
    pilot_normalized = {_normalize(prompt) for prompt in pilot_prompts}
    for row in accepted:
        normalized = _normalize(row["prompt_text"])
        _require(normalized not in train_normalized, "train prompt overlap detected")
        _require(
            normalized not in pilot_normalized, "pilot-002 prompt overlap detected"
        )
        _require(
            row["semantic_family_id"] not in train_family_ids,
            "train family overlap detected",
        )
        _require(
            row["semantic_family_id"] not in pilot_family_ids,
            "pilot-002 family overlap detected",
        )

    author_ids = {row["author_id"] for row in accepted}
    reviewer_ids = {row["reviewer_id"] for row in accepted}
    _require(
        author_ids.isdisjoint(reviewer_ids),
        "author and reviewer identities must be disjoint",
    )
    _require(
        metadata.get("authors_and_reviewers_are_different_people") is True,
        "metadata must confirm different humans",
    )
    _require(
        metadata.get("reviewer_saw_model_rankings") is False,
        "reviewer must not see model rankings",
    )
    _require(
        metadata.get("reviewer_saw_pilot_002_task_level_results") is False,
        "reviewer must not see pilot-002 task-level results",
    )
    _require(
        metadata.get("human_author_count") == len(author_ids),
        "human author count mismatch",
    )
    _require(
        metadata.get("independent_human_reviewer_count") == len(reviewer_ids),
        "human reviewer count mismatch",
    )
    for field in ("review_date", "reviewer_qualification", "dataset_license"):
        _require(
            type(metadata.get(field)) is str and bool(metadata[field].strip()),
            f"metadata {field} is required",
        )
    for field in (
        "reviewer_used_ai_assistance",
        "publication_permission",
        "prompts_may_be_public_after_evaluation",
    ):
        _require(type(metadata.get(field)) is bool, f"metadata {field} must be boolean")
    _require(
        metadata.get("author_ids") == sorted(author_ids), "metadata author ids mismatch"
    )
    _require(
        metadata.get("reviewer_ids") == sorted(reviewer_ids),
        "metadata reviewer ids mismatch",
    )

    accepted.sort(key=lambda row: row["task_id"])
    source_hashes = {
        REQUIRED_PACK_FILES[0]: _sha256_bytes(authored_bytes),
        REQUIRED_PACK_FILES[1]: _sha256_bytes(review_bytes),
        REQUIRED_PACK_FILES[2]: _sha256_bytes(metadata_bytes),
    }
    return {
        "schema_version": "router-v2-blind-v2-human-pack-validation-v1",
        "status": "VALID",
        "task_count": 64,
        "negative_labeled_task_count": 48,
        "family_count": 64,
        "gold_distribution": dict(sorted(gold_counts.items())),
        "negative_distribution": dict(
            sorted((str(key), value) for key, value in target_counts.items())
        ),
        "negative_target_coverage_count": len(target_counts),
        "human_author_count": len(author_ids),
        "independent_human_reviewer_count": len(reviewer_ids),
        "exact_review_agreement_count": len(accepted),
        "excluded_candidate_count": excluded,
        "ai_assistance_disclosure": metadata["reviewer_used_ai_assistance"],
        "publication_permission": metadata["publication_permission"],
        "prompts_may_be_public_after_evaluation": metadata[
            "prompts_may_be_public_after_evaluation"
        ],
        "dataset_license": metadata["dataset_license"],
        "review_date": metadata["review_date"],
        "reviewer_qualification": metadata["reviewer_qualification"],
        "source_file_sha256": source_hashes,
        "first_read_timestamp": first_read_timestamp,
        "duplicate_checks": {
            "task_ids_unique": True,
            "prompt_bytes_unique": True,
            "nfkc_casefold_prompts_unique": True,
            "semantic_families_unique": True,
        },
        "train_overlap_checks": {"prompt_overlap_count": 0, "family_overlap_count": 0},
        "pilot_002_overlap_checks": {
            "prompt_overlap_count": 0,
            "family_overlap_count": 0,
        },
        "phase16_overlap_checks": {"prompt_overlap_count": 0},
        "model_scores_observed": False,
        "tasks": accepted,
    }


def build_dataset_freeze_documents(
    validation: dict[str, Any], *, commit_a: str
) -> dict[str, bytes]:
    _require(validation.get("status") == "VALID", "validated human pack is required")
    _require(
        type(commit_a) is str and len(commit_a) == 40,
        "Commit A must be a 40-character Git SHA",
    )
    publish = bool(
        validation["publication_permission"]
        and validation["prompts_may_be_public_after_evaluation"]
    )
    task_rows = []
    for task in validation["tasks"]:
        row = {
            "task_id": task["task_id"],
            "prompt_text_sha256": task["prompt_text_sha256"],
            "semantic_family_id": task["semantic_family_id"],
            "gold_skill_id": task["gold_skill_id"],
            "negative_skill_id": task["negative_skill_id"],
            "source_type": "HUMAN_AUTHORED",
        }
        if publish:
            row["prompt_text"] = task["prompt_text"]
        task_rows.append(row)
    task_bytes = b"".join(_canonical_json_bytes(row) for row in task_rows)
    review_summary = {
        "schema_version": "router-v2-blind-v2-review-summary-v1",
        "human_author_count": validation["human_author_count"],
        "independent_human_reviewer_count": validation[
            "independent_human_reviewer_count"
        ],
        "exact_review_agreement_count": validation["exact_review_agreement_count"],
        "excluded_candidate_count": validation["excluded_candidate_count"],
        "ai_assistance_disclosure": validation["ai_assistance_disclosure"],
        "dataset_license": validation["dataset_license"],
        "publication_permission": validation["publication_permission"],
        "prompts_may_be_public_after_evaluation": validation[
            "prompts_may_be_public_after_evaluation"
        ],
    }
    review_bytes = _canonical_json_bytes(review_summary)
    manifest = {
        "schema_version": "router-v2-blind-v2-manifest-v1",
        "commit_a": commit_a,
        "dataset_sha256": _sha256_bytes(task_bytes),
        "task_count": 64,
        "negative_labeled_task_count": 48,
        "gold_distribution": validation["gold_distribution"],
        "negative_distribution": validation["negative_distribution"],
        "family_count": 64,
        "human_author_count": validation["human_author_count"],
        "independent_human_reviewer_count": validation[
            "independent_human_reviewer_count"
        ],
        "ai_assistance_disclosure": validation["ai_assistance_disclosure"],
        "exact_review_agreement_count": validation["exact_review_agreement_count"],
        "excluded_candidate_count": validation["excluded_candidate_count"],
        "duplicate_checks": validation["duplicate_checks"],
        "train_overlap_checks": validation["train_overlap_checks"],
        "pilot_002_overlap_checks": validation["pilot_002_overlap_checks"],
        "phase16_overlap_checks": validation["phase16_overlap_checks"],
        "source_file_sha256": validation["source_file_sha256"],
        "per_row_prompt_sha256": [row["prompt_text_sha256"] for row in task_rows],
        "blind_v2_data_first_read_timestamp": validation["first_read_timestamp"],
        "prompts_committed": publish,
        "model_scores_observed": False,
        "evaluation_started": False,
        "retraining_after_data_access": False,
        "gate_changed_after_data_access": False,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    return {
        "blind-v2-tasks.jsonl": task_bytes,
        "blind-v2-review-summary.json": review_bytes,
        "blind-v2-manifest.json": manifest_bytes,
    }


def validate_frozen_dataset_documents(
    validation: dict[str, Any], documents: dict[str, bytes]
) -> list[dict[str, Any]]:
    _require(
        set(documents)
        == {
            "blind-v2-tasks.jsonl",
            "blind-v2-review-summary.json",
            "blind-v2-manifest.json",
        },
        "frozen dataset document set mismatch",
    )
    manifest = _json_no_duplicate_keys(
        documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    commit_a = manifest.get("commit_a")
    _require(type(commit_a) is str, "frozen dataset Commit A binding is missing")
    rebuilt = build_dataset_freeze_documents(validation, commit_a=cast(str, commit_a))
    for name, expected in rebuilt.items():
        _require(documents[name] == expected, f"frozen dataset bytes mismatch: {name}")
    return cast(list[dict[str, Any]], validation["tasks"])


def write_dataset_freeze(documents: dict[str, bytes], output_dir: Path | str) -> None:
    root = Path(output_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in (
        "blind-v2-tasks.jsonl",
        "blind-v2-review-summary.json",
        "blind-v2-manifest.json",
    ):
        payload = documents[name]
        with (root / name).open("xb") as handle:
            handle.write(payload)


def write_authoring_templates() -> list[Path]:
    root = AUTHORING_TEMPLATE_ROOT
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    authored = root / "blind-v2-authored.template.csv"
    review = root / "blind-v2-independent-review.template.csv"
    metadata = root / "reviewer-metadata.template.json"
    guide = root / "blind-v2-human-authoring-guide.md"
    authored.write_text(",".join(AUTHORED_FIELDS) + "\n", encoding="utf-8")
    review.write_text(",".join(REVIEW_FIELDS) + "\n", encoding="utf-8")
    metadata.write_bytes(
        _canonical_json_bytes(
            {
                "author_ids": [],
                "reviewer_ids": [],
                "human_author_count": 0,
                "independent_human_reviewer_count": 0,
                "authors_and_reviewers_are_different_people": False,
                "review_date": "",
                "reviewer_saw_model_rankings": False,
                "reviewer_saw_pilot_002_task_level_results": False,
                "reviewer_used_ai_assistance": False,
                "reviewer_qualification": "",
                "dataset_license": "",
                "publication_permission": False,
                "prompts_may_be_public_after_evaluation": False,
            }
        )
    )
    guide.write_text(
        "# Router V2 blind-v2 human authoring guide\n\n"
        "Humans must author candidate tasks and a different human must independently "
        "review labels. Do not include model scores, rankings, skill ids/names, benchmark "
        "metadata, old prompts, or AI-generated replacement rows. Freeze exactly 64 "
        "accepted tasks, 48 negative labels, 16 skills x 4 tasks, and 64 disjoint families.\n",
        encoding="utf-8",
    )
    return [authored, review, metadata, guide]


def _manifest_rows_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return _sha256_bytes(payload)


def _verify_model_files(
    model_root: Path, rows: list[dict[str, Any]], expected_hash: str
) -> None:
    _require(
        _manifest_rows_hash(rows) == expected_hash, "model file manifest hash mismatch"
    )
    for row in rows:
        relative = Path(row["path"])
        _require(
            not relative.is_absolute() and ".." not in relative.parts,
            "model file path is unsafe",
        )
        target = model_root / relative
        _require(target.is_file(), f"missing model file: {relative}")
        _require(
            target.stat().st_size == row["size"],
            f"model file size mismatch: {relative}",
        )
        _require(
            _sha256_file(target) == row["sha256"],
            f"model file hash mismatch: {relative}",
        )


def _repository_file(repository_root: Path, relative_value: Any, *, label: str) -> Path:
    _require(
        type(relative_value) is str and bool(relative_value), f"{label} path mismatch"
    )
    relative = Path(relative_value)
    _require(
        not relative.is_absolute() and ".." not in relative.parts,
        f"{label} path must be repository-relative",
    )
    resolved = (repository_root / relative).resolve(strict=True)
    _require(
        resolved.is_relative_to(repository_root.resolve(strict=True)),
        f"{label} path escapes repository",
    )
    _require(resolved.is_file(), f"{label} path must be a file")
    return resolved


def _artifact_binding(
    artifacts: list[dict[str, Any]], arm: str, seed: int
) -> dict[str, Any]:
    matches = [
        row for row in artifacts if row.get("arm") == arm and row.get("seed") == seed
    ]
    _require(len(matches) == 1, f"pilot {arm}/{seed} artifact binding mismatch")
    return matches[0]


def validate_preregistration_authority(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    verify_model_files: bool = True,
    canonical_path_required: bool = True,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    if canonical_path_required:
        _require(
            preregistration_file
            == (repository / PREREGISTRATION_RELATIVE).resolve(strict=True),
            "preregistration must use the canonical repository path",
        )
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    semantic_sha256 = preregistration.get("preregistration_sha256")
    _require(type(semantic_sha256) is str, "preregistration semantic hash is missing")
    unhashed = {
        key: value
        for key, value in preregistration.items()
        if key != "preregistration_sha256"
    }
    _require(
        canonical_sha256(unhashed) == semantic_sha256,
        "preregistration semantic hash mismatch",
    )
    validate_preregistration_truth(preregistration)

    contract = preregistered_evaluation_contract()
    _require(
        preregistration.get("preregistration_parent_git_commit")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("current_git_commit_before_commit_a")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("origin_main_git_commit")
        == PREREGISTRATION_PARENT_COMMIT,
        "preregistration parent Git binding mismatch",
    )
    _require(
        preregistration.get("blind_v2_expected_task_count") == 64
        and preregistration.get("blind_v2_expected_negative_labeled_task_count") == 48,
        "blind-v2 count binding mismatch",
    )
    _require(
        preregistration.get("statistics") == contract["statistics"],
        "statistics binding mismatch",
    )
    _require(
        preregistration.get("latency_measurement_protocol") == contract["latency"],
        "latency protocol binding mismatch",
    )
    _require(
        preregistration.get("evaluation_output_namespace")
        == str(FINAL_NAMESPACE_RELATIVE),
        "canonical namespace binding mismatch",
    )
    expected_metric_definitions = {
        "raw_count_first": True,
        "positive_denominator": 64,
        "negative_denominator": 48,
        "fields": [
            "recall_at_1",
            "recall_at_5",
            "mrr",
            "ndcg_at_5",
            "negative_hit_at_1",
            "negative_hit_at_5",
            "first_negative_rank",
            "latency_p50_ms",
            "latency_p95_ms",
        ],
        "aggregate_mean": "arithmetic",
        "aggregate_std": "sample_n_minus_1",
    }
    _require(
        preregistration.get("metric_definitions") == expected_metric_definitions,
        "metric definition binding mismatch",
    )
    for field, expected_truth in (
        ("retraining_allowed", False),
        ("threshold_change_allowed", False),
        ("best_seed_selection_allowed", False),
        ("posthoc_tuning_allowed", False),
        ("blind_v3_allowed", False),
        ("default_router_unchanged", True),
        ("production_ready", False),
        ("release_eligible", False),
        ("router_promotion_requires_separate_human_decision", True),
    ):
        _require(
            preregistration.get(field) is expected_truth,
            f"preregistration truth binding mismatch: {field}",
        )
    _require(preregistration.get("gate") == contract["gate"], "gate binding mismatch")
    evaluator = preregistration.get("evaluator")
    _require(type(evaluator) is dict, "evaluator binding is missing")
    evaluator = cast(dict[str, Any], evaluator)
    _require(
        evaluator.get("contract_sha256") == canonical_sha256(contract),
        "evaluator contract hash mismatch",
    )
    gate_artifact = preregistration.get("pilot_002_gate_artifact")
    _require(type(gate_artifact) is dict, "pilot-002 gate artifact binding is missing")
    gate_artifact = cast(dict[str, Any], gate_artifact)
    _require(
        gate_artifact.get("gate_semantic_sha256") == canonical_sha256(contract["gate"]),
        "gate binding mismatch",
    )
    gate_file = _repository_file(
        repository, gate_artifact.get("path"), label="gate artifact"
    )
    _require(
        _sha256_file(gate_file) == gate_artifact.get("file_sha256"),
        "gate artifact file hash mismatch",
    )
    gate_document = _json_no_duplicate_keys(gate_file.read_bytes(), "gate artifact")
    _require(gate_document.get("gate") == contract["gate"], "gate binding mismatch")
    _require(
        gate_document.get("plan_sha256") == gate_artifact.get("plan_semantic_sha256"),
        "gate plan semantic hash mismatch",
    )

    query = preregistration.get("query_contract")
    _require(type(query) is dict, "query contract binding is missing")
    query = cast(dict[str, Any], query)
    _require(
        query.get("version") == QUERY_CONTRACT_VERSION,
        "query contract version mismatch",
    )
    query_file = _repository_file(repository, query.get("path"), label="query contract")
    _require(
        _sha256_file(query_file) == query.get("sha256"),
        "query contract source hash mismatch",
    )
    skill_index = preregistration.get("skill_index")
    _require(type(skill_index) is dict, "skill index binding is missing")
    skill_index = cast(dict[str, Any], skill_index)
    skill_index_file = _repository_file(
        repository, skill_index.get("path"), label="skill index"
    )
    _require(
        _sha256_file(skill_index_file) == skill_index.get("sha256"),
        "skill index hash mismatch",
    )
    skill_builder = preregistration.get("skill_representation_builder")
    _require(type(skill_builder) is dict, "skill builder binding is missing")
    skill_builder = cast(dict[str, Any], skill_builder)
    _require(
        skill_builder.get("version") == SKILL_REPRESENTATION_BUILDER_VERSION,
        "skill builder version mismatch",
    )
    skill_builder_file = _repository_file(
        repository, skill_builder.get("path"), label="skill builder"
    )
    _require(
        _sha256_file(skill_builder_file) == skill_builder.get("sha256"),
        "skill builder source hash mismatch",
    )
    source_files = evaluator.get("source_files")
    _require(
        type(source_files) is list and bool(source_files),
        "evaluator sources are missing",
    )
    _require(
        {cast(dict[str, Any], row).get("path") for row in cast(list[Any], source_files)}
        == set(EVALUATOR_SOURCE_PATHS),
        "evaluator source set mismatch",
    )
    for raw_row in cast(list[Any], source_files):
        row = cast(dict[str, Any], raw_row)
        _require(type(row) is dict, "evaluator source binding mismatch")
        source = _repository_file(repository, row.get("path"), label="evaluator source")
        _require(
            _sha256_file(source) == row.get("sha256"),
            "evaluator source hash mismatch",
        )

    frozen_inputs = preregistration.get("frozen_inputs")
    _require(type(frozen_inputs) is dict, "frozen input bindings are missing")
    frozen_inputs = cast(dict[str, Any], frozen_inputs)
    for key in (
        "training_data_manifest",
        "accepted_pairs",
        "heldout_labels",
        "pilot_002_manifest",
        "pilot_002_truth_erratum",
        "pilot_002_evaluation_summary",
        "pilot_002_per_seed",
        "pilot_002_result_report",
        "pilot_002_route_results",
    ):
        binding = frozen_inputs.get(key)
        _require(type(binding) is dict, f"frozen {key} binding is missing")
        binding = cast(dict[str, Any], binding)
        frozen_file = _repository_file(
            repository, binding.get("path"), label=f"frozen {key}"
        )
        _require(
            _sha256_file(frozen_file) == binding.get("sha256"),
            f"frozen {key} hash mismatch",
        )

    phase16_files = preregistration.get("old_phase16_prompt_files")
    _require(
        type(phase16_files) is list and len(phase16_files) == 16,
        "old Phase 16 prompt bindings are missing",
    )
    phase16_paths: set[str] = set()
    for raw_binding in cast(list[Any], phase16_files):
        _require(type(raw_binding) is dict, "old Phase 16 prompt binding mismatch")
        binding = cast(dict[str, Any], raw_binding)
        phase16_file = _repository_file(
            repository, binding.get("path"), label="old Phase 16 prompt"
        )
        relative = phase16_file.relative_to(repository).as_posix()
        _require(relative not in phase16_paths, "old Phase 16 prompt path duplicated")
        phase16_paths.add(relative)
        _require(
            _sha256_file(phase16_file) == binding.get("sha256"),
            "old Phase 16 prompt hash mismatch",
        )

    pilot_binding = cast(dict[str, Any], frozen_inputs["pilot_002_manifest"])
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    _require(
        pilot_file
        == (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
        == _repository_file(
            repository, pilot_binding.get("path"), label="pilot-002 manifest"
        ),
        "pilot-002 manifest path is not preregistered",
    )
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    _require(
        pilot.get("manifest_sha256") == pilot_binding.get("semantic_sha256"),
        "pilot-002 manifest semantic hash mismatch",
    )

    base_binding = preregistration.get("base_model")
    _require(type(base_binding) is dict, "base model binding is missing")
    base_binding = cast(dict[str, Any], base_binding)
    base = pilot.get("base_model")
    _require(type(base) is dict, "pilot base model binding is missing")
    base = cast(dict[str, Any], base)
    _require(
        base_binding.get("model_id") == base.get("id")
        and base_binding.get("revision") == base.get("revision")
        and base_binding.get("checkpoint_path") == base.get("path")
        and base_binding.get("model_file_manifest_sha256")
        == base.get("file_manifest_sha256")
        and base_binding.get("model_files") == base.get("file_manifest_rows"),
        "base model binding mismatch",
    )
    artifacts = pilot.get("training_artifacts")
    _require(type(artifacts) is list, "pilot training artifacts are missing")
    artifacts = cast(list[dict[str, Any]], artifacts)
    arm_a_bindings = base_binding.get("per_seed_model_manifest_bindings")
    _require(
        type(arm_a_bindings) is list
        and {
            cast(dict[str, Any], row).get("seed")
            for row in cast(list[Any], arm_a_bindings)
        }
        == set(SEEDS),
        "Arm A model manifest grid mismatch",
    )
    for raw_preregistered in cast(list[Any], arm_a_bindings):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "A", preregistered["seed"])
        for field in (
            "model_path",
            "model_manifest_path",
            "model_manifest_file_sha256",
            "model_manifest_sha256",
            "model_file_manifest_sha256",
        ):
            _require(
                preregistered.get(field) == actual.get(field),
                "Arm A model manifest binding mismatch",
            )
    arm_c = preregistration.get("arm_c_checkpoints")
    _require(type(arm_c) is list and len(arm_c) == 3, "Arm C bindings are missing")
    for raw_preregistered in cast(list[Any], arm_c):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "C", preregistered["seed"])
        expected_checkpoint = {
            "checkpoint_path": actual["model_path"],
            "model_manifest_path": actual["model_manifest_path"],
            "model_manifest_file_sha256": actual["model_manifest_file_sha256"],
            "model_manifest_sha256": actual["model_manifest_sha256"],
            "model_file_manifest_sha256": actual["model_file_manifest_sha256"],
            "model_files": actual["model_file_manifest"],
        }
        _require(
            all(
                preregistered.get(field) == value
                for field, value in expected_checkpoint.items()
            ),
            "Arm C checkpoint binding mismatch",
        )

    if verify_model_files:
        base_path = Path(cast(str, base["path"]))
        _verify_model_files(
            base_path,
            cast(list[dict[str, Any]], base["file_manifest_rows"]),
            cast(str, base["file_manifest_sha256"]),
        )
        for arm in ARMS:
            for seed in SEEDS:
                artifact = _artifact_binding(artifacts, arm, seed)
                model_path = Path(artifact["model_path"])
                _verify_model_files(
                    model_path,
                    artifact["model_file_manifest"],
                    artifact["model_file_manifest_sha256"],
                )
                model_manifest = Path(artifact["model_manifest_path"])
                _require(
                    model_manifest.is_file()
                    and _sha256_file(model_manifest)
                    == artifact["model_manifest_file_sha256"],
                    f"{arm}/{seed} model manifest file hash mismatch",
                )
    return {
        "status": "VALID",
        "preregistration_sha256": semantic_sha256,
        "pilot_manifest_sha256": pilot_binding["sha256"],
        "preregistration_file_sha256": _sha256_file(preregistration_file),
        "model_files_verified": verify_model_files,
    }


def load_preregistered_human_validation_inputs(
    preregistration_path: Path | str, *, repository_root: Path | str
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    frozen = cast(dict[str, Any], preregistration["frozen_inputs"])
    skills_binding = cast(dict[str, Any], preregistration["skill_index"])
    skills = _json_no_duplicate_keys(
        b'{"skills":'
        + _repository_file(
            repository, skills_binding["path"], label="skill index"
        ).read_bytes()
        + b"}",
        "skill index wrapper",
    )["skills"]
    _require(type(skills) is list, "skill index must be a JSON array")

    accepted_binding = cast(dict[str, Any], frozen["accepted_pairs"])
    accepted_rows = _jsonl_no_duplicate_keys(
        _repository_file(
            repository, accepted_binding["path"], label="accepted pairs"
        ).read_bytes(),
        "accepted pairs",
    )
    heldout_binding = cast(dict[str, Any], frozen["heldout_labels"])
    heldout_rows = _jsonl_no_duplicate_keys(
        _repository_file(
            repository, heldout_binding["path"], label="heldout labels"
        ).read_bytes(),
        "heldout labels",
    )
    phase16_prompts = [
        _repository_file(
            repository,
            cast(dict[str, Any], raw_binding)["path"],
            label="old Phase 16 prompt",
        ).read_text(encoding="utf-8")
        for raw_binding in cast(list[Any], preregistration["old_phase16_prompt_files"])
    ]
    return {
        "preregistration": preregistration,
        "canonical_skills": cast(list[dict[str, Any]], skills),
        "train_prompts": [str(row["query_text"]) for row in accepted_rows],
        "pilot_prompts": [str(row["query_text"]) for row in heldout_rows],
        "train_family_ids": {
            str(row["positive_source_record_id"]) for row in accepted_rows
        },
        "pilot_family_ids": {
            str(row["positive_source_record_id"]) for row in heldout_rows
        },
        "phase16_prompts": phase16_prompts,
    }


def read_frozen_dataset_documents(repository_root: Path | str) -> dict[str, bytes]:
    repository = Path(repository_root).resolve(strict=True)
    root = (repository / DATASET_FREEZE_RELATIVE).resolve(strict=True)
    _require(root.is_relative_to(repository), "frozen dataset root escapes repository")
    actual = {path.name for path in root.iterdir() if path.is_file()}
    _require(
        actual == set(DATASET_FREEZE_FILENAMES),
        "frozen dataset directory must contain exactly three files",
    )
    return {
        filename: (root / filename).read_bytes()
        for filename in DATASET_FREEZE_FILENAMES
    }


def build_authoritative_lineage_bindings(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    frozen_documents: dict[str, bytes],
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    authority = validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    blind_manifest = _json_no_duplicate_keys(
        frozen_documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    artifacts = cast(list[dict[str, Any]], pilot["training_artifacts"])
    model_bindings = []
    for seed in SEEDS:
        for arm in ARMS:
            artifact = _artifact_binding(artifacts, arm, seed)
            model_bindings.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "model_path": artifact["model_path"],
                    "model_manifest_path": artifact["model_manifest_path"],
                    "model_manifest_file_sha256": artifact[
                        "model_manifest_file_sha256"
                    ],
                    "model_manifest_sha256": artifact["model_manifest_sha256"],
                    "model_file_manifest_sha256": artifact[
                        "model_file_manifest_sha256"
                    ],
                    "model_files": artifact["model_file_manifest"],
                }
            )
    return {
        "preregistration": {
            "path": preregistration_file.relative_to(repository).as_posix(),
            "file_sha256": authority["preregistration_file_sha256"],
            "semantic_sha256": authority["preregistration_sha256"],
        },
        "pilot_manifest": cast(dict[str, Any], preregistration["frozen_inputs"])[
            "pilot_002_manifest"
        ],
        "frozen_inputs": preregistration["frozen_inputs"],
        "old_phase16_prompt_files": preregistration["old_phase16_prompt_files"],
        "base_model": {
            "id": cast(dict[str, Any], pilot["base_model"])["id"],
            "revision": cast(dict[str, Any], pilot["base_model"])["revision"],
            "file_manifest_sha256": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_sha256"
            ],
            "model_files": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_rows"
            ],
        },
        "evaluation_models": model_bindings,
        "blind_v2_dataset": {
            "tasks_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-tasks.jsonl"]
            ),
            "manifest_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-manifest.json"]
            ),
            "dataset_sha256": blind_manifest["dataset_sha256"],
            "source_file_sha256": blind_manifest["source_file_sha256"],
            "per_row_prompt_sha256": blind_manifest["per_row_prompt_sha256"],
        },
        "human_review": {
            "review_summary_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-review-summary.json"]
            ),
            "source_file_sha256": blind_manifest["source_file_sha256"],
            "human_author_count": blind_manifest["human_author_count"],
            "independent_human_reviewer_count": blind_manifest[
                "independent_human_reviewer_count"
            ],
            "exact_review_agreement_count": blind_manifest[
                "exact_review_agreement_count"
            ],
        },
        "skill_index": preregistration["skill_index"],
        "query_contract": preregistration["query_contract"],
        "skill_representation_builder": preregistration["skill_representation_builder"],
        "gate": preregistration["pilot_002_gate_artifact"],
        "evaluator": preregistration["evaluator"],
    }


class _LocalSentenceTransformerEncoder:
    def __init__(self, model_path: Path) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real model smoke"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        value = self._model.encode(texts, normalize_embeddings=normalize_embeddings)
        if hasattr(value, "tolist"):
            value = value.tolist()
        return cast(list[list[float]], value)


def run_model_load_smoke(
    pilot_manifest_path: Path | str,
    *,
    preregistration_path: Path | str,
    repository_root: Path | str,
    encoder_factory: EncoderFactory | None = None,
    authority_validator: AuthorityValidator = validate_preregistration_authority,
) -> dict[str, Any]:
    authority_validator(
        preregistration_path,
        repository_root=repository_root,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    manifest = _json_no_duplicate_keys(
        Path(pilot_manifest_path).read_bytes(), "pilot manifest"
    )
    base = manifest["base_model"]
    base_path = Path(base["path"])
    _verify_model_files(
        base_path, base["file_manifest_rows"], base["file_manifest_sha256"]
    )
    c_artifacts = sorted(
        [row for row in manifest["training_artifacts"] if row.get("arm") == "C"],
        key=lambda row: row["seed"],
    )
    _require(
        [row["seed"] for row in c_artifacts] == list(SEEDS), "Arm C smoke grid mismatch"
    )
    for artifact in c_artifacts:
        model_path = Path(artifact["model_path"])
        _verify_model_files(
            model_path,
            artifact["model_file_manifest"],
            artifact["model_file_manifest_sha256"],
        )
        manifest_path = Path(artifact["model_manifest_path"])
        _require(manifest_path.is_file(), "missing model manifest")
        _require(
            _sha256_file(manifest_path) == artifact["model_manifest_file_sha256"],
            "model manifest file hash mismatch",
        )
    factory = encoder_factory or (
        lambda arm, seed, model_path: _LocalSentenceTransformerEncoder(model_path)
    )
    temporary = Path(tempfile.mkdtemp(prefix="hermes-blind-v2-model-smoke-"))
    os.chmod(temporary, 0o700)
    dimensions = []
    models = []
    try:
        materialized = temporary / "arm-A"
        shutil.copytree(base_path, materialized, symlinks=False)
        smoke_bindings = [
            {"arm": "A", "seed": 7170, "model_path": materialized},
            *[
                {
                    "arm": "C",
                    "seed": artifact["seed"],
                    "model_path": Path(artifact["model_path"]),
                }
                for artifact in c_artifacts
            ],
        ]
        for binding in smoke_bindings:
            encoder = factory(binding["arm"], binding["seed"], binding["model_path"])
            embeddings = encoder.encode(
                list(MODEL_LOAD_SMOKE_TEXTS), normalize_embeddings=True
            )
            if hasattr(embeddings, "tolist"):
                embeddings = embeddings.tolist()
            _require(
                type(embeddings) is list and len(embeddings) == 2,
                "smoke embedding row count mismatch",
            )
            _require(
                all(type(row) is list and row for row in embeddings),
                "smoke embeddings must be non-empty vectors",
            )
            dimension = len(embeddings[0])
            _require(
                all(len(row) == dimension for row in embeddings),
                "smoke embedding dimensions differ",
            )
            _require(
                all(math.isfinite(float(value)) for row in embeddings for value in row),
                "smoke embeddings must be finite",
            )
            dimensions.append(dimension)
            models.append({"arm": binding["arm"], "seed": binding["seed"]})
        _require(len(set(dimensions)) == 1, "model embedding dimensions differ")
        return {
            "schema_version": "router-v2-blind-v2-model-load-smoke-v1",
            "smoke_status": "PASS",
            "models": models,
            "embedding_dimension": dimensions[0],
            "device": "cpu",
            "synthetic_strings": list(MODEL_LOAD_SMOKE_TEXTS),
            "benchmark_metrics_computed": False,
            "blind_v2_data_read": False,
        }
    finally:
        shutil.rmtree(temporary)


def build_model_load_smoke_receipt(
    smoke: dict[str, Any], *, commit_a: str, preregistration_sha256: str
) -> dict[str, Any]:
    _require(
        set(smoke)
        == {
            "schema_version",
            "smoke_status",
            "models",
            "embedding_dimension",
            "device",
            "synthetic_strings",
            "benchmark_metrics_computed",
            "blind_v2_data_read",
        },
        "smoke result structure mismatch",
    )
    _require(
        smoke.get("schema_version") == "router-v2-blind-v2-model-load-smoke-v1",
        "smoke schema mismatch",
    )
    _require(smoke.get("smoke_status") == "PASS", "passing smoke is required")
    _require(smoke.get("blind_v2_data_read") is False, "smoke read blind-v2 data")
    _require(
        smoke.get("benchmark_metrics_computed") is False,
        "smoke computed benchmark metrics",
    )
    _require(
        smoke.get("models")
        == [
            {"arm": "A", "seed": 7170},
            {"arm": "C", "seed": 7170},
            {"arm": "C", "seed": 7171},
            {"arm": "C", "seed": 7172},
        ],
        "smoke model grid mismatch",
    )
    _require(
        smoke.get("synthetic_strings") == list(MODEL_LOAD_SMOKE_TEXTS),
        "smoke strings mismatch",
    )
    _require(
        type(commit_a) is str and len(commit_a) == 40,
        "smoke Commit A binding mismatch",
    )
    _require(
        type(preregistration_sha256) is str and len(preregistration_sha256) == 64,
        "smoke preregistration binding mismatch",
    )
    document = {
        "schema_version": "router-v2-blind-v2-model-load-smoke-receipt-v1",
        "commit_a": commit_a,
        "preregistration_sha256": preregistration_sha256,
        "smoke": smoke,
    }
    return {**document, "receipt_sha256": canonical_sha256(document)}


def model_load_smoke_receipt_path(commit_a: str) -> Path:
    _require(type(commit_a) is str and len(commit_a) == 40, "Commit A SHA mismatch")
    return SMOKE_RECEIPT_ROOT / f"{commit_a}.json"


def write_model_load_smoke_receipt(receipt: dict[str, Any]) -> Path:
    commit_a = receipt.get("commit_a")
    _require(type(commit_a) is str, "smoke receipt Commit A is missing")
    path = model_load_smoke_receipt_path(cast(str, commit_a))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(receipt))
    return path


def validate_model_load_smoke_receipt(
    *, commit_a: str, preregistration_sha256: str
) -> dict[str, Any]:
    path = model_load_smoke_receipt_path(commit_a)
    receipt = _json_no_duplicate_keys(path.read_bytes(), "model-load smoke receipt")
    receipt_sha256 = receipt.get("receipt_sha256")
    unhashed = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(
        receipt_sha256 == canonical_sha256(unhashed),
        "model-load smoke receipt hash mismatch",
    )
    _require(
        receipt.get("commit_a") == commit_a
        and receipt.get("preregistration_sha256") == preregistration_sha256,
        "model-load smoke receipt authority mismatch",
    )
    smoke = receipt.get("smoke")
    _require(type(smoke) is dict, "model-load smoke receipt structure mismatch")
    rebuilt = build_model_load_smoke_receipt(
        cast(dict[str, Any], smoke),
        commit_a=commit_a,
        preregistration_sha256=preregistration_sha256,
    )
    _require(receipt == rebuilt, "model-load smoke receipt structure mismatch")
    return receipt


class _SentenceTransformerScorer:
    def __init__(self, model_path: Path, skills: list[dict[str, Any]]) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real evaluation"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )
        self._skill_ids = [str(row["id"]) for row in skills]
        value = self._model.encode(
            [_skill_text(row) for row in skills], normalize_embeddings=True
        )
        if hasattr(value, "tolist"):
            value = value.tolist()
        self._skill_vectors = cast(list[list[float]], value)

    def rank(self, query: str, skill_ids: list[str]) -> list[str]:
        _require(skill_ids == self._skill_ids, "skill order changed during evaluation")
        value = self._model.encode([query], normalize_embeddings=True)
        if hasattr(value, "tolist"):
            value = value.tolist()
        query_vector = cast(list[list[float]], value)[0]
        scores = [
            quantize8(
                sum(
                    float(left) * float(right)
                    for left, right in zip(query_vector, vector, strict=True)
                )
            )
            for vector in self._skill_vectors
        ]
        return [
            skill_id
            for skill_id, _ in sorted(
                zip(self._skill_ids, scores, strict=True),
                key=lambda item: (-Decimal(item[1]), item[0]),
            )
        ]


def evaluate_routes(
    tasks: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
    *,
    scorer_factory: ScorerFactory | None = None,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> list[dict[str, Any]]:
    _require(len(tasks) == 64, "evaluation requires 64 tasks")
    ordered_tasks = sorted(tasks, key=lambda row: row["task_id"])
    _require(
        len({row["task_id"] for row in ordered_tasks}) == 64,
        "evaluation task ids must be unique",
    )
    ordered_skills = sorted(skills, key=lambda row: row["id"])
    skill_ids = [str(row["id"]) for row in ordered_skills]
    _require(
        len(skill_ids) == 16 and len(set(skill_ids)) == 16,
        "evaluation requires 16 skills",
    )
    binding_grid = {(row.get("arm"), row.get("seed")): row for row in model_bindings}
    _require(
        set(binding_grid) == {(arm, seed) for seed in SEEDS for arm in ARMS},
        "evaluation model bindings must be the complete A/C seed grid",
    )
    routes = []
    for seed in SEEDS:
        for arm in ARMS:
            binding = binding_grid[(arm, seed)]
            model_path = Path(binding["model_path"])
            scorer = (
                scorer_factory(arm, seed, model_path)
                if scorer_factory is not None
                else _SentenceTransformerScorer(model_path, ordered_skills)
            )
            for task in ordered_tasks:
                query = router_query_text(task["prompt_text"])
                scorer.rank(query, skill_ids)
                start = clock_ns()
                ranked = scorer.rank(query, skill_ids)
                end = clock_ns()
                _require(
                    len(ranked) == 16 and set(ranked) == set(skill_ids),
                    "scorer ranking must contain every skill once",
                )
                gold = task["gold_skill_id"]
                negative = task.get("negative_skill_id")
                routes.append(
                    {
                        "arm": arm,
                        "seed": seed,
                        "task_id": task["task_id"],
                        "gold_skill_id": gold,
                        "tempting_negative_skill_id": negative,
                        "semantic_family_id": task["semantic_family_id"],
                        "gold_rank": ranked.index(gold) + 1,
                        "tempting_negative_rank": (
                            ranked.index(negative) + 1 if negative is not None else None
                        ),
                        "latency_ns": end - start,
                    }
                )
    return routes


def build_evaluation_documents(
    route_rows: list[dict[str, Any]],
    *,
    commit_a: str,
    commit_b: str,
    evaluator_commit: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_artifacts: dict[str, bytes],
) -> dict[str, bytes]:
    _require(
        set(input_artifacts)
        == {"preregistration.json", "blind-v2-manifest.json", "review-summary.json"},
        "evaluation input artifact set mismatch",
    )
    _require(
        set(attempt_artifacts) == {"attempt-1.started.json", "attempt-1.terminal.json"},
        "attempt artifact set mismatch",
    )
    per_seed = [
        build_per_seed_result(
            [row for row in route_rows if row["arm"] == arm and row["seed"] == seed]
        )
        for seed in SEEDS
        for arm in ARMS
    ]
    aggregate = build_aggregate_results(per_seed)
    paired = build_paired_results(route_rows)
    statistics = build_statistics(route_rows)
    failures = build_failure_slices(route_rows)
    gate = apply_preregistered_gate(per_seed)
    summary = {
        "schema_version": "router-v2-blind-v2-evaluation-summary-v1",
        **gate,
        "task_count": 64,
        "negative_labeled_task_count": 48,
    }
    report = (
        "# Router V2 final blind-v2\n\n"
        f"Research conclusion: `{gate['research_conclusion']}`\n\n"
        "Default router remains unchanged. This is not a production, release, or SOTA claim.\n"
    ).encode("utf-8")
    result_documents = {
        "per-seed.json": _canonical_json_bytes(per_seed),
        "aggregate.json": _canonical_json_bytes(aggregate),
        "paired.json": _canonical_json_bytes(paired),
        "statistics.json": _canonical_json_bytes(statistics),
        "failure-slices.json": _canonical_json_bytes(failures),
        "evaluation-summary.json": _canonical_json_bytes(summary),
        "result-report.md": report,
    }
    documents = {**input_artifacts, **result_documents}
    lineage = build_lineage_manifest(
        commit_a=commit_a,
        commit_b=commit_b,
        evaluator_commit=evaluator_commit,
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=frozen_bindings,
        artifacts={**documents, **attempt_artifacts},
    )
    return {**documents, "lineage-manifest.json": _canonical_json_bytes(lineage)}


def _write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(value))


def build_attempt_started_document(started_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "router-v2-blind-v2-attempt-started-v1",
        "attempt_number": 1,
        "maximum_attempts": 1,
        **started_payload,
    }


def build_attempt_terminal_document(artifact_count: int) -> dict[str, Any]:
    _require(
        artifact_count == len(EVALUATION_OUTPUT_FILENAMES), "artifact count mismatch"
    )
    return {
        "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
        "attempt_number": 1,
        "status": "COMPLETED",
        "artifact_count": artifact_count,
    }


def _assert_output_safe(
    output_root: Path, repository_root: Path, protected_roots: list[Path]
) -> Path:
    repository = repository_root.resolve(strict=True)
    resolved = output_root.resolve(strict=False)
    canonical = (repository / FINAL_NAMESPACE_RELATIVE).resolve(strict=False)
    _require(
        resolved == canonical,
        "evaluation output must use the canonical namespace",
    )
    for root in protected_roots:
        protected = root.resolve(strict=False)
        _require(
            not resolved.is_relative_to(protected),
            "evaluation output may not be inside a protected root",
        )
    return resolved


def run_single_attempt(
    output_root: Path | str,
    *,
    repository_root: Path | str,
    started_payload: dict[str, Any],
    evaluate: Callable[[], dict[str, bytes]],
    protected_roots: list[Path],
) -> dict[str, Any]:
    output = _assert_output_safe(
        Path(output_root), Path(repository_root), protected_roots
    )
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    started = build_attempt_started_document(started_payload)
    _write_exclusive_json(output / "attempt-1.started.json", started)
    try:
        documents = evaluate()
        _require(type(documents) is dict, "evaluation must return artifact bytes")
        for name, payload in sorted(documents.items()):
            _require(
                type(name) is str
                and "/" not in name
                and name not in {"attempt-1.started.json", "attempt-1.terminal.json"},
                "evaluation artifact path is invalid",
            )
            _require(
                type(payload) is bytes, "evaluation artifact payload must be bytes"
            )
            with (output / name).open("xb") as handle:
                handle.write(payload)
        _require(
            set(documents) == set(EVALUATION_OUTPUT_FILENAMES),
            "evaluation output artifact set mismatch",
        )
        terminal = build_attempt_terminal_document(len(documents))
        _write_exclusive_json(output / "attempt-1.terminal.json", terminal)
        return terminal
    except Exception as exc:
        terminal = {
            "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
            "attempt_number": 1,
            "status": "INFRASTRUCTURE_FAILURE",
            "research_conclusion": "BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_allowed": False,
        }
        terminal_path = output / "attempt-1.terminal.json"
        if not terminal_path.exists():
            _write_exclusive_json(terminal_path, terminal)
        raise


def human_pack_root_from_environment(repository_root: Path | str) -> Path | None:
    value = os.environ.get("HERMES_BLIND_V2_ROOT")
    if not value:
        return None
    root = Path(value)
    _require(root.is_absolute(), "HERMES_BLIND_V2_ROOT must be absolute")
    if not root.exists() or any(
        not (root / name).is_file() for name in REQUIRED_PACK_FILES
    ):
        return None
    _outside_repository(root, Path(repository_root))
    return root
