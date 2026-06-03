import json
from pathlib import Path

import pytest

from hermes_skilleval.diagnostic_dashboard import (
    build_diagnostic_dashboard_payload,
    render_diagnostic_dashboard_html,
    write_diagnostic_dashboard,
)
from hermes_skilleval.diagnostics import (
    write_inspect_artifact,
    write_lint_artifact,
    write_route_artifact,
    write_scan_artifact,
)


def test_diagnostic_dashboard_payload_and_html_show_required_sections(tmp_path: Path):
    scan_path, lint_path, inspect_path, route_path = _write_artifacts(tmp_path)

    payload = build_diagnostic_dashboard_payload(
        scan_path=scan_path,
        lint_path=lint_path,
        inspect_path=inspect_path,
        route_paths=[route_path],
    )
    html = render_diagnostic_dashboard_html(payload)

    assert payload["artifact_type"] == "diagnostic_dashboard"
    assert payload["summary"]["skill_count"] == 2
    assert "Source summary" in html
    assert "Routing-readiness findings" in html
    assert "Route examples" in html
    assert "Conflict risk clusters" in html
    assert "runtime agent integration" not in html.lower()
    assert "labeled benchmark results" not in html.lower()


def test_write_diagnostic_dashboard_is_self_contained_html(tmp_path: Path):
    scan_path, lint_path, inspect_path, route_path = _write_artifacts(tmp_path)
    output = tmp_path / "diagnostic-dashboard.html"

    write_diagnostic_dashboard(
        output_path=output,
        scan_path=scan_path,
        lint_path=lint_path,
        inspect_path=inspect_path,
        route_paths=[route_path],
    )

    html = output.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__" in html
    assert "Diagnostic Skill Library Dashboard" in html


@pytest.mark.parametrize(
    ("field", "expected_type"),
    [
        ("scan", "diagnostic_scan"),
        ("lint", "diagnostic_lint"),
        ("inspect", "diagnostic_inspect"),
        ("route", "diagnostic_route"),
    ],
)
def test_diagnostic_dashboard_rejects_wrong_artifact_types(
    tmp_path: Path,
    field: str,
    expected_type: str,
):
    scan_path, lint_path, inspect_path, route_path = _write_artifacts(tmp_path)
    paths = {
        "scan": scan_path,
        "lint": lint_path,
        "inspect": inspect_path,
        "route": route_path,
    }
    paths[field].write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_scan" if field != "scan" else "diagnostic_lint",
                "schema_version": "diagnostic.v1",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=f"{field} artifact must be {expected_type}"):
        build_diagnostic_dashboard_payload(
            scan_path=scan_path,
            lint_path=lint_path,
            inspect_path=inspect_path,
            route_paths=[route_path],
        )


def test_diagnostic_dashboard_rejects_wrong_schema_version(tmp_path: Path):
    scan_path, lint_path, inspect_path, route_path = _write_artifacts(tmp_path)
    scan_path.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_scan",
                "schema_version": "legacy.v0",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="scan artifact schema_version must be diagnostic.v1"):
        build_diagnostic_dashboard_payload(
            scan_path=scan_path,
            lint_path=lint_path,
            inspect_path=inspect_path,
            route_paths=[route_path],
        )


def _write_artifacts(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
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
    scan_path = tmp_path / "scan.json"
    lint_path = tmp_path / "lint.json"
    inspect_path = tmp_path / "inspect.json"
    route_path = tmp_path / "route.json"
    write_scan_artifact(tmp_path / "skills", scan_path)
    write_lint_artifact(scan_path, lint_path)
    write_inspect_artifact(scan_path, inspect_path)
    write_route_artifact(
        "smoke test a local browser page",
        scan_path,
        route_path,
        top_k=2,
        inspect_path=inspect_path,
    )
    return scan_path, lint_path, inspect_path, route_path


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
