## ADDED Requirements

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
