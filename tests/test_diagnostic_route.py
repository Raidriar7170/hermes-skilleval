from pathlib import Path

import pytest

from hermes_skilleval.diagnostics import (
    route_diagnostic_query,
    write_inspect_artifact,
    write_route_artifact,
    write_scan_artifact,
)


def test_route_returns_top_k_candidates_with_scores_evidence_and_risks(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    inspect_path = tmp_path / "inspect.json"
    _write_skill(
        tmp_path / "skills" / "browser" / "browser-smoke-testing" / "SKILL.md",
        name="browser-smoke-testing",
        description="Use when smoke testing local browser pages and checking console errors.",
        body="Use for browser smoke tests and console triage.",
    )
    _write_skill(
        tmp_path / "skills" / "browser" / "browser-visual-review" / "SKILL.md",
        name="browser-visual-review",
        description="Use when reviewing local browser screenshots for visual regressions.",
        body="Do not use for console-only browser smoke checks.",
    )
    _write_skill(
        tmp_path / "skills" / "research" / "paper-summary" / "SKILL.md",
        name="paper-summary",
        description="Use when summarizing research papers.",
        body="Do not use for browser UI testing.",
    )
    write_scan_artifact(tmp_path / "skills", scan_path)
    write_inspect_artifact(scan_path, inspect_path)

    output = tmp_path / "route.json"
    artifact = write_route_artifact(
        "smoke test a local browser page and check console errors",
        scan_path,
        output,
        top_k=2,
        inspect_path=inspect_path,
    )

    assert output.exists()
    assert artifact["artifact_type"] == "diagnostic_route"
    assert artifact["query"] == "smoke test a local browser page and check console errors"
    assert [candidate["skill_id"] for candidate in artifact["candidates"]] == [
        "browser-smoke-testing",
        "browser-visual-review",
    ]
    assert [candidate["rank"] for candidate in artifact["candidates"]] == [1, 2]
    first = artifact["candidates"][0]
    assert first["score"] > 0
    assert {"browser", "smoke"} <= set(first["evidence"]["matched_terms"])
    assert first["evidence"]["source_fields"]
    assert {flag["code"] for flag in first["risk_flags"]} == {
        "conflict_cluster",
        "weak_boundary",
    }


def test_route_empty_index_errors(tmp_path: Path):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        '{"artifact_type":"diagnostic_scan","schema_version":"diagnostic.v1","skills":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="diagnostic skill index is empty"):
        route_diagnostic_query("debug failing tests", scan_path, top_k=3)


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
