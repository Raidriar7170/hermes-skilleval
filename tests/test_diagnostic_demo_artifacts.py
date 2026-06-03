import json
import re
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.diagnostic_artifact_drift import compare_diagnostic_artifacts


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


def test_diagnostic_demo_pr_review_packet_is_committed_and_bounded():
    packet = _read_json(DEMO_DIR / "pr-review-packet.json")
    markdown = (DEMO_DIR / "pr-review-packet.md").read_text(encoding="utf-8")

    assert packet["artifact_type"] == "diagnostic_pr_review_packet"
    assert packet["schema_version"] == SCHEMA_VERSION
    assert packet["decision"] == "PASS"
    assert packet["verdict_source"]["artifact_type"] == "diagnostic_ci_gate"
    assert Path(packet["verdict_source"]["path"]).name == "ci-gate-report.json"
    assert packet["policy_status"] == "passed"
    assert packet["summary"] == {
        "conflict_cluster_count": 4,
        "lint_finding_count": 5,
        "missing_route_evidence_count": 0,
        "route_count": 2,
        "route_risk_flag_count": 15,
        "skill_count": 5,
    }
    assert packet["source_artifacts"]["scan"] == "docs/demo/diagnostic-onboarding/scan.json"
    assert {Path(route).name for route in packet["source_artifacts"]["routes"]} == {
        "route-browser-smoke.json",
        "route-debug-red-green.json",
    }
    assert packet["evidence_gaps"] == []
    assert any(item["code"] == "review_worthy_route_risks" for item in packet["attention_items"])

    assert "# Diagnostic PR Review Packet" in markdown
    assert "Decision: `PASS`" in markdown
    assert "review-worthy diagnostic signals" in markdown
    assert "not GitHub API integration" in markdown
    assert "not a PR annotation system" in markdown
    assert "not a Marketplace Action" in markdown
    assert "not SaaS" in markdown
    assert "not a runtime MCP router" in markdown
    assert "not a SOTA claim" in markdown
    for risky_phrase in [
        "calls the GitHub API",
        "writes PR annotations",
        "released as a Marketplace Action",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark",
    ]:
        assert risky_phrase not in markdown


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


def test_diagnostic_demo_drift_check_passes_documented_regeneration_flow(
    tmp_path: Path,
):
    actual_dir = tmp_path / "diagnostic-onboarding-regenerated"
    actual_dir.mkdir()
    _regenerate_diagnostic_demo(actual_dir)

    report = compare_diagnostic_artifacts(
        expected_path=DEMO_DIR,
        actual_path=actual_dir,
        output_path=tmp_path / "drift-report.json",
        markdown_output_path=tmp_path / "drift-report.md",
    )

    assert report["decision"] == "PASS"
    assert report["summary"]["drift_count"] == 0
    assert {
        artifact["artifact"]
        for artifact in report["compared_artifacts"]
    } == {
        "scan.json",
        "lint.json",
        "inspect.json",
        "route-browser-smoke.json",
        "route-debug-red-green.json",
        "dashboard.html",
        "ci-gate-report.json",
        "pr-review-packet.json",
    }


def test_diagnostic_demo_drift_check_cli_passes_documented_regeneration_flow(
    tmp_path: Path,
):
    actual_dir = tmp_path / "diagnostic-onboarding-regenerated"
    actual_dir.mkdir()
    _regenerate_diagnostic_demo(actual_dir)
    output = tmp_path / "drift-report.json"
    markdown = tmp_path / "drift-report.md"

    assert (
        main(
            [
                "diagnostic-artifact-drift-check",
                "--expected",
                str(DEMO_DIR),
                "--actual",
                str(actual_dir),
                "--output",
                str(output),
                "--markdown-output",
                str(markdown),
            ]
        )
        == 0
    )

    report = _read_json(output)
    assert report["decision"] == "PASS"
    assert report["summary"] == {"compared_count": 8, "drift_count": 0}
    assert "Ignored volatile fields" in markdown.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill(artifact: dict, skill_id: str) -> dict:
    return next(skill for skill in artifact["skills"] if skill["id"] == skill_id)


def _regenerate_diagnostic_demo(output_dir: Path) -> None:
    source = DEMO_DIR / "source" / "skills"
    scan = output_dir / "scan.json"
    lint = output_dir / "lint.json"
    inspect = output_dir / "inspect.json"
    route_browser = output_dir / "route-browser-smoke.json"
    route_debug = output_dir / "route-debug-red-green.json"
    dashboard = output_dir / "dashboard.html"
    gate_json = output_dir / "ci-gate-report.json"
    gate_markdown = output_dir / "ci-gate-report.md"
    pr_json = output_dir / "pr-review-packet.json"
    pr_markdown = output_dir / "pr-review-packet.md"

    assert main(["scan", str(source), "--output", str(scan)]) == 0
    assert main(["lint", "--index", str(scan), "--output", str(lint)]) == 0
    assert main(["inspect", "--index", str(scan), "--output", str(inspect)]) == 0
    assert (
        main(
            [
                "route",
                "smoke test a local browser page and check console errors",
                "--index",
                str(scan),
                "--inspect",
                str(inspect),
                "--top-k",
                "3",
                "--output",
                str(route_browser),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "route",
                "debug failing tests with a red-green loop",
                "--index",
                str(scan),
                "--inspect",
                str(inspect),
                "--top-k",
                "3",
                "--output",
                str(route_debug),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-dashboard",
                "--scan",
                str(scan),
                "--lint",
                str(lint),
                "--inspect",
                str(inspect),
                "--route",
                str(route_browser),
                "--route",
                str(route_debug),
                "--output",
                str(dashboard),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-ci-gate",
                "--scan",
                str(scan),
                "--lint",
                str(lint),
                "--inspect",
                str(inspect),
                "--route",
                str(route_browser),
                "--route",
                str(route_debug),
                "--output",
                str(gate_json),
                "--markdown-output",
                str(gate_markdown),
                "--max-lint-findings",
                "5",
                "--max-conflict-clusters",
                "4",
                "--max-route-risk-flags",
                "15",
                "--min-route-candidates",
                "3",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "diagnostic-pr-review-surface",
                "--gate-report",
                str(gate_json),
                "--output",
                str(pr_json),
                "--markdown-output",
                str(pr_markdown),
            ]
        )
        == 0
    )
