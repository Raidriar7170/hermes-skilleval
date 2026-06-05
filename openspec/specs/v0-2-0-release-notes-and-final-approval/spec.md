# v0-2-0-release-notes-and-final-approval Specification

## Purpose
Define the bounded `v0.2.0` release-notes draft and final human approval
checklist that support GO/NO-GO review without creating a tag, GitHub Release,
Marketplace publication, or public release action.
## Requirements
### Requirement: Provide v0.2.0 release notes draft
The system SHALL provide committed `v0.2.0` release notes that describe the
published GitHub Release package, implemented capabilities, committed evidence,
and post-release boundaries.

#### Scenario: Inspect release notes
- **WHEN** a reviewer opens `docs/release-notes/v0.2.0.md`
- **THEN** it MUST link the `v0.2.0` release decision package, Phase 16 blind
  validation, Phase 17 release selector, Phase 18 release manifest, local
  external-consumer action smoke, hosted consumer action smoke, final approval
  checklist, and post-release evidence
- **AND** it MUST state that `v0.2.0` includes reusable GitHub Action support
  and external consumer smoke evidence
- **AND** it MUST describe `finetuned-embedding` as not approved for default and
  `baseline-minilm` as the current default router
- **AND** it MUST NOT describe the release notes as unpublished, release
  candidate material, or not a `v0.2.0` release

### Requirement: Provide final human approval checklist
The system SHALL preserve the final approval checklist artifact as historical
pre-publish GO/NO-GO review evidence without presenting it as the current
publication record.

#### Scenario: Inspect machine-readable checklist
- **WHEN** a reviewer opens the final approval checklist JSON
- **THEN** it MUST record `release_version` as `v0.2.0`
- **AND** it MUST preserve the original pre-publish review values for
  `overall_decision`, `published`, `tag_created`, `github_release_created`, and
  `marketplace_published`
- **AND** it MUST record the release notes, release decision package, local
  action smoke, hosted action smoke, tests, OpenSpec validation, release-check,
  tag check, release check, and overclaim scan as review inputs

#### Scenario: Inspect reviewer-readable checklist
- **WHEN** a reviewer opens the final approval checklist Markdown
- **THEN** it MUST include separate `GO Conditions`, `NO-GO Until`, and
  `Requires Human Confirmation` sections
- **AND** it MUST identify itself as historical pre-publish review evidence
- **AND** it MUST link the release notes, release decision package, and source
  evidence

### Requirement: Preserve release boundaries
The system SHALL distinguish historical final approval review from current
post-release publication facts.

#### Scenario: Avoid final-approval overclaims
- **WHEN** docs, tests, Human Briefs, release notes, or final checklist artifacts
  describe `v0.2.0`
- **THEN** they MUST NOT claim Marketplace Action publication, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, SOTA benchmark status,
  production readiness, automatic merge approval, automatic release
  publication, or `finetuned-embedding` default-router approval
- **AND** current public docs MAY state that the `v0.2.0` tag and GitHub
  Release exist when they cite post-release evidence
- **AND** they MUST NOT recommend patch release publication without explicit
  human confirmation

### Requirement: Validate final approval evidence
The system SHALL test that release notes, final approval artifacts, and
post-release evidence stay consistent with committed source evidence.

#### Scenario: Run final approval tests
- **WHEN** project tests run
- **THEN** they MUST verify release notes content, checklist fields,
  post-release fields, source links, source artifact hashes, forbidden claims,
  and public-surface links
- **AND** they MUST fail if current public docs describe `v0.2.0` as still
  unpublished, an RC, or not a `v0.2.0` release

### Requirement: Provide v0.2.1 patch release notes and post-release evidence
The system SHALL provide bounded `v0.2.1` patch release notes and post-release
publication evidence when the patch release is published.

#### Scenario: Inspect v0.2.1 release notes
- **WHEN** a reviewer opens `docs/release-notes/v0.2.1.md`
- **THEN** the notes MUST describe the release as a patch release for
  post-release onboarding cleanup
- **AND** they MUST link the `v0.2.0` post-release evidence, the
  post-release-onboarding cleanup Human Brief, and the `v0.2.1` post-release
  evidence after publication
- **AND** they MUST state that `baseline-minilm` remains the default router and
  `finetuned-embedding` is not approved as default
- **AND** they MUST NOT claim Marketplace publication, GitHub API PR comments, PR
  annotations, SaaS, runtime MCP routing, SOTA benchmark status, production
  readiness, automatic merge approval, automatic release publication, or
  `finetuned-embedding` default-router approval

#### Scenario: Inspect v0.2.1 post-release evidence
- **WHEN** a reviewer opens the `v0.2.1` post-release evidence files
- **THEN** they MUST record whether the tag exists, whether the GitHub Release
  exists, the release URL, the release commit, and validation commands
- **AND** they MUST state that Marketplace publication remains false
- **AND** they MUST NOT be created with published-true facts until the tag and
  GitHub Release have been verified
