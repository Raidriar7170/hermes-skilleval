import json
from pathlib import Path

import pytest

from hermes_skilleval.diagnostic_artifact_drift import (
    compare_diagnostic_artifacts,
)


def test_compare_diagnostic_artifacts_ignores_generated_at(tmp_path: Path):
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
            "skills": [
                {
                    "id": "debug-loop",
                    "generated_at": "2026-06-03T00:00:00+00:00",
                }
            ],
        },
    )
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T01:00:00+00:00",
            "summary": {"skill_count": 1},
            "skills": [
                {
                    "id": "debug-loop",
                    "generated_at": "2026-06-03T01:00:00+00:00",
                }
            ],
        },
    )

    report = compare_diagnostic_artifacts(
        expected_path=expected,
        actual_path=actual,
        output_path=output,
        markdown_output_path=markdown,
    )

    assert report["decision"] == "PASS"
    assert report["policy"]["ignored_fields"] == [
        "generated_at",
        "local_artifact_paths",
    ]
    assert report["summary"] == {"compared_count": 1, "drift_count": 0}
    assert report["compared_artifacts"][0]["artifact"] == "expected-scan.json"
    assert report["compared_artifacts"][0]["status"] == "PASS"
    assert report["compared_artifacts"][0]["ignored_fields"] == [
        "generated_at",
        "local_artifact_paths",
    ]
    assert json.loads(output.read_text(encoding="utf-8"))["decision"] == "PASS"
    assert "Decision: `PASS`" in markdown.read_text(encoding="utf-8")


def test_compare_diagnostic_artifacts_fails_on_semantic_drift(tmp_path: Path):
    expected = tmp_path / "expected-lint.json"
    actual = tmp_path / "actual-lint.json"
    output = tmp_path / "drift-report.json"
    _write_json(
        expected,
        {
            "artifact_type": "diagnostic_lint",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T00:00:00+00:00",
            "summary": {"finding_count": 1},
            "findings": [{"code": "missing_description", "skill_id": "helper"}],
        },
    )
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_lint",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T01:00:00+00:00",
            "summary": {"finding_count": 2},
            "findings": [{"code": "missing_description", "skill_id": "helper"}],
        },
    )

    report = compare_diagnostic_artifacts(
        expected_path=expected,
        actual_path=actual,
        output_path=output,
    )

    assert report["decision"] == "FAIL"
    assert report["summary"] == {"compared_count": 1, "drift_count": 1}
    drift = report["compared_artifacts"][0]
    assert drift["artifact"] == "expected-lint.json"
    assert drift["status"] == "FAIL"
    assert "/summary/finding_count" in drift["differences"]
    assert json.loads(output.read_text(encoding="utf-8"))["decision"] == "FAIL"


def test_compare_diagnostic_pr_review_packet_ignores_regeneration_local_paths(
    tmp_path: Path,
):
    expected = tmp_path / "expected-pr-review-packet.json"
    actual = tmp_path / "actual-pr-review-packet.json"
    _write_json(
        expected,
        {
            "artifact_type": "diagnostic_pr_review_packet",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T00:00:00+00:00",
            "verdict_source": {
                "artifact_type": "diagnostic_ci_gate",
                "decision": "PASS",
                "path": "docs/demo/diagnostic-onboarding/ci-gate-report.json",
            },
            "source_artifacts": {
                "scan": "docs/demo/diagnostic-onboarding/scan.json",
                "lint": "docs/demo/diagnostic-onboarding/lint.json",
                "inspect": "docs/demo/diagnostic-onboarding/inspect.json",
                "routes": ["docs/demo/diagnostic-onboarding/route-browser-smoke.json"],
            },
            "route_reports": [
                {
                    "path": "docs/demo/diagnostic-onboarding/route-browser-smoke.json",
                    "candidate_count": 3,
                }
            ],
        },
    )
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_pr_review_packet",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T01:00:00+00:00",
            "verdict_source": {
                "artifact_type": "diagnostic_ci_gate",
                "decision": "PASS",
                "path": "<external>/ci-gate-report.json",
            },
            "source_artifacts": {
                "scan": "<external>/scan.json",
                "lint": "<external>/lint.json",
                "inspect": "<external>/inspect.json",
                "routes": ["<external>/route-browser-smoke.json"],
            },
            "route_reports": [
                {
                    "path": "<external>/route-browser-smoke.json",
                    "candidate_count": 3,
                }
            ],
        },
    )

    report = compare_diagnostic_artifacts(expected_path=expected, actual_path=actual)

    assert report["decision"] == "PASS"
    assert report["compared_artifacts"][0]["ignored_fields"] == [
        "generated_at",
        "local_artifact_paths",
    ]


def test_compare_diagnostic_artifacts_does_not_ignore_unapproved_path_fields(
    tmp_path: Path,
):
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    _write_json(
        expected,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
            "metadata": {"custom_path": "docs/demo/expected.json"},
        },
    )
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
            "metadata": {"custom_path": "<external>/actual.json"},
        },
    )

    report = compare_diagnostic_artifacts(expected_path=expected, actual_path=actual)

    assert report["decision"] == "FAIL"
    assert "/metadata/custom_path" in report["compared_artifacts"][0]["differences"]


def test_compare_diagnostic_dashboard_html_payload(tmp_path: Path):
    expected = tmp_path / "expected-dashboard.html"
    actual = tmp_path / "actual-dashboard.html"
    _write_dashboard(
        expected,
        {
            "artifact_type": "diagnostic_dashboard",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T00:00:00+00:00",
            "summary": {"route_count": 2},
        },
    )
    _write_dashboard(
        actual,
        {
            "artifact_type": "diagnostic_dashboard",
            "schema_version": "diagnostic.v1",
            "generated_at": "2026-06-03T01:00:00+00:00",
            "summary": {"route_count": 2},
        },
    )

    report = compare_diagnostic_artifacts(expected_path=expected, actual_path=actual)

    assert report["decision"] == "PASS"
    assert report["compared_artifacts"][0]["artifact_type"] == "diagnostic_dashboard"


def test_compare_diagnostic_artifacts_rejects_unsupported_inputs(tmp_path: Path):
    expected = tmp_path / "expected.txt"
    actual = tmp_path / "actual.txt"
    expected.write_text("plain text is not a diagnostic artifact", encoding="utf-8")
    actual.write_text("plain text is not a diagnostic artifact", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported diagnostic artifact"):
        compare_diagnostic_artifacts(expected_path=expected, actual_path=actual)


def test_compare_diagnostic_artifacts_names_malformed_json_input(tmp_path: Path):
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    expected.write_text('{"artifact_type": "diagnostic_scan"', encoding="utf-8")
    _write_json(
        actual,
        {
            "artifact_type": "diagnostic_scan",
            "schema_version": "diagnostic.v1",
        },
    )

    with pytest.raises(ValueError) as exc_info:
        compare_diagnostic_artifacts(expected_path=expected, actual_path=actual)

    message = str(exc_info.value)
    assert str(expected) in message
    assert "has invalid JSON" in message


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_dashboard(path: Path, payload: dict) -> None:
    payload_json = json.dumps(payload, sort_keys=True)
    path.write_text(
        "<!doctype html><script>"
        f"window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__ = {payload_json};"
        "</script>",
        encoding="utf-8",
    )
