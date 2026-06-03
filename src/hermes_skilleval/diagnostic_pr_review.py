from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "diagnostic.v1"


BOUNDARIES = [
    "Local reviewer-facing diagnostic evidence only; not GitHub API integration.",
    "not a PR annotation system.",
    "not a Marketplace Action.",
    "not SaaS.",
    "not a runtime MCP router.",
    "not a SOTA claim.",
]


def write_diagnostic_pr_review_packet(
    *,
    gate_report_path: Path | str,
    output_path: Path | str,
    markdown_output_path: Path | str,
) -> dict[str, Any]:
    gate_report = _read_gate_report(gate_report_path)
    decision = gate_report["decision"]
    summary = dict(gate_report.get("summary", {}))
    failed_policies = _dict_list(gate_report.get("failed_policies", []))

    packet = {
        "artifact_type": "diagnostic_pr_review_packet",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "decision": decision,
        "policy_status": "passed" if decision == "PASS" else "failed",
        "verdict_source": {
            "artifact_type": "diagnostic_ci_gate",
            "path": _display_path(gate_report_path),
            "decision": decision,
        },
        "summary": summary,
        "source_artifacts": _source_artifacts(gate_report),
        "attention_items": _attention_items(summary, failed_policies),
        "evidence_gaps": _evidence_gaps(summary),
        "route_reports": _route_reports(gate_report.get("route_reports", [])),
        "boundaries": BOUNDARIES,
    }

    _write_json(output_path, packet)
    _write_markdown(markdown_output_path, packet)
    return packet


def _read_gate_report(path: Path | str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid diagnostic CI gate report: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"invalid diagnostic CI gate report: {path} is not an object")
    if payload.get("artifact_type") != "diagnostic_ci_gate":
        raise ValueError(
            f"invalid diagnostic CI gate report: {path} has artifact_type "
            f"{payload.get('artifact_type')!r}"
        )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"invalid diagnostic CI gate report: {path} has schema_version "
            f"{payload.get('schema_version')!r}"
        )
    if payload.get("decision") not in {"PASS", "FAIL"}:
        raise ValueError(
            f"invalid diagnostic CI gate report: {path} has decision "
            f"{payload.get('decision')!r}"
        )
    return payload


def _source_artifacts(gate_report: dict[str, Any]) -> dict[str, Any]:
    inputs = gate_report.get("inputs", {})
    if not isinstance(inputs, dict):
        inputs = {}
    routes = inputs.get("routes", [])
    if not isinstance(routes, list):
        routes = []
    return {
        "scan": _display_path(inputs.get("scan")),
        "lint": _display_path(inputs.get("lint")),
        "inspect": _display_path(inputs.get("inspect")),
        "routes": [_display_path(route) for route in routes],
    }


def _attention_items(
    summary: dict[str, Any],
    failed_policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for policy in failed_policies:
        items.append(
            {
                "code": _string_or_empty(policy.get("code")),
                "kind": "failed_policy",
                "actual": policy.get("actual"),
                "limit": policy.get("limit"),
                "message": _string_or_empty(policy.get("message")),
            }
        )

    signal_specs = [
        (
            "review_worthy_lint_findings",
            "lint_finding_count",
            "Lint findings are review-worthy diagnostic signals.",
        ),
        (
            "review_worthy_conflict_clusters",
            "conflict_cluster_count",
            "Conflict clusters are review-worthy diagnostic signals.",
        ),
        (
            "review_worthy_route_risks",
            "route_risk_flag_count",
            "Route risk flags are review-worthy diagnostic signals.",
        ),
    ]
    for code, summary_key, message in signal_specs:
        count = _int(summary.get(summary_key))
        if count > 0:
            items.append(
                {
                    "code": code,
                    "kind": "review_signal",
                    "count": count,
                    "message": message,
                }
            )
    return items


def _evidence_gaps(summary: dict[str, Any]) -> list[dict[str, Any]]:
    missing_route_evidence = _int(summary.get("missing_route_evidence_count"))
    if missing_route_evidence == 0:
        return []
    return [
        {
            "code": "missing_route_evidence",
            "count": missing_route_evidence,
            "message": "One or more routed candidates lack visible matched-term evidence.",
        }
    ]


def _write_json(path: Path | str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path | str, packet: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Diagnostic PR Review Packet",
        "",
        f"- Decision: `{packet['decision']}`",
        f"- Policy status: `{packet['policy_status']}`",
        (
            "- Verdict source: "
            f"`{packet['verdict_source']['artifact_type']}` at "
            f"`{packet['verdict_source']['path']}`"
        ),
        (
            "- Scope: local reviewer-facing diagnostic evidence for pull "
            "request discussion"
        ),
        (
            "- Claim boundary: not GitHub API integration, not a PR annotation "
            "system, not a Marketplace Action, not SaaS, not a runtime MCP "
            "router, and not a SOTA claim"
        ),
        "",
        "## Summary",
        "",
    ]
    for key, value in packet["summary"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Must Review", ""])
    if packet["attention_items"]:
        for item in packet["attention_items"]:
            if item["kind"] == "failed_policy":
                lines.append(
                    f"- `{item['code']}` actual={item['actual']} "
                    f"limit={item['limit']}: {item['message']}"
                )
            else:
                lines.append(
                    f"- `{item['code']}` count={item['count']}: "
                    f"{item['message']} Treat this as a review signal, not "
                    "proof that a skill is duplicated, unsafe, or wrong."
                )
    else:
        lines.append("- None")

    lines.extend(["", "## Evidence Gaps", ""])
    if packet["evidence_gaps"]:
        for gap in packet["evidence_gaps"]:
            lines.append(f"- {gap['code']}: {gap['count']} - {gap['message']}")
    else:
        lines.append("- None")

    lines.extend(["", "## Source Artifacts", ""])
    source_artifacts = packet["source_artifacts"]
    for key in ("scan", "lint", "inspect"):
        if source_artifacts[key]:
            lines.append(f"- {key}: `{source_artifacts[key]}`")
    for route in source_artifacts["routes"]:
        lines.append(f"- route: `{route}`")

    lines.extend(["", "## Boundaries", ""])
    for boundary in packet["boundaries"]:
        lines.append(f"- {boundary}")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _route_reports(value: Any) -> list[dict[str, Any]]:
    reports = _dict_list(value)
    sanitized: list[dict[str, Any]] = []
    for report in reports:
        sanitized_report = dict(report)
        sanitized_report["path"] = _display_path(report.get("path"))
        sanitized.append(sanitized_report)
    return sanitized


def _display_path(value: Any) -> str:
    if not isinstance(value, (str, Path)):
        return ""
    raw_path = str(value)
    if not raw_path:
        return ""
    path = Path(raw_path)
    if not path.is_absolute():
        return raw_path
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return f"<external>/{path.name}"


def _string_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
