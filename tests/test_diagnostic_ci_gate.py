import json
from pathlib import Path

from hermes_skilleval.diagnostic_ci_gate import run_diagnostic_ci_gate


def test_diagnostic_ci_gate_passes_within_explicit_thresholds(tmp_path: Path):
    scan, lint, inspect, routes = _write_artifacts(tmp_path, lint_findings=1, clusters=1)
    json_report = tmp_path / "gate.json"
    markdown_report = tmp_path / "gate.md"

    result = run_diagnostic_ci_gate(
        scan_path=scan,
        lint_path=lint,
        inspect_path=inspect,
        route_paths=routes,
        output_path=json_report,
        markdown_output_path=markdown_report,
        max_lint_findings=1,
        max_conflict_clusters=1,
        max_route_risk_flags=2,
        min_route_candidates=1,
        require_route_evidence=True,
    )

    assert result["decision"] == "PASS"
    assert result["failed_policies"] == []
    assert json.loads(json_report.read_text(encoding="utf-8"))["decision"] == "PASS"
    report_text = markdown_report.read_text(encoding="utf-8")
    assert "# Diagnostic CI Gate" in report_text
    assert "Decision: `PASS`" in report_text
    assert "local artifact validation" in report_text
    assert "artifact-based CI validation" in report_text
    assert "not a Marketplace Action" in report_text
    assert "not a PR annotation system" in report_text
    assert "not SaaS" in report_text
    assert "not a runtime MCP router" in report_text
    assert "not a SOTA claim" in report_text


def test_diagnostic_ci_gate_fails_when_thresholds_are_exceeded(tmp_path: Path):
    scan, lint, inspect, routes = _write_artifacts(tmp_path, lint_findings=2, clusters=1)
    json_report = tmp_path / "gate.json"
    markdown_report = tmp_path / "gate.md"

    result = run_diagnostic_ci_gate(
        scan_path=scan,
        lint_path=lint,
        inspect_path=inspect,
        route_paths=routes,
        output_path=json_report,
        markdown_output_path=markdown_report,
        max_lint_findings=1,
        max_conflict_clusters=0,
        max_route_risk_flags=0,
        min_route_candidates=1,
        require_route_evidence=True,
    )

    assert result["decision"] == "FAIL"
    failed_codes = {policy["code"] for policy in result["failed_policies"]}
    assert {
        "max_lint_findings",
        "max_conflict_clusters",
        "max_route_risk_flags",
    } <= failed_codes
    assert json.loads(json_report.read_text(encoding="utf-8"))["decision"] == "FAIL"
    assert "Decision: `FAIL`" in markdown_report.read_text(encoding="utf-8")


def test_diagnostic_ci_gate_flags_missing_evidence_and_too_few_candidates(
    tmp_path: Path,
):
    scan, lint, inspect, routes = _write_artifacts(tmp_path, lint_findings=0, clusters=0)
    route_payload = json.loads(routes[0].read_text(encoding="utf-8"))
    route_payload["candidates"][0]["evidence"]["matched_terms"] = []
    routes[0].write_text(json.dumps(route_payload), encoding="utf-8")

    result = run_diagnostic_ci_gate(
        scan_path=scan,
        lint_path=lint,
        inspect_path=inspect,
        route_paths=routes,
        output_path=tmp_path / "gate.json",
        markdown_output_path=tmp_path / "gate.md",
        max_lint_findings=0,
        max_conflict_clusters=0,
        max_route_risk_flags=2,
        min_route_candidates=2,
        require_route_evidence=True,
    )

    assert result["decision"] == "FAIL"
    failed_codes = {policy["code"] for policy in result["failed_policies"]}
    assert {"require_route_evidence", "min_route_candidates"} <= failed_codes


def test_diagnostic_ci_gate_rejects_invalid_artifact_type(tmp_path: Path):
    scan, lint, inspect, routes = _write_artifacts(tmp_path, lint_findings=0, clusters=0)
    payload = json.loads(lint.read_text(encoding="utf-8"))
    payload["artifact_type"] = "diagnostic_dashboard"
    lint.write_text(json.dumps(payload), encoding="utf-8")

    try:
        run_diagnostic_ci_gate(
            scan_path=scan,
            lint_path=lint,
            inspect_path=inspect,
            route_paths=routes,
            output_path=tmp_path / "gate.json",
            markdown_output_path=tmp_path / "gate.md",
        )
    except ValueError as exc:
        assert "invalid diagnostic_lint artifact" in str(exc)
    else:
        raise AssertionError("invalid lint artifact should fail")


def _write_artifacts(
    tmp_path: Path,
    *,
    lint_findings: int,
    clusters: int,
) -> tuple[Path, Path, Path, list[Path]]:
    scan = tmp_path / "scan.json"
    lint = tmp_path / "lint.json"
    inspect = tmp_path / "inspect.json"
    route = tmp_path / "route.json"
    scan.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_scan",
                "schema_version": "diagnostic.v1",
                "summary": {"skill_count": 2, "warning_count": 0},
                "skills": [{"id": "browser-smoke-testing"}, {"id": "browser-visual-review"}],
            }
        ),
        encoding="utf-8",
    )
    lint.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_lint",
                "schema_version": "diagnostic.v1",
                "summary": {
                    "skill_count": 2,
                    "finding_count": lint_findings,
                    "findings_by_severity": {"warning": lint_findings},
                },
                "findings": [
                    {"skill_id": f"skill-{index}", "severity": "warning"}
                    for index in range(lint_findings)
                ],
            }
        ),
        encoding="utf-8",
    )
    inspect.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_inspect",
                "schema_version": "diagnostic.v1",
                "summary": {"skill_count": 2, "cluster_count": clusters},
                "clusters": [
                    {"cluster_id": f"risk-cluster-{index:03d}", "risk_level": "review"}
                    for index in range(clusters)
                ],
            }
        ),
        encoding="utf-8",
    )
    route.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_route",
                "schema_version": "diagnostic.v1",
                "query": "smoke test browser",
                "summary": {"candidate_count": 1, "risk_flag_count": 2},
                "candidates": [
                    {
                        "skill_id": "browser-smoke-testing",
                        "evidence": {"matched_terms": ["browser"]},
                        "risk_flags": [
                            {"code": "conflict_cluster"},
                            {"code": "weak_boundary"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return scan, lint, inspect, [route]
