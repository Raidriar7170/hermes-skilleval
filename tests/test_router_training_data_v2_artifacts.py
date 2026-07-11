from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from hermes_skilleval.router_training_data_v2 import (
    BLOCKER_CODES,
    qualify_router_training_data_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/demo/router-training-data-v2-qualification-pack"
TASKS = ROOT / "benchmarks/migration-tasks"
SKILLS = ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"

EXPECTED_COUNTS = {
    "accepted_train_pair_count": 0,
    "cross_category_easy_negative_count": 144,
    "matrix_candidate_count": 192,
    "positive_count": 16,
    "reject_example_count": 0,
    "reserved_matrix_row_count": 64,
    "reserved_positive_or_same_category_count": 16,
    "same_category_negative_candidate_count": 32,
    "source_pair_count": 28,
    "target_skill_count": 16,
    "task_count": 12,
    "train_policy_candidate_count": 32,
    "train_positive_skill_coverage_count": 11,
}
ROW_FIELDS = {
    "accepted_for_training",
    "candidate_type",
    "disposition",
    "label",
    "pair_id",
    "prompt_text_sha256",
    "query_text",
    "schema_version",
    "skill_id",
    "skill_text",
    "source",
    "source_split",
    "task_id",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path = PACK / "candidate-pairs.jsonl") -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_committed_pack_parses_and_preserves_exact_blocked_contract():
    rows = _rows()
    report = json.loads(
        (PACK / "qualification-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))

    assert len(rows) == 192
    assert all(set(row) == ROW_FIELDS for row in rows)
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v1"
    }
    assert [row["pair_id"] for row in rows] == sorted(row["pair_id"] for row in rows)
    assert len({row["pair_id"] for row in rows}) == 192
    assert Counter(row["candidate_type"] for row in rows) == {
        "positive": 16,
        "same_category_negative_candidate": 32,
        "cross_category_easy_negative": 144,
    }
    assert sum(row["disposition"] == "RESERVED_SOURCE_TEST" for row in rows) == 64
    assert all(row["accepted_for_training"] is False for row in rows)
    assert all(
        row["disposition"] == "RESERVED_SOURCE_TEST"
        for row in rows
        if row["source_split"] == "test"
    )

    assert report["schema_version"] == (
        "router-training-data-v2-qualification-report-v1"
    )
    assert report["policy_id"] == "router-training-data-v2-qualification-v1"
    assert report["qualification_status"] == "REVIEW_REQUIRED"
    assert report["router_decision"] == "KEEP_BASELINE"
    assert report["can_start_training"] is False
    assert report["blocker_codes"] == BLOCKER_CODES
    assert report["counts"] == EXPECTED_COUNTS
    assert manifest["schema_version"] == "router-training-data-v2-manifest-v1"
    assert manifest["policy_id"] == "router-training-data-v2-qualification-v1"
    assert manifest["counts"] == EXPECTED_COUNTS
    assert not (PACK / "training-pairs.jsonl").exists()


def test_manifest_binds_every_repository_relative_input_and_output_hash():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    input_records = manifest["inputs"]["files"]

    assert len(input_records) == 25
    assert [record["path"] for record in input_records] == sorted(
        record["path"] for record in input_records
    )
    assert all(not Path(record["path"]).is_absolute() for record in input_records)
    for record in input_records:
        assert _sha256(ROOT / record["path"]) == record["sha256"]

    assert manifest["inputs"]["task_root"] == "benchmarks/migration-tasks"
    assert manifest["inputs"]["skills_index"] == {
        "path": "docs/demo/phase9-real-skill-library-migration/skills.json",
        "sha256": _sha256(SKILLS),
    }
    assert [record["path"] for record in manifest["outputs"]] == [
        "candidate-pairs.jsonl",
        "qualification-report.json",
    ]
    for record in manifest["outputs"]:
        output = PACK / record["path"]
        assert len(output.read_bytes()) == record["bytes"]
        assert _sha256(output) == record["sha256"]

    machine_text = "\n".join(
        (PACK / name).read_text(encoding="utf-8")
        for name in (
            "candidate-pairs.jsonl",
            "qualification-report.json",
            "manifest.json",
        )
    )
    assert str(ROOT) not in machine_text
    assert "blind-migration-tasks" not in machine_text


def test_committed_pack_regenerates_byte_identically_into_fresh_target(tmp_path: Path):
    regenerated = tmp_path / "fresh-pack"
    qualify_router_training_data_v2(
        tasks_path=TASKS,
        skills_index_path=SKILLS,
        output_dir=regenerated,
        repository_root=ROOT,
    )

    for name in (
        "candidate-pairs.jsonl",
        "qualification-report.json",
        "manifest.json",
    ):
        assert (regenerated / name).read_bytes() == (PACK / name).read_bytes()
    assert not (regenerated / "training-pairs.jsonl").exists()


def test_readme_regeneration_and_truth_boundaries_match_artifacts():
    readme = (PACK / "README.md").read_text(encoding="utf-8")

    for truth in (
        "`REVIEW_REQUIRED`",
        "`KEEP_BASELINE`",
        "`can_start_training=false`",
        "Accepted training pairs: 0",
        "Train-positive target-skill coverage: 11/16",
        *[f"`{code}`" for code in BLOCKER_CODES],
    ):
        assert truth in readme
    for boundary in (
        "did not train",
        "blind prompt",
        "A100/GPU",
        "checkpoint",
        "benchmark improvement",
        "merge",
        "release",
        "archive",
    ):
        assert boundary in readme

    assert 'TMP_ROOT="$(mktemp -d' in readme
    assert 'OUT="$TMP_ROOT/pack"' in readme
    assert "qualify-router-training-data-v2" in readme
    assert 'cmp "docs/demo/router-training-data-v2-qualification-pack/$name"' in readme
    assert "candidate-pairs.jsonl qualification-report.json manifest.json" in readme
    assert '--output-dir "$OUT"' in readme
    assert (
        "--output-dir docs/demo/router-training-data-v2-qualification-pack"
        not in readme
    )
    assert "training-pairs.jsonl" in readme

    assert _sha256(PACK / "candidate-pairs.jsonl") in readme
    assert _sha256(PACK / "qualification-report.json") in readme
    assert _sha256(PACK / "manifest.json") in readme
