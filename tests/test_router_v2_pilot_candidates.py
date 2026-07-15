from __future__ import annotations

import inspect
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_pilot_candidates as candidate_module
from hermes_skilleval.router_v2_pilot_candidates import (
    HELDOUT_USAGE,
    TRAIN_USAGE,
    build_candidate_bundle,
    canonical_sha256,
    select_heldout_candidate,
    validate_candidate_bundle,
    with_row_sha256,
)


ROOT = Path(__file__).parents[1]


def _copy_frozen_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    paths = [
        Path("data/router-v2-v4/source-manifest.json"),
        Path("data/router-v2-v4/source-candidates.jsonl"),
        Path("docs/demo/phase9-real-skill-library-migration/skills.json"),
        Path(
            "artifacts/router-v2-v4/internal-training-pilot/"
            "router-v2-v4-confusion-mined-pilot-001/mining/mining.jsonl"
        ),
        Path(
            "artifacts/router-v2-v4/internal-training-pilot/"
            "router-v2-v4-confusion-mined-pilot-001/mining/mining-manifest.json"
        ),
        Path(
            "artifacts/router-v2-v4/internal-training-pilot/"
            "router-v2-v4-confusion-mined-pilot-001/mining/prior-review-filter.json"
        ),
    ]
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _load_output(output_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in (output_dir / "candidates.jsonl").read_text().splitlines()
    ]
    manifest = json.loads((output_dir / "candidate-manifest.json").read_text())
    return rows, manifest


def test_candidate_bundle_is_deterministic_excludes_authored_and_is_score_blind(
    tmp_path: Path,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = build_candidate_bundle(repository_root=root, output_dir=first_output)
    second = build_candidate_bundle(repository_root=root, output_dir=second_output)

    assert first == second
    assert (first["train_count"], first["heldout_count"]) == (43, 16)
    assert (first_output / "candidates.jsonl").read_bytes() == (
        second_output / "candidates.jsonl"
    ).read_bytes()
    assert (first_output / "candidate-manifest.json").read_bytes() == (
        second_output / "candidate-manifest.json"
    ).read_bytes()
    rows, manifest = _load_output(first_output)
    train = [row for row in rows if row["usage"] == TRAIN_USAGE]
    heldout = [row for row in rows if row["usage"] == HELDOUT_USAGE]
    assert len(rows) == 59
    assert rows == [*train, *heldout]
    assert len(train) == 43 and len(heldout) == 16
    prior_report = json.loads(
        (
            root / "artifacts/router-v2-v4/internal-training-pilot/"
            "router-v2-v4-confusion-mined-pilot-001/mining/prior-review-filter.json"
        ).read_text()
    )
    retained_source_ids = prior_report["retained_source_record_ids"]
    retained_task_ids = {
        source_id.split(":hard-negative-candidate:", maxsplit=1)[0]
        for source_id in retained_source_ids
    }
    assert len(retained_source_ids) == len(retained_task_ids) == 21
    assert retained_task_ids.isdisjoint(row["task_id"] for row in train)
    assert len(retained_task_ids | {row["task_id"] for row in train}) == 64
    assert all(row["mining_round"] == 1 and row["baseline_hard"] for row in train)
    assert all(
        row["candidate_skill_id"] != row["authored_hard_negative_skill_id"]
        for row in train
    )
    disputed = set(manifest["excluded_disputed_source_record_ids"])
    assert all(
        f"{row['task_id']}:hard-negative-candidate:{row['candidate_skill_id']}"
        not in disputed
        for row in train
    )
    assert all(
        row["baseline_scores_read"] is False
        and row["selector_version"] == "taxonomy-lexical-v1"
        and "mining_row_sha256" not in row
        for row in heldout
    )
    assert manifest["heldout_mining_eligible"] is False
    assert manifest["heldout_training_eligible"] is False
    assert (manifest["candidate_count"], manifest["train_count"]) == (59, 43)
    assert manifest["mining_jsonl_sha256"] == (
        "29d20c95f1e280de2a24875ea3cfbf4fd5fbae8fb513d749c13da3ab2df21f88"
    )
    assert manifest["mining_manifest_sha256"] == (
        "1eba5a66f5065ae6792f43c2c8b186db2628d33a2a7c2a0d9f0e0787935e6a2d"
    )
    assert manifest["prior_review_filter_sha256"] == (
        "d8bffc89872f5795e7a366e3ff1f01de6a1a04e120e09c2ef01bb223b81025cc"
    )


def test_heldout_selector_has_no_mining_or_baseline_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_rows = [
        json.loads(line)
        for line in (ROOT / "data/router-v2-v4/source-candidates.jsonl")
        .read_text()
        .splitlines()
    ]
    source = next(
        row
        for row in source_rows
        if row["split"] == "non_blind_test" and row["source_role"] == "POSITIVE"
    )
    skills = json.loads(
        (ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json").read_text()
    )

    assert list(inspect.signature(select_heldout_candidate).parameters) == [
        "source_row",
        "skills",
    ]

    def forbidden_load(*args: object, **kwargs: object) -> object:
        raise AssertionError("heldout selector must not load mining or baseline inputs")

    monkeypatch.setattr(candidate_module, "_load_inputs", forbidden_load)
    first = select_heldout_candidate(source, skills)
    second = select_heldout_candidate(deepcopy(source), deepcopy(skills))
    assert first == second
    assert first["skill_id"] != source["positive_skill_id"]
    assert len(first["selector_top_3"]) <= 3

    def skill(skill_id: str, category: str, body: str) -> dict[str, Any]:
        return {
            "id": skill_id,
            "name": skill_id,
            "category": category,
            "description": "",
            "trigger_terms": [],
            "body": body,
        }

    lowercase_only = select_heldout_candidate(
        {"positive_skill_id": "gold", "query_text": "STRAẞE"},
        [
            skill("gold", "same", ""),
            skill("a-zero-overlap", "same", "foo"),
            skill("z-casefold-only", "same", "strasse"),
            skill("different-category", "other", "stra e"),
        ],
    )
    assert lowercase_only["skill_id"] == "a-zero-overlap"
    assert all(
        item["skill_id"] != "different-category"
        for item in lowercase_only["selector_top_3"]
    )


def test_candidate_validator_rejects_resigned_candidate_hash_drift(
    tmp_path: Path,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    output = tmp_path / "output"
    build_candidate_bundle(repository_root=root, output_dir=output)
    rows, manifest = _load_output(output)
    drifted = deepcopy(rows)
    drifted[0]["candidate_sha256"] = "f" * 64
    drifted[0] = with_row_sha256(drifted[0])

    with pytest.raises(ValueError, match="candidate SHA-256"):
        validate_candidate_bundle(
            drifted,
            manifest,
            repository_root=root,
        )

    drifted = deepcopy(rows)
    drifted[0]["candidate_skill_record_sha256"] = "e" * 64
    drifted[0] = with_row_sha256(drifted[0])
    with pytest.raises(ValueError, match="candidate SHA-256"):
        validate_candidate_bundle(
            drifted,
            manifest,
            repository_root=root,
        )


def test_candidate_build_drift_and_write_failure_have_no_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _copy_frozen_repo(tmp_path)
    mining = (
        root / "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-001/mining/mining.jsonl"
    )
    mining.write_bytes(mining.read_bytes() + b" ")
    output = tmp_path / "drift-output"
    with pytest.raises(ValueError, match="mining JSONL file SHA-256"):
        build_candidate_bundle(repository_root=root, output_dir=output)
    assert not output.exists()

    root = _copy_frozen_repo(tmp_path / "manifest-drift")
    mining_manifest = (
        root / "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-001/mining/mining-manifest.json"
    )
    manifest_value = json.loads(mining_manifest.read_text())
    manifest_value["row_count"] = 63
    mining_manifest.write_text(
        json.dumps(
            manifest_value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    output = tmp_path / "manifest-drift-output"
    with pytest.raises(ValueError, match="mining manifest file SHA-256"):
        build_candidate_bundle(repository_root=root, output_dir=output)
    assert not output.exists()

    root = _copy_frozen_repo(tmp_path / "prior-drift")
    prior_filter = (
        root / "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-001/mining/prior-review-filter.json"
    )
    prior_value = json.loads(prior_filter.read_text())
    prior_value["excluded_disputed_source_record_ids"] = prior_value[
        "excluded_disputed_source_record_ids"
    ][1:]
    prior_value["disputed_count"] = 28
    prior_value["report_sha256"] = canonical_sha256(
        {key: value for key, value in prior_value.items() if key != "report_sha256"}
    )
    prior_filter.write_text(
        json.dumps(
            prior_value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    output = tmp_path / "prior-drift-output"
    with pytest.raises(ValueError, match="prior-review filter file SHA-256"):
        build_candidate_bundle(repository_root=root, output_dir=output)
    assert not output.exists()

    root = _copy_frozen_repo(tmp_path / "clean")
    output = tmp_path / "write-output"
    original_write_bytes = Path.write_bytes
    writes = 0

    def failing_write(path: Path, payload: bytes) -> int:
        nonlocal writes
        if path.parent.name.startswith(".write-output.staging-"):
            writes += 1
            if writes == 2:
                raise OSError("candidate second-file failure")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", failing_write)
    with pytest.raises(OSError, match="second-file"):
        build_candidate_bundle(repository_root=root, output_dir=output)
    assert not output.exists()
    assert list(tmp_path.glob(".write-output.staging-*")) == []


def test_candidate_build_rejects_outside_fixed_input_before_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _copy_frozen_repo(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n")
    mining = (
        root / "artifacts/router-v2-v4/internal-training-pilot/"
        "router-v2-v4-confusion-mined-pilot-001/mining/mining.jsonl"
    )
    mining.unlink()
    mining.symlink_to(outside)
    reads: list[Path] = []
    original_read_bytes = Path.read_bytes

    def probed_read(path: Path) -> bytes:
        reads.append(path.resolve(strict=False))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", probed_read)
    with pytest.raises(ValueError, match="inside repository root"):
        build_candidate_bundle(
            repository_root=root,
            output_dir=tmp_path / "outside-output",
        )
    assert reads == []


def test_candidate_hash_and_row_hash_are_canonical(tmp_path: Path) -> None:
    root = _copy_frozen_repo(tmp_path)
    output = tmp_path / "output"
    build_candidate_bundle(repository_root=root, output_dir=output)
    rows, manifest = _load_output(output)
    assert manifest["rows_sha256"] == canonical_sha256(rows)
    assert all(with_row_sha256(row) == row for row in rows)
