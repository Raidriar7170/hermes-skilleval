from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


POLICY_ID = "router-v2-reviewed-source-policy-v1"
DRAFT_SCHEMA_VERSION = "router-v2-reviewed-source-draft-v1"
CANDIDATE_SCHEMA_VERSION = "router-v2-reviewed-source-record-v1"
MANIFEST_SCHEMA_VERSION = "router-v2-source-snapshot-manifest-v1"
CANONICAL_SKILL_INDEX = "docs/demo/phase9-real-skill-library-migration/skills.json"
CANONICAL_DRAFT = "data/router-v2-v4/source-draft.jsonl"
CANONICAL_CANDIDATES = "data/router-v2-v4/source-candidates.jsonl"
CANONICAL_QUEUE = "data/router-v2-v4/review-queue.csv"
CANONICAL_MANIFEST = "data/router-v2-v4/source-manifest.json"
CANONICAL_SKILL_INDEX_SHA256 = (
    "c67a786a6dcdc6f71716894f22f8ba409c38ec0954a07143b09a0372159ccaf5"
)

DRAFT_FIELDS = frozenset(
    {
        "schema_version",
        "draft_id",
        "prompt_family_id",
        "split",
        "draft_role",
        "positive_skill_id",
        "hard_negative_skill_id",
        "prompt_text",
    }
)
CANDIDATE_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_version",
        "policy_id",
        "source_record_id",
        "draft_id",
        "task_id",
        "prompt_family_id",
        "split",
        "source_role",
        "positive_skill_id",
        "skill_id",
        "query_text",
        "query_text_policy",
        "prompt_text_sha256",
        "skill_record_sha256",
        "source_kind",
        "source_artifact_path",
        "source_draft_line_sha256",
        "status",
        "decision",
        "reviewer",
        "reason",
    }
)
QUEUE_FIELDS = (
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "draft_id",
    "task_id",
    "prompt_family_id",
    "split",
    "source_role",
    "positive_skill_id",
    "positive_skill_name",
    "skill_id",
    "skill_name",
    "skill_category",
    "skill_description",
    "query_text",
    "prompt_text_sha256",
    "status",
    "decision",
    "reviewer",
    "reason",
)
MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_version",
        "policy_id",
        "snapshot_id",
        "ordering",
        "duplicate_policy",
        "runtime",
        "inputs",
        "outputs",
        "counts",
        "skill_distribution",
        "records",
        "non_actions",
    }
)

SPLIT_ORDER = ("train", "calibration", "non_blind_test")
ROLE_ORDER = ("POSITIVE", "HARD_NEGATIVE_CANDIDATE", "NO_SKILL_CANDIDATE")
NON_ACTIONS = tuple(
    sorted(
        {
            "accepted_pairs",
            "archive",
            "blind_v2",
            "checkpoint",
            "dashboard",
            "deploy",
            "gpu_access",
            "human_brief",
            "model_training",
            "preflight",
            "release",
            "review_decisions",
            "router_promotion",
            "tag",
            "threshold_tuning",
            "training_input",
        }
    )
)
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*\Z")

EXPECTED_SKILL_CATEGORIES = {
    "accessibility-tree-inspection": "browser-gui",
    "browser-smoke-testing": "browser-gui",
    "form-interaction-flow": "browser-gui",
    "visual-regression-review": "browser-gui",
    "mcp-tool-routing": "claude-code",
    "plan-mode": "claude-code",
    "slash-command-workflow": "claude-code",
    "task-tool-delegation": "claude-code",
    "apply-patch-discipline": "codex",
    "evidence-backed-final": "codex",
    "subagent-worker-protocol": "codex",
    "workspace-git-hygiene": "codex",
    "systematic-debugging": "superpowers",
    "test-driven-development": "superpowers",
    "using-git-worktrees": "superpowers",
    "verification-before-completion": "superpowers",
}

EXPECTED_COUNTS = {
    "total": 192,
    "train_positive": 64,
    "train_hard_negative_candidate": 64,
    "calibration_positive": 16,
    "non_blind_test_positive": 16,
    "calibration_no_skill_candidate": 16,
    "non_blind_test_no_skill_candidate": 16,
}


def build_router_v2_reviewed_source_snapshot(
    *,
    draft_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
    repository_root: Path | str,
) -> dict[str, Any]:
    """Validate and freeze the deterministic pre-review Router V2 v4 snapshot."""

    raw_skill_path = Path(skills_index_path)
    raw_target = Path(output_dir)
    raw_draft = Path(draft_path)
    if raw_skill_path.is_symlink() or not raw_skill_path.is_file():
        raise ValueError("skills index must be a regular non-symlink file")
    if raw_target.is_symlink() or not raw_target.is_dir():
        raise ValueError("output directory must be a regular non-symlink directory")
    if raw_draft.is_symlink() or not raw_draft.is_file():
        raise ValueError("source draft must be a regular non-symlink file")

    repo_root = Path(repository_root).resolve(strict=True)
    skill_path = raw_skill_path.resolve(strict=True)
    expected_skill_path = (repo_root / CANONICAL_SKILL_INDEX).resolve(strict=True)
    if skill_path != expected_skill_path:
        raise ValueError("skills index must be the canonical Skill Index path")

    target = raw_target.resolve(strict=True)
    draft = raw_draft.resolve(strict=True)
    expected_draft = (target / "source-draft.jsonl").resolve(strict=True)
    if draft != expected_draft:
        raise ValueError("draft_path must be output_dir/source-draft.jsonl")
    _validate_output_target(target, repo_root)

    skill_bytes = skill_path.read_bytes()
    if _sha256(skill_bytes) != CANONICAL_SKILL_INDEX_SHA256:
        raise ValueError("canonical Skill Index SHA-256 drift")
    skills = _load_skill_index(skill_bytes)

    draft_bytes = draft.read_bytes()
    draft_rows, draft_lines = _load_jsonl(draft_bytes, label="source draft")
    _validate_draft_rows(draft_rows, draft_lines, skills)

    candidates = _expand_candidates(draft_rows, draft_lines, skills)
    candidate_lines = [_json_line_bytes(row) for row in candidates]
    candidate_bytes = b"".join(candidate_lines)
    queue_bytes = _build_queue_bytes(candidates, candidate_lines, skills)
    manifest = _build_manifest(
        skill_bytes=skill_bytes,
        skills=skills,
        draft_bytes=draft_bytes,
        draft_rows=draft_rows,
        draft_lines=draft_lines,
        candidates=candidates,
        candidate_lines=candidate_lines,
        candidate_bytes=candidate_bytes,
        queue_bytes=queue_bytes,
    )
    manifest_bytes = _json_document_bytes(manifest)

    _publish_generated_files(
        target,
        {
            "source-candidates.jsonl": candidate_bytes,
            "review-queue.csv": queue_bytes,
            "source-manifest.json": manifest_bytes,
        },
    )
    return manifest


def _validate_output_target(target: Path, repo_root: Path) -> None:
    entries = sorted(path.name for path in target.iterdir())
    if entries != ["source-draft.jsonl"]:
        raise ValueError("output directory must contain only source-draft.jsonl")
    canonical_target = (repo_root / "data/router-v2-v4").resolve(strict=False)
    if target.is_relative_to(repo_root) and target != canonical_target:
        raise ValueError(
            "repository output must use the canonical data directory: data/router-v2-v4"
        )


def _load_skill_index(payload: bytes) -> dict[str, dict[str, Any]]:
    parsed = _json_loads_exact(payload.decode("utf-8", errors="strict"), "Skill Index")
    if not isinstance(parsed, list):
        raise ValueError("Skill Index must be a JSON array")
    skills: dict[str, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Skill Index rows must be objects with string ids")
        skill_id = item["id"]
        if skill_id in skills:
            raise ValueError(f"duplicate skill id: {skill_id}")
        skills[skill_id] = item
    actual_categories = {
        skill_id: row.get("category") for skill_id, row in skills.items()
    }
    if actual_categories != EXPECTED_SKILL_CATEGORIES:
        raise ValueError("canonical skill identities or categories drifted")
    return skills


def _load_jsonl(
    payload: bytes, *, label: str
) -> tuple[list[dict[str, Any]], list[bytes]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} has invalid Unicode") from exc
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} must end every row with LF")
    lines = payload.splitlines(keepends=True)
    rows: list[dict[str, Any]] = []
    for index, (line_bytes, line_text) in enumerate(
        zip(lines, text.splitlines(keepends=True), strict=True), start=1
    ):
        if not line_bytes.endswith(b"\n") or not line_text.endswith("\n"):
            raise ValueError(f"{label} line {index} is missing LF")
        value = _json_loads_exact(line_text[:-1], f"{label} line {index}")
        if not isinstance(value, dict):
            raise ValueError(f"{label} line {index} must be an object")
        rows.append(value)
    return rows, lines


def _json_loads_exact(text: str, label: str) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} has duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON") from exc


def _validate_draft_rows(
    rows: list[dict[str, Any]],
    raw_lines: list[bytes],
    skills: dict[str, dict[str, Any]],
) -> None:
    if len(rows) != 128:
        raise ValueError(f"source draft must contain exactly 128 rows, got {len(rows)}")
    seen_ids: set[str] = set()
    seen_families: set[str] = set()
    seen_prompts: dict[bytes, str] = {}
    normalized: list[tuple[str, set[str]]] = []
    role_counts: Counter[tuple[str, str]] = Counter()
    train_by_owner: Counter[str] = Counter()
    calibration_by_owner: Counter[str] = Counter()
    test_by_owner: Counter[str] = Counter()
    negative_target_counts: Counter[str] = Counter()

    for index, (row, raw_line) in enumerate(zip(rows, raw_lines, strict=True), start=1):
        unknown = set(row) - DRAFT_FIELDS
        missing = DRAFT_FIELDS - set(row)
        if unknown:
            raise ValueError(
                f"source draft line {index} has unknown fields: {sorted(unknown)}"
            )
        if missing:
            raise ValueError(
                f"source draft line {index} is missing fields: {sorted(missing)}"
            )
        _require_valid_unicode(row, f"source draft line {index}")
        if row["schema_version"] != DRAFT_SCHEMA_VERSION:
            raise ValueError(f"source draft line {index} has wrong schema_version")
        draft_id = _require_id(row["draft_id"], "draft_id")
        family = _require_id(row["prompt_family_id"], "prompt_family_id")
        if draft_id in seen_ids:
            raise ValueError(f"duplicate draft_id: {draft_id}")
        if family in seen_families:
            raise ValueError(f"duplicate prompt_family_id: {family}")
        seen_ids.add(draft_id)
        seen_families.add(family)
        split = row["split"]
        role = row["draft_role"]
        if not isinstance(split, str) or split not in SPLIT_ORDER:
            raise ValueError(f"invalid split for {draft_id}: {split!r}")
        if not isinstance(role, str) or role not in {
            "SKILL_POSITIVE",
            "NO_SKILL",
        }:
            raise ValueError(f"invalid draft_role for {draft_id}: {role!r}")
        prompt = row["prompt_text"]
        if not isinstance(prompt, str):
            raise ValueError(f"prompt_text must be a string for {draft_id}")
        _validate_prompt(prompt, draft_id)
        prompt_bytes = prompt.encode("utf-8", errors="strict")
        if prompt_bytes in seen_prompts:
            raise ValueError(
                f"duplicate prompt_text: {seen_prompts[prompt_bytes]} and {draft_id}"
            )
        seen_prompts[prompt_bytes] = draft_id
        normalized.append((draft_id, _prompt_5grams(prompt)))

        positive = row["positive_skill_id"]
        negative = row["hard_negative_skill_id"]
        if positive is not None and not isinstance(positive, str):
            raise ValueError(f"invalid positive_skill_id for {draft_id}: {positive!r}")
        if negative is not None and not isinstance(negative, str):
            raise ValueError(
                f"invalid hard_negative_skill_id for {draft_id}: {negative!r}"
            )
        if role == "SKILL_POSITIVE":
            if positive not in skills:
                raise ValueError(f"unknown positive skill for {draft_id}: {positive!r}")
            if split == "train":
                if negative not in skills:
                    raise ValueError(
                        f"unknown hard negative for {draft_id}: {negative!r}"
                    )
                if negative == positive:
                    raise ValueError(f"hard negative equals positive for {draft_id}")
                if skills[negative]["category"] != skills[positive]["category"]:
                    raise ValueError(f"hard negative category mismatch for {draft_id}")
                train_by_owner[positive] += 1
                negative_target_counts[negative] += 1
            elif negative is not None:
                raise ValueError(f"hard_negative_skill_id must be null for {draft_id}")
            elif split == "calibration":
                calibration_by_owner[positive] += 1
            else:
                test_by_owner[positive] += 1
        elif positive is not None or negative is not None or split == "train":
            raise ValueError(f"invalid no-skill relation for {draft_id}")
        role_counts[(split, role)] += 1
        if raw_line != _json_line_bytes(row):
            raise ValueError(f"source draft line {index} is not canonical JSONL")

    expected_roles = Counter(
        {
            ("train", "SKILL_POSITIVE"): 64,
            ("calibration", "SKILL_POSITIVE"): 16,
            ("non_blind_test", "SKILL_POSITIVE"): 16,
            ("calibration", "NO_SKILL"): 16,
            ("non_blind_test", "NO_SKILL"): 16,
        }
    )
    if role_counts != expected_roles:
        raise ValueError(
            f"source draft role/split counts mismatch: {dict(role_counts)}"
        )
    expected_train = {skill_id: 4 for skill_id in skills}
    expected_eval = {skill_id: 1 for skill_id in skills}
    if dict(train_by_owner) != expected_train:
        raise ValueError("train positive owner distribution must be four per skill")
    if dict(calibration_by_owner) != expected_eval:
        raise ValueError("calibration positive distribution must be one per skill")
    if dict(test_by_owner) != expected_eval:
        raise ValueError("non-blind-test positive distribution must be one per skill")
    if dict(negative_target_counts) != expected_train:
        raise ValueError("hard negative target distribution must be four per skill")
    _reject_near_duplicates(normalized)


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def _require_valid_unicode(value: Any, label: str) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"{label} contains invalid Unicode") from exc
    elif isinstance(value, dict):
        for key, item in value.items():
            _require_valid_unicode(key, label)
            _require_valid_unicode(item, label)
    elif isinstance(value, list):
        for item in value:
            _require_valid_unicode(item, label)


def _validate_prompt(prompt: str, draft_id: str) -> None:
    if len(prompt) < 5:
        raise ValueError(f"prompt_text too short for {draft_id}")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in prompt):
        raise ValueError(f"prompt_text must be printable ASCII for {draft_id}")
    if prompt != prompt.strip() or "  " in prompt:
        raise ValueError(f"prompt_text whitespace is not canonical for {draft_id}")


def _prompt_5grams(prompt: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", prompt).casefold()
    mapped = "".join(
        character if character in "abcdefghijklmnopqrstuvwxyz0123456789" else " "
        for character in normalized
    )
    collapsed = " ".join(mapped.split())
    if len(collapsed) < 5:
        raise ValueError("normalized prompt must contain at least five characters")
    return {collapsed[index : index + 5] for index in range(len(collapsed) - 4)}


def _reject_near_duplicates(normalized: list[tuple[str, set[str]]]) -> None:
    for index, (left_id, left) in enumerate(normalized):
        for right_id, right in normalized[index + 1 :]:
            similarity = len(left & right) / len(left | right)
            if similarity >= 0.85:
                raise ValueError(
                    f"near-duplicate prompts: {left_id} and {right_id} ({similarity:.6f})"
                )


def _expand_candidates(
    drafts: list[dict[str, Any]],
    draft_lines: list[bytes],
    skills: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for draft, raw_line in zip(drafts, draft_lines, strict=True):
        if draft["draft_role"] == "SKILL_POSITIVE":
            expanded.append(
                _candidate_row(
                    draft=draft,
                    raw_draft_line=raw_line,
                    source_role="POSITIVE",
                    skill_id=draft["positive_skill_id"],
                    skills=skills,
                )
            )
            if draft["split"] == "train":
                expanded.append(
                    _candidate_row(
                        draft=draft,
                        raw_draft_line=raw_line,
                        source_role="HARD_NEGATIVE_CANDIDATE",
                        skill_id=draft["hard_negative_skill_id"],
                        skills=skills,
                    )
                )
        else:
            expanded.append(
                _candidate_row(
                    draft=draft,
                    raw_draft_line=raw_line,
                    source_role="NO_SKILL_CANDIDATE",
                    skill_id=None,
                    skills=skills,
                )
            )
    split_rank = {value: index for index, value in enumerate(SPLIT_ORDER)}
    role_rank = {value: index for index, value in enumerate(ROLE_ORDER)}
    expanded.sort(
        key=lambda row: (
            split_rank[row["split"]],
            row["prompt_family_id"],
            role_rank[row["source_role"]],
            row["source_record_id"],
        )
    )
    if len(expanded) != 192 or any(set(row) != CANDIDATE_FIELDS for row in expanded):
        raise ValueError("internal candidate expansion contract failure")
    return expanded


def _candidate_row(
    *,
    draft: dict[str, Any],
    raw_draft_line: bytes,
    source_role: str,
    skill_id: str | None,
    skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    draft_id = draft["draft_id"]
    if source_role == "POSITIVE":
        source_record_id = f"{draft_id}:positive:{skill_id}"
    elif source_role == "HARD_NEGATIVE_CANDIDATE":
        source_record_id = f"{draft_id}:hard-negative-candidate:{skill_id}"
    else:
        source_record_id = f"{draft_id}:no-skill"
    skill_hash = None
    if skill_id is not None:
        skill_hash = _sha256(_json_object_bytes(skills[skill_id]))
    prompt = draft["prompt_text"]
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "artifact_version": 1,
        "policy_id": POLICY_ID,
        "source_record_id": source_record_id,
        "draft_id": draft_id,
        "task_id": draft_id,
        "prompt_family_id": draft["prompt_family_id"],
        "split": draft["split"],
        "source_role": source_role,
        "positive_skill_id": draft["positive_skill_id"],
        "skill_id": skill_id,
        "query_text": prompt,
        "query_text_policy": "prompt_only",
        "prompt_text_sha256": _sha256(prompt.encode("utf-8")),
        "skill_record_sha256": skill_hash,
        "source_kind": "ROUTER_V2_V4_AUTHORED_DRAFT",
        "source_artifact_path": CANONICAL_DRAFT,
        "source_draft_line_sha256": _sha256(raw_draft_line),
        "status": "PENDING_REVIEW",
        "decision": "",
        "reviewer": "",
        "reason": "",
    }


def _build_queue_bytes(
    candidates: list[dict[str, Any]],
    candidate_lines: list[bytes],
    skills: dict[str, dict[str, Any]],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=QUEUE_FIELDS,
        dialect="excel",
        lineterminator="\n",
    )
    writer.writeheader()
    for row, raw_line in zip(candidates, candidate_lines, strict=True):
        positive = skills.get(row["positive_skill_id"])
        candidate = skills.get(row["skill_id"])
        writer.writerow(
            {
                "source_record_id": row["source_record_id"],
                "source_record_exact_bytes_sha256": _sha256(raw_line),
                "draft_id": row["draft_id"],
                "task_id": row["task_id"],
                "prompt_family_id": row["prompt_family_id"],
                "split": row["split"],
                "source_role": row["source_role"],
                "positive_skill_id": row["positive_skill_id"] or "",
                "positive_skill_name": positive["name"] if positive else "",
                "skill_id": row["skill_id"] or "",
                "skill_name": candidate["name"] if candidate else "",
                "skill_category": candidate["category"] if candidate else "",
                "skill_description": candidate["description"] if candidate else "",
                "query_text": row["query_text"],
                "prompt_text_sha256": row["prompt_text_sha256"],
                "status": row["status"],
                "decision": "",
                "reviewer": "",
                "reason": "",
            }
        )
    return output.getvalue().encode("utf-8")


def _build_manifest(
    *,
    skill_bytes: bytes,
    skills: dict[str, dict[str, Any]],
    draft_bytes: bytes,
    draft_rows: list[dict[str, Any]],
    draft_lines: list[bytes],
    candidates: list[dict[str, Any]],
    candidate_lines: list[bytes],
    candidate_bytes: bytes,
    queue_bytes: bytes,
) -> dict[str, Any]:
    policy_bytes = POLICY_ID.encode("utf-8")
    snapshot_digest = _sha256(skill_bytes + b"\0" + draft_bytes + b"\0" + policy_bytes)
    draft_line_by_id = {
        row["draft_id"]: _sha256(raw_line)
        for row, raw_line in zip(draft_rows, draft_lines, strict=True)
    }
    records = [
        {
            "source_record_id": row["source_record_id"],
            "draft_id": row["draft_id"],
            "draft_line_sha256": draft_line_by_id[row["draft_id"]],
            "source_record_exact_bytes_sha256": _sha256(raw_line),
            "prompt_text_sha256": row["prompt_text_sha256"],
            "prompt_family_id": row["prompt_family_id"],
            "split": row["split"],
            "source_role": row["source_role"],
            "positive_skill_id": row["positive_skill_id"],
            "skill_id": row["skill_id"],
        }
        for row, raw_line in zip(candidates, candidate_lines, strict=True)
    ]
    counts = _candidate_counts(candidates)
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"candidate counts mismatch: {counts}")
    distribution = {
        "train_positive_by_skill": _skill_counts(
            candidates, split="train", role="POSITIVE", field="positive_skill_id"
        ),
        "calibration_positive_by_skill": _skill_counts(
            candidates,
            split="calibration",
            role="POSITIVE",
            field="positive_skill_id",
        ),
        "non_blind_test_positive_by_skill": _skill_counts(
            candidates,
            split="non_blind_test",
            role="POSITIVE",
            field="positive_skill_id",
        ),
        "hard_negative_owner_by_skill": _skill_counts(
            candidates,
            split="train",
            role="HARD_NEGATIVE_CANDIDATE",
            field="positive_skill_id",
        ),
        "hard_negative_target_by_skill": _skill_counts(
            candidates,
            split="train",
            role="HARD_NEGATIVE_CANDIDATE",
            field="skill_id",
        ),
    }
    expected_ids = sorted(skills)
    if any(sorted(value) != expected_ids for value in distribution.values()):
        raise ValueError("skill distribution is incomplete")
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_version": 1,
        "policy_id": POLICY_ID,
        "snapshot_id": f"router-v2-v4-source-{snapshot_digest[:16]}",
        "ordering": {
            "split_order": list(SPLIT_ORDER),
            "source_role_order": list(ROLE_ORDER),
            "sort_keys": [
                "split",
                "prompt_family_id",
                "source_role",
                "source_record_id",
            ],
        },
        "duplicate_policy": {
            "algorithm_id": "ascii-nfkc-casefold-char5-jaccard-v1",
            "threshold": 0.85,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "unicode_data_version": unicodedata.unidata_version,
        },
        "inputs": {
            "skill_index": _file_record(
                CANONICAL_SKILL_INDEX, skill_bytes, len(skills)
            ),
            "source_draft": _file_record(CANONICAL_DRAFT, draft_bytes, len(draft_rows)),
        },
        "outputs": {
            "source_candidates": _file_record(
                CANONICAL_CANDIDATES, candidate_bytes, len(candidates)
            ),
            "review_queue": _file_record(CANONICAL_QUEUE, queue_bytes, len(candidates)),
        },
        "counts": counts,
        "skill_distribution": distribution,
        "records": records,
        "non_actions": list(NON_ACTIONS),
    }


def _candidate_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(candidates),
        "train_positive": sum(
            row["split"] == "train" and row["source_role"] == "POSITIVE"
            for row in candidates
        ),
        "train_hard_negative_candidate": sum(
            row["split"] == "train" and row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
            for row in candidates
        ),
        "calibration_positive": sum(
            row["split"] == "calibration" and row["source_role"] == "POSITIVE"
            for row in candidates
        ),
        "non_blind_test_positive": sum(
            row["split"] == "non_blind_test" and row["source_role"] == "POSITIVE"
            for row in candidates
        ),
        "calibration_no_skill_candidate": sum(
            row["split"] == "calibration" and row["source_role"] == "NO_SKILL_CANDIDATE"
            for row in candidates
        ),
        "non_blind_test_no_skill_candidate": sum(
            row["split"] == "non_blind_test"
            and row["source_role"] == "NO_SKILL_CANDIDATE"
            for row in candidates
        ),
    }


def _skill_counts(
    candidates: list[dict[str, Any]],
    *,
    split: str,
    role: str,
    field: str,
) -> dict[str, int]:
    counts = Counter(
        row[field]
        for row in candidates
        if row["split"] == split and row["source_role"] == role
    )
    return {skill_id: counts[skill_id] for skill_id in sorted(counts)}


def _file_record(path: str, payload: bytes, row_count: int) -> dict[str, Any]:
    return {
        "path": path,
        "sha256": _sha256(payload),
        "byte_size": len(payload),
        "row_count": row_count,
    }


def _publish_generated_files(target: Path, files: dict[str, bytes]) -> None:
    stage = Path(tempfile.mkdtemp(prefix=".router-v2-v4-stage-", dir=target.parent))
    published: list[tuple[Path, Path]] = []
    try:
        for name, payload in files.items():
            (stage / name).write_bytes(payload)
        if sorted(path.name for path in target.iterdir()) != ["source-draft.jsonl"]:
            raise ValueError("output directory must contain only source-draft.jsonl")
        for name in sorted(files):
            source = stage / name
            destination = target / name
            os.link(source, destination)
            published.append((source, destination))
    except BaseException as exc:
        cleanup_errors: list[OSError] = []
        for source, destination in reversed(published):
            try:
                if destination.exists() and source.samefile(destination):
                    destination.unlink()
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        try:
            shutil.rmtree(stage)
        except OSError as cleanup_error:
            cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            raise RuntimeError(
                "failed to roll back staged snapshot publication"
            ) from exc
        raise
    else:
        shutil.rmtree(stage)


def _json_object_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_line_bytes(payload: Any) -> bytes:
    return _json_object_bytes(payload) + b"\n"


def _json_document_bytes(payload: Any) -> bytes:
    return _json_line_bytes(payload)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-path", type=Path, required=True)
    parser.add_argument("--skills-index-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_router_v2_reviewed_source_snapshot(
        draft_path=args.draft_path,
        skills_index_path=args.skills_index_path,
        output_dir=args.output_dir,
        repository_root=args.repository_root,
    )
    print(
        json.dumps(
            {
                "snapshot_id": manifest["snapshot_id"],
                "counts": manifest["counts"],
                "status": "PENDING_REVIEW",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
