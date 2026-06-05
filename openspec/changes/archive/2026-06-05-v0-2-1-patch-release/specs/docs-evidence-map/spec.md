## ADDED Requirements

### Requirement: Surface v0.2.1 patch release evidence
The evidence map SHALL link the `v0.2.1` patch release notes and post-release
publication evidence after the patch release is published.

#### Scenario: Inspect v0.2.1 evidence navigation
- **WHEN** a reviewer opens `docs/evidence-map.md` after the `v0.2.1` patch
  release
- **THEN** it MUST link `docs/release-notes/v0.2.1.md`
- **AND** it MUST link `docs/demo/v0.2.1-post-release/post-release.md`
- **AND** it MUST distinguish `v0.2.0` historical release evidence from the
  current `v0.2.1` patch publication record
- **AND** it MUST NOT claim Marketplace publication, GitHub API PR comments, PR
  annotations, SaaS, runtime MCP routing, SOTA benchmark status, production
  readiness, automatic merge approval, or `finetuned-embedding`
  default-router approval
