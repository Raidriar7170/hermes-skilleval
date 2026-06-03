import json
from pathlib import Path

import pytest

from hermes_skilleval.diagnostic_pr_review import write_diagnostic_pr_review_packet


def test_diagnostic_pr_review_packet_summarizes_passing_gate_report(tmp_path: Path):
    gate_report = _write_gate_report(
        tmp_path,
        decision="PASS",
        failed_policies=[],
        missing_route_evidence_count=0,
    )
    json_output = tmp_path / "pr-review-packet.json"
    markdown_output = tmp_path / "pr-review-packet.md"

    packet = write_diagnostic_pr_review_packet(
        gate_report_path=gate_report,
        output_path=json_output,
        markdown_output_path=markdown_output,
    )

    assert packet["artifact_type"] == "diagnostic_pr_review_packet"
    assert packet["schema_version"] == "diagnostic.v1"
    assert packet["decision"] == "PASS"
    assert packet["verdict_source"] == {
        "artifact_type": "diagnostic_ci_gate",
        "path": f"<external>/{gate_report.name}",
        "decision": "PASS",
    }
    assert packet["policy_status"] == "passed"
    assert packet["summary"]["lint_finding_count"] == 1
    assert packet["source_artifacts"]["scan"].endswith("scan.json")
    assert packet["source_artifacts"]["routes"] == ["route-browser-smoke.json"]
    assert packet["evidence_gaps"] == []
    assert any(item["code"] == "review_worthy_route_risks" for item in packet["attention_items"])
    assert "not a PR annotation system" in " ".join(packet["boundaries"])
    assert json.loads(json_output.read_text(encoding="utf-8")) == packet

    markdown = markdown_output.read_text(encoding="utf-8")
    assert "# Diagnostic PR Review Packet" in markdown
    assert "Decision: `PASS`" in markdown
    assert "Verdict source: `diagnostic_ci_gate`" in markdown
    assert "review-worthy diagnostic signals" in markdown
    assert "route-browser-smoke.json" in markdown
    assert "not GitHub API integration" in markdown
    assert "not a PR annotation system" in markdown
    assert "not a Marketplace Action" in markdown
    assert "not SaaS" in markdown
    assert "not a runtime MCP router" in markdown
    assert "not a SOTA claim" in markdown


def test_diagnostic_pr_review_packet_sanitizes_absolute_paths(tmp_path: Path):
    gate_report = _write_gate_report(
        tmp_path,
        decision="PASS",
        failed_policies=[],
        missing_route_evidence_count=0,
        absolute_paths=True,
    )

    packet = write_diagnostic_pr_review_packet(
        gate_report_path=gate_report,
        output_path=tmp_path / "packet.json",
        markdown_output_path=tmp_path / "packet.md",
    )
    markdown = (tmp_path / "packet.md").read_text(encoding="utf-8")
    packet_text = json.dumps(packet, sort_keys=True)

    assert str(tmp_path) not in packet_text
    assert str(tmp_path) not in markdown
    assert packet["verdict_source"]["path"] == f"<external>/{gate_report.name}"
    assert packet["source_artifacts"]["scan"] == "<external>/scan.json"
    assert packet["route_reports"][0]["path"] == "<external>/route-browser-smoke.json"


def test_diagnostic_pr_review_packet_preserves_failed_gate_verdict(tmp_path: Path):
    gate_report = _write_gate_report(
        tmp_path,
        decision="FAIL",
        failed_policies=[
            {
                "code": "max_lint_findings",
                "actual": 3,
                "limit": 1,
                "message": "Lint findings exceed the configured threshold.",
            },
            {
                "code": "require_route_evidence",
                "actual": 1,
                "limit": 0,
                "message": "One routed candidate lacks matched-term evidence.",
            },
        ],
        missing_route_evidence_count=1,
    )

    packet = write_diagnostic_pr_review_packet(
        gate_report_path=gate_report,
        output_path=tmp_path / "failed-packet.json",
        markdown_output_path=tmp_path / "failed-packet.md",
    )

    assert packet["decision"] == "FAIL"
    assert packet["policy_status"] == "failed"
    assert [item["code"] for item in packet["attention_items"][:2]] == [
        "max_lint_findings",
        "require_route_evidence",
    ]
    assert packet["evidence_gaps"] == [
        {
            "code": "missing_route_evidence",
            "count": 1,
            "message": "One or more routed candidates lack visible matched-term evidence.",
        }
    ]

    markdown = (tmp_path / "failed-packet.md").read_text(encoding="utf-8")
    assert "Decision: `FAIL`" in markdown
    assert "`max_lint_findings` actual=3 limit=1" in markdown
    assert "`require_route_evidence` actual=1 limit=0" in markdown
    assert "missing_route_evidence: 1" in markdown


def test_diagnostic_pr_review_packet_rejects_invalid_gate_report(tmp_path: Path):
    invalid = tmp_path / "gate.json"
    invalid.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_scan",
                "schema_version": "diagnostic.v1",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid diagnostic CI gate report"):
        write_diagnostic_pr_review_packet(
            gate_report_path=invalid,
            output_path=tmp_path / "packet.json",
            markdown_output_path=tmp_path / "packet.md",
        )


def test_diagnostic_pr_review_packet_rejects_missing_gate_report(tmp_path: Path):
    with pytest.raises(OSError):
        write_diagnostic_pr_review_packet(
            gate_report_path=tmp_path / "missing.json",
            output_path=tmp_path / "packet.json",
            markdown_output_path=tmp_path / "packet.md",
        )


def test_diagnostic_pr_review_packet_rejects_malformed_gate_report(tmp_path: Path):
    malformed = tmp_path / "gate.json"
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid diagnostic CI gate report"):
        write_diagnostic_pr_review_packet(
            gate_report_path=malformed,
            output_path=tmp_path / "packet.json",
            markdown_output_path=tmp_path / "packet.md",
        )


def _write_gate_report(
    tmp_path: Path,
    *,
    decision: str,
    failed_policies: list[dict],
    missing_route_evidence_count: int,
    absolute_paths: bool = False,
) -> Path:
    gate_report = tmp_path / "gate-report.json"
    scan_path = tmp_path / "scan.json" if absolute_paths else "scan.json"
    lint_path = tmp_path / "lint.json" if absolute_paths else "lint.json"
    inspect_path = tmp_path / "inspect.json" if absolute_paths else "inspect.json"
    route_path = tmp_path / "route-browser-smoke.json" if absolute_paths else "route-browser-smoke.json"
    gate_report.write_text(
        json.dumps(
            {
                "artifact_type": "diagnostic_ci_gate",
                "schema_version": "diagnostic.v1",
                "generated_at": "2026-06-02T11:25:41+00:00",
                "decision": decision,
                "scope": "local artifact validation for diagnostic skill-library CI",
                "policy": {
                    "max_lint_findings": 1,
                    "max_conflict_clusters": 1,
                    "max_route_risk_flags": 2,
                    "min_route_candidates": 1,
                    "require_route_evidence": True,
                },
                "inputs": {
                    "scan": str(scan_path),
                    "lint": str(lint_path),
                    "inspect": str(inspect_path),
                    "routes": [str(route_path)],
                },
                "summary": {
                    "skill_count": 2,
                    "lint_finding_count": 1,
                    "conflict_cluster_count": 1,
                    "route_count": 1,
                    "route_risk_flag_count": 2,
                    "missing_route_evidence_count": missing_route_evidence_count,
                },
                "failed_policies": failed_policies,
                "route_reports": [
                    {
                        "path": str(route_path),
                        "query": "smoke test browser",
                        "candidate_count": 1,
                        "risk_flag_count": 2,
                        "missing_evidence_count": missing_route_evidence_count,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return gate_report
