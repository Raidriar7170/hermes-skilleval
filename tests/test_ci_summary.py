import json
from pathlib import Path

from hermes_skilleval.ci_summary import write_ci_summary


def test_ci_summary_allows_merge_when_required_checks_pass(tmp_path: Path):
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text(
        "\n".join(
            [
                ".github/workflows/validate.yml",
                "src/hermes_skilleval/ci_summary.py",
                "tests/test_ci_summary.py",
                "docs/demo/diagnostic-onboarding/scan.json",
                "openspec/changes/pr-facing-ci-summary/specs/pr-facing-ci-summary/spec.md",
                "README.md",
                "benchmarks/tasks/example/task.yaml",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    overclaim_root = tmp_path / "public"
    overclaim_root.mkdir()
    (overclaim_root / "README.md").write_text(
        "This local summary does not claim SOTA or release approval.\n",
        encoding="utf-8",
    )

    output = tmp_path / "ci-summary.json"
    markdown = tmp_path / "ci-summary.md"
    summary = write_ci_summary(
        checks=[
            ("pytest", "success"),
            ("openspec validate", "PASS"),
            ("release-check", "SUCCESS"),
            ("diagnostic-gate", "pass"),
            ("diagnostic-drift", "skipped_optional"),
        ],
        changed_files_path=changed_files,
        release_check_path=tmp_path / "release-check-summary.json",
        diagnostic_gate_path=tmp_path / "diagnostic-ci-gate.json",
        diagnostic_drift_path=tmp_path / "diagnostic-artifact-drift.json",
        overclaim_roots=[overclaim_root],
        output_path=output,
        markdown_output_path=markdown,
    )

    assert summary["decision"] == "ALLOW_MERGE"
    assert summary["artifact_type"] == "ci_summary"
    assert summary["checks"][0]["normalized_status"] == "PASS"
    assert summary["overclaim_scan"]["match_count"] == 0
    assert summary["changed_files"]["groups"]["workflow"] == [
        ".github/workflows/validate.yml"
    ]
    assert summary["changed_files"]["groups"]["source"] == [
        "src/hermes_skilleval/ci_summary.py"
    ]
    assert summary["changed_files"]["groups"]["tests"] == ["tests/test_ci_summary.py"]
    assert summary["changed_files"]["groups"]["diagnostics"] == [
        "docs/demo/diagnostic-onboarding/scan.json"
    ]
    assert summary["changed_files"]["groups"]["openspec"] == [
        "openspec/changes/pr-facing-ci-summary/specs/pr-facing-ci-summary/spec.md"
    ]
    assert summary["changed_files"]["groups"]["docs"] == ["README.md"]
    assert summary["changed_files"]["groups"]["other"] == [
        "benchmarks/tasks/example/task.yaml"
    ]
    assert json.loads(output.read_text(encoding="utf-8")) == summary

    rendered = markdown.read_text(encoding="utf-8")
    assert "# PR-facing CI Summary" in rendered
    assert "Decision: `ALLOW_MERGE`" in rendered
    assert "local/GitHub Actions summary" in rendered
    assert "not a GitHub API comment bot" in rendered
    assert "not release approval" in rendered
    assert "| pytest | PASS | success |" in rendered
    assert "## Changed Files" in rendered


def test_ci_summary_blocks_merge_on_failed_check_or_overclaim(tmp_path: Path):
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text("README.md\n", encoding="utf-8")
    overclaim_root = tmp_path / "public"
    overclaim_root.mkdir()
    (overclaim_root / "README.md").write_text(
        "This project is production-ready and released as SOTA.\n",
        encoding="utf-8",
    )

    summary = write_ci_summary(
        checks=[("pytest", "success"), ("release-check", "failure")],
        changed_files_path=changed_files,
        release_check_path=None,
        diagnostic_gate_path=None,
        diagnostic_drift_path=None,
        overclaim_roots=[overclaim_root],
        output_path=tmp_path / "summary.json",
        markdown_output_path=tmp_path / "summary.md",
    )

    assert summary["decision"] == "BLOCK_MERGE"
    assert summary["checks"][1]["normalized_status"] == "FAIL"
    assert summary["overclaim_scan"]["status"] == "FAIL"
    assert summary["overclaim_scan"]["match_count"] == 1
