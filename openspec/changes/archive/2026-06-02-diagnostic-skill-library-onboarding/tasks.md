## 1. Diagnostic Data Model and Source Scanning

- [x] 1.1 Define diagnostic artifact schemas for scan, lint, route, inspect, and dashboard inputs.
- [x] 1.2 Add Markdown skill folder scanning that writes source-annotated diagnostic skill records.
- [x] 1.3 Add MCP tool schema scanning for stable tool name, description, and input schema summaries.
- [x] 1.4 Add unsupported-source error handling and parser warning propagation.
- [x] 1.5 Add tests for Markdown folder scan, MCP schema scan, warnings, and unsupported sources.

## 2. Routing Clarity Lint

- [x] 2.1 Implement routing-clarity lint findings for missing descriptions, weak activation cues, missing boundaries, and generic terms.
- [x] 2.2 Ensure lint findings avoid generic Markdown or prose-style checks.
- [x] 2.3 Write lint JSON artifacts with stable per-skill finding fields and summary counts.
- [x] 2.4 Add tests for routing clarity findings and non-findings.

## 3. Conflict Risk Inspection

- [x] 3.1 Implement explainable conflict signals for token overlap, trigger-term overlap, category proximity, missing boundaries, and route co-appearance.
- [x] 3.2 Group signals into conflict risk clusters with involved skills and evidence terms.
- [x] 3.3 Ensure inspect output uses review-worthy risk language and avoids definitive duplicate or merge verdicts.
- [x] 3.4 Add tests for cluster generation, evidence terms, and wording boundaries.

## 4. Unlabeled Query Routing

- [x] 4.1 Add diagnostic route support for a free-form query against a diagnostic skill index.
- [x] 4.2 Emit top-k candidates with scores, route evidence, and route risk flags.
- [x] 4.3 Connect route risk flags to conflict clusters and weak boundary evidence when available.
- [x] 4.4 Add tests for top-k route artifacts, evidence extraction, near-miss risk flags, and empty-index errors.

## 5. Diagnostic Dashboard

- [x] 5.1 Add a static diagnostic dashboard renderer separate from the existing benchmark dashboard renderer.
- [x] 5.2 Show source summaries, routing-readiness findings, route examples, and conflict risk clusters.
- [x] 5.3 Ensure the dashboard is self-contained and does not require a server, SaaS backend, runtime agent integration, or benchmark labels.
- [x] 5.4 Add tests or snapshot assertions for dashboard payload construction and required text sections.

## 6. CLI Front Door

- [x] 6.1 Add `scan`, `lint`, `route`, and `inspect` commands as the Diagnostic CLI Front Door.
- [x] 6.2 Keep existing evaluation-oriented commands available and behaviorally unchanged.
- [x] 6.3 Add CLI smoke tests for scan, lint, route, inspect, and diagnostic dashboard generation.
- [x] 6.4 Document default output paths or require explicit output paths consistently across diagnostic commands.

## 7. Documentation and Onboarding

- [x] 7.1 Add a concise diagnostic onboarding section to README without expanding the experiment-log footprint.
- [x] 7.2 Add detailed diagnostic command usage to docs while preserving existing benchmark/release-gate documentation.
- [x] 7.3 Link diagnostic artifacts to the future labeled regression and CI gate path without claiming P0 merge blocking.
- [x] 7.4 Generate or update the Chinese Human Brief HTML for this phase from the OpenSpec artifacts and validation results.

## 8. Verification

- [x] 8.1 Run focused tests for diagnostic models, source scanning, lint, inspect, route, dashboard, and CLI smoke coverage.
- [x] 8.2 Run the full pytest suite.
- [x] 8.3 Run the existing release-check command to confirm Phase 16-18 release evidence remains reproducible.
- [x] 8.4 Run `git diff --check` before completion.
