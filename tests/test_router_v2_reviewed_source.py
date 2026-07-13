from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import io
import json
import platform
import shutil
import subprocess
import unicodedata
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_reviewed_source as reviewed_source
from hermes_skilleval.router_v2_reviewed_source import (
    CANDIDATE_FIELDS,
    CANONICAL_SKILL_INDEX_SHA256,
    MANIFEST_FIELDS,
    QUEUE_FIELDS,
    build_router_v2_reviewed_source_snapshot,
)


ROOT = Path(__file__).parents[1]
CANONICAL_INDEX = ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
CANONICAL_DRAFT = ROOT / "data/router-v2-v4/source-draft.jsonl"

EXPECTED_COUNTS = {
    "total": 192,
    "train_positive": 64,
    "train_hard_negative_candidate": 64,
    "calibration_positive": 16,
    "non_blind_test_positive": 16,
    "calibration_no_skill_candidate": 16,
    "non_blind_test_no_skill_candidate": 16,
}

EXPECTED_NON_ACTIONS = sorted(
    [
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
    ]
)

PROTECTED_BASELINE_OIDS = {
    "docs/demo/phase14-finetuned-embedding-router": "cd0ea8a60de9144403b44dba0859e7888e1d805f",
    "docs/demo/phase15-held-out-generalization": "25a1a9ad235f6ec1a6939414d67768c75266e665",
    "docs/demo/phase16-blind-validation": "ae2390e580b0f905316ad1e047801dc47535ef68",
    "docs/demo/phase17-calibrated-release-selector": "87960aa8ed5fabaf4244730926b6e3688a0a2033",
    "docs/demo/phase18-ci-release-reproducibility": "8524fed102111616809c9923052f23b6e934559e",
    "benchmarks/blind-migration-tasks": "4132139c513cd936086ef535fc52310361ee8c59",
    "benchmarks/migration-tasks": "ef29338c5b668a4ef01013f35bb7a3c90d574cae",
    "docs/demo/router-training-data-v2-qualification-pack": "0d0f79f7da387b2379e60501e1d7358659e1987a",
    "docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl": "7f5c026a1bdefa06b205335b7c8e67810a7fc7a4",
    "docs/demo/router-training-data-v2-qualification-pack/qualification-report.json": "d2db024035e69200cd37541d36b210ebb2c23a2a",
    "docs/demo/router-training-data-v2-qualification-pack/manifest.json": "c8eb9bfb66eddce95ecb52e90f9be328b9180bd2",
}

FILE_RECORD_FIELDS = {"path", "sha256", "byte_size", "row_count"}
MANIFEST_RECORD_FIELDS = {
    "source_record_id",
    "draft_id",
    "draft_line_sha256",
    "source_record_exact_bytes_sha256",
    "prompt_text_sha256",
    "prompt_family_id",
    "split",
    "source_role",
    "positive_skill_id",
    "skill_id",
}
PROTECTED_WORKTREE_PATHS = (
    "docs/demo/phase14-finetuned-embedding-router",
    "docs/demo/phase15-held-out-generalization",
    "docs/demo/phase16-blind-validation",
    "docs/demo/phase17-calibrated-release-selector",
    "docs/demo/phase18-ci-release-reproducibility",
    "benchmarks/blind-migration-tasks",
    "benchmarks/migration-tasks",
    "docs/demo/router-training-data-v2-qualification-pack",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_bytes(b"".join(_json_bytes(row) for row in rows))


def _fresh_snapshot_dir(tmp_path: Path, name: str = "snapshot") -> Path:
    target = tmp_path / name
    target.mkdir()
    shutil.copyfile(CANONICAL_DRAFT, target / "source-draft.jsonl")
    return target


def _build(tmp_path: Path, name: str = "snapshot") -> Path:
    target = _fresh_snapshot_dir(tmp_path, name)
    build_router_v2_reviewed_source_snapshot(
        draft_path=target / "source-draft.jsonl",
        skills_index_path=CANONICAL_INDEX,
        output_dir=target,
        repository_root=ROOT,
    )
    return target


def _candidate_lines(path: Path) -> list[bytes]:
    lines = path.read_bytes().splitlines(keepends=True)
    assert lines and all(line.endswith(b"\n") for line in lines)
    return lines


def test_canonical_skill_index_anchor_is_exact():
    assert _sha256(CANONICAL_INDEX.read_bytes()) == CANONICAL_SKILL_INDEX_SHA256
    assert CANONICAL_SKILL_INDEX_SHA256 == (
        "c67a786a6dcdc6f71716894f22f8ba409c38ec0954a07143b09a0372159ccaf5"
    )

    skills = json.loads(CANONICAL_INDEX.read_text(encoding="utf-8"))
    assert len(skills) == 16
    assert Counter(skill["category"] for skill in skills) == {
        "browser-gui": 4,
        "claude-code": 4,
        "codex": 4,
        "superpowers": 4,
    }


def test_protected_baseline_tree_and_blob_identities_are_unchanged():
    for path, expected_oid in PROTECTED_BASELINE_OIDS.items():
        actual = subprocess.run(
            ["git", "rev-parse", f"HEAD:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == expected_oid, path

    status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            *PROTECTED_WORKTREE_PATHS,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""


def test_canonical_draft_expands_to_exact_balanced_192_rows(tmp_path):
    target = _build(tmp_path)
    rows = _load_jsonl(target / "source-candidates.jsonl")
    manifest = json.loads((target / "source-manifest.json").read_text(encoding="utf-8"))

    assert len(_load_jsonl(target / "source-draft.jsonl")) == 128
    assert len(rows) == 192
    assert manifest["counts"] == EXPECTED_COUNTS
    assert manifest["skill_distribution"] == {
        "train_positive_by_skill": {skill_id: 4 for skill_id in sorted(_skill_ids())},
        "calibration_positive_by_skill": {
            skill_id: 1 for skill_id in sorted(_skill_ids())
        },
        "non_blind_test_positive_by_skill": {
            skill_id: 1 for skill_id in sorted(_skill_ids())
        },
        "hard_negative_owner_by_skill": {
            skill_id: 4 for skill_id in sorted(_skill_ids())
        },
        "hard_negative_target_by_skill": {
            skill_id: 4 for skill_id in sorted(_skill_ids())
        },
    }

    assert all(row["status"] == "PENDING_REVIEW" for row in rows)
    assert all(row["decision"] == "" for row in rows)
    assert all(row["reviewer"] == "" for row in rows)
    assert all(row["reason"] == "" for row in rows)
    assert not (target / "review-decisions.csv").exists()
    assert not (target / "accepted-pairs.jsonl").exists()
    assert not (target / "training-input-manifest.json").exists()


def test_hard_negative_owner_and_target_relations_are_exact(tmp_path):
    target = _build(tmp_path)
    rows = _load_jsonl(target / "source-candidates.jsonl")
    skills = {skill["id"]: skill for skill in _skills()}
    negatives = [row for row in rows if row["source_role"] == "HARD_NEGATIVE_CANDIDATE"]

    assert Counter(row["positive_skill_id"] for row in negatives) == {
        skill_id: 4 for skill_id in sorted(skills)
    }
    assert Counter(row["skill_id"] for row in negatives) == {
        skill_id: 4 for skill_id in sorted(skills)
    }
    for row in negatives:
        assert row["positive_skill_id"] != row["skill_id"]
        assert (
            skills[row["positive_skill_id"]]["category"]
            == skills[row["skill_id"]]["category"]
        )


def test_families_are_split_disjoint_and_prompt_reuse_is_only_train_pair(tmp_path):
    target = _build(tmp_path)
    rows = _load_jsonl(target / "source-candidates.jsonl")
    families_by_split = {
        split: {row["prompt_family_id"] for row in rows if row["split"] == split}
        for split in ("train", "calibration", "non_blind_test")
    }

    assert families_by_split["train"].isdisjoint(families_by_split["calibration"])
    assert families_by_split["train"].isdisjoint(families_by_split["non_blind_test"])
    assert families_by_split["calibration"].isdisjoint(
        families_by_split["non_blind_test"]
    )

    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_prompt.setdefault(row["query_text"], []).append(row)
    assert sorted(len(group) for group in by_prompt.values()) == [1] * 64 + [2] * 64
    for group in by_prompt.values():
        if len(group) == 2:
            assert {row["source_role"] for row in group} == {
                "POSITIVE",
                "HARD_NEGATIVE_CANDIDATE",
            }
            assert len({row["draft_id"] for row in group}) == 1
            assert len({row["prompt_family_id"] for row in group}) == 1
            assert {row["split"] for row in group} == {"train"}


def test_source_queue_and_manifest_exact_shapes_and_bytes(tmp_path):
    target = _build(tmp_path)
    source_path = target / "source-candidates.jsonl"
    manifest_path = target / "source-manifest.json"
    queue_path = target / "review-queue.csv"
    rows = _load_jsonl(source_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_lines = _candidate_lines(source_path)

    assert all(set(row) == CANDIDATE_FIELDS for row in rows)
    assert set(manifest) == MANIFEST_FIELDS
    assert manifest["schema_version"] == "router-v2-source-snapshot-manifest-v1"
    assert manifest["artifact_version"] == 1
    assert manifest["policy_id"] == "router-v2-reviewed-source-policy-v1"
    assert manifest["runtime"] == {
        "python_version": platform.python_version(),
        "unicode_data_version": unicodedata.unidata_version,
    }
    assert manifest["non_actions"] == EXPECTED_NON_ACTIONS
    assert manifest["duplicate_policy"] == {
        "algorithm_id": "ascii-nfkc-casefold-char5-jaccard-v1",
        "threshold": 0.85,
    }
    assert manifest["ordering"] == {
        "split_order": ["train", "calibration", "non_blind_test"],
        "source_role_order": [
            "POSITIVE",
            "HARD_NEGATIVE_CANDIDATE",
            "NO_SKILL_CANDIDATE",
        ],
        "sort_keys": [
            "split",
            "prompt_family_id",
            "source_role",
            "source_record_id",
        ],
    }

    with queue_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        queue_rows = list(reader)
        assert reader.fieldnames == list(QUEUE_FIELDS)
    assert len(queue_rows) == 192
    assert all(
        row["decision"] == row["reviewer"] == row["reason"] == "" for row in queue_rows
    )

    record_manifest = {row["source_record_id"]: row for row in manifest["records"]}
    for row, raw_line in zip(rows, source_lines, strict=True):
        record = record_manifest[row["source_record_id"]]
        assert record["source_record_exact_bytes_sha256"] == _sha256(raw_line)
        assert row["prompt_text_sha256"] == _sha256(row["query_text"].encode("utf-8"))
    assert manifest["outputs"]["source_candidates"]["sha256"] == _sha256(
        source_path.read_bytes()
    )
    assert manifest["outputs"]["review_queue"]["sha256"] == _sha256(
        queue_path.read_bytes()
    )


def test_manifest_and_queue_provenance_are_independently_recomputed(tmp_path):
    target = _build(tmp_path)
    draft_bytes = (target / "source-draft.jsonl").read_bytes()
    draft_lines = draft_bytes.splitlines(keepends=True)
    drafts = [json.loads(line) for line in draft_lines]
    draft_by_id = {row["draft_id"]: row for row in drafts}
    draft_line_by_id = {
        row["draft_id"]: raw_line
        for row, raw_line in zip(drafts, draft_lines, strict=True)
    }
    skill_bytes = CANONICAL_INDEX.read_bytes()
    skills = {row["id"]: row for row in json.loads(skill_bytes)}

    source_path = target / "source-candidates.jsonl"
    source_bytes = source_path.read_bytes()
    source_lines = source_bytes.splitlines(keepends=True)
    rows = [json.loads(line) for line in source_lines]
    queue_path = target / "review-queue.csv"
    queue_bytes = queue_path.read_bytes()
    manifest_path = target / "source-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)

    assert source_bytes == b"".join(_json_bytes(row) for row in rows)
    assert manifest_bytes == _json_bytes(manifest)
    assert set(manifest["runtime"]) == {"python_version", "unicode_data_version"}
    assert set(manifest["inputs"]) == {"skill_index", "source_draft"}
    assert set(manifest["outputs"]) == {"source_candidates", "review_queue"}
    assert all(
        set(value) == FILE_RECORD_FIELDS for value in manifest["inputs"].values()
    )
    assert all(
        set(value) == FILE_RECORD_FIELDS for value in manifest["outputs"].values()
    )
    assert set(manifest["counts"]) == set(EXPECTED_COUNTS)
    assert set(manifest["skill_distribution"]) == {
        "train_positive_by_skill",
        "calibration_positive_by_skill",
        "non_blind_test_positive_by_skill",
        "hard_negative_owner_by_skill",
        "hard_negative_target_by_skill",
    }
    assert len(manifest["records"]) == 192
    assert all(set(record) == MANIFEST_RECORD_FIELDS for record in manifest["records"])

    assert manifest["inputs"] == {
        "skill_index": {
            "path": "docs/demo/phase9-real-skill-library-migration/skills.json",
            "sha256": _sha256(skill_bytes),
            "byte_size": len(skill_bytes),
            "row_count": 16,
        },
        "source_draft": {
            "path": "data/router-v2-v4/source-draft.jsonl",
            "sha256": _sha256(draft_bytes),
            "byte_size": len(draft_bytes),
            "row_count": 128,
        },
    }
    assert manifest["outputs"] == {
        "source_candidates": {
            "path": "data/router-v2-v4/source-candidates.jsonl",
            "sha256": _sha256(source_bytes),
            "byte_size": len(source_bytes),
            "row_count": 192,
        },
        "review_queue": {
            "path": "data/router-v2-v4/review-queue.csv",
            "sha256": _sha256(queue_bytes),
            "byte_size": len(queue_bytes),
            "row_count": 192,
        },
    }
    snapshot_payload = (
        skill_bytes
        + b"\0"
        + draft_bytes
        + b"\0"
        + b"router-v2-reviewed-source-policy-v1"
    )
    assert manifest["snapshot_id"] == (
        f"router-v2-v4-source-{_sha256(snapshot_payload)[:16]}"
    )

    records = {record["source_record_id"]: record for record in manifest["records"]}
    expected_sort = {"train": 0, "calibration": 1, "non_blind_test": 2}
    expected_role = {
        "POSITIVE": 0,
        "HARD_NEGATIVE_CANDIDATE": 1,
        "NO_SKILL_CANDIDATE": 2,
    }
    assert rows == sorted(
        rows,
        key=lambda row: (
            expected_sort[row["split"]],
            row["prompt_family_id"],
            expected_role[row["source_role"]],
            row["source_record_id"],
        ),
    )
    for row, raw_line in zip(rows, source_lines, strict=True):
        draft = draft_by_id[row["draft_id"]]
        if row["source_role"] == "POSITIVE":
            expected_id = f"{row['draft_id']}:positive:{row['skill_id']}"
        elif row["source_role"] == "HARD_NEGATIVE_CANDIDATE":
            expected_id = f"{row['draft_id']}:hard-negative-candidate:{row['skill_id']}"
        else:
            expected_id = f"{row['draft_id']}:no-skill"
        assert row["source_record_id"] == expected_id
        assert row["task_id"] == row["draft_id"]
        assert row["query_text"] == draft["prompt_text"]
        assert row["positive_skill_id"] == draft["positive_skill_id"]
        assert row["schema_version"] == "router-v2-reviewed-source-record-v1"
        assert row["artifact_version"] == 1
        assert row["policy_id"] == "router-v2-reviewed-source-policy-v1"
        assert row["source_kind"] == "ROUTER_V2_V4_AUTHORED_DRAFT"
        assert row["source_artifact_path"] == "data/router-v2-v4/source-draft.jsonl"
        assert row["query_text_policy"] == "prompt_only"
        assert row["source_draft_line_sha256"] == _sha256(
            draft_line_by_id[row["draft_id"]]
        )
        expected_skill_hash = (
            _sha256(
                json.dumps(
                    skills[row["skill_id"]],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if row["skill_id"] is not None
            else None
        )
        assert row["skill_record_sha256"] == expected_skill_hash
        record = records[row["source_record_id"]]
        assert record == {
            "source_record_id": row["source_record_id"],
            "draft_id": row["draft_id"],
            "draft_line_sha256": _sha256(draft_line_by_id[row["draft_id"]]),
            "source_record_exact_bytes_sha256": _sha256(raw_line),
            "prompt_text_sha256": row["prompt_text_sha256"],
            "prompt_family_id": row["prompt_family_id"],
            "split": row["split"],
            "source_role": row["source_role"],
            "positive_skill_id": row["positive_skill_id"],
            "skill_id": row["skill_id"],
        }

    with queue_path.open(encoding="utf-8", newline="") as handle:
        queue_rows = list(csv.DictReader(handle))
    expected_queue_rows = []
    for row, raw_line in zip(rows, source_lines, strict=True):
        positive = skills.get(row["positive_skill_id"])
        candidate = skills.get(row["skill_id"])
        expected_queue_rows.append(
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
                "status": "PENDING_REVIEW",
                "decision": "",
                "reviewer": "",
                "reason": "",
            }
        )
    assert queue_rows == expected_queue_rows
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=QUEUE_FIELDS,
        dialect="excel",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(expected_queue_rows)
    assert queue_bytes == output.getvalue().encode("utf-8")


def test_two_isolated_builds_are_byte_identical(tmp_path):
    left = _build(tmp_path, "left")
    right = _build(tmp_path, "right")
    for name in ("source-candidates.jsonl", "review-queue.csv", "source-manifest.json"):
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_canonical_generated_artifacts_match_fresh_isolated_build(tmp_path):
    regenerated = _build(tmp_path)
    canonical = ROOT / "data/router-v2-v4"
    for name in ("source-candidates.jsonl", "review-queue.csv"):
        assert (canonical / name).read_bytes() == (regenerated / name).read_bytes()

    canonical_manifest_bytes = (canonical / "source-manifest.json").read_bytes()
    canonical_manifest = json.loads(canonical_manifest_bytes)
    regenerated_manifest = json.loads(
        (regenerated / "source-manifest.json").read_text(encoding="utf-8")
    )
    assert canonical_manifest["runtime"] == {
        "python_version": "3.12.2",
        "unicode_data_version": "15.0.0",
    }
    regenerated_manifest["runtime"] = canonical_manifest["runtime"]
    assert _json_bytes(regenerated_manifest) == canonical_manifest_bytes


def test_runtime_diagnostics_do_not_change_source_or_queue_bytes(tmp_path, monkeypatch):
    baseline = _build(tmp_path, "baseline-runtime")
    monkeypatch.setattr(reviewed_source.platform, "python_version", lambda: "9.9.9")
    monkeypatch.setattr(reviewed_source.unicodedata, "unidata_version", "99.0.0")
    alternate = _build(tmp_path, "alternate-runtime")

    for name in ("source-candidates.jsonl", "review-queue.csv"):
        assert (baseline / name).read_bytes() == (alternate / name).read_bytes()
    baseline_manifest = json.loads(
        (baseline / "source-manifest.json").read_text(encoding="utf-8")
    )
    alternate_manifest = json.loads(
        (alternate / "source-manifest.json").read_text(encoding="utf-8")
    )
    assert alternate_manifest["runtime"] == {
        "python_version": "9.9.9",
        "unicode_data_version": "99.0.0",
    }
    alternate_manifest["runtime"] = baseline_manifest["runtime"]
    assert alternate_manifest == baseline_manifest


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unknown-field", "unknown"),
        ("duplicate-draft-id", "draft_id"),
        ("duplicate-family", "prompt_family_id"),
        ("duplicate-prompt", "duplicate"),
        ("near-duplicate-prompt", "near-duplicate"),
        ("cross-category-negative", "category"),
        ("lone-surrogate", "Unicode"),
        ("prefilled-decision", "unknown"),
    ],
)
def test_invalid_drafts_fail_before_snapshot_publication(
    tmp_path, mutation: str, message: str
):
    target = _fresh_snapshot_dir(tmp_path)
    rows = _load_jsonl(target / "source-draft.jsonl")
    if mutation == "unknown-field":
        rows[0]["extra"] = "forbidden"
    elif mutation == "duplicate-draft-id":
        rows[1]["draft_id"] = rows[0]["draft_id"]
    elif mutation == "duplicate-family":
        rows[1]["prompt_family_id"] = rows[0]["prompt_family_id"]
    elif mutation == "duplicate-prompt":
        rows[1]["prompt_text"] = rows[0]["prompt_text"]
    elif mutation == "near-duplicate-prompt":
        rows[1]["prompt_text"] = f"{rows[0]['prompt_text']} now"
    elif mutation == "cross-category-negative":
        rows[0]["hard_negative_skill_id"] = "systematic-debugging"
    elif mutation == "lone-surrogate":
        rows[0]["prompt_text"] = "Invalid surrogate " + chr(0xD800) + " prompt"
    elif mutation == "prefilled-decision":
        rows[0]["decision"] = "ACCEPT_POSITIVE"
    if mutation == "lone-surrogate":
        escaped = b"".join(
            (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode(
                "utf-8"
            )
            for row in rows
        )
        (target / "source-draft.jsonl").write_bytes(escaped)
    else:
        _write_jsonl(target / "source-draft.jsonl", rows)

    with pytest.raises(ValueError, match=message):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=CANONICAL_INDEX,
            output_dir=target,
            repository_root=ROOT,
        )
    assert sorted(path.name for path in target.iterdir()) == ["source-draft.jsonl"]


def test_existing_generated_or_unexpected_target_is_rejected(tmp_path):
    for name in ("source-candidates.jsonl", "unexpected.txt"):
        target = _fresh_snapshot_dir(tmp_path, name.replace(".", "-"))
        (target / name).write_text("stale", encoding="utf-8")
        with pytest.raises(ValueError, match="only source-draft.jsonl"):
            build_router_v2_reviewed_source_snapshot(
                draft_path=target / "source-draft.jsonl",
                skills_index_path=CANONICAL_INDEX,
                output_dir=target,
                repository_root=ROOT,
            )
        assert (target / name).read_text(encoding="utf-8") == "stale"


def test_publish_failure_rolls_back_every_generated_target(tmp_path, monkeypatch):
    target = _fresh_snapshot_dir(tmp_path)
    original_link = reviewed_source.os.link
    calls = 0

    def fail_second_link(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected publication failure")
        return original_link(source, destination)

    monkeypatch.setattr(reviewed_source.os, "link", fail_second_link)
    with pytest.raises(OSError, match="injected publication failure"):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=CANONICAL_INDEX,
            output_dir=target,
            repository_root=ROOT,
        )
    assert sorted(path.name for path in target.iterdir()) == ["source-draft.jsonl"]
    assert list(target.parent.glob(".router-v2-v4-stage-*")) == []


def test_concurrent_generated_target_is_never_overwritten(tmp_path, monkeypatch):
    target = _fresh_snapshot_dir(tmp_path)
    original_link = reviewed_source.os.link
    sentinel = b"concurrent-owner\n"
    injected = False

    def inject_existing_target(source, destination):
        nonlocal injected
        destination = Path(destination)
        if not injected:
            injected = True
            destination.write_bytes(sentinel)
        return original_link(source, destination)

    monkeypatch.setattr(reviewed_source.os, "link", inject_existing_target)
    with pytest.raises(FileExistsError):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=CANONICAL_INDEX,
            output_dir=target,
            repository_root=ROOT,
        )
    generated = sorted(path.name for path in target.iterdir())
    assert generated == ["review-queue.csv", "source-draft.jsonl"]
    assert (target / "review-queue.csv").read_bytes() == sentinel


def test_source_draft_symlink_is_rejected(tmp_path):
    target = tmp_path / "snapshot"
    target.mkdir()
    (target / "source-draft.jsonl").symlink_to(CANONICAL_DRAFT)

    with pytest.raises(ValueError, match="regular non-symlink"):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=CANONICAL_INDEX,
            output_dir=target,
            repository_root=ROOT,
        )
    assert (target / "source-draft.jsonl").is_symlink()


def test_noncanonical_output_inside_repository_is_rejected(tmp_path):
    fake_repo = tmp_path / "repo"
    fake_index = fake_repo / "docs/demo/phase9-real-skill-library-migration/skills.json"
    fake_index.parent.mkdir(parents=True)
    shutil.copyfile(CANONICAL_INDEX, fake_index)
    target = fake_repo / "benchmarks/migration-tasks/alternate-snapshot"
    target.mkdir(parents=True)
    shutil.copyfile(CANONICAL_DRAFT, target / "source-draft.jsonl")

    with pytest.raises(ValueError, match="canonical data directory"):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=fake_index,
            output_dir=target,
            repository_root=fake_repo,
        )
    assert sorted(path.name for path in target.iterdir()) == ["source-draft.jsonl"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("split", []),
        ("draft_role", {}),
        ("positive_skill_id", []),
        ("hard_negative_skill_id", {}),
    ],
)
def test_malformed_draft_types_fail_as_value_error(tmp_path, field, value):
    target = _fresh_snapshot_dir(tmp_path)
    rows = _load_jsonl(target / "source-draft.jsonl")
    rows[0][field] = value
    _write_jsonl(target / "source-draft.jsonl", rows)

    with pytest.raises(ValueError, match=field):
        build_router_v2_reviewed_source_snapshot(
            draft_path=target / "source-draft.jsonl",
            skills_index_path=CANONICAL_INDEX,
            output_dir=target,
            repository_root=ROOT,
        )


def test_source_module_has_no_training_or_model_import_graph():
    spec = importlib.util.find_spec("hermes_skilleval.router_v2_reviewed_source")
    assert spec is not None and spec.origin is not None
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots <= {
        "__future__",
        "argparse",
        "collections",
        "csv",
        "hashlib",
        "io",
        "json",
        "os",
        "pathlib",
        "platform",
        "re",
        "shutil",
        "tempfile",
        "typing",
        "unicodedata",
    }


def test_new_draft_does_not_exactly_reuse_public_or_protected_prompt_strings():
    draft_hashes = {
        _sha256(row["prompt_text"].encode("utf-8")): row["draft_id"]
        for row in _load_jsonl(CANONICAL_DRAFT)
    }
    collisions: list[tuple[str, str]] = []
    for root in ("benchmarks/migration-tasks", "benchmarks/blind-migration-tasks"):
        for path in sorted((ROOT / root).glob("*/prompt.md")):
            payload = path.read_text(encoding="utf-8").strip().encode("utf-8")
            digest = _sha256(payload)
            if digest in draft_hashes:
                collisions.append(
                    (path.relative_to(ROOT).as_posix(), draft_hashes[digest])
                )

    protected_json_roots = (
        "docs/demo/phase14-finetuned-embedding-router",
        "docs/demo/phase15-held-out-generalization",
        "docs/demo/phase16-blind-validation",
        "docs/demo/phase17-calibrated-release-selector",
        "docs/demo/phase18-ci-release-reproducibility",
        "docs/demo/router-training-data-v2-qualification-pack",
    )
    prompt_fields = {"query_text", "prompt", "prompt_text", "task_prompt"}

    def prompt_values(value: Any) -> Iterator[str]:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in prompt_fields and isinstance(item, str):
                    yield item
                yield from prompt_values(item)
        elif isinstance(value, list):
            for item in value:
                yield from prompt_values(item)

    for root in protected_json_roots:
        paths = sorted((ROOT / root).rglob("*.json"))
        paths += sorted((ROOT / root).rglob("*.jsonl"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            values = (
                [json.loads(line) for line in text.splitlines() if line.strip()]
                if path.suffix == ".jsonl"
                else [json.loads(text)]
            )
            for parsed in values:
                for value in prompt_values(parsed):
                    digest = _sha256(value.encode("utf-8"))
                    if digest in draft_hashes:
                        collisions.append(
                            (path.relative_to(ROOT).as_posix(), draft_hashes[digest])
                        )
    assert collisions == []


def _skills() -> list[dict[str, Any]]:
    return json.loads(CANONICAL_INDEX.read_text(encoding="utf-8"))


def _skill_ids() -> set[str]:
    return {skill["id"] for skill in _skills()}
