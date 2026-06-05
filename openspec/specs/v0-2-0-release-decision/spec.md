# v0-2-0-release-decision Specification

## Purpose
Define the bounded reviewer-facing `v0.2.0` release decision package that
aggregates release-gate and reusable-action RC evidence for human review
without authorizing publication, default-router promotion, Marketplace release,
or public release actions.
## Requirements
### Requirement: Provide v0.2.0 release decision package
The system SHALL preserve the committed `v0.2.0` release decision package as
historical pre-publish review evidence while current public docs reflect the
published post-release state.

#### Scenario: Inspect machine-readable decision
- **WHEN** a reviewer opens the historical `v0.2.0` release decision JSON
- **THEN** it MUST record the original pre-publish `release_decision` as
  `NEEDS_REVIEW`
- **AND** it MUST record the original pre-publish `published` value as `false`
- **AND** it MUST record `router_decision` as `KEEP_BASELINE`
- **AND** it MUST record `default_router` as `baseline-minilm`
- **AND** it MUST record `finetuned_embedding_approved_for_default` as `false`

#### Scenario: Inspect reviewer-readable decision
- **WHEN** a reviewer opens the Markdown release decision summary
- **THEN** it MUST link Phase 16 blind validation, Phase 17 release decision,
  Phase 18 release manifest, local external-consumer action smoke, hosted
  consumer action smoke, and the release-check summary
- **AND** it MUST explain that the decision package was pre-publish review
  evidence and not the current post-release publication record

### Requirement: Preserve publication boundaries
The system SHALL distinguish historical release review readiness from current
post-release publication facts and product-readiness claims.

#### Scenario: Avoid release decision overclaims
- **WHEN** docs, Human Briefs, tests, or decision artifacts describe the
  historical `v0.2.0` decision package
- **THEN** they MUST NOT present the decision package itself as Marketplace
  Action publication, production readiness, benchmark leadership, SOTA status,
  PR comments, PR annotations, SaaS, runtime MCP routing, automatic merge
  approval, or `finetuned-embedding` default-router approval
- **AND** current public docs MAY separately state that the `v0.2.0` tag and
  GitHub Release exist when they cite post-release evidence

#### Scenario: Require explicit next approval
- **WHEN** current docs recommend a next release action after `v0.2.0`
- **THEN** they MUST require explicit human confirmation before any patch tag,
  GitHub Release, Marketplace publication, or other public release action

### Requirement: Validate release decision evidence
The system SHALL test that the historical release decision package remains
consistent with its committed source evidence and does not override current
post-release docs.

#### Scenario: Run release decision tests
- **WHEN** project tests run
- **THEN** they MUST verify the decision JSON, Markdown links, evidence
  manifest, forbidden claims, and current release-check result
- **AND** they MUST fail if current public docs use the pre-publish decision
  package to claim that `v0.2.0` is still unpublished
