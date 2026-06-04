## ADDED Requirements

### Requirement: Provide local external consumer smoke evidence
The system SHALL provide a committed local external-consumer smoke pack for the
Reusable GitHub Action RC without requiring hosted GitHub Actions, secrets,
remote repositories, tags, releases, or Marketplace publication.

#### Scenario: Inspect smoke pack
- **WHEN** a reviewer opens the smoke pack
- **THEN** it MUST include a README, a consumer workflow example, generated gate
  JSON/Markdown artifacts, generated CI summary JSON/Markdown artifacts, and
  boundary wording that describes the pack as local RC smoke evidence
- **AND** it MUST NOT claim Marketplace Action publication, a release tag,
  GitHub API PR comments, PR annotations, SaaS, runtime MCP routing, production
  readiness, release approval, or automatic merge approval

#### Scenario: Run external consumer action shell smoke
- **WHEN** project tests construct a separate temporary consumer repository
- **THEN** they MUST run the action gate shell step from consumer repository
  paths with `SKILLEVAL_*` inputs and `GITHUB_STEP_SUMMARY`
- **AND** the generated smoke artifacts MUST record `ALLOW_MERGE`,
  `recall_at_5` of `1.0`, `negative_hit_rate` of `0.0`, and bounded RC wording

### Requirement: Surface external consumer smoke evidence
The system SHALL link the local external-consumer smoke pack from
reviewer-facing public docs without changing release posture.

#### Scenario: Evidence map links consumer smoke pack
- **WHEN** a reviewer opens the evidence map
- **THEN** the Reusable Action RC Evidence section MUST link to the external
  consumer smoke pack
- **AND** the row MUST describe it as local smoke evidence, not hosted GitHub
  Actions proof, release approval, Marketplace publication, or production
  readiness
