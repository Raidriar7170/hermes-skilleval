## MODIFIED Requirements

### Requirement: Preserve bounded reusable action claims
The system SHALL describe the reusable action as a release-candidate scaffold
until a separate release/tag phase is explicitly approved.

#### Scenario: Avoid release and product overclaims
- **WHEN** docs, examples, summaries, Human Briefs, action reports, or release
  decision packages describe the reusable action
- **THEN** they MUST NOT claim `v0.2.0` has been released, Marketplace Action
  publication, GitHub API PR comments, PR annotations, SaaS dashboard, runtime
  MCP routing, SOTA benchmark status, production readiness, release approval, or
  automatic merge approval

#### Scenario: Use action smoke as review evidence
- **WHEN** the `v0.2.0` release decision package cites local external-consumer
  or hosted consumer action smoke
- **THEN** it MUST describe those artifacts as RC support evidence for human
  release review
- **AND** it MUST NOT describe them as release approval or publication evidence
