# reusable-github-action-rc Specification

## Purpose
Provide a bounded reusable GitHub composite action release-candidate scaffold
that lets external repositories run an offline SkillEval gate against their own
skills and labeled benchmark without tokens, release publication, Marketplace
claims, PR comments, SaaS, or runtime router services.
## Requirements
### Requirement: Provide reusable composite action scaffold
The system SHALL provide a repository-root GitHub composite action release
candidate that can run the SkillEval gate from a consumer repository without
requiring GitHub API comments, PR annotations, SaaS, runtime MCP routing, or
Marketplace publication.

#### Scenario: Hosted consumer workflow runs the RC action
- **WHEN** a hosted consumer GitHub Actions workflow calls
  `Raidriar7170/hermes-skilleval@main`
- **THEN** the action MUST run `skilleval github-action-gate` against
  consumer-owned `skills` and `benchmark` paths
- **AND** the hosted workflow MUST upload gate report, CI summary, and results
  artifacts
- **AND** the evidence MUST remain RC smoke evidence rather than a release tag,
  Marketplace publication, PR automation, SaaS, runtime MCP router, production
  readiness, release approval, or automatic merge approval

### Requirement: Provide external onboarding example
The system SHALL include a public-safe `examples/github-action/` directory that
demonstrates fresh-clone action usage.

#### Scenario: Inspect example fixtures
- **WHEN** a maintainer opens the example directory
- **THEN** it MUST contain example `SKILL.md` files, labeled benchmark tasks, and
  an example workflow that references the action by branch or commit placeholder
  rather than an unpublished `v0.2.0` tag

#### Scenario: Run fresh-clone smoke
- **WHEN** the repository is copied or cloned into a fresh temporary directory
- **THEN** the documented example smoke command MUST install the package and run
  the action gate against the example fixtures without network-only model
  downloads, GitHub API tokens, a server, SaaS, or runtime MCP services

### Requirement: Preserve bounded reusable action claims
The system SHALL describe the reusable action as a release-candidate scaffold
until a separate release/tag phase is explicitly approved.

#### Scenario: Avoid release and product overclaims
- **WHEN** docs, examples, summaries, Human Briefs, or action reports describe
  the reusable action
- **THEN** they MUST NOT claim `v0.2.0` has been released, Marketplace Action
  publication, GitHub API PR comments, PR annotations, SaaS dashboard, runtime
  MCP routing, SOTA benchmark status, production readiness, release approval, or
  automatic merge approval
