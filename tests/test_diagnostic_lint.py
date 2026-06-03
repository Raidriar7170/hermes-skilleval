from pathlib import Path

from hermes_skilleval.diagnostics import (
    lint_diagnostic_index,
    write_lint_artifact,
    write_scan_artifact,
)


def test_lint_reports_routing_clarity_findings(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    _write_skill(
        tmp_path / "skills" / "agent" / "thin-agent" / "SKILL.md",
        name="thin-agent",
        description="",
        body="Use this for tasks and general help.",
    )
    _write_skill(
        tmp_path / "skills" / "coding" / "systematic-debugging" / "SKILL.md",
        name="systematic-debugging",
        description="Use when diagnosing failing tests with hypothesis-driven debugging.",
        body=(
            "Use when tests fail, stack traces repeat, or logs need triage.\n"
            "Avoid when the task is greenfield feature design."
        ),
    )
    write_scan_artifact(tmp_path / "skills", scan_path)

    lint_path = tmp_path / "lint.json"
    artifact = write_lint_artifact(scan_path, lint_path)

    assert lint_path.exists()
    assert artifact["artifact_type"] == "diagnostic_lint"
    assert artifact["summary"]["skill_count"] == 2
    assert artifact["summary"]["finding_count"] == 4

    thin_codes = {
        finding["code"]
        for finding in artifact["findings"]
        if finding["skill_id"] == "thin-agent"
    }
    assert thin_codes == {
        "missing_description",
        "weak_activation_cues",
        "missing_negative_boundaries",
        "generic_terms",
    }
    assert {
        finding["code"]
        for finding in artifact["findings"]
        if finding["skill_id"] == "systematic-debugging"
    } == set()


def test_lint_avoids_generic_markdown_or_prose_style_findings(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    _write_skill(
        tmp_path / "skills" / "writing" / "plain-style" / "SKILL.md",
        name="plain-style",
        description="Use when editing technical prose for clearer developer docs.",
        body=(
            "Use when docs need clearer examples, definitions, or reviewer notes.\n"
            "Do not use when the task is code execution or routing evaluation."
        ),
    )
    write_scan_artifact(tmp_path / "skills", scan_path)

    artifact = lint_diagnostic_index(scan_path)

    assert artifact["findings"] == []
    assert "markdown" not in str(artifact).lower()
    assert "prose_style" not in str(artifact)


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
