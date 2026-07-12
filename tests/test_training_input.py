from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from hermes_skilleval.training_input import (
    TrainingInputError,
    _verify_training_handoff,
    load_training_input,
)
from training_input_test_support import (
    ACCEPTANCE_HASH_FIELDS,
    SOURCE_HASH_FIELDS,
    canonical_hash,
    make_accepted_row,
    rehash_row,
    write_synthetic_training_package,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_load_training_input_returns_one_frozen_ordered_minimal_handoff(tmp_path):
    rows = [
        make_accepted_row(1),
        make_accepted_row(2, supervision_label="HARD_NEGATIVE"),
    ]
    manifest = write_synthetic_training_package(tmp_path / "package", rows=rows)

    handoff = load_training_input(manifest)

    assert handoff.package_id == "synthetic-training-input-test-only"
    assert isinstance(handoff.examples, tuple)
    assert [example.accepted_record_id for example in handoff.examples] == [
        "synthetic-accepted-1",
        "synthetic-accepted-2",
    ]
    assert tuple(
        vars(example) if hasattr(example, "__dict__") else ()
        for example in handoff.examples
    ) == ((), ())
    assert handoff.examples[0].query_text == rows[0]["query_text"]
    assert handoff.examples[1].supervision_label == "HARD_NEGATIVE"
    with pytest.raises(FrozenInstanceError):
        handoff.examples[0].query_text = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "artifact_version",
        "policy_id",
        "package_id",
        "accepted_pairs",
        "qualification_report",
    ],
)
def test_manifest_rejects_each_missing_exact_field(tmp_path, field):
    manifest = write_synthetic_training_package(tmp_path / field)
    payload = _read_json(manifest)
    del payload[field]
    _write_json(manifest, payload)

    with pytest.raises(TrainingInputError, match="manifest.*fields"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "nested,field",
    [
        ("accepted_pairs", "path"),
        ("accepted_pairs", "sha256"),
        ("accepted_pairs", "row_count"),
        ("qualification_report", "path"),
        ("qualification_report", "sha256"),
    ],
)
def test_manifest_rejects_missing_nested_field(tmp_path, nested, field):
    manifest = write_synthetic_training_package(tmp_path / f"{nested}-{field}")
    payload = _read_json(manifest)
    del payload[nested][field]
    _write_json(manifest, payload)

    with pytest.raises(TrainingInputError, match=f"{nested}.*fields"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "location", ["manifest", "accepted_pairs", "qualification_report"]
)
def test_manifest_rejects_unknown_fields(tmp_path, location):
    manifest = write_synthetic_training_package(tmp_path / location)
    payload = _read_json(manifest)
    target = payload if location == "manifest" else payload[location]
    target["compatibility_mode"] = True
    _write_json(manifest, payload)

    with pytest.raises(TrainingInputError, match="fields"):
        load_training_input(manifest)


@pytest.mark.parametrize("field", list(make_accepted_row().keys()))
def test_accepted_row_rejects_each_missing_exact_field(tmp_path, field):
    row = make_accepted_row()
    del row[field]
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match="accepted row.*fields"):
        load_training_input(manifest)


@pytest.mark.parametrize("field", ["label", "alternate_query", "category", "family"])
def test_accepted_row_rejects_unknown_or_metadata_fields(tmp_path, field):
    row = make_accepted_row()
    row[field] = 1 if field == "label" else "forbidden"
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match="accepted row.*fields"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "unsafe",
    [
        "/absolute.jsonl",
        ".",
        "../escape.jsonl",
        "nested/../pairs.jsonl",
        "nested\\pairs.jsonl",
        "./accepted-pairs.jsonl",
        "nested//pairs.jsonl",
    ],
)
def test_manifest_rejects_unsafe_noncanonical_paths_before_content(tmp_path, unsafe):
    manifest = write_synthetic_training_package(
        tmp_path / "package",
        accepted_pairs_overrides={"path": unsafe, "sha256": "0" * 64},
    )

    with pytest.raises(TrainingInputError, match="accepted_pairs.path"):
        load_training_input(manifest)


def test_manifest_rejects_symlink_nonregular_and_aliased_paths(tmp_path):
    symlink_root = tmp_path / "symlink"
    manifest = write_synthetic_training_package(symlink_root)
    pairs = symlink_root / "accepted-pairs.jsonl"
    target = symlink_root / "target.jsonl"
    pairs.rename(target)
    pairs.symlink_to(target.name)
    with pytest.raises(TrainingInputError, match="symlink"):
        load_training_input(manifest)

    directory_root = tmp_path / "directory"
    manifest = write_synthetic_training_package(directory_root)
    pairs = directory_root / "accepted-pairs.jsonl"
    pairs.unlink()
    pairs.mkdir()
    with pytest.raises(TrainingInputError, match="regular file"):
        load_training_input(manifest)

    alias_root = tmp_path / "alias"
    manifest = write_synthetic_training_package(alias_root)
    payload = _read_json(manifest)
    payload["qualification_report"] = dict(payload["accepted_pairs"])
    payload["qualification_report"].pop("row_count")
    _write_json(manifest, payload)
    with pytest.raises(TrainingInputError, match="distinct files"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "report_patch",
    [
        {"can_start_training": False},
        {"blocker_codes": ["MANUAL_ACCEPTANCE_MISSING"]},
        {"schema_version": "legacy-report-v2"},
        {"artifact_version": 2},
        {"policy_id": "legacy-policy-v2"},
        {"counts": {"accepted_train_pair_count": 2}},
    ],
)
def test_bound_report_must_be_exact_ready_and_count_matched(tmp_path, report_patch):
    manifest = write_synthetic_training_package(
        tmp_path / "package", report_overrides=report_patch
    )

    with pytest.raises(TrainingInputError, match="qualification report"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "manifest_patch",
    [
        {"schema_version": "legacy-manifest-v2"},
        {"artifact_version": 2},
        {"artifact_version": True},
        {"policy_id": "legacy-admission-v2"},
        {"package_id": ""},
    ],
)
def test_manifest_identifiers_and_types_are_exact(tmp_path, manifest_patch):
    manifest = write_synthetic_training_package(
        tmp_path / "package", manifest_overrides=manifest_patch
    )

    with pytest.raises(TrainingInputError, match="manifest"):
        load_training_input(manifest)


def test_manifest_package_id_must_be_nonblank(tmp_path):
    manifest = write_synthetic_training_package(
        tmp_path, manifest_overrides={"package_id": " \t\n "}
    )

    with pytest.raises(TrainingInputError, match="package_id.*non-blank"):
        load_training_input(manifest)


def test_padded_package_id_is_preserved_and_bound_by_genuine_fingerprint(tmp_path):
    manifest = write_synthetic_training_package(
        tmp_path, manifest_overrides={"package_id": " synthetic-package "}
    )
    handoff = load_training_input(manifest)

    assert handoff.package_id == " synthetic-package "
    _verify_training_handoff(handoff)

    object.__setattr__(handoff, "package_id", handoff.package_id.strip())
    with pytest.raises(TrainingInputError, match="content fingerprint"):
        _verify_training_handoff(handoff)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "legacy-row-v2"),
        ("artifact_version", 2),
        ("artifact_version", True),
        ("policy_id", "legacy-admission-v2"),
        ("source_schema_version", "legacy-candidate-v2"),
        ("query_text_policy", "composite"),
        ("accepted_for_training", False),
        ("training_split", "dev"),
        ("task_id", ""),
        ("skill_id", ""),
        ("query_text", ""),
        ("skill_text", ""),
        ("reviewer", ""),
        ("review_reason", ""),
    ],
)
def test_row_exact_constants_and_evidence_are_required(tmp_path, field, value):
    row = make_accepted_row(overrides={field: value})
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match="accepted row"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "field",
    [
        "accepted_record_id",
        "pair_id",
        "source_record_id",
        "task_id",
        "skill_id",
        "query_text",
        "skill_text",
        "reviewer",
        "review_reason",
    ],
)
def test_row_identity_text_and_review_evidence_must_be_nonblank(tmp_path, field):
    row = make_accepted_row(overrides={field: " \t\n "})
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match=f"{field}.*non-blank"):
        load_training_input(manifest)


def test_nonblank_text_is_preserved_not_trimmed_in_handoff_and_hashes(tmp_path):
    row = make_accepted_row(
        overrides={
            "accepted_record_id": " accepted-with-spaces ",
            "query_text": " prompt bytes stay exact ",
            "skill_text": " skill bytes stay exact ",
            "reviewer": " reviewer bytes stay exact ",
            "review_reason": " evidence bytes stay exact ",
        }
    )
    manifest = write_synthetic_training_package(tmp_path, rows=[row])

    handoff = load_training_input(manifest)

    assert handoff.examples[0].accepted_record_id == " accepted-with-spaces "
    assert handoff.examples[0].query_text == " prompt bytes stay exact "
    assert handoff.examples[0].skill_text == " skill bytes stay exact "


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_kind", "NOT_BLIND_BUT_UNKNOWN"),
        ("source_dataset_id", "router-training-data-v2-phase16"),
        ("source_artifact_path", "docs/demo/blind-safe-looking/candidates.jsonl"),
        ("source_split", "test"),
        ("candidate_type", "cross_category_easy_negative"),
        ("candidate_type", "provisional_negative"),
    ],
)
def test_source_allowlist_is_exact_default_deny(tmp_path, field, value):
    row = make_accepted_row(overrides={field: value})
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match="source|role"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "label,status,candidate",
    [
        ("POSITIVE", "ACCEPTED_HARD_NEGATIVE", "positive"),
        ("POSITIVE", "ACCEPTED_POSITIVE", "same_category_negative_candidate"),
        ("HARD_NEGATIVE", "ACCEPTED_POSITIVE", "same_category_negative_candidate"),
        ("HARD_NEGATIVE", "ACCEPTED_HARD_NEGATIVE", "positive"),
        ("UNKNOWN", "ACCEPTED_POSITIVE", "positive"),
    ],
)
def test_only_two_bidirectional_role_mappings_are_admitted(
    tmp_path, label, status, candidate
):
    row = make_accepted_row(
        overrides={
            "supervision_label": label,
            "review_status": status,
            "candidate_type": candidate,
        }
    )
    manifest = write_synthetic_training_package(tmp_path / label, rows=[row])

    with pytest.raises(TrainingInputError, match="role"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "duplicate_field",
    [
        "accepted_record_id",
        "pair_id",
        "source_record_id",
    ],
)
def test_each_stable_identity_is_independently_unique(tmp_path, duplicate_field):
    first = make_accepted_row(1)
    second = make_accepted_row(2)
    second[duplicate_field] = first[duplicate_field]
    rehash_row(second)
    manifest = write_synthetic_training_package(
        tmp_path / duplicate_field, rows=[first, second]
    )

    with pytest.raises(TrainingInputError, match="duplicate"):
        load_training_input(manifest)


def test_source_identity_tuple_is_unique(tmp_path):
    first = make_accepted_row(1)
    second = make_accepted_row(2)
    second["source_record_id"] = first["source_record_id"]
    rehash_row(second)
    manifest = write_synthetic_training_package(tmp_path, rows=[first, second])

    with pytest.raises(TrainingInputError, match="duplicate"):
        load_training_input(manifest)


@pytest.mark.parametrize("field", SOURCE_HASH_FIELDS)
def test_every_source_hash_projection_field_is_bound(tmp_path, field):
    row = make_accepted_row()
    original_hash = row["source_hash"]
    row[field] = f"tampered-{field}"
    if field == "prompt_text_sha256":
        row[field] = "f" * 64
    assert row["source_hash"] == original_hash
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(
        TrainingInputError, match="source_hash|prompt_text_sha256|source|role"
    ):
        load_training_input(manifest)


@pytest.mark.parametrize("field", ACCEPTANCE_HASH_FIELDS)
def test_every_acceptance_hash_projection_field_is_bound(tmp_path, field):
    row = make_accepted_row()
    row[field] = f"tampered-{field}"
    if field == "accepted_for_training":
        row[field] = False
    assert row["acceptance_hash"] != canonical_hash(
        {name: row[name] for name in ACCEPTANCE_HASH_FIELDS}
    )
    manifest = write_synthetic_training_package(tmp_path / field, rows=[row])

    with pytest.raises(TrainingInputError, match="acceptance_hash|accepted row|role"):
        load_training_input(manifest)


@pytest.mark.parametrize(
    "nested,field,value",
    [
        ("accepted_pairs", "sha256", "0" * 64),
        ("qualification_report", "sha256", "0" * 64),
        ("accepted_pairs", "row_count", 2),
        ("accepted_pairs", "row_count", 0),
        ("accepted_pairs", "row_count", True),
    ],
)
def test_bound_hashes_and_counts_are_verified(tmp_path, nested, field, value):
    if nested == "accepted_pairs":
        manifest = write_synthetic_training_package(
            tmp_path, accepted_pairs_overrides={field: value}
        )
    else:
        manifest = write_synthetic_training_package(
            tmp_path, qualification_report_overrides={field: value}
        )

    with pytest.raises(TrainingInputError, match="sha256|row_count"):
        load_training_input(manifest)


def test_malformed_or_blank_jsonl_rejects_whole_package_with_line(tmp_path):
    for name, raw in [("malformed", b"{broken\n"), ("blank", b"\n")]:
        manifest = write_synthetic_training_package(tmp_path / name, raw_pairs=raw)
        with pytest.raises(TrainingInputError, match="accepted-pairs.jsonl:1"):
            load_training_input(manifest)


def test_current_canonical_candidates_are_not_an_admission_manifest():
    candidates = Path(
        "docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl"
    )

    with pytest.raises(TrainingInputError, match="manifest"):
        load_training_input(candidates)
