## ADDED Requirements

### Requirement: Scan real skill sources

The system SHALL provide a diagnostic scan workflow that accepts real user-owned
skill sources and writes a source-annotated skill index artifact.

#### Scenario: Scan Markdown skill folder

- **WHEN** a Skill Library Maintainer scans a directory containing one or more `SKILL.md` files
- **THEN** the system MUST write a JSON artifact containing normalized skills, source type, source paths, routing cues, and parser warnings

#### Scenario: Scan MCP tool schema

- **WHEN** a Skill Library Maintainer scans an MCP tool schema file such as `mcp.json`
- **THEN** the system MUST write a JSON artifact containing tool-like skill records derived from tool names, descriptions, and input schema summaries

#### Scenario: Reject unsupported source

- **WHEN** the scan input is neither a supported Markdown skill folder nor a supported MCP tool schema file
- **THEN** the system MUST fail with a clear error that names the unsupported source shape

### Requirement: Lint routing clarity

The system SHALL provide a diagnostic lint workflow that evaluates whether
individual skills are clear enough for routing.

#### Scenario: Report routing clarity findings

- **WHEN** a Skill Library Maintainer lints a diagnostic skill index
- **THEN** the system MUST write a JSON artifact with per-skill findings for missing descriptions, generic activation cues, weak boundaries, or missing negative boundaries

#### Scenario: Avoid generic document lint

- **WHEN** the lint workflow analyzes a valid skill
- **THEN** the system MUST NOT report findings for general Markdown formatting or prose style unless they affect routing clarity

### Requirement: Route unlabeled query with evidence

The system SHALL provide a diagnostic route workflow for free-form queries
without requiring gold or negative labels.

#### Scenario: Return top-k route candidates

- **WHEN** a Skill Library Maintainer routes a free-form query against a diagnostic skill index
- **THEN** the system MUST write a JSON artifact containing the query, selected top-k skills, scores, route evidence, and route risk flags

#### Scenario: Explain near-miss risk

- **WHEN** a routed candidate belongs to an existing conflict risk cluster or has weak boundary evidence
- **THEN** the system MUST include a route risk flag that explains the ambiguity source

### Requirement: Inspect conflict risk clusters

The system SHALL provide a diagnostic inspect workflow that surfaces explainable
conflict risk clusters inside a skill library.

#### Scenario: Generate conflict clusters

- **WHEN** a Skill Library Maintainer inspects a diagnostic skill index
- **THEN** the system MUST write a JSON artifact containing conflict risk clusters, involved skills, conflict signals, and evidence terms

#### Scenario: Avoid definitive conflict verdicts

- **WHEN** the inspect workflow reports a cluster
- **THEN** the system MUST describe the cluster as review-worthy risk and MUST NOT claim the skills are definitely duplicates or must be merged

### Requirement: Render static diagnostic dashboard

The system SHALL provide a static diagnostic dashboard for the zero-label
onboarding path.

#### Scenario: Render dashboard from diagnostic artifacts

- **WHEN** scan, lint, route, or inspect artifacts are available
- **THEN** the system MUST render a self-contained HTML dashboard with source summaries, routing-readiness findings, route examples, and conflict risk clusters

#### Scenario: Preserve diagnostic scope

- **WHEN** the diagnostic dashboard is generated
- **THEN** the system MUST NOT require a server, hosted SaaS backend, runtime agent integration, or labeled benchmark results

### Requirement: Preserve evaluation workflows

The system SHALL preserve the existing benchmark and release-gate workflows while
adding the diagnostic onboarding front door.

#### Scenario: Existing evaluation commands remain available

- **WHEN** the diagnostic commands are added
- **THEN** existing evaluation-oriented commands such as index, eval, compare, dashboard, verify-release, select-release-router, and release-check MUST remain available

#### Scenario: Diagnostic artifacts support later CI gates

- **WHEN** diagnostic commands write JSON artifacts
- **THEN** the artifacts MUST use stable fields suitable for later comparison by CI gate productization
