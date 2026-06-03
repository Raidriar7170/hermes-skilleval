import json
import re
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.diagnostic_artifact_drift import compare_diagnostic_artifacts


REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = REPO_ROOT / "docs" / "demo" / "external-skill-library-validation"
SCHEMA_VERSION = "diagnostic.v1"

TRACKS = {
    "markdown-skills": {
        "source": PACK_DIR / "source" / "markdown-skills",
        "source_type": "markdown_skill",
        "skill_ids": {"release-note-review", "workflow-evidence-audit"},
        "routes": {
            "route-release-note-review.json": (
                "review release notes for evidence boundaries and non-goals"
            ),
            "route-workflow-evidence.json": (
                "audit validation workflow evidence before a maintainer review"
            ),
        },
        "thresholds": {
            "max_lint_findings": "4",
            "max_conflict_clusters": "4",
            "max_route_risk_flags": "20",
            "min_route_candidates": "2",
        },
    },
    "mcp-tool-schema": {
        "source": PACK_DIR / "source" / "mcp-tool-schema" / "tools.json",
        "source_type": "mcp_tool_schema",
        "skill_ids": {"capture_browser_console", "inspect_artifact_drift"},
        "routes": {
            "route-browser-console.json": (
                "capture browser console diagnostics for a local maintainer page"
            ),
            "route-artifact-drift.json": (
                "inspect semantic artifact drift between expected and regenerated reports"
            ),
        },
        "thresholds": {
            "max_lint_findings": "4",
            "max_conflict_clusters": "4",
            "max_route_risk_flags": "20",
            "min_route_candidates": "2",
        },
    },
}

COMPARABLE_ARTIFACTS = {
    f"{track}/{name}"
    for track, spec in TRACKS.items()
    for name in [
        "scan.json",
        "lint.json",
        "inspect.json",
        *spec["routes"].keys(),
        "dashboard.html",
        "ci-gate-report.json",
        "pr-review-packet.json",
    ]
}


def test_external_validation_pack_artifacts_have_stable_contract():
    assert PACK_DIR.is_dir()
    assert (PACK_DIR / "README.md").is_file()

    for track, spec in TRACKS.items():
        track_dir = PACK_DIR / track
        assert spec["source"].exists()
        assert track_dir.is_dir()

        scan = _read_json(track_dir / "scan.json")
        assert scan["artifact_type"] == "diagnostic_scan"
        assert scan["schema_version"] == SCHEMA_VERSION
        assert scan["summary"]["source_types"] == {spec["source_type"]: len(spec["skill_ids"])}
        assert {skill["id"] for skill in scan["skills"]} == spec["skill_ids"]

        lint = _read_json(track_dir / "lint.json")
        inspect = _read_json(track_dir / "inspect.json")
        assert lint["artifact_type"] == "diagnostic_lint"
        assert inspect["artifact_type"] == "diagnostic_inspect"
        assert lint["schema_version"] == SCHEMA_VERSION
        assert inspect["schema_version"] == SCHEMA_VERSION

        for route_name, query in spec["routes"].items():
            route = _read_json(track_dir / route_name)
            assert route["artifact_type"] == "diagnostic_route"
            assert route["schema_version"] == SCHEMA_VERSION
            assert route["query"] == query
            assert route["summary"]["candidate_count"] >= 2
            assert all(
                candidate["evidence"]["matched_terms"]
                for candidate in route["candidates"]
            )

        dashboard = (track_dir / "dashboard.html").read_text(encoding="utf-8")
        assert "<!doctype html>" in dashboard
        assert "window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__" in dashboard
        assert 'src="http' not in dashboard
        assert 'href="http' not in dashboard

        gate = _read_json(track_dir / "ci-gate-report.json")
        assert gate["artifact_type"] == "diagnostic_ci_gate"
        assert gate["schema_version"] == SCHEMA_VERSION
        assert gate["decision"] == "PASS"
        assert gate["summary"]["route_count"] == len(spec["routes"])

        packet = _read_json(track_dir / "pr-review-packet.json")
        assert packet["artifact_type"] == "diagnostic_pr_review_packet"
        assert packet["schema_version"] == SCHEMA_VERSION
        assert packet["decision"] == "PASS"
        assert packet["verdict_source"]["artifact_type"] == "diagnostic_ci_gate"


def test_external_validation_pack_preserves_bounded_claims():
    reviewed_paths = sorted(path for path in PACK_DIR.rglob("*") if path.is_file()) + [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "usage.md",
    ]
    combined_text = "\n".join(
        path.read_text(encoding="utf-8") for path in reviewed_paths
    ).lower()

    for required_boundary in [
        "not a marketplace action",
        "not github api pr comments",
        "not pr annotations",
        "not saas",
        "not a runtime mcp router",
        "not a sota claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
    ]:
        assert required_boundary in combined_text

    assert "/users/" not in combined_text
    assert "/root" not in combined_text
    for secret_phrase in ["access_token", "api_key", "secret", "password"]:
        assert secret_phrase not in combined_text
    assert not re.search(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", combined_text)
    assert not re.search(r"\b172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b", combined_text)
    assert not re.search(r"\b192\.168\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", combined_text)
    for risky_phrase in [
        "released as a marketplace action",
        "calls the github api",
        "writes pr annotations",
        "hosted saas product",
        "runtime mcp router for agents",
        "sota benchmark status",
        "production-ready",
        "approves the release",
    ]:
        assert risky_phrase not in combined_text


def test_external_validation_pack_drift_check_passes_documented_regeneration_flow(
    tmp_path: Path,
):
    actual_dir = tmp_path / "external-skill-library-validation-regenerated"
    _regenerate_external_pack(actual_dir)

    report = compare_diagnostic_artifacts(
        expected_path=PACK_DIR,
        actual_path=actual_dir,
        output_path=tmp_path / "drift-report.json",
        markdown_output_path=tmp_path / "drift-report.md",
    )

    assert report["decision"] == "PASS"
    assert report["summary"] == {
        "compared_count": len(COMPARABLE_ARTIFACTS),
        "drift_count": 0,
    }
    assert {
        artifact["artifact"]
        for artifact in report["compared_artifacts"]
    } == COMPARABLE_ARTIFACTS


def test_external_validation_pack_drift_check_cli_detects_semantic_drift(
    tmp_path: Path,
):
    actual_dir = tmp_path / "external-skill-library-validation-regenerated"
    _regenerate_external_pack(actual_dir)
    scan_path = actual_dir / "markdown-skills" / "scan.json"
    scan = _read_json(scan_path)
    scan["summary"]["skill_count"] += 1
    scan_path.write_text(
        json.dumps(scan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "drift-report.json"
    markdown = tmp_path / "drift-report.md"
    result = main(
        [
            "diagnostic-artifact-drift-check",
            "--expected",
            str(PACK_DIR),
            "--actual",
            str(actual_dir),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ]
    )

    assert result != 0
    report = _read_json(output)
    assert report["decision"] == "FAIL"
    drifted = [
        artifact for artifact in report["compared_artifacts"] if artifact["status"] == "FAIL"
    ]
    assert drifted[0]["artifact"] == "markdown-skills/scan.json"
    assert "/summary/skill_count" in drifted[0]["differences"]


def _regenerate_external_pack(output_dir: Path) -> None:
    for track, spec in TRACKS.items():
        track_dir = output_dir / track
        track_dir.mkdir(parents=True, exist_ok=True)
        _regenerate_track(track_dir, spec)


def _regenerate_track(track_dir: Path, spec: dict) -> None:
    scan = track_dir / "scan.json"
    lint = track_dir / "lint.json"
    inspect = track_dir / "inspect.json"
    dashboard = track_dir / "dashboard.html"
    gate_json = track_dir / "ci-gate-report.json"
    gate_markdown = track_dir / "ci-gate-report.md"
    pr_json = track_dir / "pr-review-packet.json"
    pr_markdown = track_dir / "pr-review-packet.md"
    routes = {name: track_dir / name for name in spec["routes"]}

    assert main(["scan", str(spec["source"]), "--output", str(scan)]) == 0
    assert main(["lint", "--index", str(scan), "--output", str(lint)]) == 0
    assert main(["inspect", "--index", str(scan), "--output", str(inspect)]) == 0
    for route_name, query in spec["routes"].items():
        assert (
            main(
                [
                    "route",
                    query,
                    "--index",
                    str(scan),
                    "--inspect",
                    str(inspect),
                    "--top-k",
                    "2",
                    "--output",
                    str(routes[route_name]),
                ]
            )
            == 0
        )
    dashboard_args = [
        "diagnostic-dashboard",
        "--scan",
        str(scan),
        "--lint",
        str(lint),
        "--inspect",
        str(inspect),
    ]
    for route in routes.values():
        dashboard_args.extend(["--route", str(route)])
    dashboard_args.extend(["--output", str(dashboard)])
    assert main(dashboard_args) == 0

    gate_args = [
        "diagnostic-ci-gate",
        "--scan",
        str(scan),
        "--lint",
        str(lint),
        "--inspect",
        str(inspect),
    ]
    for route in routes.values():
        gate_args.extend(["--route", str(route)])
    thresholds = spec["thresholds"]
    gate_args.extend(
        [
            "--output",
            str(gate_json),
            "--markdown-output",
            str(gate_markdown),
            "--max-lint-findings",
            thresholds["max_lint_findings"],
            "--max-conflict-clusters",
            thresholds["max_conflict_clusters"],
            "--max-route-risk-flags",
            thresholds["max_route_risk_flags"],
            "--min-route-candidates",
            thresholds["min_route_candidates"],
        ]
    )
    assert main(gate_args) == 0
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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
