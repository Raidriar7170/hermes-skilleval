# hosted-consumer-action-smoke Specification

## Purpose
Provide committed hosted GitHub Actions consumer smoke evidence for the
Reusable GitHub Action RC while preserving release-candidate boundaries and
avoiding release, Marketplace, PR automation, SaaS, or runtime routing claims.
## Requirements
### Requirement: Provide hosted consumer action smoke evidence
The system SHALL provide committed hosted GitHub Actions consumer smoke evidence
for the Reusable GitHub Action RC without requiring secrets, release tags,
GitHub Releases, Marketplace publication, PR comments, PR annotations, SaaS, or
runtime MCP routing.

#### Scenario: Inspect hosted smoke evidence pack
- **WHEN** a reviewer opens the hosted smoke evidence pack
- **THEN** it MUST include a README, consumer workflow source, run metadata
  JSON, input manifest JSON, generated gate JSON/Markdown artifacts, generated
  CI summary JSON/Markdown artifacts, results JSONL, and bounded wording
- **AND** it MUST identify the consumer repository, workflow name, run URL,
  run conclusion, producer action ref, and artifact names
- **AND** it MUST NOT claim Marketplace Action publication, a release tag,
  GitHub API PR comments, PR annotations, SaaS, runtime MCP routing, production
  readiness, release approval, or automatic merge approval

#### Scenario: Hosted workflow allows merge
- **WHEN** the hosted consumer workflow completes
- **THEN** the committed run metadata MUST record a successful workflow
  conclusion for the expected consumer repository and action ref
- **AND** the downloaded gate artifacts MUST record `ALLOW_MERGE`,
  `recall_at_5` of `1.0`, `negative_hit_rate` of `0.0`, and bounded RC wording
- **AND** the input manifest MUST record that the hosted consumer fixtures were
  copied from the repository's public GitHub Action example fixture

### Requirement: Surface hosted consumer smoke evidence
The system SHALL link hosted consumer smoke evidence from reviewer-facing public
docs while preserving release-candidate boundaries.

#### Scenario: Evidence map links hosted smoke
- **WHEN** a reviewer opens the evidence map
- **THEN** the Reusable Action RC Evidence section MUST link to the hosted
  consumer smoke pack, hosted run metadata, hosted gate report, hosted CI
  summary, synced OpenSpec spec, and phase Human Brief
- **AND** the row MUST describe it as hosted smoke evidence rather than
  Marketplace publication, release approval, product readiness, PR automation,
  SaaS, or runtime MCP routing
