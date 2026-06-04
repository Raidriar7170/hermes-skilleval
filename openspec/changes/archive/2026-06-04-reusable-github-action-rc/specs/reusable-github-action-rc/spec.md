## ADDED Requirements

### Requirement: Provide reusable composite action scaffold
The system SHALL provide a root-level GitHub composite action scaffold that runs
SkillEval against an external skill library and labeled benchmark without
requiring GitHub API tokens.

#### Scenario: Inspect action metadata
- **WHEN** a maintainer opens `action.yml`
- **THEN** it MUST declare `skill-path`, `benchmark-path`,
  `min-recall-at-k`, `max-negative-hit-rate`, and `upload-artifacts` inputs
- **AND** it MUST use `runs.using: composite`
- **AND** it MUST NOT declare GitHub API token, PR comment, PR annotation, SaaS,
  runtime MCP router, Marketplace publication, release publication, or tag
  creation steps

#### Scenario: Run external benchmark gate
- **WHEN** the action runs with a skill path, benchmark path, and thresholds
- **THEN** it MUST run SkillEval offline, write gate JSON/Markdown artifacts,
  append a Markdown summary to `$GITHUB_STEP_SUMMARY`, and exit non-zero when
  recall or negative-hit thresholds fail

#### Scenario: Optionally upload artifacts
- **WHEN** `upload-artifacts` is set to `true`
- **THEN** the action MAY upload generated SkillEval artifacts with the standard
  artifact action
- **AND** it MUST remain optional and token-free for callers

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
