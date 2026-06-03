import json
from pathlib import Path

from hermes_skilleval.cli import main


def test_cli_diagnostic_front_door_smoke(tmp_path: Path):
    skills = tmp_path / "skills"
    _write_skill(
        skills / "browser" / "browser-smoke-testing" / "SKILL.md",
        name="browser-smoke-testing",
        description="Use when smoke testing local browser pages and checking console errors.",
        body="Use for browser smoke tests and console triage.",
    )
    _write_skill(
        skills / "browser" / "browser-visual-review" / "SKILL.md",
        name="browser-visual-review",
        description="Use when reviewing local browser screenshots for visual regressions.",
        body="Do not use for console-only browser smoke checks.",
    )

    scan_path = tmp_path / "scan.json"
    lint_path = tmp_path / "lint.json"
    inspect_path = tmp_path / "inspect.json"
    route_path = tmp_path / "route.json"
    dashboard_path = tmp_path / "diagnostic-dashboard.html"
    gate_json_path = tmp_path / "diagnostic-ci-gate.json"
    gate_markdown_path = tmp_path / "diagnostic-ci-gate.md"
    pr_review_json_path = tmp_path / "diagnostic-pr-review-packet.json"
    pr_review_markdown_path = tmp_path / "diagnostic-pr-review-packet.md"

    assert main(["scan", str(skills), "--output", str(scan_path)]) == 0
    assert main(["lint", "--index", str(scan_path), "--output", str(lint_path)]) == 0
    assert main(["inspect", "--index", str(scan_path), "--output", str(inspect_path)]) == 0
    assert (
        main(
            [
                "route",
                "smoke test a local browser page",
                "--index",
                str(scan_path),
                "--top-k",
                "2",
                "--inspect",
                str(inspect_path),
                "--output",
                str(route_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-dashboard",
                "--scan",
                str(scan_path),
                "--lint",
                str(lint_path),
                "--inspect",
                str(inspect_path),
                "--route",
                str(route_path),
                "--output",
                str(dashboard_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-ci-gate",
                "--scan",
                str(scan_path),
                "--lint",
                str(lint_path),
                "--inspect",
                str(inspect_path),
                "--route",
                str(route_path),
                "--output",
                str(gate_json_path),
                "--markdown-output",
                str(gate_markdown_path),
                "--max-lint-findings",
                "10",
                "--max-conflict-clusters",
                "10",
                "--max-route-risk-flags",
                "10",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-pr-review-surface",
                "--gate-report",
                str(gate_json_path),
                "--output",
                str(pr_review_json_path),
                "--markdown-output",
                str(pr_review_markdown_path),
            ]
        )
        == 0
    )

    assert json.loads(scan_path.read_text(encoding="utf-8"))["artifact_type"] == "diagnostic_scan"
    assert json.loads(lint_path.read_text(encoding="utf-8"))["artifact_type"] == "diagnostic_lint"
    assert json.loads(inspect_path.read_text(encoding="utf-8"))["artifact_type"] == "diagnostic_inspect"
    assert json.loads(route_path.read_text(encoding="utf-8"))["artifact_type"] == "diagnostic_route"
    assert json.loads(gate_json_path.read_text(encoding="utf-8"))["artifact_type"] == "diagnostic_ci_gate"
    assert (
        json.loads(pr_review_json_path.read_text(encoding="utf-8"))["artifact_type"]
        == "diagnostic_pr_review_packet"
    )
    assert "Diagnostic Skill Library Dashboard" in dashboard_path.read_text(encoding="utf-8")
    assert "artifact-based CI validation" in gate_markdown_path.read_text(encoding="utf-8")
    assert "Diagnostic PR Review Packet" in pr_review_markdown_path.read_text(encoding="utf-8")
    assert "not GitHub API integration" in pr_review_markdown_path.read_text(encoding="utf-8")


def test_cli_diagnostic_commands_require_explicit_outputs(tmp_path: Path):
    skills = tmp_path / "skills"
    _write_skill(
        skills / "coding" / "debug-loop" / "SKILL.md",
        name="debug-loop",
        description="Use when debugging failing tests.",
        body="Do not use for greenfield design.",
    )

    assert main(["scan", str(skills)]) == 2


def test_cli_diagnostic_ci_gate_policy_failure_writes_report_and_returns_nonzero(
    tmp_path: Path,
):
    skills = tmp_path / "skills"
    _write_skill(
        skills / "coding" / "debug-loop" / "SKILL.md",
        name="debug-loop",
        description="Use when debugging failing tests.",
        body="Do not use for greenfield design.",
    )
    scan_path = tmp_path / "scan.json"
    lint_path = tmp_path / "lint.json"
    inspect_path = tmp_path / "inspect.json"
    route_path = tmp_path / "route.json"
    gate_path = tmp_path / "gate.json"

    assert main(["scan", str(skills), "--output", str(scan_path)]) == 0
    assert main(["lint", "--index", str(scan_path), "--output", str(lint_path)]) == 0
    assert main(["inspect", "--index", str(scan_path), "--output", str(inspect_path)]) == 0
    assert (
        main(
            [
                "route",
                "debug failing tests",
                "--index",
                str(scan_path),
                "--inspect",
                str(inspect_path),
                "--output",
                str(route_path),
            ]
        )
        == 0
    )

    result = main(
        [
            "diagnostic-ci-gate",
            "--scan",
            str(scan_path),
            "--lint",
            str(lint_path),
            "--inspect",
            str(inspect_path),
            "--route",
            str(route_path),
            "--output",
            str(gate_path),
            "--max-lint-findings",
            "0",
            "--max-conflict-clusters",
            "0",
            "--max-route-risk-flags",
            "0",
            "--min-route-candidates",
            "2",
        ]
    )

    assert result != 0
    assert json.loads(gate_path.read_text(encoding="utf-8"))["decision"] == "FAIL"


def test_cli_diagnostic_artifact_drift_returns_nonzero_on_drift(tmp_path: Path):
    expected = tmp_path / "expected-scan.json"
    actual = tmp_path / "actual-scan.json"
    output = tmp_path / "drift-report.json"
    markdown = tmp_path / "drift-report.md"
    _write_json(
        expected,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T00:00:00+00:00",
            "summary": {"skill_count": 1},
            "skills": [{"id": "debug-loop"}],
        },
    )
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T01:00:00+00:00",
            "summary": {"skill_count": 2},
            "skills": [{"id": "debug-loop"}],
        },
    )

    result = main(
        [
            "diagnostic-artifact-drift-check",
            "--expected",
            str(expected),
            "--actual",
            str(actual),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ]
    )

    assert result != 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["decision"] == "FAIL"
    assert report["compared_artifacts"][0]["artifact"] == "expected-scan.json"
    assert "Decision: `FAIL`" in markdown.read_text(encoding="utf-8")


def test_cli_diagnostic_artifact_drift_requires_markdown_output(tmp_path: Path):
    expected = tmp_path / "expected-scan.json"
    actual = tmp_path / "actual-scan.json"
    output = tmp_path / "drift-report.json"
    payload = {
        "artifact_type": "diagnostic_scan",
        "schema_version": "diagnostic.v1",
        "generated_at": "2026-06-03T00:00:00+00:00",
        "summary": {"skill_count": 1},
        "skills": [{"id": "debug-loop"}],
    }
    _write_json(expected, payload)
    _write_json(actual, payload)

    result = main(
        [
            "diagnostic-artifact-drift-check",
            "--expected",
            str(expected),
            "--actual",
            str(actual),
            "--output",
            str(output),
        ]
    )

    assert result == 2
    assert not output.exists()


def test_cli_scan_unsupported_source_returns_clear_error_without_traceback(
    tmp_path: Path,
    capsys,
):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("not a supported skill source", encoding="utf-8")
    output = tmp_path / "scan.json"

    assert main(["scan", str(unsupported), "--output", str(output)]) == 2
    captured = capsys.readouterr()

    assert "unsupported skill source shape" in captured.err
    assert "Traceback" not in captured.err
    assert not output.exists()


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
