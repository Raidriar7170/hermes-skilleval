# external-skill-library-validation-pack Specification

## Purpose
TBD - created by archiving change external-skill-library-validation-pack. Update Purpose after archive.
## Requirements
### Requirement: Provide external-style validation evidence pack
The system SHALL provide a committed External Skill Library Validation Pack that
validates diagnostic workflows against public-safe external-style skill source
fixtures.

#### Scenario: Inspect committed external validation pack
- **WHEN** a Skill Library Maintainer opens the external validation demo
  directory
- **THEN** the system MUST provide source fixtures, scan, lint, inspect, route,
  dashboard, CI gate, and drift-comparable diagnostic artifacts for the pack

#### Scenario: Cover supported external source shapes
- **WHEN** the external validation pack is regenerated
- **THEN** it MUST exercise both Markdown `SKILL.md` folder sources and
  MCP-style tool schema JSON sources without requiring benchmark labels

### Requirement: Regenerate external pack deterministically
The system SHALL provide documented commands and tests that regenerate the
external-style validation pack from committed source fixtures.

#### Scenario: Regenerate without external services
- **WHEN** a developer follows the documented local commands
- **THEN** the system MUST regenerate the external pack artifacts without
  requiring network access, model downloads, a server, SaaS, GitHub API access,
  or tokens

#### Scenario: Detect semantic drift
- **WHEN** regenerated external pack artifacts differ semantically from the
  committed artifacts
- **THEN** the diagnostic artifact drift check MUST report `FAIL` and name the
  changed artifact

### Requirement: Preserve bounded external validation claims
The system SHALL describe the external validation pack as local diagnostic
evidence only.

#### Scenario: Avoid product integration claims
- **WHEN** docs, artifacts, dashboards, workflow summaries, or reports describe
  the external validation pack
- **THEN** they MUST NOT claim Marketplace Action release, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, SOTA benchmark status,
  production readiness, or release approval

### Requirement: Validate external pack in GitHub Actions
The repository validation workflow SHALL regenerate and validate the external
validation pack during each validate run.

#### Scenario: Run external pack validation in CI
- **WHEN** GitHub Actions runs the repository validate workflow
- **THEN** it MUST regenerate the external pack into `$RUNNER_TEMP`, run the
  diagnostic CI gate and artifact drift check for the pack, and publish the
  external pack artifacts as workflow artifacts

#### Scenario: Keep CI external pack outputs outside checkout
- **WHEN** the validate workflow writes regenerated external validation outputs
- **THEN** it MUST write them outside the repository working tree
