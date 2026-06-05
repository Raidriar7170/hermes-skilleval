## MODIFIED Requirements

### Requirement: Provide local external consumer smoke evidence
The system SHALL provide committed local external-consumer smoke evidence for
the reusable GitHub Action path without requiring hosted GitHub Actions,
secrets, remote repositories, Marketplace publication, PR comments, PR
annotations, SaaS, or runtime MCP routing.

#### Scenario: Inspect smoke pack
- **WHEN** a reviewer opens the smoke pack
- **THEN** it MUST include a README, a consumer workflow example, generated gate
  JSON/Markdown artifacts, generated CI summary JSON/Markdown artifacts, and
  boundary wording that describes the pack as local external-consumer smoke
  evidence
- **AND** current workflow examples MUST use
  `Raidriar7170/hermes-skilleval@v0.2.0`
- **AND** it MUST NOT claim Marketplace Action publication, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, production readiness,
  release approval, automatic release publication, or automatic merge approval

#### Scenario: Run external consumer action shell smoke
- **WHEN** project tests construct a separate temporary consumer repository
- **THEN** they MUST run the action gate shell step from consumer repository
  paths with `SKILLEVAL_*` inputs and `GITHUB_STEP_SUMMARY`
- **AND** the generated smoke artifacts MUST record `ALLOW_MERGE`,
  `recall_at_5` of `1.0`, `negative_hit_rate` of `0.0`, and bounded
  post-release wording
- **AND** the smoke MUST NOT depend on absolute local paths, private
  directories, secrets, browser state, SaaS, or runtime MCP services

### Requirement: Surface external consumer smoke evidence
The system SHALL link the local external-consumer smoke pack from
reviewer-facing public docs without confusing historical smoke evidence with
current released Action onboarding.

#### Scenario: Evidence map links consumer smoke pack
- **WHEN** a reviewer opens the evidence map
- **THEN** the reusable Action evidence section MUST link to the external
  consumer smoke pack
- **AND** the row MUST describe it as local smoke evidence, not Marketplace
  publication, release approval, product readiness, PR automation, SaaS, or
  runtime MCP routing
- **AND** current onboarding links MUST direct users to the `@v0.2.0` workflow
  example
