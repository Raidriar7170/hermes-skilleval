"""Current generators must never rewrite historical release evidence."""

from pathlib import Path
import subprocess

import pytest

from hermes_skilleval.cli import main
from hermes_skilleval.historical_outputs import protect_historical_output

ROOT = Path(__file__).resolve().parents[1]


def historical_state():
    roots = [
        ROOT / "docs/demo/phase17-calibrated-release-selector",
        ROOT / "docs/demo/phase18-ci-release-reproducibility",
    ]
    contents = {
        str(p): p.read_bytes() for r in roots for p in r.rglob("*") if p.is_file()
    }
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *map(str, roots)], cwd=ROOT
    )
    return contents, status


def test_repeated_release_generation_preserves_history(tmp_path):
    before = historical_state()
    for name in ("first", "second"):
        output = tmp_path / name
        assert (
            main(
                [
                    "release-check",
                    "--phase17-output-dir",
                    str(output / "selection"),
                    "--release-output-dir",
                    str(output / "report"),
                ]
            )
            == 0
        )
        assert historical_state() == before
        assert (output / "report/release-manifest.json").is_file()


def test_protected_second_output_rejects_before_first_output_written(tmp_path):
    before = historical_state()
    assert (
        main(
            [
                "release-check",
                "--phase17-output-dir",
                str(tmp_path / "selection"),
                "--release-output-dir",
                str(ROOT / "docs/demo/phase18-ci-release-reproducibility"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "selection").exists()
    assert historical_state() == before


def test_output_guard_resolves_symlinks_and_allows_unrelated_fixture(tmp_path):
    link = tmp_path / "alias"
    link.symlink_to(ROOT / "docs/demo", target_is_directory=True)
    with pytest.raises(ValueError, match="Protected historical output"):
        protect_historical_output(link / "new-report.json")
    protect_historical_output(tmp_path / "docs/demo/new-report.json")
