from __future__ import annotations

import hashlib
import errno
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_internal_package as package_module
from hermes_skilleval.router_v2_internal_package import (
    CANONICAL_OUTPUT_PATH,
    REVIEW_FREEZE_GIT_COMMIT,
    build_internal_package,
    canonical_sha256,
    validate_internal_package,
    with_row_sha256,
)


ROOT = Path(__file__).parents[1]
TEST_CODE_COMMIT = "b" * 40
BASE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001"
)
FIXED_PATHS = [
    Path("data/router-v2-v4/source-manifest.json"),
    Path("data/router-v2-v4/source-candidates.jsonl"),
    Path("docs/demo/phase9-real-skill-library-migration/skills.json"),
    BASE / "mining/mining.jsonl",
    BASE / "mining/mining-manifest.json",
    BASE / "mining/prior-review-filter.json",
    BASE / "candidates/round-1/candidates.jsonl",
    BASE / "candidates/round-1/candidate-manifest.json",
    BASE / "review/review-rubric.json",
    BASE / "review/round-1/pass-1.model-opinions.jsonl",
    BASE / "review/round-1/pass-2.model-opinions.jsonl",
    BASE / "review/round-1/adjudication.decisions.jsonl",
    BASE / "review/round-1/adjudication.model-opinions.jsonl",
]

ACCEPTED_ROW_FIELDS = {
    "schema_version",
    "example_id",
    "query_text",
    "query_sha256",
    "positive_source_record_id",
    "positive_source_record_exact_bytes_sha256",
    "gold_skill_id",
    "skill_id",
    "skill_text",
    "skill_text_sha256",
    "skill_record_sha256",
    "label",
    "role",
    "evidence_source",
    "hard_negative_id",
    "hard_negative_sha256",
    "candidate_rank",
    "score_margin",
    "mining_row_sha256",
    "review_binding_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "model_id",
    "model_revision",
    "model_file_manifest_sha256",
    "row_sha256",
}

HELDOUT_ROW_FIELDS = {
    "schema_version",
    "candidate_id",
    "candidate_sha256",
    "task_id",
    "query_text",
    "query_sha256",
    "positive_source_record_id",
    "positive_source_record_exact_bytes_sha256",
    "gold_skill_id",
    "gold_skill_record_sha256",
    "candidate_skill_id",
    "candidate_skill_text",
    "candidate_skill_text_sha256",
    "candidate_skill_record_sha256",
    "usage",
    "training_eligible",
    "mining_eligible",
    "adjudication_row_sha256",
    "pass_1_row_sha256",
    "pass_2_row_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "row_sha256",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _load_output(
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return (
        _load_jsonl(output_dir / "accepted-pairs.jsonl"),
        _load_jsonl(output_dir / "heldout-labels.jsonl"),
        json.loads((output_dir / "data-manifest.json").read_text()),
    )


def _copy_frozen_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in FIXED_PATHS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _build(root: Path) -> tuple[dict[str, Any], Path]:
    manifest = package_module._build_internal_package_for_test(
        repository_root=root, code_git_commit=TEST_CODE_COMMIT
    )
    return manifest, root / CANONICAL_OUTPUT_PATH


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        )
    )


def test_actual_fixture_builds_exact_deterministic_package(tmp_path: Path) -> None:
    first_root = _copy_frozen_repo(tmp_path / "first")
    second_root = _copy_frozen_repo(tmp_path / "second")

    first, first_dir = _build(first_root)
    second, second_dir = _build(second_root)

    assert first == second
    assert {path.name for path in first_dir.iterdir()} == {
        "accepted-pairs.jsonl",
        "heldout-labels.jsonl",
        "data-manifest.json",
    }
    assert all(
        (first_dir / name).read_bytes() == (second_dir / name).read_bytes()
        for name in (
            "accepted-pairs.jsonl",
            "heldout-labels.jsonl",
            "data-manifest.json",
        )
    )
    accepted, heldout, manifest = _load_output(first_dir)
    positives = [row for row in accepted if row["role"] == "POSITIVE"]
    negatives = [row for row in accepted if row["role"] == "HARD_NEGATIVE"]
    assert (len(accepted), len(positives), len(negatives), len(heldout)) == (
        116,
        64,
        52,
        9,
    )
    assert accepted == [*positives, *negatives]
    assert all(set(row) == ACCEPTED_ROW_FIELDS for row in accepted)
    assert all(set(row) == HELDOUT_ROW_FIELDS for row in heldout)
    assert [row["example_id"] for row in positives] == sorted(
        row["example_id"] for row in positives
    )
    assert [row["example_id"] for row in negatives] == sorted(
        row["example_id"] for row in negatives
    )
    assert {(row["label"], row["role"]) for row in positives} == {(1, "POSITIVE")}
    assert {(row["label"], row["role"]) for row in negatives} == {(0, "HARD_NEGATIVE")}
    assert manifest["counts"] == {
        "accepted_pair_count": 116,
        "positive_count": 64,
        "hard_negative_count": 52,
        "prior_retained_hard_negative_count": 21,
        "round_1_supported_hard_negative_count": 31,
        "heldout_supported_count": 9,
        "supplement_count": 0,
    }
    assert manifest["hard_negative_gold_skill_coverage_count"] == 15
    assert manifest["hard_negative_gold_skill_coverage_maximized"] is True
    assert (
        manifest["valid_hard_negative_gold_skill_coverage"]
        == manifest["hard_negative_gold_skill_coverage"]
    )
    assert "apply-patch-discipline" not in manifest["hard_negative_gold_skill_coverage"]
    assert manifest["review_freeze_git_commit"] == REVIEW_FREEZE_GIT_COMMIT
    assert manifest["code_git_commit"] == TEST_CODE_COMMIT
    assert (
        validate_internal_package(first_root, code_git_commit=TEST_CODE_COMMIT)
        == manifest
    )


def test_package_excludes_disputed_easy_heldout_and_non_train_sources(
    tmp_path: Path,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    _, output_dir = _build(root)
    accepted, heldout, manifest = _load_output(output_dir)
    negatives = [row for row in accepted if row["role"] == "HARD_NEGATIVE"]
    prior = json.loads((ROOT / BASE / "mining/prior-review-filter.json").read_text())
    source_rows = _load_jsonl(ROOT / "data/router-v2-v4/source-candidates.jsonl")
    candidates = {
        row["candidate_id"]: row
        for row in _load_jsonl(ROOT / BASE / "candidates/round-1/candidates.jsonl")
    }
    adjudications = _load_jsonl(
        ROOT / BASE / "review/round-1/adjudication.model-opinions.jsonl"
    )
    old_all = {
        row["source_record_id"]
        for row in source_rows
        if row["split"] == "train" and row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
    }
    retained = set(prior["retained_source_record_ids"])
    disputed_old = set(prior["excluded_disputed_source_record_ids"])
    easy_old = old_all - retained - disputed_old
    disputed_new = {
        row["candidate_id"]
        for row in adjudications
        if row["usage"] == "TRAIN_HARD_NEGATIVE_CANDIDATE"
        and row["adjudicated_model_opinion"] != "HARD_NEGATIVE_ROLE_SUPPORTED"
    }
    heldout_ids = {row["candidate_id"] for row in heldout}
    negative_ids = {row["hard_negative_id"] for row in negatives}

    assert (len(disputed_old), len(easy_old), len(disputed_new)) == (29, 14, 12)
    assert retained <= negative_ids
    assert negative_ids.isdisjoint(disputed_old | easy_old | disputed_new | heldout_ids)
    assert len({row["example_id"] for row in negatives}) == 52
    assert all(
        candidates[row["hard_negative_id"]]["usage"] == "TRAIN_HARD_NEGATIVE_CANDIDATE"
        for row in negatives
        if row["evidence_source"] == "ROUND_1_ADJUDICATED_SUPPORTED"
    )
    assert set(manifest["training_exclusions"]) == {
        "calibration",
        "test",
        "non_blind_test",
        "no_skill",
        "disputed",
        "ambiguous",
        "unsupported",
        "easy_negative",
    }


def test_rows_bind_exact_skill_text_source_model_and_review_evidence(
    tmp_path: Path,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    _, output_dir = _build(root)
    accepted, heldout, manifest = _load_output(output_dir)
    skills = {
        row["id"]: row
        for row in json.loads(
            (
                ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
            ).read_text()
        )
    }
    candidates = {
        row["candidate_id"]: row
        for row in _load_jsonl(ROOT / BASE / "candidates/round-1/candidates.jsonl")
    }
    adjudications = {
        row["candidate_id"]: row
        for row in _load_jsonl(
            ROOT / BASE / "review/round-1/adjudication.model-opinions.jsonl"
        )
    }

    for row in accepted:
        skill = skills[row["skill_id"]]
        expected_text = " ".join(
            [
                skill["id"].replace("-", " "),
                skill["name"],
                skill["category"],
                skill["description"],
                " ".join(skill["trigger_terms"]),
                skill["body"],
            ]
        )
        assert row["skill_text"] == expected_text
        assert row["skill_text_sha256"] == canonical_sha256(expected_text)
        assert row["skill_record_sha256"] == canonical_sha256(skill)
        assert row == with_row_sha256(
            {k: v for k, v in row.items() if k != "row_sha256"}
        )
        if row["evidence_source"] == "ROUND_1_ADJUDICATED_SUPPORTED":
            candidate = candidates[row["hard_negative_id"]]
            review = adjudications[row["hard_negative_id"]]
            assert row["candidate_rank"] == candidate["candidate_rank"]
            assert row["score_margin"] == candidate["score_margin"]
            assert row["mining_row_sha256"] == candidate["mining_row_sha256"]
            assert row["review_binding_sha256"] == review["row_sha256"]
    for row in heldout:
        review = adjudications[row["candidate_id"]]
        assert row["usage"] == "HELD_OUT_EVAL_ONLY"
        assert row["training_eligible"] is False
        assert row["mining_eligible"] is False
        assert row["adjudication_row_sha256"] == review["row_sha256"]
        assert row["pass_1_row_sha256"] == review["pass_1_row_sha256"]
        assert row["pass_2_row_sha256"] == review["pass_2_row_sha256"]
    assert manifest["input_artifact_sha256"] == package_module.FIXED_INPUT_SHA256


def test_validator_rejects_truth_inflation_candidate_drift_and_heldout_leakage(
    tmp_path: Path,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    _, output_dir = _build(root)
    accepted, heldout, manifest = _load_output(output_dir)

    inflated = deepcopy(manifest)
    inflated["release_eligible"] = True
    (output_dir / "data-manifest.json").write_text(
        json.dumps(inflated, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(ValueError, match="truth field release_eligible mismatch"):
        validate_internal_package(root, code_git_commit=TEST_CODE_COMMIT)

    fresh_root = _copy_frozen_repo(tmp_path / "fresh")
    _, output_dir = _build(fresh_root)
    accepted, heldout, manifest = _load_output(output_dir)
    hard_negative = next(row for row in accepted if row["role"] == "HARD_NEGATIVE")
    hard_negative["score_margin"] = "0.00000000"
    resigned = with_row_sha256(
        {k: v for k, v in hard_negative.items() if k != "row_sha256"}
    )
    accepted[accepted.index(hard_negative)] = resigned
    _write_jsonl(output_dir / "accepted-pairs.jsonl", accepted)
    manifest["accepted_pairs_jsonl_sha256"] = hashlib.sha256(
        (output_dir / "accepted-pairs.jsonl").read_bytes()
    ).hexdigest()
    manifest["accepted_rows_sha256"] = canonical_sha256(accepted)
    (output_dir / "data-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(ValueError, match="rank or margin evidence mismatch"):
        validate_internal_package(fresh_root, code_git_commit=TEST_CODE_COMMIT)

    leak_root = _copy_frozen_repo(tmp_path / "leak")
    _, leak_dir = _build(leak_root)
    accepted, heldout, manifest = _load_output(leak_dir)
    accepted[-1]["hard_negative_id"] = heldout[0]["candidate_id"]
    accepted[-1] = with_row_sha256(
        {k: v for k, v in accepted[-1].items() if k != "row_sha256"}
    )
    _write_jsonl(leak_dir / "accepted-pairs.jsonl", accepted)
    manifest["accepted_pairs_jsonl_sha256"] = hashlib.sha256(
        (leak_dir / "accepted-pairs.jsonl").read_bytes()
    ).hexdigest()
    manifest["accepted_rows_sha256"] = canonical_sha256(accepted)
    (leak_dir / "data-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(
        ValueError, match="heldout candidate leaked into accepted pairs"
    ):
        validate_internal_package(leak_root, code_git_commit=TEST_CODE_COMMIT)


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        (BASE / "candidates/round-1/candidates.jsonl", "candidates SHA-256 mismatch"),
        (
            BASE / "review/round-1/adjudication.decisions.jsonl",
            "adjudication decisions SHA-256 mismatch",
        ),
    ],
)
def test_pinned_input_drift_fails_before_output_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: Path,
    expected: str,
) -> None:
    root = _copy_frozen_repo(tmp_path)
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n")
    output_dir = root / CANONICAL_OUTPUT_PATH

    with pytest.raises(ValueError, match=expected):
        package_module._build_internal_package_for_test(
            repository_root=root, code_git_commit=TEST_CODE_COMMIT
        )

    assert not output_dir.exists()


def test_dirty_repository_write_failure_and_concurrent_publish_are_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dirty_root = _copy_frozen_repo(tmp_path / "dirty")
    monkeypatch.setattr(package_module, "_git_head", lambda _: TEST_CODE_COMMIT)
    for status in (" M tracked.py\n", "?? untracked.py\n"):
        monkeypatch.setattr(package_module, "_git_status_porcelain", lambda _: status)
        with pytest.raises(ValueError, match="repository must be completely clean"):
            build_internal_package(dirty_root)
        assert not (dirty_root / CANONICAL_OUTPUT_PATH).exists()

    write_root = _copy_frozen_repo(tmp_path / "write")
    output_dir = write_root / CANONICAL_OUTPUT_PATH
    real_write = package_module._write_file
    calls = 0

    def fail_second(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-file failure")
        real_write(path, payload)

    monkeypatch.setattr(package_module, "_write_file", fail_second)
    with pytest.raises(OSError, match="injected second-file failure"):
        package_module._build_internal_package_for_test(
            repository_root=write_root, code_git_commit=TEST_CODE_COMMIT
        )

    assert not output_dir.exists()
    assert not list(output_dir.parent.glob(f".{output_dir.name}.staging-*"))

    publish_root = _copy_frozen_repo(tmp_path / "publish")
    output_dir = publish_root / CANONICAL_OUTPUT_PATH

    def create_concurrent_target(path: Path) -> None:
        path.mkdir()

    monkeypatch.setattr(package_module, "_write_file", real_write)
    monkeypatch.setattr(package_module, "_before_publish", create_concurrent_target)
    with pytest.raises(FileExistsError):
        package_module._build_internal_package_for_test(
            repository_root=publish_root, code_git_commit=TEST_CODE_COMMIT
        )

    assert output_dir.is_dir() and not list(output_dir.iterdir())
    assert not list(output_dir.parent.glob(f".{output_dir.name}.staging-*"))

    primitive_root = _copy_frozen_repo(tmp_path / "primitive-error")
    output_dir = primitive_root / CANONICAL_OUTPUT_PATH

    def fail_primitive(source: Path, target: Path) -> None:
        raise OSError(errno.EIO, f"injected primitive failure: {source} -> {target}")

    monkeypatch.setattr(package_module, "_before_publish", lambda _: None)
    monkeypatch.setattr(package_module, "_atomic_publish_noreplace", fail_primitive)
    with pytest.raises(OSError, match="injected primitive failure"):
        package_module._build_internal_package_for_test(
            repository_root=primitive_root, code_git_commit=TEST_CODE_COMMIT
        )
    assert not output_dir.exists()
    assert not list(output_dir.parent.glob(f".{output_dir.name}.staging-*"))

    unsupported_root = _copy_frozen_repo(tmp_path / "unsupported")
    output_dir = unsupported_root / CANONICAL_OUTPUT_PATH
    monkeypatch.undo()
    monkeypatch.setattr(package_module.sys, "platform", "unsupported-test-platform")
    with pytest.raises(RuntimeError, match="no supported no-replace atomic publish"):
        package_module._build_internal_package_for_test(
            repository_root=unsupported_root, code_git_commit=TEST_CODE_COMMIT
        )
    assert not output_dir.exists()
    assert not list(output_dir.parent.glob(f".{output_dir.name}.staging-*"))
