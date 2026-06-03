# diagnostic-ci-gate Specification

## Purpose
TBD - created by archiving change diagnostic-ci-gate. Update Purpose after archive.
## Requirements
### Requirement: Run diagnostic artifacts through a CI gate
The system SHALL provide a deterministic diagnostic CI gate that validates scan,
lint, inspect, and route artifacts against explicit thresholds.

#### Scenario: Pass within thresholds
- **WHEN** a Skill Library Maintainer runs the diagnostic CI gate with artifacts
  whose lint findings, conflict clusters, route risk flags, and missing evidence
  are within the configured thresholds
- **THEN** the system MUST write JSON and Markdown reports and exit successfully

#### Scenario: Fail above thresholds
- **WHEN** diagnostic artifacts exceed a configured threshold
- **THEN** the system MUST write JSON and Markdown reports naming the exceeded
  policy and exit with a non-zero status

#### Scenario: Reject invalid artifact contract
- **WHEN** the gate receives an artifact with an unsupported artifact type or
  schema version
- **THEN** the system MUST fail with a clear error naming the invalid artifact

### Requirement: Preserve bounded CI gate claims
The system SHALL describe diagnostic CI gate output as local artifact validation
for Skill Library Maintainers.

#### Scenario: Avoid runtime or hosted claims
- **WHEN** docs, workflow examples, or reports describe the diagnostic CI gate
- **THEN** they MUST NOT claim hosted SaaS, runtime MCP routing, GitHub
  Marketplace Action release, benchmark SOTA, or automatic merge blocking beyond
  normal CI failure semantics

### Requirement: Demonstrate GitHub Actions wiring
The system SHALL include a lightweight GitHub Actions workflow example that runs
the diagnostic CI gate without network-only model dependencies.

#### Scenario: Validate committed demo artifacts in CI
- **WHEN** GitHub Actions runs the repository validation workflow
- **THEN** it MUST run the diagnostic CI gate against committed diagnostic demo
  artifacts and write fresh gate reports outside the repository working tree

#### Scenario: Preserve existing release gate
- **WHEN** the diagnostic CI job is added
- **THEN** the existing pytest and Phase 18 release reproducibility gate MUST
  remain part of validation
