# diagnostic-artifact-drift-check Specification

## Purpose
Define deterministic semantic comparison for regenerated diagnostic artifacts,
including approved volatile-field normalization and bounded drift-report claims.

## Requirements
### Requirement: Compare diagnostic artifacts semantically
The system SHALL provide a deterministic diagnostic artifact drift check that
compares expected and actual diagnostic artifacts after normalizing approved
volatile fields.

#### Scenario: Pass when only volatile fields differ
- **WHEN** expected and actual diagnostic artifacts differ only by allowed
  volatile fields such as `generated_at` and local artifact path displays
- **THEN** the system MUST report `PASS` and write JSON and Markdown drift
  reports

#### Scenario: Fail on semantic artifact drift
- **WHEN** expected and actual diagnostic artifacts differ in non-volatile
  fields
- **THEN** the system MUST report `FAIL`, name the changed artifact, and exit
  non-zero from the CLI

#### Scenario: Reject unsupported artifact input
- **WHEN** the drift check receives missing, malformed, or unsupported artifacts
- **THEN** the system MUST fail with a clear error naming the invalid input

### Requirement: Support diagnostic demo directory comparison
The system SHALL compare committed and regenerated diagnostic demo directories
without requiring network access, model downloads, a server, or SaaS.

#### Scenario: Compare known demo artifact files
- **WHEN** a developer runs the drift check with expected and actual diagnostic
  demo directories
- **THEN** the system MUST compare the committed diagnostic JSON artifacts,
  dashboard payload, CI gate report, and PR review packet report

#### Scenario: Preserve bounded drift claims
- **WHEN** docs or reports describe the drift check
- **THEN** they MUST NOT claim GitHub API integration, PR annotations,
  Marketplace Action release, SaaS, runtime MCP routing, benchmark SOTA, or
  release approval
### Requirement: Run diagnostic artifact drift check in GitHub Actions
The system SHALL run the diagnostic artifact drift check in the repository
validation workflow after regenerating diagnostic demo artifacts into a
temporary directory.

#### Scenario: Validate regenerated demo artifacts in CI
- **WHEN** GitHub Actions runs the repository validation workflow
- **THEN** it MUST regenerate the diagnostic onboarding demo artifacts outside
  the repository working tree and run `skilleval diagnostic-artifact-drift-check`
  against the committed demo directory

#### Scenario: Keep CI drift reports outside the repository
- **WHEN** the validation workflow writes diagnostic artifact drift reports
- **THEN** it MUST write JSON and Markdown drift reports outside the repository
  working tree

#### Scenario: Preserve bounded CI claims
- **WHEN** docs, workflow examples, or reports describe the CI drift check
- **THEN** they MUST NOT claim GitHub API integration, PR annotations,
  Marketplace Action release, SaaS, runtime MCP routing, benchmark SOTA, or
  release approval
