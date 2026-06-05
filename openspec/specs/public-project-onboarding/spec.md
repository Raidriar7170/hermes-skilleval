# public-project-onboarding Specification

## Purpose
Define the public README, version metadata, released Action examples, fresh-clone
demo path, and conservative claim boundaries that make Hermes SkillEval
approachable for external maintainers after `v0.2.0`.

## Requirements
### Requirement: Present a developer-tool README front door
The system SHALL present the repository homepage as a developer tool for
evaluating and regression-testing agent skill routing before presenting long
review history.

#### Scenario: Inspect README first screen
- **WHEN** an external maintainer opens `README.md`
- **THEN** the first screen MUST include the tagline "Evaluate, route, and
  regression-test agent skills before they break your coding agent."
- **AND** it MUST state that Hermes SkillEval helps maintainers of Claude Code,
  Codex, Cursor-style skill libraries, and MCP tool schemas detect wrong-skill
  activations, near-miss conflicts, and routing regressions in CI
- **AND** it MUST include scannable sections for What it does, Why skill
  routing is hard, Quick Start, Use as GitHub Action, Example failure caught,
  Dashboard preview, Evidence links, and Limitations / Boundaries
- **AND** it MUST keep detailed phase history and long evidence chains outside
  the README front door by linking to `docs/evidence-map.md` or
  `docs/release-handoff.md`

### Requirement: Keep version metadata aligned with v0.2.0
The system SHALL keep current project metadata aligned with the published
`v0.2.1` patch release state.

#### Scenario: Inspect package metadata
- **WHEN** a maintainer inspects `pyproject.toml` and package version metadata
- **THEN** the current project version MUST be `0.2.1`
- **AND** current user-facing docs MUST NOT describe the package as `0.1.0`,
  unreleased, a release candidate, or not a `v0.2.1` release

### Requirement: Provide released GitHub Action onboarding
The system SHALL provide a copy/paste GitHub Actions workflow for the published
`v0.2.1` reusable repository Action.

#### Scenario: Copy README workflow
- **WHEN** an external maintainer copies the README GitHub Action example
- **THEN** the workflow MUST call `Raidriar7170/hermes-skilleval@v0.2.1`
- **AND** it MUST include `skill-path`, `benchmark-path`, `min-recall-at-k`,
  `max-negative-hit-rate`, and `upload-artifacts` inputs
- **AND** it MUST explain that the action writes GitHub Actions step summary
  content and uploadable artifacts
- **AND** it MUST state that no GitHub API token is required

### Requirement: Provide fresh-clone external-user demo path
The system SHALL provide repository-relative local and GitHub Action trial
paths for external users.

#### Scenario: Run local fresh-clone smoke
- **WHEN** a fresh clone follows the documented local demo path
- **THEN** the commands MUST install the package with developer extras and run
  scan, route, gate, and CI summary commands against committed example skills
  and benchmark fixtures
- **AND** the commands MUST NOT depend on absolute local paths, private
  directories, browser caches, manually generated temporary files, network-only
  model downloads, secrets, SaaS, or runtime MCP services

#### Scenario: Try GitHub Action fixture
- **WHEN** an external maintainer follows the documented Action trial path
- **THEN** the docs MUST explain copying the workflow, example skill folder, and
  example benchmark into a consumer repository
- **AND** the expected gate result MUST be expressed as `ALLOW_MERGE` or
  `BLOCK_MERGE` from the generated summary and artifacts

### Requirement: Plan an external demo repository without claiming it exists
The system SHALL document a future external demo repository plan without
creating or overclaiming that repository.

#### Scenario: Inspect demo repo plan
- **WHEN** a maintainer opens the demo repo plan
- **THEN** it MUST name the future repository
  `Raidriar7170/hermes-skilleval-demo`
- **AND** it MUST describe a Good PR scenario that produces `ALLOW_MERGE`
- **AND** it MUST describe a Bad PR scenario that introduces a routing
  regression or negative hit and produces `BLOCK_MERGE`
- **AND** current docs MUST NOT claim the demo repository exists unless it has
  actually been created and verified

### Requirement: Preserve concise public boundaries
The system SHALL preserve conservative public boundaries while avoiding stale
pre-release wording.

#### Scenario: Inspect current public boundaries
- **WHEN** current README, usage docs, examples, action metadata, or release
  notes describe the project
- **THEN** they MUST preserve this concise boundary: "This is a reusable
  repository Action, not a Marketplace-published Action, not a GitHub API PR
  comment bot, not a SaaS dashboard, and not a runtime MCP router."
- **AND** they MUST NOT claim Marketplace Action publication, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, public leaderboard,
  SOTA benchmark status, production readiness, automatic merge approval,
  automatic release publication, or `finetuned-embedding` default-router
  approval
- **AND** they MUST state that `baseline-minilm` remains the default router
