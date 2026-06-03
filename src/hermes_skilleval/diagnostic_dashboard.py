from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from hermes_skilleval.diagnostics import SCHEMA_VERSION


def build_diagnostic_dashboard_payload(
    *,
    scan_path: Path | str,
    lint_path: Path | str | None = None,
    inspect_path: Path | str | None = None,
    route_paths: list[Path | str] | None = None,
) -> dict[str, Any]:
    scan = _read_diagnostic_artifact(scan_path, label="scan", expected_type="diagnostic_scan")
    lint = (
        _read_diagnostic_artifact(lint_path, label="lint", expected_type="diagnostic_lint")
        if lint_path
        else None
    )
    inspect = (
        _read_diagnostic_artifact(
            inspect_path,
            label="inspect",
            expected_type="diagnostic_inspect",
        )
        if inspect_path
        else None
    )
    routes = [
        _read_diagnostic_artifact(path, label="route", expected_type="diagnostic_route")
        for path in (route_paths or [])
    ]

    skills = scan.get("skills", [])
    findings = lint.get("findings", []) if lint else []
    clusters = inspect.get("clusters", []) if inspect else []
    return {
        "artifact_type": "diagnostic_dashboard",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "sources": {
            "scan": str(scan_path),
            "lint": str(lint_path) if lint_path else None,
            "inspect": str(inspect_path) if inspect_path else None,
            "routes": [str(path) for path in (route_paths or [])],
        },
        "summary": {
            "skill_count": len(skills),
            "lint_finding_count": len(findings),
            "conflict_cluster_count": len(clusters),
            "route_count": len(routes),
            "source_types": scan.get("summary", {}).get("source_types", {}),
        },
        "scan": scan,
        "lint": lint,
        "inspect": inspect,
        "routes": routes,
    }


def write_diagnostic_dashboard(
    *,
    output_path: Path | str,
    scan_path: Path | str,
    lint_path: Path | str | None = None,
    inspect_path: Path | str | None = None,
    route_paths: list[Path | str] | None = None,
) -> dict[str, Any]:
    payload = build_diagnostic_dashboard_payload(
        scan_path=scan_path,
        lint_path=lint_path,
        inspect_path=inspect_path,
        route_paths=route_paths,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_diagnostic_dashboard_html(payload), encoding="utf-8")
    return payload


def render_diagnostic_dashboard_html(payload: dict[str, Any]) -> str:
    payload_json = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    summary = payload["summary"]
    findings = (payload.get("lint") or {}).get("findings", [])
    clusters = (payload.get("inspect") or {}).get("clusters", [])
    routes = payload.get("routes") or []
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnostic Skill Library Dashboard</title>
  <style>{_css()}</style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Hermes SkillEval</p>
      <h1>Diagnostic Skill Library Dashboard</h1>
      <p class="subhead">Static review surface for scan, lint, route, and inspect artifacts.</p>
    </header>
    <section>
      <h2>Source summary</h2>
      <div class="metrics">
        <div><span>{summary["skill_count"]}</span><small>Skills</small></div>
        <div><span>{summary["lint_finding_count"]}</span><small>Findings</small></div>
        <div><span>{summary["conflict_cluster_count"]}</span><small>Risk clusters</small></div>
        <div><span>{summary["route_count"]}</span><small>Route examples</small></div>
      </div>
      {_source_types(summary.get("source_types", {}))}
    </section>
    <section>
      <h2>Routing-readiness findings</h2>
      {_findings_html(findings)}
    </section>
    <section>
      <h2>Route examples</h2>
      {_routes_html(routes)}
    </section>
    <section>
      <h2>Conflict risk clusters</h2>
      {_clusters_html(clusters)}
    </section>
  </main>
  <script>window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__ = {payload_json};</script>
</body>
</html>
"""


def _source_types(source_types: dict[str, int]) -> str:
    if not source_types:
        return "<p>No source type summary available.</p>"
    items = "".join(
        f"<li><code>{escape(name)}</code>: {count}</li>"
        for name, count in sorted(source_types.items())
    )
    return f"<ul>{items}</ul>"


def _findings_html(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "<p>No routing-readiness findings in the provided lint artifact.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(finding.get('skill_id', ''))}</td>"
        f"<td><code>{escape(finding.get('code', ''))}</code></td>"
        f"<td>{escape(finding.get('message', ''))}</td>"
        "</tr>"
        for finding in findings
    )
    return f"<table><thead><tr><th>Skill</th><th>Code</th><th>Finding</th></tr></thead><tbody>{rows}</tbody></table>"


def _routes_html(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "<p>No route examples were provided.</p>"
    cards = []
    for route in routes:
        candidates = route.get("candidates", [])
        candidate_items = "".join(
            f"<li><code>{escape(candidate.get('skill_id', ''))}</code> "
            f"score {candidate.get('score', 0)}</li>"
            for candidate in candidates
        )
        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(route.get('query', 'Untitled query'))}</h3>"
            f"<ol>{candidate_items}</ol>"
            "</article>"
        )
    return "".join(cards)


def _clusters_html(clusters: list[dict[str, Any]]) -> str:
    if not clusters:
        return "<p>No conflict risk clusters in the provided inspect artifact.</p>"
    cards = []
    for cluster in clusters:
        skills = ", ".join(cluster.get("involved_skills", []))
        terms = ", ".join(cluster.get("evidence_terms", [])[:10])
        cards.append(
            "<article class=\"card\">"
            f"<h3>{escape(cluster.get('cluster_id', 'risk-cluster'))}</h3>"
            f"<p>{escape(cluster.get('summary', 'Review-worthy routing risk.'))}</p>"
            f"<p><strong>Skills:</strong> {escape(skills)}</p>"
            f"<p><strong>Evidence terms:</strong> {escape(terms)}</p>"
            "</article>"
        )
    return "".join(cards)


def _css() -> str:
    return """
    :root { color-scheme: light; --ink: #18212f; --muted: #5a6575; --line: #d9e0ea; --panel: #f7f9fb; --accent: #0f766e; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: #fff; line-height: 1.55; }
    main { max-width: 1080px; margin: 0 auto; padding: 40px 24px 64px; }
    header { border-bottom: 1px solid var(--line); margin-bottom: 28px; padding-bottom: 18px; }
    .eyebrow { color: var(--accent); font-weight: 700; margin: 0 0 6px; }
    h1 { font-size: 32px; margin: 0; letter-spacing: 0; }
    h2 { font-size: 20px; margin: 28px 0 12px; letter-spacing: 0; }
    h3 { margin: 0 0 8px; font-size: 16px; letter-spacing: 0; }
    .subhead { color: var(--muted); margin: 8px 0 0; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
    .metrics div, .card { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 14px; }
    .metrics span { display: block; font-size: 24px; font-weight: 800; }
    .metrics small { color: var(--muted); }
    table { width: 100%; border-collapse: collapse; border: 1px solid var(--line); }
    th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { background: var(--panel); }
    code { background: #edf2f7; border-radius: 4px; padding: 1px 4px; }
    .card { margin-bottom: 10px; }
    """


def _read_json(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"diagnostic dashboard input must be an object: {path}")
    return payload


def _read_diagnostic_artifact(
    path: Path | str,
    *,
    label: str,
    expected_type: str,
) -> dict[str, Any]:
    payload = _read_json(path)
    if payload.get("artifact_type") != expected_type:
        raise ValueError(f"{label} artifact must be {expected_type}: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{label} artifact schema_version must be {SCHEMA_VERSION}: {path}")
    return payload


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
