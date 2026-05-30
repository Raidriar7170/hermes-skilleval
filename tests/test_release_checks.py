from __future__ import annotations

import json
from pathlib import Path

from hermes_skilleval.release_checks import (
    find_checkpoint_files,
    find_overclaim_matches,
    find_sensitive_matches,
    run_release_checks,
    verify_required_paths,
    write_release_check_summary,
)


def test_find_sensitive_matches_detects_secret_patterns(tmp_path: Path) -> None:
    path = tmp_path / "public.md"
    path.write_text(
        "\n".join(
            [
                "api_key=abc123",
                "Bearer abc123",
                "AKIAIOSFODNN7EXAMPLE",
                "sk-example123456",
                "10.0.0.1",
                "/root/private-cache",
            ]
        ),
        encoding="utf-8",
    )

    matches = find_sensitive_matches([path])

    assert [match.line_number for match in matches] == [1, 2, 3, 4, 5, 6]
    assert all(match.path == path for match in matches)


def test_find_checkpoint_files_detects_checkpoint_file_root(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_text("not real weights", encoding="utf-8")

    assert find_checkpoint_files(checkpoint) == [checkpoint]


def test_find_checkpoint_files_detects_checkpoint_dir_root(tmp_path: Path) -> None:
    checkpoint = tmp_path / "models" / "router.pt"
    checkpoint.parent.mkdir()
    checkpoint.write_text("not real weights", encoding="utf-8")

    assert find_checkpoint_files(tmp_path) == [checkpoint]


def test_find_overclaim_matches_flags_affirmative_public_claims(
    tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    path.write_text(
        "\n".join(
            [
                "This is a state-of-the-art router.",
                "This is production-ready.",
                "This is a standard external benchmark.",
                "This is SOTA for agent skills.",
            ]
        ),
        encoding="utf-8",
    )

    matches = find_overclaim_matches([path])

    assert [match.line_number for match in matches] == [1, 2, 3, 4]


def test_find_overclaim_matches_allows_negative_disclaimers(tmp_path: Path) -> None:
    path = tmp_path / "phase.md"
    path.write_text(
        "\n".join(
            [
                "This does not establish SOTA.",
                "This is not a standard external benchmark.",
                "This does not claim state-of-the-art quality.",
                "This should not be described as production-ready.",
            ]
        ),
        encoding="utf-8",
    )

    assert find_overclaim_matches([path]) == []


def test_verify_required_paths_reports_missing_as_review_required(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "README.md"
    missing = tmp_path / "missing.md"
    existing.write_text("# ok\n", encoding="utf-8")

    result = verify_required_paths([existing, missing])

    assert result.ok is False
    assert result.status == "REVIEW_REQUIRED"
    assert str(missing) in result.message


def test_run_release_checks_reports_missing_public_root_as_review_required(
    tmp_path: Path,
) -> None:
    summary = run_release_checks(
        public_roots=[tmp_path / "missing-public"],
        required_paths=[],
    )

    assert summary["status"] == "REVIEW_REQUIRED"
    assert summary["match_count"] == 0


def test_run_release_checks_excludes_docs_superpowers_by_default(
    tmp_path: Path,
) -> None:
    old_plan = tmp_path / "docs" / "superpowers" / "plans" / "old-plan.md"
    old_plan.parent.mkdir(parents=True)
    old_plan.write_text(
        "Example regex catches AKIAIOSFODNN7EXAMPLE and production-ready.\n",
        encoding="utf-8",
    )
    public_file = tmp_path / "docs" / "release.md"
    public_file.write_text("This is bounded release evidence.\n", encoding="utf-8")

    summary = run_release_checks(public_roots=[tmp_path], required_paths=[public_file])

    assert summary["status"] == "PASS"
    assert summary["match_count"] == 0


def test_run_release_checks_scans_public_root_file(tmp_path: Path) -> None:
    public_file = tmp_path / "release.md"
    public_file.write_text("This is SOTA evidence.\n", encoding="utf-8")

    summary = run_release_checks(public_roots=[public_file], required_paths=[])

    assert summary["status"] == "FAIL"
    assert summary["match_count"] == 1
    assert summary["matches"]["overclaims"][0]["path"] == str(public_file)


def test_write_release_check_summary_writes_json(tmp_path: Path) -> None:
    public_file = tmp_path / "release.md"
    output = tmp_path / "release-check-summary.json"
    public_file.write_text("This is bounded release evidence.\n", encoding="utf-8")

    summary = write_release_check_summary(
        public_roots=[public_file],
        required_paths=[public_file],
        output_path=output,
    )

    assert summary["status"] == "PASS"
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "PASS"
