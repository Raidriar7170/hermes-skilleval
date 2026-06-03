from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hermes_skilleval.release_checks import TextMatch, find_overclaim_matches


SCHEMA_VERSION = "ci-summary.v1"
PASS_STATUSES = {"PASS", "SUCCESS", "SKIPPED_OPTIONAL"}
FAIL_STATUSES = {
    "FAIL",
    "FAILURE",
    "FAILED",
    "CANCELLED",
    "CANCELED",
    "TIMED_OUT",
    "TIMEOUT",
    "ERROR",
    "MISSING",
    "REVIEW_REQUIRED",
}
GROUP_ORDER = ("workflow", "source", "tests", "docs", "openspec", "diagnostics", "other")


def write_ci_summary(
    *,
    checks: Iterable[tuple[str, str]],
    changed_files_path: Path | None,
    release_check_path: Path | None,
    diagnostic_gate_path: Path | None,
    diagnostic_drift_path: Path | None,
    overclaim_roots: list[Path],
    output_path: Path,
    markdown_output_path: Path,
) -> dict[str, object]:
    check_records = [_check_record(name, status) for name, status in checks]
    changed_files = _changed_file_summary(changed_files_path)
    overclaim_scan = _overclaim_scan(overclaim_roots)
    decision = _decision(check_records, overclaim_scan)
    summary = {
        "artifact_type": "ci_summary",
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "checks": check_records,
        "report_paths": {
            "release_check": _path_string(release_check_path),
            "diagnostic_gate": _path_string(diagnostic_gate_path),
            "diagnostic_drift": _path_string(diagnostic_drift_path),
        },
        "changed_files": changed_files,
        "overclaim_scan": overclaim_scan,
        "scope": (
            "local/GitHub Actions summary; not a GitHub API comment bot, not a "
            "PR annotation system, not a Marketplace Action, not SaaS, not a "
            "runtime MCP router, and not release approval"
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.write_text(render_markdown(summary), encoding="utf-8")
    return summary


def render_markdown(summary: dict[str, object]) -> str:
    checks = summary["checks"]
    assert isinstance(checks, list)
    changed_files = summary["changed_files"]
    assert isinstance(changed_files, dict)
    groups = changed_files["groups"]
    assert isinstance(groups, dict)
    overclaim_scan = summary["overclaim_scan"]
    assert isinstance(overclaim_scan, dict)
    report_paths = summary["report_paths"]
    assert isinstance(report_paths, dict)

    lines = [
        "# PR-facing CI Summary",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        (
            "Scope: local/GitHub Actions summary; not a GitHub API comment bot, "
            "not a PR annotation system, not a Marketplace Action, not SaaS, "
            "not a runtime MCP router, and not release approval."
        ),
        "",
        "## Checks",
        "",
        "| Check | Normalized | Raw status |",
        "|---|---|---|",
    ]
    for check in checks:
        assert isinstance(check, dict)
        lines.append(
            "| {name} | {normalized_status} | {raw_status} |".format(**check)
        )

    lines.extend(
        [
            "",
            "## Reports",
            "",
        ]
    )
    for name, path in report_paths.items():
        lines.append(f"- {name.replace('_', ' ')}: `{path or 'not provided'}`")

    lines.extend(
        [
            "",
            "## Overclaim Scan",
            "",
            f"- Status: `{overclaim_scan['status']}`",
            f"- Matches: {overclaim_scan['match_count']}",
        ]
    )
    for match in overclaim_scan["matches"]:
        assert isinstance(match, dict)
        lines.append(f"- `{match['path']}:{match['line_number']}` {match['text']}")

    lines.extend(
        [
            "",
            "## Changed Files",
            "",
        ]
    )
    for group in GROUP_ORDER:
        paths = groups[group]
        lines.append(f"### {group} ({len(paths)})")
        if paths:
            lines.extend(f"- `{path}`" for path in paths)
        else:
            lines.append("- none")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _check_record(name: str, raw_status: str) -> dict[str, str]:
    normalized = _normalize_status(raw_status)
    return {
        "name": name,
        "raw_status": raw_status,
        "normalized_status": normalized,
    }


def _normalize_status(status: str) -> str:
    normalized = status.strip().upper().replace("-", "_")
    if normalized in {"OK", "PASSED", "PASSING", "SUCCESS"}:
        return "PASS"
    if normalized in {"PASS", "SKIPPED_OPTIONAL"}:
        return normalized
    if normalized in FAIL_STATUSES:
        return "FAIL"
    return "FAIL"


def _decision(
    checks: list[dict[str, str]],
    overclaim_scan: dict[str, object],
) -> str:
    if not checks:
        return "BLOCK_MERGE"
    if any(check["normalized_status"] not in PASS_STATUSES for check in checks):
        return "BLOCK_MERGE"
    if overclaim_scan["status"] != "PASS":
        return "BLOCK_MERGE"
    return "ALLOW_MERGE"


def _changed_file_summary(changed_files_path: Path | None) -> dict[str, object]:
    groups = {group: [] for group in GROUP_ORDER}
    paths: list[str] = []
    if changed_files_path is not None and changed_files_path.exists():
        paths = sorted(
            {
                line.strip()
                for line in changed_files_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        )
    for path in paths:
        groups[_group_for_path(path)].append(path)
    return {
        "path": _path_string(changed_files_path),
        "count": len(paths),
        "groups": groups,
    }


def _group_for_path(path: str) -> str:
    if path.startswith(".github/workflows/"):
        return "workflow"
    if path.startswith("src/"):
        return "source"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("docs/demo/diagnostic-onboarding") or path.startswith(
        "docs/demo/external-skill-library-validation"
    ):
        return "diagnostics"
    if path.startswith("openspec/"):
        return "openspec"
    if path == "README.md" or path.startswith("docs/"):
        return "docs"
    return "other"


def _overclaim_scan(roots: list[Path]) -> dict[str, object]:
    matches = find_overclaim_matches(roots) if roots else []
    return {
        "status": "FAIL" if matches else "PASS",
        "match_count": len(matches),
        "roots": [str(path) for path in roots],
        "matches": [_match_record(match) for match in matches],
    }


def _match_record(match: TextMatch) -> dict[str, object]:
    return {
        "path": str(match.path),
        "line_number": match.line_number,
        "text": match.text.strip(),
    }


def _path_string(path: Path | None) -> str | None:
    return str(path) if path is not None else None
