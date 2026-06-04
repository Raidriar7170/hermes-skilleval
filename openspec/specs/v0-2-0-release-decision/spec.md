# v0-2-0-release-decision Specification

## Purpose
Define the bounded reviewer-facing `v0.2.0` release decision package that
aggregates release-gate and reusable-action RC evidence for human review
without authorizing publication, default-router promotion, Marketplace release,
or public release actions.

## Requirements
### Requirement: Provide v0.2.0 release decision package
The system SHALL provide a committed `v0.2.0` release decision package that
summarizes current release-gate and Reusable GitHub Action RC evidence without
publishing the release.

#### Scenario: Inspect machine-readable decision
- **WHEN** a reviewer opens the `v0.2.0` release decision JSON
- **THEN** it MUST record `release_decision` as `NEEDS_REVIEW`
- **AND** it MUST record `published` as `false`
- **AND** it MUST record `router_decision` as `KEEP_BASELINE`
- **AND** it MUST record `default_router` as `baseline-minilm`
- **AND** it MUST record `finetuned_embedding_approved_for_default` as `false`

#### Scenario: Inspect reviewer-readable decision
- **WHEN** a reviewer opens the Markdown release decision summary
- **THEN** it MUST link Phase 16 blind validation, Phase 17 release decision,
  Phase 18 release manifest, local external-consumer action smoke, hosted
  consumer action smoke, and the release-check summary
- **AND** it MUST explain that current evidence supports human release review
  but not automatic publication

### Requirement: Preserve publication boundaries
The system SHALL distinguish release review readiness from publication or
product-readiness claims.

#### Scenario: Avoid release overclaims
- **WHEN** docs, Human Briefs, tests, or decision artifacts describe the
  `v0.2.0` decision
- **THEN** they MUST NOT claim a `v0.2.0` tag exists, a GitHub Release exists,
  Marketplace Action publication, production readiness, benchmark leadership,
  SOTA status, PR comments, PR annotations, SaaS, runtime MCP routing,
  automatic merge approval, or `finetuned-embedding` default-router approval

#### Scenario: Require explicit next approval
- **WHEN** the decision package recommends a next step
- **THEN** it MUST require explicit human confirmation before tag creation,
  GitHub Release creation, Marketplace publication, or any public release
  action

### Requirement: Validate release decision evidence
The system SHALL test that the release decision package remains consistent with
current committed evidence.

#### Scenario: Run release decision tests
- **WHEN** project tests run
- **THEN** they MUST verify the decision JSON, Markdown links, evidence
  manifest, forbidden claims, and current release-check result
- **AND** they MUST fail if the release decision says `RELEASED`, `APPROVED`,
  or `PUBLISHED` without a separate release action
