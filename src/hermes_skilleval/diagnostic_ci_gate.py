from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "diagnostic.v1"


def run_diagnostic_ci_gate(
    *,
    scan_path: Path | str,
    lint_path: Path | str,
    inspect_path: Path | str,
    route_paths: list[Path | str],
    output_path: Path | str,
    markdown_output_path: Path | str | None = None,
    max_lint_findings: int = 0,
    max_conflict_clusters: int = 0,
    max_route_risk_flags: int = 0,
    min_route_candidates: int = 1,
    require_route_evidence: bool = True,
) -> dict[str, Any]:
    if not route_paths:
        raise ValueError("--route must be provided at least once")
    _validate_non_negative(max_lint_findings, "--max-lint-findings")
    _validate_non_negative(max_conflict_clusters, "--max-conflict-clusters")
    _validate_non_negative(max_route_risk_flags, "--max-route-risk-flags")
    _validate_non_negative(min_route_candidates, "--min-route-candidates")

    scan = _read_artifact(scan_path, "diagnostic_scan")
    lint = _read_artifact(lint_path, "diagnostic_lint")
    inspect = _read_artifact(inspect_path, "diagnostic_inspect")
    routes = [_read_artifact(path, "diagnostic_route") for path in route_paths]

    lint_findings = _count_list_or_summary(lint, "findings", "finding_count")
    conflict_clusters = _count_list_or_summary(inspect, "clusters", "cluster_count")
    route_reports = [_route_report(path, route) for path, route in zip(route_paths, routes)]
    route_risk_flags = sum(report["risk_flag_count"] for report in route_reports)
    missing_route_evidence = sum(report["missing_evidence_count"] for report in route_reports)
    route_candidate_violations = [
        report for report in route_reports if report["candidate_count"] < min_route_candidates
    ]

    failed_policies = []
    _append_threshold_failure(
        failed_policies,
        code="max_lint_findings",
        actual=lint_findings,
        limit=max_lint_findings,
        message="Lint findings exceed the configured diagnostic CI threshold.",
    )
    _append_threshold_failure(
        failed_policies,
        code="max_conflict_clusters",
        actual=conflict_clusters,
        limit=max_conflict_clusters,
        message="Conflict risk clusters exceed the configured diagnostic CI threshold.",
    )
    _append_threshold_failure(
        failed_policies,
        code="max_route_risk_flags",
        actual=route_risk_flags,
        limit=max_route_risk_flags,
        message="Route risk flags exceed the configured diagnostic CI threshold.",
    )
    if require_route_evidence and missing_route_evidence:
        failed_policies.append(
            {
                "code": "require_route_evidence",
                "actual": missing_route_evidence,
                "limit": 0,
                "message": "One or more routed candidates lack visible matched-term evidence.",
            }
        )
    for report in route_candidate_violations:
        failed_policies.append(
            {
                "code": "min_route_candidates",
                "actual": report["candidate_count"],
                "limit": min_route_candidates,
                "message": f"Route artifact has too few candidates: {report['path']}",
            }
        )

    decision = "FAIL" if failed_policies else "PASS"
    result = {
        "artifact_type": "diagnostic_ci_gate",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "decision": decision,
        "scope": "local artifact validation for diagnostic skill-library CI",
        "policy": {
            "max_lint_findings": max_lint_findings,
            "max_conflict_clusters": max_conflict_clusters,
            "max_route_risk_flags": max_route_risk_flags,
            "min_route_candidates": min_route_candidates,
            "require_route_evidence": require_route_evidence,
        },
        "inputs": {
            "scan": str(scan_path),
            "lint": str(lint_path),
            "inspect": str(inspect_path),
            "routes": [str(path) for path in route_paths],
        },
        "summary": {
            "skill_count": scan.get("summary", {}).get("skill_count", len(scan.get("skills", []))),
            "lint_finding_count": lint_findings,
            "conflict_cluster_count": conflict_clusters,
            "route_count": len(route_reports),
            "route_risk_flag_count": route_risk_flags,
            "missing_route_evidence_count": missing_route_evidence,
        },
        "failed_policies": failed_policies,
        "route_reports": route_reports,
    }

    _write_json(output_path, result)
    if markdown_output_path is not None:
        _write_markdown(markdown_output_path, result)
    return result


def _read_artifact(path: Path | str, expected_type: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {expected_type} artifact: {path} is not an object")
    if payload.get("artifact_type") != expected_type:
        raise ValueError(
            f"invalid {expected_type} artifact: {path} has artifact_type "
            f"{payload.get('artifact_type')!r}"
        )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"invalid {expected_type} artifact: {path} has schema_version "
            f"{payload.get('schema_version')!r}"
        )
    return payload


def _route_report(path: Path | str, route: dict[str, Any]) -> dict[str, Any]:
    candidates = [item for item in route.get("candidates", []) if isinstance(item, dict)]
    risk_flag_count = sum(
        len(candidate.get("risk_flags", []))
        for candidate in candidates
        if isinstance(candidate.get("risk_flags", []), list)
    )
    missing_evidence = 0
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        matched_terms = evidence.get("matched_terms", []) if isinstance(evidence, dict) else []
        if not matched_terms:
            missing_evidence += 1
    return {
        "path": str(path),
        "query": route.get("query"),
        "candidate_count": len(candidates),
        "risk_flag_count": risk_flag_count,
        "missing_evidence_count": missing_evidence,
    }


def _count_list_or_summary(artifact: dict[str, Any], list_key: str, summary_key: str) -> int:
    items = artifact.get(list_key)
    if isinstance(items, list):
        return len(items)
    count = artifact.get("summary", {}).get(summary_key, 0)
    return int(count) if isinstance(count, int) else 0


def _append_threshold_failure(
    failed_policies: list[dict[str, Any]],
    *,
    code: str,
    actual: int,
    limit: int,
    message: str,
) -> None:
    if actual > limit:
        failed_policies.append(
            {
                "code": code,
                "actual": actual,
                "limit": limit,
                "message": message,
            }
        )


def _validate_non_negative(value: int, flag: str) -> None:
    if value < 0:
        raise ValueError(f"{flag} must be non-negative")


def _write_json(path: Path | str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path | str, result: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Diagnostic CI Gate",
        "",
        f"- Decision: `{result['decision']}`",
        "- Scope: local artifact validation for diagnostic skill-library CI",
        (
            "- Claim boundary: artifact-based CI validation, not a Marketplace "
            "Action, not a PR annotation system, not SaaS, not a runtime MCP "
            "router, and not a SOTA claim"
        ),
        "",
        "## Summary",
        "",
    ]
    for key, value in result["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Policy", ""])
    for key, value in result["policy"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failed Policies", ""])
    if result["failed_policies"]:
        for policy in result["failed_policies"]:
            lines.append(
                f"- `{policy['code']}` actual={policy['actual']} "
                f"limit={policy['limit']}: {policy['message']}"
            )
    else:
        lines.append("- None")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
