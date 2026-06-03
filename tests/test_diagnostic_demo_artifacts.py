import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "docs" / "demo" / "diagnostic-onboarding"
SCHEMA_VERSION = "diagnostic.v1"


def test_diagnostic_demo_artifacts_have_stable_contract():
    artifacts = {
        "scan.json": "diagnostic_scan",
        "lint.json": "diagnostic_lint",
        "inspect.json": "diagnostic_inspect",
    }

    for filename, artifact_type in artifacts.items():
        payload = _read_json(DEMO_DIR / filename)
        assert payload["artifact_type"] == artifact_type
        assert payload["schema_version"] == SCHEMA_VERSION

    scan = _read_json(DEMO_DIR / "scan.json")
    assert {skill["id"] for skill in scan["skills"]} == {
        "browser-smoke-testing",
        "browser-visual-review",
        "debug-loop",
        "red-green-testing",
        "general-helper",
    }
    general = _skill(scan, "general-helper")
    assert general["parser_warnings"] == [
        "missing frontmatter; used fallback metadata",
    ]

    route_paths = sorted(DEMO_DIR.glob("route-*.json"))
    assert {path.name for path in route_paths} == {
        "route-browser-smoke.json",
        "route-debug-red-green.json",
    }
    for route_path in route_paths:
        route = _read_json(route_path)
        assert route["artifact_type"] == "diagnostic_route"
        assert route["schema_version"] == SCHEMA_VERSION
        assert route["candidates"]
        assert any(candidate["evidence"]["matched_terms"] for candidate in route["candidates"])


def test_diagnostic_demo_route_evidence_and_risks_are_visible():
    route = _read_json(DEMO_DIR / "route-browser-smoke.json")

    assert route["query"] == "smoke test a local browser page and check console errors"
    candidate_ids = [candidate["skill_id"] for candidate in route["candidates"]]
    assert "browser-smoke-testing" in candidate_ids
    assert "browser-visual-review" in candidate_ids

    primary = route["candidates"][0]
    assert primary["skill_id"] == "browser-smoke-testing"
    assert {"browser", "console"} <= set(primary["evidence"]["matched_terms"])
    assert primary["evidence"]["source_fields"]
    all_flags = {
        flag["code"]
        for candidate in route["candidates"]
        for flag in candidate["risk_flags"]
    }
    assert {"conflict_cluster", "weak_boundary"} <= all_flags


def test_diagnostic_demo_conflicts_and_lint_are_review_worthy():
    inspect = _read_json(DEMO_DIR / "inspect.json")
    lint = _read_json(DEMO_DIR / "lint.json")

    assert inspect["summary"]["cluster_count"] >= 1
    cluster_text = json.dumps(inspect["clusters"], sort_keys=True)
    assert "Review-worthy routing risk" in cluster_text
    assert "duplicate" not in cluster_text.lower()
    assert "must merge" not in cluster_text.lower()
    assert any(
        set(cluster["involved_skills"])
        == {"browser-smoke-testing", "browser-visual-review"}
        for cluster in inspect["clusters"]
    )

    finding_codes = {
        finding["code"]
        for finding in lint["findings"]
        if finding["skill_id"] == "general-helper"
    }
    assert {
        "missing_description",
        "weak_activation_cues",
        "missing_negative_boundaries",
        "generic_terms",
    } <= finding_codes


def test_diagnostic_demo_ci_gate_reports_are_committed_and_bounded():
    report = _read_json(DEMO_DIR / "ci-gate-report.json")
    markdown = (DEMO_DIR / "ci-gate-report.md").read_text(encoding="utf-8")

    assert report["artifact_type"] == "diagnostic_ci_gate"
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["decision"] == "PASS"
    assert report["scope"] == "local artifact validation for diagnostic skill-library CI"
    assert report["policy"] == {
        "max_conflict_clusters": 4,
        "max_lint_findings": 5,
        "max_route_risk_flags": 15,
        "min_route_candidates": 3,
        "require_route_evidence": True,
    }
    assert report["summary"] == {
        "conflict_cluster_count": 4,
        "lint_finding_count": 5,
        "missing_route_evidence_count": 0,
        "route_count": 2,
        "route_risk_flag_count": 15,
        "skill_count": 5,
    }
    assert report["failed_policies"] == []
    assert {Path(route["path"]).name for route in report["route_reports"]} == {
        "route-browser-smoke.json",
        "route-debug-red-green.json",
    }

    assert "Decision: `PASS`" in markdown
    assert "artifact-based CI validation" in markdown
    assert "not a Marketplace Action" in markdown
    assert "not a PR annotation system" in markdown
    assert "not SaaS" in markdown
    assert "not a runtime MCP router" in markdown
    assert "not a SOTA claim" in markdown


def test_diagnostic_demo_dashboard_is_self_contained_and_bounded():
    html = (DEMO_DIR / "dashboard.html").read_text(encoding="utf-8")
    reviewed_paths = sorted(
        path
        for path in DEMO_DIR.rglob("*")
        if path.is_file()
    ) + [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "usage.md",
    ]
    combined_text = "\n".join(
        path.read_text(encoding="utf-8") for path in reviewed_paths
    ).lower()

    assert "<!doctype html>" in html
    assert "window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__" in html
    assert 'src="http' not in html
    assert 'href="http' not in html
    assert "/users/" not in combined_text
    assert "/root" not in combined_text
    for secret_phrase in ["access_token", "api_key", "secret", "password"]:
        assert secret_phrase not in combined_text
    assert not re.search(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", combined_text)
    assert not re.search(r"\b172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b", combined_text)
    assert not re.search(r"\b192\.168\.\d{1,3}\.\d{1,3}\b", combined_text)
    for phrase in [
        "leaderboard",
        "hosted product",
        "hosted saas product",
        "merge-blocking",
        "merge blocking",
        "released as a marketplace action",
        "writes pr annotations",
        "runtime mcp router for agents",
        "sota benchmark",
    ]:
        assert phrase not in combined_text


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill(artifact: dict, skill_id: str) -> dict:
    return next(skill for skill in artifact["skills"] if skill["id"] == skill_id)
