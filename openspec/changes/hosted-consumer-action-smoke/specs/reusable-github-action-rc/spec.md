## MODIFIED Requirements

### Requirement: Provide reusable GitHub composite action RC
The system SHALL provide a repository-root GitHub composite action release
candidate that can run the SkillEval gate from a consumer repository without
requiring GitHub API comments, PR annotations, SaaS, runtime MCP routing, or
Marketplace publication.

#### Scenario: Hosted consumer workflow runs the RC action
- **WHEN** a hosted consumer GitHub Actions workflow calls
  `Raidriar7170/hermes-skilleval@main`
- **THEN** the action MUST run `skilleval github-action-gate` against
  consumer-owned `skills` and `benchmark` paths
- **AND** the hosted workflow MUST upload gate report, CI summary, and results
  artifacts
- **AND** the evidence MUST remain RC smoke evidence rather than a release tag,
  Marketplace publication, PR automation, SaaS, runtime MCP router, production
  readiness, release approval, or automatic merge approval
