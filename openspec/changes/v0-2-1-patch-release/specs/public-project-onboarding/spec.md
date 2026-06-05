## MODIFIED Requirements

### Requirement: Keep version metadata aligned with v0.2.0
The system SHALL keep current project metadata aligned with the published
`v0.2.1` patch release state.

#### Scenario: Inspect package metadata
- **WHEN** a maintainer inspects `pyproject.toml` and package version metadata
- **THEN** the current project version MUST be `0.2.1`
- **AND** current user-facing docs MUST NOT describe the package as `0.1.0`,
  unreleased, a release candidate, or not a `v0.2.1` release

### Requirement: Provide released GitHub Action onboarding
The system SHALL provide a copy/paste GitHub Actions workflow for the published
`v0.2.1` reusable repository Action.

#### Scenario: Copy README workflow
- **WHEN** an external maintainer copies the README GitHub Action example
- **THEN** the workflow MUST call `Raidriar7170/hermes-skilleval@v0.2.1`
- **AND** it MUST include `skill-path`, `benchmark-path`, `min-recall-at-k`,
  `max-negative-hit-rate`, and `upload-artifacts` inputs
- **AND** it MUST explain that the action writes GitHub Actions step summary
  content and uploadable artifacts
- **AND** it MUST state that no GitHub API token is required
