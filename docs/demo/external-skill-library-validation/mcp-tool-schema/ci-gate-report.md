# Diagnostic CI Gate

- Decision: `PASS`
- Scope: local artifact validation for diagnostic skill-library CI
- Claim boundary: artifact-based CI validation, not a Marketplace Action, not a PR annotation system, not SaaS, not a runtime MCP router, and not a SOTA claim

## Summary

- skill_count: 2
- lint_finding_count: 0
- conflict_cluster_count: 1
- route_count: 2
- route_risk_flag_count: 4
- missing_route_evidence_count: 0

## Policy

- max_lint_findings: 4
- max_conflict_clusters: 4
- max_route_risk_flags: 20
- min_route_candidates: 2
- require_route_evidence: True

## Failed Policies

- None
