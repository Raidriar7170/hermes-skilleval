# reusable-github-action-rc Specification

## Purpose
Provide a bounded reusable GitHub composite action release-candidate scaffold
that lets external repositories run an offline SkillEval gate against their own
skills and labeled benchmark without tokens, release publication, Marketplace
claims, PR comments, SaaS, or runtime router services.
## Requirements
### Requirement: Provide reusable composite action scaffold
The system SHALL provide a repository-root GitHub composite action for the
published `v0.2.0` reusable repository Action that can run the SkillEval gate
from a consumer repository without requiring GitHub API comments, PR
annotations, SaaS, runtime MCP routing, or Marketplace publication.

#### Scenario: Consumer workflow runs the released action
- **WHEN** a consumer GitHub Actions workflow calls
  `Raidriar7170/hermes-skilleval@v0.2.0`
- **THEN** the action MUST run `skilleval github-action-gate` against
  consumer-owned `skills` and `benchmark` paths
- **AND** the workflow MUST be able to write a GitHub Actions step summary
  and upload gate report, CI summary, and results artifacts
- **AND** the action MUST NOT require a GitHub API token, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, or Marketplace
  publication

### Requirement: Provide external onboarding example
The system SHALL include a public-safe `examples/github-action/` directory that
demonstrates fresh-clone usage for the published reusable repository Action.

#### Scenario: Inspect example fixtures
- **WHEN** a maintainer opens the example directory
- **THEN** it MUST contain example `SKILL.md` files, labeled benchmark tasks,
  and an example workflow that references
  `Raidriar7170/hermes-skilleval@v0.2.0`
- **AND** it MUST describe the example as a reusable GitHub Action example, not
  as an RC, unpublished tag, Marketplace Action, PR automation, SaaS, or
  runtime MCP router

#### Scenario: Run fresh-clone smoke
- **WHEN** the repository is copied or cloned into a fresh temporary directory
- **THEN** the documented example smoke command MUST install the package and run
  the action gate against the example fixtures without network-only model
  downloads, GitHub API tokens, a server, SaaS, or runtime MCP services

### Requirement: Preserve bounded reusable action claims
The system SHALL describe the reusable Action as a published `v0.2.0`
repository Action while preserving the distinction from Marketplace
publication, PR automation, SaaS, and runtime router services.

#### Scenario: Avoid product overclaims
- **WHEN** docs, examples, summaries, Human Briefs, action reports, or release
  materials describe the reusable Action
- **THEN** current user-facing surfaces MUST NOT call it an RC, recommend
  `@main` for released onboarding, or say it is not a `v0.2.0` release
- **AND** they MUST NOT claim Marketplace Action publication, GitHub API PR
  comments, PR annotations, SaaS dashboard, runtime MCP routing, SOTA benchmark
  status, production readiness, release approval, automatic release
  publication, automatic merge approval, or `finetuned-embedding`
  default-router approval

#### Scenario: Preserve historical action smoke evidence
- **WHEN** historical smoke artifacts record pre-release refs such as `@main`
- **THEN** current docs MAY link them as historical smoke evidence
- **AND** current docs MUST NOT present those refs as the recommended current
  onboarding path
