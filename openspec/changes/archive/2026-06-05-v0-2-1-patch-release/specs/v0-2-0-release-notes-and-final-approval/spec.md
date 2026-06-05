## ADDED Requirements

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
