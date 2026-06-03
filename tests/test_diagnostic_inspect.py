from pathlib import Path

from hermes_skilleval.diagnostics import (
    inspect_diagnostic_index,
    write_inspect_artifact,
    write_scan_artifact,
)


def test_inspect_groups_explainable_conflict_risk_clusters(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    _write_skill(
        tmp_path / "skills" / "browser" / "browser-smoke-testing" / "SKILL.md",
        name="browser-smoke-testing",
        description="Use when smoke testing local browser pages and checking console errors.",
        body="Use for browser smoke testing, page loading checks, and console triage.",
    )
    _write_skill(
        tmp_path / "skills" / "browser" / "browser-visual-review" / "SKILL.md",
        name="browser-visual-review",
        description="Use when reviewing local browser screenshots for visual regressions.",
        body="Use for browser screenshot review, layout checks, and visual regression triage.",
    )
    _write_skill(
        tmp_path / "skills" / "research" / "paper-summary" / "SKILL.md",
        name="paper-summary",
        description="Use when summarizing research papers and extracting citations.",
        body="Do not use for browser UI testing or screenshot review.",
    )
    write_scan_artifact(tmp_path / "skills", scan_path)

    output = tmp_path / "inspect.json"
    artifact = write_inspect_artifact(scan_path, output)

    assert output.exists()
    assert artifact["artifact_type"] == "diagnostic_inspect"
    assert artifact["summary"]["cluster_count"] == 1
    cluster = artifact["clusters"][0]
    assert cluster["involved_skills"] == [
        "browser-smoke-testing",
        "browser-visual-review",
    ]
    assert "Review-worthy routing risk" in cluster["summary"]
    signal_types = {signal["type"] for signal in cluster["signals"]}
    assert {
        "token_overlap",
        "trigger_term_overlap",
        "category_proximity",
        "missing_boundaries",
        "route_coappearance",
    } <= signal_types
    assert "browser" in cluster["evidence_terms"]


def test_inspect_uses_review_worthy_language_not_definitive_verdicts(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    _write_skill(
        tmp_path / "skills" / "coding" / "debug-loop" / "SKILL.md",
        name="debug-loop",
        description="Use when debugging failing tests and repeated errors.",
        body="Use when failures are already observed.",
    )
    _write_skill(
        tmp_path / "skills" / "coding" / "test-red-green" / "SKILL.md",
        name="test-red-green",
        description="Use when debugging failing tests with red green loops.",
        body="Use when failures are already observed.",
    )
    write_scan_artifact(tmp_path / "skills", scan_path)

    artifact_text = str(inspect_diagnostic_index(scan_path)).lower()

    assert "review-worthy" in artifact_text
    assert "duplicate" not in artifact_text
    assert "must merge" not in artifact_text


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
