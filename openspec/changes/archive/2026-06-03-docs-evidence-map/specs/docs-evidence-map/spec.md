## ADDED Requirements

### Requirement: Provide bounded evidence map
The system SHALL provide a reviewer-facing documentation evidence map that
groups committed SkillEval evidence by reviewer task.

#### Scenario: Inspect evidence map categories
- **WHEN** a reviewer opens the evidence map
- **THEN** it MUST include categories for project positioning, release-gate
  evidence, diagnostic onboarding, external-style validation, PR-facing CI
  summary, OpenSpec specs, and Human Briefs

#### Scenario: Link to committed evidence
- **WHEN** the evidence map lists an artifact
- **THEN** the listed path MUST point to a committed repository file or stable
  repository workflow page

### Requirement: Preserve source-of-truth boundaries
The evidence map SHALL act as a navigation layer and MUST NOT replace the
underlying evidence artifacts.

#### Scenario: Explain proof and limits
- **WHEN** an evidence map row describes an artifact
- **THEN** it MUST state what the artifact helps verify and avoid presenting
  the map itself as release approval, benchmark leadership, or product
  integration evidence

#### Scenario: Avoid overclaiming product capabilities
- **WHEN** README, usage docs, or the evidence map describe the map
- **THEN** they MUST NOT claim Marketplace Action release, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, SOTA benchmark status,
  production readiness, automatic merge approval, or release approval

### Requirement: Surface evidence map from public docs
The repository SHALL link the evidence map from public reviewer entry points.

#### Scenario: README links evidence map
- **WHEN** a reviewer follows the README recruiter or diagnostic review path
- **THEN** the README MUST provide a link to the evidence map

#### Scenario: Usage docs link evidence map
- **WHEN** a maintainer reads the CLI usage guide
- **THEN** `docs/usage.md` MUST provide a link to the evidence map as a local
  navigation aid

### Requirement: Test evidence map integrity
The test suite SHALL verify that the evidence map remains usable and bounded.

#### Scenario: Verify evidence map links
- **WHEN** project-surface tests run
- **THEN** they MUST verify that local relative links in the evidence map
  resolve to existing repository paths

#### Scenario: Verify evidence map wording
- **WHEN** project-surface tests scan the evidence map and linked public docs
- **THEN** they MUST fail if the map introduces disallowed product or
  benchmark-leadership claims
