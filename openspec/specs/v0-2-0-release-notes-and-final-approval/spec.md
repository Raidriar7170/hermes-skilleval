# v0-2-0-release-notes-and-final-approval Specification

## Purpose
Define the bounded `v0.2.0` release-notes draft and final human approval
checklist that support GO/NO-GO review without creating a tag, GitHub Release,
Marketplace publication, or public release action.

## Requirements
### Requirement: Provide v0.2.0 release notes draft
The system SHALL provide a committed `v0.2.0` release-notes draft that describes
only implemented capabilities and does not claim publication.

#### Scenario: Inspect release notes
- **WHEN** a reviewer opens `docs/release-notes/v0.2.0.md`
- **THEN** it MUST link the `v0.2.0` release decision package, Phase 16 blind
  validation, Phase 17 release selector, Phase 18 release manifest, local
  external-consumer action smoke, hosted consumer action smoke, and the final
  approval checklist
- **AND** it MUST state that the notes are prepared for human approval and are
  not a tag, GitHub Release, Marketplace publication, or proof of publication
- **AND** it MUST describe `finetuned-embedding` as not approved for default and
  `baseline-minilm` as the current default router

### Requirement: Provide final human approval checklist
The system SHALL provide a final approval checklist artifact that supports a
human GO/NO-GO decision without performing publication.

#### Scenario: Inspect machine-readable checklist
- **WHEN** a reviewer opens the final approval checklist JSON
- **THEN** it MUST record `release_version` as `v0.2.0`
- **AND** it MUST record `overall_decision` as `NEEDS_REVIEW`
- **AND** it MUST record `published`, `tag_created`, `github_release_created`,
  and `marketplace_published` as `false`
- **AND** it MUST record the release notes draft, release decision package,
  local action smoke, hosted action smoke, tests, OpenSpec validation,
  release-check, tag check, release check, and overclaim scan as review inputs

#### Scenario: Inspect reviewer-readable checklist
- **WHEN** a reviewer opens the final approval checklist Markdown
- **THEN** it MUST include separate `GO Conditions`, `NO-GO Until`, and
  `Requires Human Confirmation` sections
- **AND** it MUST list missing or unapproved publication actions as NO-GO until
  the user explicitly confirms publishing
- **AND** it MUST link the release-notes draft, release decision package, and
  source evidence

### Requirement: Preserve release boundaries
The system SHALL distinguish final approval review from release publication.

#### Scenario: Avoid final-approval overclaims
- **WHEN** docs, tests, Human Briefs, release notes, or final checklist artifacts
  describe `v0.2.0`
- **THEN** they MUST NOT claim a `v0.2.0` tag exists, a GitHub Release exists,
  Marketplace Action publication, GitHub API PR comments, PR annotations, SaaS,
  runtime MCP routing, SOTA benchmark status, production readiness, automatic
  merge approval, or `finetuned-embedding` default-router approval
- **AND** they MUST NOT recommend publishing without explicit human confirmation

### Requirement: Validate final approval evidence
The system SHALL test that release notes and final approval artifacts stay
consistent with committed source evidence.

#### Scenario: Run final approval tests
- **WHEN** project tests run
- **THEN** they MUST verify release notes content, checklist fields, source links,
  source artifact hashes, forbidden claims, and public-surface links
- **AND** they MUST fail if the final checklist records `GO` or `PUBLISHED`
  without a separate publish action
